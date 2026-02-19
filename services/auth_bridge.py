"""
AuthBridgeService - Bridge token authentication.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from guestman.models import Customer

from ..conf import doorman_settings
from ..exceptions import GateError
from ..gates import Gates
from ..models import BridgeToken, IdentityLink
from ..signals import bridge_token_created, customer_authenticated

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger("doorman.auth_bridge")
User = get_user_model()


@dataclass
class TokenResult:
    """Result of token creation."""

    success: bool
    token: str | None = None
    url: str | None = None
    expires_at: str | None = None
    error: str | None = None


@dataclass
class AuthResult:
    """Result of token exchange."""

    success: bool
    user: User | None = None
    customer: Customer | None = None
    created_user: bool = False
    error: str | None = None


class AuthBridgeService:
    """
    Bridge token authentication service.

    Creates tokens for chat-to-web authentication and
    handles token exchange for Django session creation.
    """

    # ===========================================
    # Create Token
    # ===========================================

    @classmethod
    def create_token(
        cls,
        customer: Customer,
        audience: str = BridgeToken.Audience.WEB_GENERAL,
        source: str = BridgeToken.Source.MANYCHAT,
        ttl_minutes: int | None = None,
        metadata: dict | None = None,
    ) -> TokenResult:
        """
        Create a BridgeToken for Customer.

        Args:
            customer: Customer from Guestman
            audience: Token audience/scope
            source: Token source (manychat, api, internal)
            ttl_minutes: Time to live in minutes (default from settings)
            metadata: Additional metadata to store

        Returns:
            TokenResult with token and URL
        """
        ttl = ttl_minutes or doorman_settings.BRIDGE_TOKEN_TTL_MINUTES
        expires_at = timezone.now() + timedelta(minutes=ttl)

        token = BridgeToken.objects.create(
            customer_id=customer.uuid,
            audience=audience,
            source=source,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        url = cls._build_url(token.token)

        # Signal
        bridge_token_created.send(
            sender=cls,
            token=token,
            customer=customer,
            audience=audience,
            source=source,
        )

        logger.info(
            "Bridge token created",
            extra={"customer_id": str(customer.uuid), "audience": audience},
        )

        return TokenResult(
            success=True,
            token=token.token,
            url=url,
            expires_at=expires_at.isoformat(),
        )

    @classmethod
    def _build_url(cls, token: str) -> str:
        """Build the exchange URL for a token."""
        # Try to get domain from Sites framework
        try:
            from django.contrib.sites.models import Site

            domain = Site.objects.get_current().domain
        except Exception:
            domain = doorman_settings.DEFAULT_DOMAIN

        path = reverse("doorman:bridge-exchange")
        protocol = "https" if doorman_settings.USE_HTTPS else "http"

        return f"{protocol}://{domain}{path}?t={token}"

    # ===========================================
    # Exchange
    # ===========================================

    @classmethod
    @transaction.atomic
    def exchange(
        cls,
        token_str: str,
        request: "HttpRequest",
        required_audience: str | None = None,
        preserve_session_keys: list[str] | None = None,
    ) -> AuthResult:
        """
        Exchange token for Django session.

        Args:
            token_str: Token string
            request: Django HttpRequest
            required_audience: If set, token must have this audience
            preserve_session_keys: Session keys to preserve across login
                                   (e.g., ["basket_session_key"])

        Returns:
            AuthResult with user and customer
        """
        # Find token
        try:
            token = BridgeToken.objects.get(token=token_str)
        except BridgeToken.DoesNotExist:
            logger.warning("Invalid token", extra={"token": token_str[:8]})
            return AuthResult(success=False, error="Invalid token.")

        # G7: Validate
        try:
            Gates.bridge_token_validity(token, required_audience)
        except GateError as e:
            return AuthResult(success=False, error=e.message)

        # Fetch Customer from Guestman
        try:
            customer = token.get_customer()
        except Customer.DoesNotExist:
            return AuthResult(success=False, error="Customer not found.")

        if not customer.is_active:
            return AuthResult(success=False, error="Account inactive.")

        # Get or create User
        user, created_user = cls._get_or_create_user(customer)

        # Mark token as used
        token.mark_used(user)

        # Preserve session keys before login (login may rotate session)
        preserved = {}
        if preserve_session_keys:
            for key in preserve_session_keys:
                if key in request.session:
                    preserved[key] = request.session[key]
                    logger.info(f"Preserving session key '{key}': {preserved[key]}")
            logger.info(f"Session keys to preserve: {list(preserved.keys())}")
        else:
            logger.info("No session keys to preserve (preserve_session_keys is None or empty)")

        # Django login
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        # Restore preserved session keys after login
        if preserved:
            for key, value in preserved.items():
                request.session[key] = value
                logger.info(f"Restored session key '{key}': {value}")
            request.session.modified = True
        else:
            logger.info("No session keys were preserved to restore")

        # Signal
        customer_authenticated.send(
            sender=cls,
            customer=customer,
            user=user,
            method="bridge_token",
            request=request,
        )

        logger.info(
            "Token exchanged",
            extra={
                "customer_id": str(customer.uuid),
                "user_id": user.id,
                "created_user": created_user,
            },
        )

        return AuthResult(
            success=True,
            user=user,
            customer=customer,
            created_user=created_user,
        )

    @classmethod
    def _get_or_create_user(cls, customer: Customer) -> tuple[User, bool]:
        """
        Get or create User for Customer.

        Args:
            customer: Customer from Guestman

        Returns:
            (User, created) tuple
        """
        # Check existing link
        try:
            link = IdentityLink.objects.select_related("user").get(
                customer_id=customer.uuid,
            )
            return link.user, False
        except IdentityLink.DoesNotExist:
            pass

        # Create User
        username = f"customer_{str(customer.uuid).replace('-', '')[:12]}"
        user = User.objects.create_user(username=username)

        # Set name from customer
        if customer.name:
            parts = customer.name.split(" ", 1)
            user.first_name = parts[0]
            if len(parts) > 1:
                user.last_name = parts[1]
            user.save(update_fields=["first_name", "last_name"])

        # Create link
        IdentityLink.objects.create(user=user, customer_id=customer.uuid)

        logger.info(
            "User created for customer",
            extra={"customer_id": str(customer.uuid), "user_id": user.id},
        )

        return user, True

    # ===========================================
    # Utilities
    # ===========================================

    @classmethod
    def get_customer_for_user(cls, user) -> Customer | None:
        """
        Get Customer for a Django User.

        Args:
            user: Django User instance

        Returns:
            Customer or None
        """
        try:
            link = IdentityLink.objects.get(user=user)
            return link.get_customer()
        except IdentityLink.DoesNotExist:
            return None
        except Customer.DoesNotExist:
            return None

    @classmethod
    def get_user_for_customer(cls, customer: Customer) -> User | None:
        """
        Get Django User for a Customer.

        Args:
            customer: Customer from Guestman

        Returns:
            User or None
        """
        try:
            link = IdentityLink.objects.select_related("user").get(
                customer_id=customer.uuid,
            )
            return link.user
        except IdentityLink.DoesNotExist:
            return None

    @classmethod
    def cleanup_expired_tokens(cls, days: int = 7) -> int:
        """
        Delete expired tokens older than N days.

        Args:
            days: Delete tokens older than this many days

        Returns:
            Number of deleted tokens
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = BridgeToken.objects.filter(
            expires_at__lt=cutoff,
        ).delete()
        return deleted

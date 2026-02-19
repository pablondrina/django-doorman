"""
VerificationService - OTP code verification.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from guestman.models import Customer
from guestman.services import customer as customer_service

from ..conf import doorman_settings
from ..exceptions import GateError
from ..gates import Gates
from ..models import MagicCode
from ..signals import magic_code_sent, magic_code_verified

if TYPE_CHECKING:
    from django.http import HttpRequest

    from ..senders import MessageSenderProtocol

logger = logging.getLogger("doorman.verification")


def normalize_phone(value: str) -> str:
    """
    Normalize phone number to E.164 format.

    Brazilian phone numbers:
    - 11 digits: DDD (2) + mobile (9 digits) -> +55 + 11 digits
    - 10 digits: DDD (2) + landline (8 digits) -> +55 + 10 digits
    """
    if not value:
        return value

    value = value.strip()

    # Email: lowercase
    if "@" in value:
        return value.lower()

    # Phone: remove all non-digits first
    digits_only = re.sub(r"[^\d]", "", value)

    # Handle Brazilian numbers
    if len(digits_only) == 11:
        return f"+55{digits_only}"
    elif len(digits_only) == 10:
        return f"+55{digits_only}"
    elif len(digits_only) == 13 and digits_only.startswith("55"):
        return f"+{digits_only}"
    elif len(digits_only) == 12 and digits_only.startswith("55"):
        return f"+{digits_only}"
    elif value.startswith("+") and len(digits_only) == 11:
        return f"+55{digits_only}"
    elif len(digits_only) >= 12 and digits_only.startswith("55"):
        return f"+{digits_only}"

    # Fallback
    if digits_only:
        if len(digits_only) in (10, 11):
            return f"+55{digits_only}"
        return f"+{digits_only}"

    return value


@dataclass
class CodeRequestResult:
    """Result of code request."""

    success: bool
    code_id: str | None = None
    expires_at: str | None = None
    error: str | None = None


@dataclass
class VerifyResult:
    """Result of code verification."""

    success: bool
    customer: Customer | None = None
    created_customer: bool = False
    error: str | None = None
    attempts_remaining: int | None = None


class VerificationService:
    """
    OTP code verification service.

    Handles code generation, sending, and verification
    for login and contact verification flows.
    """

    # ===========================================
    # Request Code
    # ===========================================

    @classmethod
    def request_code(
        cls,
        target_value: str,
        purpose: str = MagicCode.Purpose.LOGIN,
        delivery_method: str = MagicCode.DeliveryMethod.WHATSAPP,
        ip_address: str | None = None,
        sender: "MessageSenderProtocol | None" = None,
    ) -> CodeRequestResult:
        """
        Request a verification code.

        Args:
            target_value: Phone (E.164) or email
            purpose: Code purpose (login, verify_contact)
            delivery_method: How to send (whatsapp, sms, email)
            ip_address: Client IP for rate limiting
            sender: Custom sender (default from settings)

        Returns:
            CodeRequestResult with code_id and expiration
        """
        # Normalize target
        target_value = normalize_phone(target_value)

        # G9: Rate limit by target
        try:
            Gates.rate_limit(
                key=target_value,
                max_requests=doorman_settings.CODE_RATE_LIMIT_MAX,
                window_minutes=doorman_settings.CODE_RATE_LIMIT_WINDOW_MINUTES,
            )
        except GateError:
            return CodeRequestResult(
                success=False,
                error="Too many attempts. Please wait a few minutes.",
            )

        # G10: Rate limit by IP
        if ip_address:
            try:
                Gates.ip_rate_limit(ip_address)
            except GateError:
                return CodeRequestResult(
                    success=False,
                    error="Too many attempts from this location.",
                )

        # Invalidate previous codes
        MagicCode.objects.filter(
            target_value=target_value,
            purpose=purpose,
            status__in=[MagicCode.Status.PENDING, MagicCode.Status.SENT],
        ).update(status=MagicCode.Status.EXPIRED)

        # Create code
        code = MagicCode.objects.create(
            target_value=target_value,
            purpose=purpose,
            delivery_method=delivery_method,
            ip_address=ip_address,
        )

        # Send code
        sender = sender or cls._get_default_sender()
        try:
            sent = sender.send_code(target_value, code.code, delivery_method)
            if sent:
                code.mark_sent()
            else:
                return CodeRequestResult(success=False, error="Failed to send code.")
        except Exception:
            logger.exception("Send failed", extra={"target": target_value})
            return CodeRequestResult(success=False, error="Error sending code.")

        # Signal
        magic_code_sent.send(
            sender=cls,
            code=code,
            target_value=target_value,
            delivery_method=delivery_method,
        )

        logger.info("Code sent", extra={"target": target_value, "purpose": purpose})

        return CodeRequestResult(
            success=True,
            code_id=str(code.id),
            expires_at=code.expires_at.isoformat(),
        )

    # ===========================================
    # Verify for Login
    # ===========================================

    @classmethod
    @transaction.atomic
    def verify_for_login(
        cls,
        target_value: str,
        code_input: str,
        request: "HttpRequest | None" = None,
    ) -> VerifyResult:
        """
        Verify code for login.

        Creates or retrieves Customer and marks code as verified.

        Args:
            target_value: Phone or email
            code_input: User-provided code
            request: Django request for audit

        Returns:
            VerifyResult with customer
        """
        target_value = normalize_phone(target_value)

        # Find valid code
        code = cls._get_valid_code(target_value, MagicCode.Purpose.LOGIN)
        if not code:
            return VerifyResult(
                success=False,
                error="Code expired. Please request a new one.",
            )

        # Verify code
        if code.code != code_input.strip():
            code.record_attempt()
            return VerifyResult(
                success=False,
                error="Incorrect code.",
                attempts_remaining=code.attempts_remaining,
            )

        # Get or create Customer via Guestman
        # First try to find existing customer by phone
        customer = customer_service.get_by_phone(target_value)
        created = False

        if not customer:
            # Create new customer
            import uuid as uuid_lib

            customer = customer_service.create(
                code=f"WEB-{str(uuid_lib.uuid4())[:8].upper()}",
                first_name="",
                phone=target_value,
            )
            created = True

        # Mark code verified
        code.mark_verified(customer.uuid)

        # Signal
        magic_code_verified.send(
            sender=cls,
            code=code,
            customer=customer,
            purpose=MagicCode.Purpose.LOGIN,
        )

        logger.info(
            "Login verified",
            extra={
                "customer_id": str(customer.uuid),
                "created": created,
            },
        )

        return VerifyResult(
            success=True,
            customer=customer,
            created_customer=created,
        )

    # ===========================================
    # Helpers
    # ===========================================

    @classmethod
    def _get_valid_code(cls, target_value: str, purpose: str) -> MagicCode | None:
        """Get the most recent valid code for target and purpose."""
        try:
            return MagicCode.objects.filter(
                target_value=target_value,
                purpose=purpose,
                status__in=[MagicCode.Status.PENDING, MagicCode.Status.SENT],
                expires_at__gt=timezone.now(),
            ).latest("created_at")
        except MagicCode.DoesNotExist:
            return None

    @classmethod
    def _get_default_sender(cls):
        """Get the default message sender from settings."""
        from django.utils.module_loading import import_string

        sender_class = import_string(doorman_settings.MESSAGE_SENDER_CLASS)
        return sender_class()

    @classmethod
    def cleanup_expired_codes(cls, days: int = 7) -> int:
        """
        Delete expired codes older than N days.

        Args:
            days: Delete codes older than this many days

        Returns:
            Number of deleted codes
        """
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = MagicCode.objects.filter(
            expires_at__lt=cutoff,
        ).delete()
        return deleted

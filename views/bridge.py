"""
Bridge token views.
"""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from guestman.models import Customer

from ..conf import get_doorman_settings
from ..models import BridgeToken
from ..services.auth_bridge import AuthBridgeService

logger = logging.getLogger("doorman.views.bridge")


@method_decorator(csrf_exempt, name="dispatch")
class BridgeTokenCreateView(View):
    """
    Create a bridge token.

    POST /doorman/bridge-tokens

    Request body:
    {
        "customer_id": "uuid",
        "audience": "web_checkout|web_account|web_support|web_general",
        "source": "manychat|api|internal",
        "ttl_minutes": 5,
        "metadata": {}
    }

    Response:
    {
        "url": "https://...",
        "token": "...",
        "expires_at": "..."
    }
    """

    def post(self, request):
        # Parse JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # Get customer
        customer_id = data.get("customer_id")
        if not customer_id:
            return JsonResponse({"error": "customer_id required"}, status=400)

        try:
            customer = Customer.objects.get(uuid=customer_id)
        except Customer.DoesNotExist:
            return JsonResponse({"error": "Customer not found"}, status=404)

        if not customer.is_active:
            return JsonResponse({"error": "Customer inactive"}, status=400)

        # Create token
        result = AuthBridgeService.create_token(
            customer=customer,
            audience=data.get("audience", BridgeToken.Audience.WEB_GENERAL),
            source=data.get("source", BridgeToken.Source.MANYCHAT),
            ttl_minutes=data.get("ttl_minutes"),
            metadata=data.get("metadata"),
        )

        return JsonResponse(
            {
                "url": result.url,
                "token": result.token,
                "expires_at": result.expires_at,
            }
        )


class BridgeTokenExchangeView(View):
    """
    Exchange a bridge token for a session.

    GET /doorman/bridge/exchange?t=TOKEN

    On success: Redirects to LOGIN_REDIRECT_URL
    On failure: Renders bridge_invalid.html
    """

    def get_template_name(self):
        """Get template name from settings."""
        settings = get_doorman_settings()
        return settings.TEMPLATE_BRIDGE_INVALID

    def get(self, request):
        settings = get_doorman_settings()
        token = request.GET.get("t")
        if not token:
            return render(
                request,
                self.get_template_name(),
                {"error": str(_("Token não informado."))},
            )

        result = AuthBridgeService.exchange(
            token,
            request,
            preserve_session_keys=settings.PRESERVE_SESSION_KEYS,
        )

        if result.success:
            next_url = request.GET.get("next", settings.LOGIN_REDIRECT_URL)
            return redirect(next_url)
        else:
            return render(
                request,
                self.get_template_name(),
                {"error": result.error},
            )

"""
Magic code views.
"""

import json
import logging
import re

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from ..conf import get_doorman_settings
from ..models import BridgeToken, MagicCode
from ..services.auth_bridge import AuthBridgeService
from ..services.verification import VerificationService

logger = logging.getLogger("doorman.views.magic_code")


def normalize_phone(phone_raw: str) -> str | None:
    """
    Normalize phone number to E.164 format.

    Supports Brazilian phones with or without country code.
    """
    if not phone_raw:
        return None

    # Remove all non-digits except +
    phone = re.sub(r"[^\d+]", "", phone_raw.strip())

    # Handle Brazilian numbers
    if phone.startswith("+"):
        # Already has country code
        if len(phone) >= 12:  # +55 + DDD + number
            return phone
    elif phone.startswith("55"):
        # Has country code without +
        if len(phone) >= 12:
            return f"+{phone}"
    elif len(phone) == 11:
        # DDD + 9-digit mobile
        return f"+55{phone}"
    elif len(phone) == 10:
        # DDD + 8-digit landline
        return f"+55{phone}"

    return None


def get_client_ip(request) -> str:
    """Get client IP from request."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class MagicCodeRequestView(View):
    """
    Request a magic code.

    GET /doorman/code/request
        Renders code_request.html form

    POST /doorman/code/request
        Form data: phone=...
        JSON data: {"phone": "..."}

    On success (form): Redirects to code-verify
    On success (JSON): Returns {"success": true, "phone": "..."}
    """

    def get_template_name(self):
        """Get template name from settings."""
        settings = get_doorman_settings()
        return settings.TEMPLATE_CODE_REQUEST

    def get(self, request):
        context = {
            "next": request.GET.get("next", ""),
        }
        return render(request, self.get_template_name(), context)

    def post(self, request):
        template_name = self.get_template_name()

        # Parse input
        is_json = request.content_type == "application/json"

        if is_json:
            try:
                data = json.loads(request.body)
                phone_raw = data.get("phone", "")
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        else:
            phone_raw = request.POST.get("phone", "")

        # Validate phone
        if not phone_raw:
            error = str(_("Por favor, informe seu número de WhatsApp."))
            if is_json:
                return JsonResponse({"error": error}, status=400)
            return render(request, template_name, {"error": error})

        phone = normalize_phone(phone_raw)
        if not phone:
            error = str(_("Número de telefone inválido."))
            if is_json:
                return JsonResponse({"error": error}, status=400)
            return render(
                request,
                template_name,
                {"error": error, "phone": phone_raw},
            )

        # Request code
        result = VerificationService.request_code(
            target_value=phone,
            purpose=MagicCode.Purpose.LOGIN,
            ip_address=get_client_ip(request),
        )

        if not result.success:
            if is_json:
                return JsonResponse({"error": result.error}, status=429)
            return render(
                request,
                template_name,
                {"error": result.error, "phone": phone_raw},
            )

        # Success
        if is_json:
            return JsonResponse({"success": True, "phone": phone})

        # Store phone and next URL in session
        request.session["doorman_phone"] = phone
        next_url = request.POST.get("next") or request.GET.get("next", "")
        if next_url:
            request.session["doorman_next"] = next_url

        return redirect("doorman:code-verify")


class MagicCodeVerifyView(View):
    """
    Verify a magic code.

    GET /doorman/code/verify
        Renders code_verify.html form

    POST /doorman/code/verify
        Form data: phone=..., code=...
        JSON data: {"phone": "...", "code": "..."}

    On success (form): Redirects to LOGIN_REDIRECT_URL
    On success (JSON): Returns {"success": true, "customer_id": "..."}
    """

    def get_template_name(self):
        """Get template name from settings."""
        settings = get_doorman_settings()
        return settings.TEMPLATE_CODE_VERIFY

    def get(self, request):
        phone = request.session.get("doorman_phone")
        if not phone:
            return redirect("doorman:code-request")
        return render(request, self.get_template_name(), {"phone": phone})

    def post(self, request):
        template_name = self.get_template_name()
        settings = get_doorman_settings()

        # Parse input
        is_json = request.content_type == "application/json"

        if is_json:
            try:
                data = json.loads(request.body)
                phone = data.get("phone", "")
                code = data.get("code", "")
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        else:
            phone = request.POST.get("phone") or request.session.get("doorman_phone", "")
            code = request.POST.get("code", "")

        # Validate input
        if not phone or not code:
            error = str(_("Telefone e código são obrigatórios."))
            if is_json:
                return JsonResponse({"error": error}, status=400)
            return render(
                request,
                template_name,
                {"error": error, "phone": phone},
            )

        # Normalize phone
        phone = normalize_phone(phone) or phone

        # Verify code
        result = VerificationService.verify_for_login(phone, code, request)

        if not result.success:
            if is_json:
                return JsonResponse(
                    {
                        "error": result.error,
                        "attempts_remaining": result.attempts_remaining,
                    },
                    status=400,
                )
            return render(
                request,
                template_name,
                {
                    "error": result.error,
                    "phone": phone,
                    "attempts_remaining": result.attempts_remaining,
                },
            )

        # Create session via bridge token
        token_result = AuthBridgeService.create_token(
            customer=result.customer,
            source=BridgeToken.Source.INTERNAL,
        )
        AuthBridgeService.exchange(
            token_result.token,
            request,
            preserve_session_keys=settings.PRESERVE_SESSION_KEYS,
        )

        # Get next URL from session before clearing
        next_url = request.session.pop("doorman_next", None)

        # Clear session data
        request.session.pop("doorman_phone", None)

        # Success
        if is_json:
            return JsonResponse(
                {
                    "success": True,
                    "customer_id": str(result.customer.uuid),
                }
            )

        # Redirect to next URL or default
        redirect_url = next_url or settings.LOGIN_REDIRECT_URL
        return redirect(redirect_url)

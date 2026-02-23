"""
Magic link views — email-based one-click login.
"""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from ..conf import get_doorman_settings
from ..services.magic_link import MagicLinkService

logger = logging.getLogger("doorman.views.magic_link")


class MagicLinkRequestView(View):
    """
    Request a magic link via email.

    GET /doorman/magic-link/
        Renders magic_link_request.html form

    POST /doorman/magic-link/
        Form data: email=...
        JSON data: {"email": "..."}

    On success (form): Re-renders with "sent" flag
    On success (JSON): Returns {"success": true}
    """

    def get_template_name(self):
        settings = get_doorman_settings()
        return settings.TEMPLATE_MAGIC_LINK_REQUEST

    def get(self, request):
        if not get_doorman_settings().MAGIC_LINK_ENABLED:
            return render(
                request,
                self.get_template_name(),
                {"error": str(_("Login via email is not available."))},
            )
        context = {"next": request.GET.get("next", "")}
        return render(request, self.get_template_name(), context)

    def post(self, request):
        template_name = self.get_template_name()

        if not get_doorman_settings().MAGIC_LINK_ENABLED:
            return JsonResponse(
                {"error": "Magic links are disabled."}, status=400
            )

        # Parse input
        is_json = request.content_type == "application/json"

        if is_json:
            try:
                data = json.loads(request.body)
                email = data.get("email", "").strip().lower()
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        else:
            email = request.POST.get("email", "").strip().lower()

        # Validate
        if not email or "@" not in email:
            error = str(_("Please enter a valid email address."))
            if is_json:
                return JsonResponse({"error": error}, status=400)
            return render(request, template_name, {"error": error, "email": email})

        # Send magic link
        result = MagicLinkService.send_magic_link(email)

        if not result.success:
            if is_json:
                return JsonResponse({"error": result.error}, status=400)
            return render(
                request,
                template_name,
                {"error": result.error, "email": email},
            )

        # Success
        if is_json:
            return JsonResponse({"success": True})

        return render(request, template_name, {"sent": True, "email": email})

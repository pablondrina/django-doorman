"""
Doorman URL configuration.

Include in your project's urls.py:
    path("doorman/", include("doorman.urls")),
"""

from django.urls import path

from .views.bridge import BridgeTokenCreateView, BridgeTokenExchangeView
from .views.magic_code import MagicCodeRequestView, MagicCodeVerifyView
from .views.magic_link import MagicLinkRequestView

app_name = "doorman"

urlpatterns = [
    # Bridge Token (link magico do Manychat)
    path("bridge/", BridgeTokenExchangeView.as_view(), name="bridge-exchange"),
    path("bridge/create/", BridgeTokenCreateView.as_view(), name="bridge-create"),
    # Magic Code (login externo via OTP)
    path("code/request/", MagicCodeRequestView.as_view(), name="code-request"),
    path("code/verify/", MagicCodeVerifyView.as_view(), name="code-verify"),
    # Magic Link (login via email - one click)
    path("magic-link/", MagicLinkRequestView.as_view(), name="magic-link"),
]

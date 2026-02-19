"""
Doorman configuration.

Usage in settings.py:
    DOORMAN = {
        "BRIDGE_TOKEN_TTL_MINUTES": 5,
        "MAGIC_CODE_TTL_MINUTES": 10,
        "MESSAGE_SENDER_CLASS": "doorman.senders.ConsoleSender",
    }
"""

from dataclasses import dataclass
from typing import Any

from django.conf import settings


@dataclass
class DoormanSettings:
    """Doorman configuration settings."""

    # Bridge Token
    BRIDGE_TOKEN_TTL_MINUTES: int = 5

    # Magic Code
    MAGIC_CODE_TTL_MINUTES: int = 10
    MAGIC_CODE_MAX_ATTEMPTS: int = 5
    CODE_RATE_LIMIT_WINDOW_MINUTES: int = 15
    CODE_RATE_LIMIT_MAX: int = 5

    # Sender
    MESSAGE_SENDER_CLASS: str = "doorman.senders.ConsoleSender"

    # WhatsApp Cloud API
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_ID: str = ""
    WHATSAPP_CODE_TEMPLATE: str = "verification_code"

    # URLs
    DEFAULT_DOMAIN: str = "localhost:8000"
    USE_HTTPS: bool = True
    LOGIN_REDIRECT_URL: str = "/"

    # Session preservation
    # Keys to preserve across login (e.g., basket_session_key for e-commerce)
    PRESERVE_SESSION_KEYS: list[str] | None = None

    # Templates (override in your project)
    TEMPLATE_CODE_REQUEST: str = "doorman/code_request.html"
    TEMPLATE_CODE_VERIFY: str = "doorman/code_verify.html"
    TEMPLATE_BRIDGE_INVALID: str = "doorman/bridge_invalid.html"


def get_doorman_settings() -> DoormanSettings:
    """Load settings from Django settings."""
    user_settings: dict[str, Any] = getattr(settings, "DOORMAN", {})
    return DoormanSettings(**user_settings)


# Singleton instance
doorman_settings = get_doorman_settings()

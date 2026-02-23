import logging

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("doorman")


class DoormanConfig(AppConfig):
    name = "doorman"
    verbose_name = _("Gestão do Acesso")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Import signals to register handlers
        from . import signals  # noqa: F401

        # Warn if API key is empty outside DEBUG
        from django.conf import settings

        from .conf import get_doorman_settings

        if not settings.DEBUG:
            ds = get_doorman_settings()
            if not ds.BRIDGE_TOKEN_API_KEY:
                logger.warning(
                    "DOORMAN.BRIDGE_TOKEN_API_KEY is empty. "
                    "Bridge token creation endpoint is unauthenticated. "
                    "Set DOORMAN['BRIDGE_TOKEN_API_KEY'] in production."
                )

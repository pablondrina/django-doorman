from django.apps import AppConfig


class DoormanConfig(AppConfig):
    name = "doorman"
    verbose_name = "Gestão do Acesso"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Import signals to register handlers
        from . import signals  # noqa: F401

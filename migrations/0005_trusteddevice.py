"""
Add TrustedDevice model for device trust (skip-OTP on repeat logins).
"""

import uuid

from django.db import migrations, models

import doorman.models.device_trust


class Migration(migrations.Migration):

    dependencies = [
        ("doorman", "0004_rename_code_to_code_hash_identitylink_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrustedDevice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "customer_id",
                    models.UUIDField(
                        db_index=True,
                        help_text="UUID do cliente no Guestman",
                        verbose_name="ID do cliente",
                    ),
                ),
                (
                    "token_hash",
                    models.CharField(
                        db_index=True,
                        help_text="HMAC-SHA256 do token do cookie.",
                        max_length=64,
                        unique=True,
                        verbose_name="hash do token",
                    ),
                ),
                (
                    "user_agent",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=512,
                        verbose_name="user agent",
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                        verbose_name="endereço IP",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Ex: 'Chrome no iPhone', derivado do user-agent.",
                        max_length=100,
                        verbose_name="rótulo",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="criado em",
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        default=doorman.models.device_trust._default_expires_at,
                        verbose_name="expira em",
                    ),
                ),
                (
                    "last_used_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="último uso",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        verbose_name="ativo",
                    ),
                ),
            ],
            options={
                "verbose_name": "dispositivo confiável",
                "verbose_name_plural": "dispositivos confiáveis",
                "db_table": "doorman_trusted_device",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["customer_id", "is_active"],
                        name="doorman_tru_custome_idx",
                    ),
                    models.Index(
                        fields=["expires_at"],
                        name="doorman_tru_expires_idx",
                    ),
                ],
            },
        ),
    ]

# Generated migration for Django Doorman

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import doorman.models.bridge_token
import doorman.models.magic_code


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IdentityLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("customer_id", models.UUIDField(db_index=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="doorman_identity_link",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "identity link",
                "verbose_name_plural": "identity links",
                "db_table": "doorman_identity_link",
            },
        ),
        migrations.CreateModel(
            name="BridgeToken",
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
                    "token",
                    models.CharField(
                        db_index=True,
                        default=doorman.models.bridge_token.generate_token,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("customer_id", models.UUIDField(db_index=True)),
                (
                    "audience",
                    models.CharField(
                        choices=[
                            ("web_checkout", "Checkout"),
                            ("web_account", "Account"),
                            ("web_support", "Support"),
                            ("web_general", "General"),
                        ],
                        default="web_general",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "expires_at",
                    models.DateTimeField(
                        default=doorman.models.bridge_token.default_expiry
                    ),
                ),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manychat", "ManyChat"),
                            ("internal", "Internal"),
                            ("api", "API"),
                        ],
                        default="manychat",
                        max_length=20,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="doorman_bridge_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "bridge token",
                "verbose_name_plural": "bridge tokens",
                "db_table": "doorman_bridge_token",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MagicCode",
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
                    "code",
                    models.CharField(
                        default=doorman.models.magic_code.generate_code, max_length=6
                    ),
                ),
                (
                    "target_value",
                    models.CharField(
                        db_index=True,
                        help_text="Phone in E.164 or email.",
                        max_length=255,
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[("login", "Login"), ("verify_contact", "Verify Contact")],
                        default="login",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("verified", "Verified"),
                            ("expired", "Expired"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "expires_at",
                    models.DateTimeField(
                        default=doorman.models.magic_code.default_code_expiry
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                (
                    "delivery_method",
                    models.CharField(
                        choices=[
                            ("whatsapp", "WhatsApp"),
                            ("sms", "SMS"),
                            ("email", "Email"),
                        ],
                        default="whatsapp",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("customer_id", models.UUIDField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "magic code",
                "verbose_name_plural": "magic codes",
                "db_table": "doorman_magic_code",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="bridgetoken",
            index=models.Index(
                fields=["customer_id", "created_at"],
                name="doorman_bri_custome_a1b2c3_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="bridgetoken",
            index=models.Index(
                fields=["expires_at"], name="doorman_bri_expires_d4e5f6_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="magiccode",
            index=models.Index(
                fields=["target_value", "status", "created_at"],
                name="doorman_mag_target__g7h8i9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="magiccode",
            index=models.Index(
                fields=["expires_at"], name="doorman_mag_expires_j0k1l2_idx"
            ),
        ),
    ]

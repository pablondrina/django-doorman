"""
D2: Rename MagicCode.code → code_hash (clarity: stores HMAC digest, not plaintext)
D3: Add IdentityLink.metadata JSONField
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doorman", "0003_alter_bridgetoken_options_alter_identitylink_options_and_more"),
    ]

    operations = [
        # D2: Rename code → code_hash
        migrations.RenameField(
            model_name="magiccode",
            old_name="code",
            new_name="code_hash",
        ),
        migrations.AlterField(
            model_name="magiccode",
            name="code_hash",
            field=models.CharField(
                help_text="HMAC-SHA256 do código OTP. Nunca armazena plaintext.",
                max_length=64,
                verbose_name="hash do código",
            ),
        ),
        # D3: Add IdentityLink.metadata
        migrations.AddField(
            model_name="identitylink",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Device info, origem do primeiro login, etc.",
                verbose_name="metadados",
            ),
        ),
    ]

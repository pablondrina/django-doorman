"""
Senders for delivering verification codes.

Protocol-based for extensibility.
"""

import logging
from typing import Protocol

logger = logging.getLogger("doorman.senders")


class MessageSenderProtocol(Protocol):
    """Protocol that senders must implement."""

    def send_code(self, target: str, code: str, method: str) -> bool:
        """
        Send verification code.

        Args:
            target: Phone number (E.164) or email
            code: 6-digit code
            method: Delivery method (whatsapp, sms, email)

        Returns:
            True if sent successfully
        """
        ...


class ConsoleSender:
    """Sender for development - prints to console."""

    def send_code(self, target: str, code: str, method: str) -> bool:
        print(f"\n{'='*50}")
        print(f"DOORMAN - Verification Code")
        print(f"   Target: {target}")
        print(f"   Method: {method}")
        print(f"   Code: {code}")
        print(f"{'='*50}\n")
        logger.info(f"[DEV] Code for {target}: {code}")
        return True


class LogSender:
    """Sender that only logs - for testing."""

    def send_code(self, target: str, code: str, method: str) -> bool:
        logger.info(f"Code for {target} via {method}: {code}")
        return True


class WhatsAppCloudAPISender:
    """Sender via WhatsApp Cloud API."""

    def __init__(self):
        from .conf import doorman_settings

        self.access_token = doorman_settings.WHATSAPP_ACCESS_TOKEN
        self.phone_id = doorman_settings.WHATSAPP_PHONE_ID
        self.template_name = doorman_settings.WHATSAPP_CODE_TEMPLATE

    def send_code(self, target: str, code: str, method: str) -> bool:
        if not all([self.access_token, self.phone_id, self.template_name]):
            logger.error("WhatsApp not configured")
            return False

        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed - required for WhatsApp sender")
            return False

        # Remove + and spaces from phone
        phone = target.replace("+", "").replace(" ", "")

        try:
            response = httpx.post(
                f"https://graph.facebook.com/v18.0/{self.phone_id}/messages",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "template",
                    "template": {
                        "name": self.template_name,
                        "language": {"code": "pt_BR"},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": code}],
                            },
                        ],
                    },
                },
                timeout=10,
            )
            response.raise_for_status()
            logger.info(f"WhatsApp code sent to {phone}")
            return True
        except Exception as e:
            logger.exception(f"WhatsApp send failed: {e}")
            return False


class SMSSender:
    """
    SMS sender stub.

    Implement with your SMS provider (Twilio, AWS SNS, etc.)
    """

    def send_code(self, target: str, code: str, method: str) -> bool:
        logger.warning(f"SMS sender not implemented - code for {target}: {code}")
        return False


class EmailSender:
    """
    Email sender using Django's email backend.
    """

    def __init__(self):
        from .conf import doorman_settings

        self.from_email = getattr(doorman_settings, "EMAIL_FROM", None)

    def send_code(self, target: str, code: str, method: str) -> bool:
        from django.core.mail import send_mail

        try:
            send_mail(
                subject="Seu codigo de verificacao",
                message=f"Seu codigo de verificacao e: {code}\n\nEste codigo expira em 10 minutos.",
                from_email=self.from_email,
                recipient_list=[target],
                fail_silently=False,
            )
            logger.info(f"Email code sent to {target}")
            return True
        except Exception as e:
            logger.exception(f"Email send failed: {e}")
            return False

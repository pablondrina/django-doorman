# Django Doorman

Phone-first authentication for Django.

> "The doorman lets you in."

## Installation

```bash
pip install django-doorman
```

```python
INSTALLED_APPS = [
    ...
    'guestman',  # Required for Customer model
    'doorman',
]
```

```bash
python manage.py migrate
```

## Configuration

```python
DOORMAN = {
    # Bridge Token
    "BRIDGE_TOKEN_TTL_MINUTES": 5,

    # Magic Code (OTP)
    "MAGIC_CODE_TTL_MINUTES": 10,
    "CODE_RATE_LIMIT_MAX": 5,
    "CODE_RATE_LIMIT_WINDOW_MINUTES": 15,

    # Message sender for OTP delivery
    "MESSAGE_SENDER_CLASS": "doorman.senders.ConsoleSender",

    # URLs
    "DEFAULT_DOMAIN": "localhost:8000",
    "USE_HTTPS": True,
    "LOGIN_REDIRECT_URL": "/",

    # WhatsApp Cloud API (optional)
    "WHATSAPP_ACCESS_TOKEN": "",
    "WHATSAPP_PHONE_ID": "",
    "WHATSAPP_CODE_TEMPLATE": "verification_code",
}
```

## URL Configuration

```python
# urls.py
urlpatterns = [
    path("doorman/", include("doorman.urls")),
]
```

## Authentication Flows

### 1. Bridge Token (Chat-to-Web)

Perfect for Manychat/WhatsApp bots that need to create web sessions.

```python
from doorman.services.auth_bridge import AuthBridgeService
from guestman.models import Customer

# Create token for customer
customer = Customer.objects.get(code="CLI-001")
result = AuthBridgeService.create_token(
    customer=customer,
    audience="web_checkout",
    source="manychat",
)

# Send URL to customer via chat
print(result.url)  # https://yoursite.com/doorman/bridge/?t=TOKEN
```

When customer clicks the link:
1. Token is validated
2. Django User is created/retrieved
3. IdentityLink connects User <-> Customer
4. Django session is created
5. Customer is redirected

### 2. Magic Code (OTP Login)

For customers logging in via phone number.

```python
from doorman.services.verification import VerificationService

# Request code (sent via WhatsApp/SMS/Email)
result = VerificationService.request_code(
    target_value="+5541999998888",
    purpose="login",
    delivery_method="whatsapp",
)

# Verify code and get customer
result = VerificationService.verify_for_login(
    target_value="+5541999998888",
    code_input="123456",
)

if result.success:
    customer = result.customer
    # Create session...
```

## Models

### IdentityLink

Links a Guestman Customer to a Django User (1:1).

```python
from doorman.models import IdentityLink

# Get customer for logged-in user
link = IdentityLink.objects.get(user=request.user)
customer = link.get_customer()

# Check if customer has web account
has_account = IdentityLink.objects.filter(customer_id=customer.uuid).exists()
```

### BridgeToken

Single-use token for chat-to-web authentication.

```python
from doorman.models import BridgeToken

token = BridgeToken.objects.create(
    customer_id=customer.uuid,
    audience=BridgeToken.Audience.WEB_CHECKOUT,
    source=BridgeToken.Source.MANYCHAT,
)

# Token properties
token.is_valid    # Not used and not expired
token.is_expired  # Past expiration time
token.token       # URL-safe token string
```

### MagicCode

OTP code for verification.

```python
from doorman.models import MagicCode

code = MagicCode.objects.create(
    target_value="+5541999998888",
    purpose=MagicCode.Purpose.LOGIN,
    delivery_method=MagicCode.DeliveryMethod.WHATSAPP,
)

# Code properties
code.code                # 6-digit code
code.is_valid            # Not expired, not max attempts
code.attempts_remaining  # How many tries left
```

## Message Senders

Doorman uses a protocol-based sender system for OTP delivery.

### Built-in Senders

| Sender | Use Case |
|--------|----------|
| `ConsoleSender` | Development - prints to console |
| `LogSender` | Testing - logs only |
| `WhatsAppCloudAPISender` | Production - WhatsApp Cloud API |
| `SMSSender` | Production - SMS (stub) |
| `EmailSender` | Production - Django email |

### Custom Sender

```python
class MySender:
    def send_code(self, target: str, code: str, method: str) -> bool:
        # Send code via your preferred method
        return True

# settings.py
DOORMAN = {
    "MESSAGE_SENDER_CLASS": "myapp.senders.MySender",
}
```

## Gates (Validation Rules)

| Gate | Description |
|------|-------------|
| G7 | BridgeToken validity (not used, not expired, correct audience) |
| G8 | MagicCode validity (not expired, attempts remaining) |
| G9 | Rate limit by target (phone/email) |
| G10 | Rate limit by IP address |

## Signals

```python
from doorman.signals import (
    customer_authenticated,
    bridge_token_created,
    magic_code_sent,
    magic_code_verified,
)

@receiver(customer_authenticated)
def on_auth(sender, customer, user, method, request, **kwargs):
    print(f"{customer} authenticated via {method}")
```

## Integration with Guestman

Doorman is designed to work with Guestman but uses UUIDs for decoupling:

```python
# Doorman stores customer_id (UUID), not FK
class BridgeToken(models.Model):
    customer_id = models.UUIDField()  # References guestman.Customer.uuid

# Fetch customer when needed
def get_customer(self):
    from guestman.models import Customer
    return Customer.objects.get(uuid=self.customer_id)
```

This allows:
- Independent deployment
- No circular dependencies
- Easy testing with mock customers

## Admin

Doorman provides Django Admin views for:
- IdentityLink (User <-> Customer links)
- BridgeToken (with masked tokens)
- MagicCode (with masked targets)

All admin views are read-only for security.

## Shopman Suite

Doorman is part of the [Shopman suite](https://github.com/pablondrina). Shared admin utilities are available via [django-shopman-commons](https://github.com/pablondrina/django-shopman-commons).

## Requirements

- Python 3.11+
- Django 5.0+
- django-guestman (for Customer model)

## License

MIT

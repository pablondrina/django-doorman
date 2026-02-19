"""
Doorman signals.

Usage:
    from doorman.signals import customer_authenticated

    @receiver(customer_authenticated)
    def handle_auth(sender, customer, user, method, request, **kwargs):
        print(f"Customer {customer} authenticated via {method}")
"""

from django.dispatch import Signal


# Dispatched when Customer authenticates via Doorman
# args: customer, user, method (bridge_token|magic_code), request
customer_authenticated = Signal()

# Dispatched when a bridge token is created
# args: token, customer, audience, source
bridge_token_created = Signal()

# Dispatched when a magic code is sent
# args: code, target_value, delivery_method
magic_code_sent = Signal()

# Dispatched when a magic code is verified
# args: code, customer, purpose
magic_code_verified = Signal()

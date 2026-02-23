"""
Doorman adapters -- CustomerResolver implementations.

Available adapters:
- NoopCustomerResolver: Returns minimal DoormanCustomerInfo using the
  phone/email as the customer UUID. For development and testing without
  a real customer backend.
- GuestmanCustomerResolver: Resolves customers via guestman.services.customer.
  This is the production adapter when Guestman is installed.

Configure via DOORMAN["CUSTOMER_RESOLVER_CLASS"]:
    # Development / testing (no Guestman dependency)
    DOORMAN = {
        "CUSTOMER_RESOLVER_CLASS": "doorman.adapters.noop.NoopCustomerResolver",
    }

    # Production (with Guestman)
    DOORMAN = {
        "CUSTOMER_RESOLVER_CLASS": "doorman.adapters.guestman.GuestmanCustomerResolver",
    }
"""

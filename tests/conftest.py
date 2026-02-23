"""Doorman test fixtures."""

from datetime import timedelta

import pytest
from django.utils import timezone

from guestman.models import Customer

from doorman.conf import reset_customer_resolver
from doorman.models import BridgeToken, MagicCode
from doorman.models.magic_code import generate_raw_code


TEST_API_KEY = "test-doorman-api-key-2026"


@pytest.fixture(autouse=True)
def _reset_resolver():
    """Reset the cached customer resolver between tests."""
    reset_customer_resolver()
    yield
    reset_customer_resolver()


@pytest.fixture
def customer(db):
    """Create a test customer."""
    return Customer.objects.create(
        code="TEST-001",
        first_name="Test",
        last_name="Customer",
        phone="5541999999999",
        email="test@example.com",
    )


@pytest.fixture
def other_customer(db):
    """Create another test customer."""
    return Customer.objects.create(
        code="TEST-002",
        first_name="Other",
        last_name="Customer",
        phone="5541888888888",
        email="other@example.com",
    )


@pytest.fixture
def bridge_token(customer):
    """Create a valid bridge token."""
    return BridgeToken.objects.create(
        customer_id=customer.uuid,
        audience=BridgeToken.Audience.WEB_GENERAL,
        source=BridgeToken.Source.MANYCHAT,
    )


@pytest.fixture
def expired_bridge_token(customer):
    """Create an expired bridge token."""
    return BridgeToken.objects.create(
        customer_id=customer.uuid,
        expires_at=timezone.now() - timedelta(minutes=1),
    )


@pytest.fixture
def magic_code(db):
    """Create a valid magic code.

    The raw 6-digit code is stored as ``code._raw_code`` so tests
    can pass it to ``verify_for_login`` while the DB stores the HMAC.
    """
    raw_code, hmac_digest = generate_raw_code()
    code = MagicCode.objects.create(
        code_hash=hmac_digest,
        target_value="+5541999999999",
        purpose=MagicCode.Purpose.LOGIN,
    )
    code.mark_sent()
    code._raw_code = raw_code
    return code


@pytest.fixture
def expired_magic_code(db):
    """Create an expired magic code."""
    return MagicCode.objects.create(
        target_value="+5541999999999",
        purpose=MagicCode.Purpose.LOGIN,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

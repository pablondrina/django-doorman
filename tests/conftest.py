"""Doorman test fixtures."""

import pytest

from guestman.models import Customer


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

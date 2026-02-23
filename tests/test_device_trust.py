"""
Tests for Device Trust (TrustedDevice model + DeviceTrustService).
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import RequestFactory, override_settings
from django.utils import timezone

from doorman.models import TrustedDevice
from doorman.services.device_trust import DeviceTrustService


@pytest.mark.django_db
class TestTrustedDeviceModel:
    """Tests for TrustedDevice model."""

    def test_create_for_customer(self):
        """Creating a device returns (device, raw_token)."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(
            customer_id=cid,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X) Chrome/120",
        )
        assert device.customer_id == cid
        assert len(raw_token) > 20
        assert device.is_valid
        assert device.label  # Should derive label from UA

    def test_verify_token_valid(self):
        """Valid raw token should return the device."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)

        found = TrustedDevice.verify_token(raw_token)
        assert found is not None
        assert found.id == device.id
        assert found.last_used_at is not None

    def test_verify_token_invalid(self):
        """Invalid token should return None."""
        found = TrustedDevice.verify_token("invalid-token-value")
        assert found is None

    def test_verify_token_expired(self):
        """Expired device token should return None."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)
        device.expires_at = timezone.now() - timedelta(days=1)
        device.save()

        found = TrustedDevice.verify_token(raw_token)
        assert found is None

    def test_verify_token_revoked(self):
        """Revoked device token should return None."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)
        device.revoke()

        found = TrustedDevice.verify_token(raw_token)
        assert found is None

    def test_revoke_all_for_customer(self):
        """Revoke all should deactivate all devices for a customer."""
        cid = uuid.uuid4()
        TrustedDevice.create_for_customer(customer_id=cid)
        TrustedDevice.create_for_customer(customer_id=cid)

        count = TrustedDevice.revoke_all_for_customer(cid)
        assert count == 2

        active = TrustedDevice.objects.filter(
            customer_id=cid, is_active=True
        ).count()
        assert active == 0

    def test_cleanup_expired(self):
        """Cleanup should delete expired devices older than N days."""
        cid = uuid.uuid4()
        device, _ = TrustedDevice.create_for_customer(customer_id=cid)
        device.expires_at = timezone.now() - timedelta(days=30)
        device.save()

        deleted = TrustedDevice.cleanup_expired(days=7)
        assert deleted == 1

    def test_token_stored_as_hmac(self):
        """Token in DB should be HMAC digest, not plaintext."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)
        assert device.token_hash != raw_token
        assert len(device.token_hash) == 64  # SHA-256 hex digest

    def test_derive_label_chrome_mac(self):
        """Label should be derived from user-agent."""
        cid = uuid.uuid4()
        device, _ = TrustedDevice.create_for_customer(
            customer_id=cid,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        assert "Chrome" in device.label
        assert "Mac" in device.label

    def test_derive_label_safari_iphone(self):
        """Label should detect Safari on iPhone."""
        cid = uuid.uuid4()
        device, _ = TrustedDevice.create_for_customer(
            customer_id=cid,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        )
        assert "Safari" in device.label
        assert "iPhone" in device.label


@pytest.mark.django_db
class TestDeviceTrustService:
    """Tests for DeviceTrustService."""

    def _make_request(self, cookies=None):
        factory = RequestFactory()
        request = factory.get("/")
        if cookies:
            request.COOKIES.update(cookies)
        return request

    def test_check_device_trust_no_cookie(self):
        """No cookie → not trusted."""
        request = self._make_request()
        assert not DeviceTrustService.check_device_trust(request, uuid.uuid4())

    def test_check_device_trust_valid(self):
        """Valid cookie → trusted."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)
        request = self._make_request(cookies={"doorman_dt": raw_token})

        assert DeviceTrustService.check_device_trust(request, cid)

    def test_check_device_trust_wrong_customer(self):
        """Cookie for different customer → not trusted."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)
        request = self._make_request(cookies={"doorman_dt": raw_token})

        other_cid = uuid.uuid4()
        assert not DeviceTrustService.check_device_trust(request, other_cid)

    @override_settings(DOORMAN={"DEVICE_TRUST_ENABLED": False})
    def test_check_device_trust_disabled(self):
        """When disabled, always returns False."""
        cid = uuid.uuid4()
        device, raw_token = TrustedDevice.create_for_customer(customer_id=cid)
        request = self._make_request(cookies={"doorman_dt": raw_token})

        assert not DeviceTrustService.check_device_trust(request, cid)

    def test_trust_device_sets_cookie(self):
        """trust_device should set a HttpOnly cookie on the response."""
        from django.http import HttpResponse

        cid = uuid.uuid4()
        request = self._make_request()
        response = HttpResponse()

        device = DeviceTrustService.trust_device(response, cid, request)
        assert device is not None

        # Check that the cookie was set
        assert "doorman_dt" in response.cookies
        cookie = response.cookies["doorman_dt"]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"

    @override_settings(DOORMAN={"DEVICE_TRUST_ENABLED": False})
    def test_trust_device_disabled(self):
        """When disabled, trust_device returns None."""
        from django.http import HttpResponse

        response = HttpResponse()
        request = self._make_request()
        result = DeviceTrustService.trust_device(response, uuid.uuid4(), request)
        assert result is None

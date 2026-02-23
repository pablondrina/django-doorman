"""
Tests for Magic Link service and views.
"""

import json
from unittest.mock import patch

import pytest
from django.test import RequestFactory, override_settings

from doorman.services.magic_link import MagicLinkService
from doorman.views.magic_link import MagicLinkRequestView


@pytest.mark.django_db
class TestMagicLinkService:
    """Tests for MagicLinkService."""

    @patch("doorman.services.magic_link.MagicLinkService._send_magic_link_email")
    def test_send_magic_link_success(self, mock_send, customer):
        """Magic link should be sent for existing customer with email."""
        mock_send.return_value = True
        result = MagicLinkService.send_magic_link(customer.email)
        assert result.success

    @patch("doorman.services.magic_link.MagicLinkService._send_magic_link_email")
    def test_send_magic_link_email_not_found(self, mock_send):
        """Unknown email should return error."""
        result = MagicLinkService.send_magic_link("unknown@example.com")
        assert not result.success
        mock_send.assert_not_called()

    def test_send_magic_link_invalid_email(self):
        """Invalid email should return error."""
        result = MagicLinkService.send_magic_link("not-an-email")
        assert not result.success

    def test_send_magic_link_empty_email(self):
        """Empty email should return error."""
        result = MagicLinkService.send_magic_link("")
        assert not result.success

    @override_settings(DOORMAN={"MAGIC_LINK_ENABLED": False})
    def test_send_magic_link_disabled(self):
        """When disabled, should return error."""
        result = MagicLinkService.send_magic_link("test@example.com")
        assert not result.success
        assert "disabled" in result.error.lower()


@pytest.mark.django_db
class TestMagicLinkView:
    """Tests for MagicLinkRequestView."""

    def test_get_renders_form(self):
        factory = RequestFactory()
        request = factory.get("/doorman/magic-link/")
        from django.contrib.sessions.backends.db import SessionStore

        request.session = SessionStore()
        response = MagicLinkRequestView.as_view()(request)
        assert response.status_code == 200

    def test_post_empty_email_returns_error(self):
        factory = RequestFactory()
        request = factory.post(
            "/doorman/magic-link/",
            json.dumps({"email": ""}),
            content_type="application/json",
        )
        from django.contrib.sessions.backends.db import SessionStore

        request.session = SessionStore()
        response = MagicLinkRequestView.as_view()(request)
        assert response.status_code == 400

    @override_settings(DOORMAN={"MAGIC_LINK_ENABLED": False})
    def test_post_disabled_returns_error(self):
        factory = RequestFactory()
        request = factory.post(
            "/doorman/magic-link/",
            json.dumps({"email": "test@example.com"}),
            content_type="application/json",
        )
        from django.contrib.sessions.backends.db import SessionStore

        request.session = SessionStore()
        response = MagicLinkRequestView.as_view()(request)
        assert response.status_code == 400

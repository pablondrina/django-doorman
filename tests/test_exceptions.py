"""
Tests for Doorman exceptions (P2 — BaseError inheritance).
"""

from commons.exceptions import BaseError
from doorman.exceptions import DoormanError, GateError


class TestDoormanExceptions:
    """Tests that DoormanError inherits from BaseError."""

    def test_doorman_error_inherits_base_error(self):
        assert issubclass(DoormanError, BaseError)

    def test_gate_error_inherits_doorman_error(self):
        assert issubclass(GateError, DoormanError)

    def test_doorman_error_default_message(self):
        err = DoormanError("TOKEN_INVALID")
        assert err.code == "TOKEN_INVALID"
        assert err.message == "Token is invalid or expired"
        assert err.as_dict()["code"] == "TOKEN_INVALID"

    def test_doorman_error_custom_message(self):
        err = DoormanError("CUSTOM", "My custom error")
        assert err.message == "My custom error"

    def test_gate_error_preserves_gate_name(self):
        err = GateError("G7_BridgeTokenValidity", "Token expired.")
        assert err.gate_name == "G7_BridgeTokenValidity"
        assert err.code == "GATE_FAILED"
        assert err.message == "Token expired."

    def test_doorman_error_is_catchable_as_base_error(self):
        """DoormanError should be catchable as BaseError."""
        try:
            raise DoormanError("TEST")
        except BaseError as e:
            assert e.code == "TEST"

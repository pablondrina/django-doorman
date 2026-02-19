"""
Doorman exceptions.
"""


class DoormanError(Exception):
    """Base exception for Doorman."""

    pass


class TokenInvalidError(DoormanError):
    """Token is invalid or expired."""

    pass


class CodeInvalidError(DoormanError):
    """Code is invalid or expired."""

    pass


class RateLimitError(DoormanError):
    """Rate limit exceeded."""

    pass


class GateError(Exception):
    """Gate validation error."""

    def __init__(self, gate_name: str, message: str, details: dict | None = None):
        self.gate_name = gate_name
        self.message = message
        self.details = details or {}
        super().__init__(f"[{gate_name}] {message}")

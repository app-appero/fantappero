"""Auth-specific domain errors."""

from __future__ import annotations


class AuthError(Exception):
    """Base class for expected auth failures."""

    code: str = "auth_error"
    message: str = "Authentication failed."
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(AuthError):
    code = "invalid_credentials"
    message = "Invalid email or password."
    status_code = 401


class EmailAlreadyRegisteredError(AuthError):
    code = "email_already_registered"
    message = "An account with this email already exists."
    status_code = 409


class RateLimitExceededError(AuthError):
    code = "rate_limit_exceeded"
    message = "Too many attempts. Try again later."
    status_code = 429


class InvalidSessionError(AuthError):
    code = "invalid_session"
    message = "Session is invalid or expired."
    status_code = 401


class InvalidTokenError(AuthError):
    code = "invalid_token"
    message = "Token is invalid or expired."
    status_code = 400


class EmailNotVerifiedError(AuthError):
    code = "email_not_verified"
    message = "Email address is not verified."
    status_code = 403


class ForbiddenError(AuthError):
    code = "forbidden"
    message = "You do not have permission to access this resource."
    status_code = 403


class NotFoundError(AuthError):
    code = "not_found"
    message = "Resource not found."
    status_code = 404

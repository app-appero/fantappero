"""Privacy and data-rights domain errors."""

from __future__ import annotations

from auth.errors import AuthError


class AccountAlreadyDeletedError(AuthError):
    code = "account_already_deleted"
    message = "This account has already been deleted."
    status_code = 400


class InvalidDeleteConfirmationError(AuthError):
    code = "invalid_delete_confirmation"
    message = "Password confirmation is required to delete your account."
    status_code = 400

"""League configuration domain errors (EP03-01)."""

from __future__ import annotations

from auth.errors import AuthError


class LeagueValidationError(AuthError):
    code = "league_validation_error"
    message = "League configuration is not valid."
    status_code = 400

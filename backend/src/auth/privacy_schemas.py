"""Pydantic schemas for privacy API (EP02-04)."""

from __future__ import annotations

from pydantic import Field

from auth.profile_schemas import ApiModel


class DeleteAccountRequest(ApiModel):
    confirm_phrase: str = Field(alias="confirmPhrase", min_length=1)
    # Obbligatoria per chi ha una password; chi accede solo con Google non ne ha una.
    password: str | None = Field(default=None, max_length=128)


class PrivacyMessageResponse(ApiModel):
    message: str

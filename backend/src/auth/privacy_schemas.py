"""Pydantic schemas for privacy API (EP02-04)."""

from __future__ import annotations

from pydantic import Field

from auth.profile_schemas import ApiModel


class DeleteAccountRequest(ApiModel):
    password: str = Field(min_length=1)
    confirm_phrase: str = Field(alias="confirmPhrase", min_length=1)


class PrivacyMessageResponse(ApiModel):
    message: str

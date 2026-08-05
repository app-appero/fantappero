"""Pydantic schemas for auth API (Italian user messages)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120, alias="displayName")


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(ApiModel):
    refresh_token: str = Field(min_length=1, alias="refreshToken")


class TokenPayloadRequest(ApiModel):
    token: str = Field(min_length=1)


class ForgotPasswordRequest(ApiModel):
    email: EmailStr


class ResetPasswordRequest(ApiModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128, alias="newPassword")


class ResendVerificationRequest(ApiModel):
    email: EmailStr


class SessionUserResponse(ApiModel):
    id: str
    displayName: str
    globalRole: str


class AuthTokensResponse(ApiModel):
    accessToken: str
    refreshToken: str
    expiresIn: int
    user: SessionUserResponse


class MessageResponse(ApiModel):
    message: str

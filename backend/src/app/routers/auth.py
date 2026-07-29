"""Auth HTTP routes (EP02-01)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.deps_auth import (
    client_rate_limit_key,
    get_auth_service,
    get_current_session,
    get_current_user,
)
from app.deps_profile import get_profile_service
from auth.schemas import (
    AuthSessionResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    TokenRequest,
)
from auth.service import AuthService
from database.models.accounts import AuthSession, User
from profiles.schemas import UserProfileResponse
from profiles.service import ProfileService

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_response(token: str, expires_at) -> AuthSessionResponse:
    return AuthSessionResponse(access_token=token, expires_at=expires_at)


@router.post(
    "/register",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    body: RegisterRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    _, token, expires_at = service.register(
        email=str(body.email),
        password=body.password,
        client_key=client_rate_limit_key(request, str(body.email)),
    )
    return _session_response(token, expires_at)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    body: LoginRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    _, token, expires_at = service.login(
        email=str(body.email),
        password=body.password,
        client_key=client_rate_limit_key(request, str(body.email)),
    )
    return _session_response(token, expires_at)


@router.post("/logout", response_model=MessageResponse)
def logout(
    session: Annotated[AuthSession, Depends(get_current_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    service.logout(session=session)
    return MessageResponse(message="Logged out.")


@router.get("/me", response_model=UserProfileResponse)
def me(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> UserProfileResponse:
    return service.get_profile(actor=user, user_id=user.id)


@router.post("/verify-email", response_model=UserProfileResponse)
def verify_email(
    body: TokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> UserProfileResponse:
    user = service.verify_email(raw_token=body.token)
    return profile_service.get_profile(actor=user, user_id=user.id)


@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(
    body: RequestPasswordResetRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    service.request_password_reset(
        email=str(body.email),
        client_key=client_rate_limit_key(request, str(body.email)),
    )
    return MessageResponse(message="If the account exists, reset instructions were sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    service.reset_password(raw_token=body.token, new_password=body.new_password)
    return MessageResponse(message="Password updated.")

"""Auth HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from auth.dependencies import get_auth_service, get_client_ip, get_current_user
from auth.exceptions import AuthError, RateLimitExceededError
from auth.models.user import User
from auth.schemas import (
    AuthTokensResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SessionUserResponse,
    TokenPayloadRequest,
)
from auth.service import AuthService
from database.enums import platform_role_to_global_role

router = APIRouter(prefix="/auth", tags=["auth"])


def _error_response(exc: AuthError) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "invalid_credentials":
        status_code = status.HTTP_401_UNAUTHORIZED
    elif exc.code == "email_not_verified":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code == "rate_limit_exceeded":
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse | JSONResponse:
    try:
        return service.register(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            client_ip=get_client_ip(request),
        )
    except AuthError as exc:
        return _error_response(exc)


@router.post("/login", response_model=AuthTokensResponse)
def login(
    body: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokensResponse | JSONResponse:
    try:
        return service.login(
            email=body.email,
            password=body.password,
            client_ip=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    except AuthError as exc:
        return _error_response(exc)


@router.post("/refresh", response_model=AuthTokensResponse)
def refresh(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokensResponse | JSONResponse:
    try:
        return service.refresh(refresh_token=body.refresh_token)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(refresh_token=body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=SessionUserResponse)
def me(current_user: User = Depends(get_current_user)) -> SessionUserResponse:
    return SessionUserResponse(
        id=str(current_user.id),
        displayName=current_user.display_name,
        globalRole=platform_role_to_global_role(current_user.platform_role).value,
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    body: TokenPayloadRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse | JSONResponse:
    try:
        return service.verify_email(token=body.token)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse | JSONResponse:
    try:
        return service.resend_verification(email=body.email, client_ip=get_client_ip(request))
    except RateLimitExceededError as exc:
        return _error_response(exc)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse | JSONResponse:
    try:
        return service.forgot_password(email=body.email, client_ip=get_client_ip(request))
    except RateLimitExceededError as exc:
        return _error_response(exc)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse | JSONResponse:
    try:
        return service.reset_password(token=body.token, new_password=body.new_password)
    except AuthError as exc:
        return _error_response(exc)

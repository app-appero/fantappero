"""Profile HTTP routes (EP02-02 / EP02-04)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse, Response

from auth.dependencies import get_privacy_service, get_profile_service
from auth.exceptions import AuthError
from auth.models.user import User
from auth.privacy_schemas import DeleteAccountRequest, PrivacyMessageResponse
from auth.privacy_service import PrivacyService
from auth.profile_schemas import (
    PolicyConsentRequest,
    ProfileResponse,
    UpdateInviteAvailabilityRequest,
    UpdateProfileRequest,
)
from auth.profile_service import ProfileService
from authorization.dependencies import require_permissions
from database.enums import Permission

router = APIRouter(prefix="/profile", tags=["profile"])


def _error_response(exc: AuthError) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "invalid_credentials":
        status_code = status.HTTP_401_UNAUTHORIZED
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return service.get_profile(current_user)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse | JSONResponse:
    try:
        return service.update_profile(current_user, body)
    except AuthError as exc:
        return _error_response(exc)


@router.patch("/disponibilita-inviti", response_model=ProfileResponse)
def update_invite_availability(
    body: UpdateInviteAvailabilityRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse | JSONResponse:
    try:
        return service.update_invite_availability(
            current_user,
            available_for_invites=body.available_for_invites,
        )
    except AuthError as exc:
        return _error_response(exc)


@router.post("/me/avatar", response_model=ProfileResponse)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse | JSONResponse:
    try:
        data = await file.read()
        return service.upload_avatar(current_user, data=data)
    except AuthError as exc:
        return _error_response(exc)


@router.delete("/me/avatar", response_model=ProfileResponse)
def remove_my_avatar(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return service.remove_avatar(current_user)


@router.post("/me/policy-consent", response_model=ProfileResponse)
def record_policy_consent(
    body: PolicyConsentRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse | JSONResponse:
    try:
        return service.record_policy_consent(current_user, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/me/export")
def export_my_data(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: PrivacyService = Depends(get_privacy_service),
) -> Response:
    payload = service.export_user_data(current_user)
    exported_at = datetime.now(UTC).strftime("%Y%m%d")
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": (f'attachment; filename="fantappero-export-{exported_at}.json"'),
        },
    )


@router.post("/me/delete", response_model=PrivacyMessageResponse)
def delete_my_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: PrivacyService = Depends(get_privacy_service),
) -> PrivacyMessageResponse | JSONResponse:
    try:
        return service.delete_account(
            current_user,
            password=body.password,
            confirm_phrase=body.confirm_phrase,
        )
    except AuthError as exc:
        return _error_response(exc)

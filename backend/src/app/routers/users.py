"""User profile routes with authorization policies (EP02-01, EP02-02, EP02-03, EP02-04)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.deps_auth import get_current_user
from app.deps_privacy import get_privacy_service
from app.deps_profile import get_profile_service
from database.models.accounts import User
from privacy.schemas import DeleteAccountRequest, DeleteAccountResponse, UserDataExportResponse
from privacy.service import PrivacyService
from profiles.schemas import UpdateProfileRequest, UserProfileResponse
from profiles.service import ProfileService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> UserProfileResponse:
    return service.get_profile(actor=user, user_id=user.id)


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    body: UpdateProfileRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> UserProfileResponse:
    return service.update_profile(actor=user, user_id=user.id, body=body)


@router.post("/me/avatar", response_model=UserProfileResponse)
async def upload_my_avatar(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
    avatar: UploadFile = File(...),
) -> UserProfileResponse:
    content = await avatar.read()
    return service.upload_avatar(
        actor=user,
        user_id=user.id,
        content=content,
        content_type=avatar.content_type,
    )


@router.get("/me/export", response_model=UserDataExportResponse)
def export_my_data(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PrivacyService, Depends(get_privacy_service)],
) -> UserDataExportResponse:
    correlation_id = request.headers.get("X-Correlation-ID")
    return service.export_user_data(
        actor=user,
        user_id=user.id,
        correlation_id=correlation_id,
    )


@router.post("/me/delete", response_model=DeleteAccountResponse)
def delete_my_account(
    body: DeleteAccountRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PrivacyService, Depends(get_privacy_service)],
) -> DeleteAccountResponse:
    correlation_id = request.headers.get("X-Correlation-ID")
    return service.delete_account(
        actor=user,
        user_id=user.id,
        body=body,
        correlation_id=correlation_id,
    )


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user(
    user_id: uuid.UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> UserProfileResponse:
    return service.get_profile(actor=actor, user_id=user_id)

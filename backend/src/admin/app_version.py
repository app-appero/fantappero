"""Versione dell'app Android: avviso «È disponibile la versione X» (pilota-1.2, Rosario 21/11).

L'APK si distribuisce a mano (cartella Drive, gruppo WhatsApp): l'operatore scrive nel pannello
l'ultima versione pubblicata (nome, versionCode, link di download, messaggio facoltativo) e l'app
la confronta con quella installata. Sta in `system_flags` (chiave ``android_app_version``, valore
JSON) come la modalità test: si cambia senza deploy e senza migrazioni.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from admin.schemas import (
    AdminAndroidAppVersionUpdateRequest,
    AndroidAppVersionResponse,
    AppVersionResponse,
)
from auth.dependencies import get_current_user, get_db_session
from auth.exceptions import TesterOnlyError
from auth.models.user import User
from auth.tester_access import TesterAccess
from authorization.dependencies import require_permissions
from database.enums import FlagScope, Permission
from database.models.infrastructure import SystemFlag
from observability.logging import get_logger

ANDROID_APP_VERSION_FLAG_KEY = "android_app_version"

_logger = get_logger(__name__)


class AppVersionStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> AppVersionResponse:
        """Una sola lettura; un valore assente o rovinato vale «non impostata» (nessun avviso)."""
        raw = self._session.scalar(
            select(SystemFlag.value).where(SystemFlag.key == ANDROID_APP_VERSION_FLAG_KEY)
        )
        if not raw:
            return AppVersionResponse(android=None)
        try:
            android = AndroidAppVersionResponse.model_validate(json.loads(raw))
        except (ValueError, TypeError):
            _logger.warning("app_version_flag_unreadable")
            return AppVersionResponse(android=None)
        return AppVersionResponse(android=android)

    def set_android(self, body: AdminAndroidAppVersionUpdateRequest) -> AppVersionResponse:
        value = json.dumps(
            {
                "latestVersionName": body.latest_version_name,
                "latestVersionCode": body.latest_version_code,
                "downloadUrl": body.download_url,
                "message": body.message,
            }
        )
        flag = self._session.scalar(
            select(SystemFlag).where(SystemFlag.key == ANDROID_APP_VERSION_FLAG_KEY)
        )
        if flag is None:
            self._session.add(
                SystemFlag(key=ANDROID_APP_VERSION_FLAG_KEY, value=value, scope=FlagScope.SYSTEM)
            )
        else:
            flag.value = value
        self._session.flush()
        return self.get()


# --- lettura per chi usa l'app --------------------------------------------------------------
router = APIRouter(prefix="/app", tags=["app"])


@router.get("/version", response_model=AppVersionResponse)
def get_app_version(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AppVersionResponse:
    """Ultima versione pubblicata dell'app. Vuota per chi non è autorizzato all'app
    (modalità test accesa e account non tra i tester)."""
    try:
        TesterAccess(session).assert_allowed(email=user.email, platform_role=user.platform_role)
    except TesterOnlyError:
        return AppVersionResponse(android=None)
    return AppVersionStore(session).get()


# --- pannello operatore ---------------------------------------------------------------------
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/app-version", response_model=AppVersionResponse)
def get_admin_app_version(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AppVersionResponse:
    return AppVersionStore(session).get()


@admin_router.put("/app-version", response_model=AppVersionResponse)
def set_admin_app_version(
    body: AdminAndroidAppVersionUpdateRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AppVersionResponse:
    result = AppVersionStore(session).set_android(body)
    _logger.info(
        "admin_app_version_changed",
        extra={
            "actor_id": str(operator.id),
            "version_name": body.latest_version_name,
            "version_code": body.latest_version_code,
        },
    )
    session.commit()
    return result

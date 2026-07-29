"""Profile dependencies for FastAPI routes."""



from __future__ import annotations



from functools import lru_cache

from typing import Annotated



from fastapi import Depends

from sqlalchemy.orm import Session



from app.deps_authorization import get_authorization_service

from app.deps_db import get_db

from authorization.service import AuthorizationService

from config.settings.profile import ProfileSettings

from profiles.service import ProfileService





@lru_cache(maxsize=1)

def get_profile_settings() -> ProfileSettings:

    return ProfileSettings()





def reset_profile_deps_cache() -> None:

    get_profile_settings.cache_clear()





def get_profile_service(

    db: Annotated[Session, Depends(get_db)],

    settings: Annotated[ProfileSettings, Depends(get_profile_settings)],

    authorization: Annotated[AuthorizationService, Depends(get_authorization_service)],

) -> ProfileService:

    return ProfileService(db, settings, authorization)



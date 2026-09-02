"""Typed environment schema for the Celery worker process."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from config.settings.base import BaseAppSettings, require_non_empty
from config.settings.fantasy_turns_settings import FantasyTurnsSettingsMixin
from config.settings.mail import MailSettingsMixin
from config.settings.notifications_settings import NotificationsSettingsMixin
from config.settings.scheduler_settings import SportsSchedulerSettingsMixin


class WorkerSettings(
    BaseAppSettings,
    MailSettingsMixin,
    SportsSchedulerSettingsMixin,
    FantasyTurnsSettingsMixin,
    NotificationsSettingsMixin,
):
    """Configuration consumed by the Celery worker / beat."""

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    celery_broker_url: str | None = Field(default=None, validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str | None = Field(
        default=None,
        validation_alias="CELERY_RESULT_BACKEND",
    )

    @field_validator(
        "database_url",
        "redis_url",
        "celery_broker_url",
        "celery_result_backend",
        mode="before",
    )
    @classmethod
    def _strip_or_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _require_infra_when_strict(self) -> WorkerSettings:
        if not self.strict_infra_required:
            return self
        require_non_empty("DATABASE_URL", self.database_url)
        require_non_empty("REDIS_URL", self.redis_url)
        broker = self.celery_broker_url or self.redis_url
        backend = self.celery_result_backend or self.redis_url
        require_non_empty("CELERY_BROKER_URL", broker)
        require_non_empty("CELERY_RESULT_BACKEND", backend)
        return self

    def resolved_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url or "redis://127.0.0.1:6379/0"

    def resolved_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url or "redis://127.0.0.1:6379/1"

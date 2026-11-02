"""Impostazioni delle segnalazioni utente e dei loro allegati."""

from __future__ import annotations

from pydantic import Field, field_validator


class FeedbackSettingsMixin:
    """Dove vivono gli allegati e quanto possono pesare."""

    feedback_storage_path: str = Field(
        default="/data/feedback",
        validation_alias="FEEDBACK_STORAGE_PATH",
        description="Cartella PRIVATA degli allegati delle segnalazioni (mai servita come statica).",
    )
    feedback_image_max_bytes: int = Field(
        default=8_388_608,
        validation_alias="FEEDBACK_IMAGE_MAX_BYTES",
        description="Peso massimo di un'immagine allegata (default 8 MiB).",
    )
    feedback_video_max_bytes: int = Field(
        default=52_428_800,
        validation_alias="FEEDBACK_VIDEO_MAX_BYTES",
        description="Peso massimo di un video allegato (default 50 MiB).",
    )
    feedback_max_attachments: int = Field(
        default=3,
        validation_alias="FEEDBACK_MAX_ATTACHMENTS",
        description="Quanti allegati al massimo per segnalazione.",
    )
    feedback_hourly_limit: int = Field(
        default=10,
        validation_alias="FEEDBACK_HOURLY_LIMIT",
        description="Segnalazioni al massimo per utente nell'ultima ora (anti-spam).",
    )
    feedback_media_link_ttl_seconds: int = Field(
        default=900,
        validation_alias="FEEDBACK_MEDIA_LINK_TTL_SECONDS",
        description="Durata dei link firmati con cui l'operatore vede gli allegati.",
    )

    @field_validator(
        "feedback_image_max_bytes",
        "feedback_video_max_bytes",
        "feedback_max_attachments",
        "feedback_hourly_limit",
        "feedback_media_link_ttl_seconds",
        mode="before",
    )
    @classmethod
    def _parse_feedback_ints(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value

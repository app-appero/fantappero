"""Segnalazioni utente: creazione, notifica agli operatori, lettura e gestione."""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.security import utc_now
from config.settings.api import ApiSettings
from database.enums import NotificationCategory, PlatformRole
from feedback import media
from feedback.models import CATEGORIES, PLATFORMS, STATUSES, FeedbackAttachment, FeedbackReport
from notifications.service import NotificationService
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)

MESSAGE_MIN_CHARS = 10
MESSAGE_MAX_CHARS = 2000
NOTE_MAX_CHARS = 2000
_EXCERPT_CHARS = 140
#: Stati che l'autore vuole conoscere. «new» (anche una riapertura) non genera avvisi.
AUTHOR_NOTIFIED_STATUSES = frozenset({"in_review", "resolved", "dismissed"})


class FeedbackError(Exception):
    """Errore di validazione/permesso con codice stabile per il client."""

    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _clean(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    return text[:limit] or None


def author_name(user: User, profile: UserProfile | None) -> str:
    if profile is not None:
        for candidate in (profile.nickname, profile.display_name):
            if candidate and candidate.strip():
                return candidate.strip()
    return user.email


class FeedbackService:
    def __init__(self, session: Session, settings: ApiSettings) -> None:
        self._session = session
        self._settings = settings

    # --- creazione ---------------------------------------------------------

    def create_report(
        self,
        user: User,
        *,
        message: str,
        category: str,
        page_context: str | None,
        platform: str | None,
        app_version: str | None,
        user_agent: str | None,
        uploads: Sequence[bytes],
    ) -> FeedbackReport:
        text = (message or "").strip()
        if len(text) < MESSAGE_MIN_CHARS:
            raise FeedbackError(
                "feedback_message_too_short",
                f"Descrivi il problema in almeno {MESSAGE_MIN_CHARS} caratteri.",
            )
        if len(text) > MESSAGE_MAX_CHARS:
            raise FeedbackError(
                "feedback_message_too_long",
                f"Il testo supera i {MESSAGE_MAX_CHARS} caratteri.",
            )
        if category not in CATEGORIES:
            raise FeedbackError("feedback_invalid_category", "Categoria non valida.")
        if platform is not None and platform not in PLATFORMS:
            platform = None
        if len(uploads) > self._settings.feedback_max_attachments:
            raise FeedbackError(
                "feedback_too_many_attachments",
                f"Puoi allegare al massimo {self._settings.feedback_max_attachments} file.",
            )
        self._check_rate_limit(user)
        checked = [self._check_upload(data) for data in uploads]

        report = FeedbackReport(
            user_id=user.id,
            category=category,
            message=text,
            page_context=_clean(page_context, 255),
            platform=platform,
            app_version=_clean(app_version, 32),
            user_agent=_clean(user_agent, 255),
            status="new",
        )
        self._session.add(report)
        self._session.flush()

        storage = Path(self._settings.resolved_feedback_storage_path())
        written: list[Path] = []
        try:
            if checked:
                storage.mkdir(parents=True, exist_ok=True)
            for data, content_type in checked:
                attachment_id = uuid4()
                stored_name = f"{attachment_id}.{media.extension_of(content_type)}"
                target = storage / stored_name
                target.write_bytes(data)
                written.append(target)
                self._session.add(
                    FeedbackAttachment(
                        id=attachment_id,
                        report_id=report.id,
                        kind=media.kind_of(content_type),
                        content_type=content_type,
                        size_bytes=len(data),
                        stored_name=stored_name,
                    )
                )
            self._session.flush()
            self._notify_operators(report, author=user)
            self._session.commit()
        except Exception:
            self._session.rollback()
            for path in written:
                with contextlib.suppress(OSError):
                    path.unlink()
            raise
        get_metrics().incr("feedback_reports_created_total", labels={"category": category})
        return self.get_report(report.id)

    def _check_rate_limit(self, user: User) -> None:
        since = utc_now() - timedelta(hours=1)
        recent = self._session.scalar(
            select(func.count())
            .select_from(FeedbackReport)
            .where(FeedbackReport.user_id == user.id, FeedbackReport.created_at >= since)
        )
        if (recent or 0) >= self._settings.feedback_hourly_limit:
            raise FeedbackError(
                "feedback_rate_limited",
                "Hai inviato molte segnalazioni di recente. Riprova tra un po'.",
                status_code=429,
            )

    def _check_upload(self, data: bytes) -> tuple[bytes, str]:
        if not data:
            raise FeedbackError("feedback_empty_attachment", "Uno degli allegati è vuoto.")
        content_type = media.detect_content_type(data)
        if content_type is None:
            raise FeedbackError(
                "feedback_invalid_attachment",
                "Formato non supportato. Usa immagini JPEG, PNG, WebP, GIF o video MP4, MOV, WebM.",
            )
        is_image = media.kind_of(content_type) == "image"
        limit = (
            self._settings.feedback_image_max_bytes
            if is_image
            else self._settings.feedback_video_max_bytes
        )
        if len(data) > limit:
            raise FeedbackError(
                "feedback_attachment_too_large",
                f"Il file supera il peso massimo di {limit // (1024 * 1024)} MB "
                f"per {'le immagini' if is_image else 'i video'}.",
                status_code=413,
            )
        return data, content_type

    # --- notifica ai soli operatori --------------------------------------------

    def _notify_operators(self, report: FeedbackReport, *, author: User) -> None:
        """In-app + push a TUTTI e SOLI gli operatori. L'autore non riceve nulla."""
        operator_ids = list(
            self._session.scalars(
                select(User.id).where(User.platform_role == PlatformRole.OPERATOR)
            ).all()
        )
        profile = self._session.get(UserProfile, author.id)
        name = author_name(author, profile)
        excerpt = report.message[:_EXCERPT_CHARS] + ("…" if len(report.message) > _EXCERPT_CHARS else "")
        service = NotificationService(self._session)
        for operator_id in operator_ids:
            service.create_notification(
                user_id=operator_id,
                category=NotificationCategory.SISTEMA,
                template_key="sistema.feedback_utente",
                template_version=1,
                params={
                    "author": name,
                    "category": report.category,
                    "excerpt": excerpt,
                    "has_media": bool(report.attachments),
                },
                dedup_key=f"feedback:{report.id}",
                push=True,
                email=False,
            )

    # --- lettura ---------------------------------------------------------------

    def get_report(self, report_id: UUID) -> FeedbackReport:
        report = self._session.scalar(
            select(FeedbackReport)
            .options(selectinload(FeedbackReport.attachments))
            .where(FeedbackReport.id == report_id)
        )
        if report is None:
            raise FeedbackError("feedback_not_found", "Segnalazione non trovata.", status_code=404)
        return report

    def list_for_user(self, user: User, *, limit: int = 50) -> list[FeedbackReport]:
        return list(
            self._session.scalars(
                select(FeedbackReport)
                .options(selectinload(FeedbackReport.attachments))
                .where(FeedbackReport.user_id == user.id)
                .order_by(FeedbackReport.created_at.desc())
                .limit(limit)
            ).all()
        )

    def list_for_operators(
        self,
        *,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[FeedbackReport], int, int]:
        """``(righe, totale con il filtro, quante sono ancora "new")``."""
        if status is not None and status not in STATUSES:
            raise FeedbackError("feedback_invalid_status", "Stato non valido.")
        base = select(FeedbackReport)
        count = select(func.count()).select_from(FeedbackReport)
        if status is not None:
            base = base.where(FeedbackReport.status == status)
            count = count.where(FeedbackReport.status == status)
        rows = list(
            self._session.scalars(
                base.options(selectinload(FeedbackReport.attachments))
                .order_by(FeedbackReport.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        total = self._session.scalar(count) or 0
        new_count = (
            self._session.scalar(
                select(func.count())
                .select_from(FeedbackReport)
                .where(FeedbackReport.status == "new")
            )
            or 0
        )
        return rows, total, new_count

    def authors(self, reports: Sequence[FeedbackReport]) -> dict[UUID, tuple[User, UserProfile | None]]:
        ids = {report.user_id for report in reports}
        if not ids:
            return {}
        users = self._session.scalars(select(User).where(User.id.in_(ids))).all()
        profiles = {
            profile.user_id: profile
            for profile in self._session.scalars(
                select(UserProfile).where(UserProfile.user_id.in_(ids))
            ).all()
        }
        return {user.id: (user, profiles.get(user.id)) for user in users}

    # --- gestione operatore --------------------------------------------------------

    def update_report(
        self,
        report_id: UUID,
        *,
        operator: User,
        status: str | None,
        operator_note: str | None,
    ) -> FeedbackReport:
        report = self.get_report(report_id)
        previous_status = report.status
        if status is not None:
            if status not in STATUSES:
                raise FeedbackError("feedback_invalid_status", "Stato non valido.")
            report.status = status
        if operator_note is not None:
            report.operator_note = operator_note.strip()[:NOTE_MAX_CHARS] or None
        report.handled_by_id = operator.id
        report.handled_at = utc_now()
        if status is not None and status != previous_status:
            self._notify_author(report)
        self._session.commit()
        return self.get_report(report_id)

    def delete_report(self, report_id: UUID) -> None:
        """Elimina fisicamente la segnalazione: righe, testo e file allegati su disco.

        Prima si cancella la riga e si conferma la transazione, poi i file: se il
        database rifiuta la cancellazione non si perde nessun allegato. Se invece
        un file non si riesce a togliere resta solo un file orfano, mai una
        segnalazione senza i suoi allegati.
        """
        report = self.get_report(report_id)
        storage = Path(self._settings.resolved_feedback_storage_path())
        paths = [storage / attachment.stored_name for attachment in report.attachments]
        self._session.delete(report)
        self._session.commit()
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("feedback_attachment_unlink_failed", extra={"file": path.name})
        get_metrics().incr("feedback_reports_deleted_total")

    # --- notifica all'autore ------------------------------------------------------------

    def _notify_author(self, report: FeedbackReport) -> None:
        """Avvisa chi ha scritto quando la segnalazione cambia stato (non per «Ricevuta»).

        La nota interna dell'operatore non viaggia mai nella notifica.
        """
        if report.status not in AUTHOR_NOTIFIED_STATUSES:
            return
        excerpt = report.message[:_EXCERPT_CHARS] + ("…" if len(report.message) > _EXCERPT_CHARS else "")
        NotificationService(self._session).create_notification(
            user_id=report.user_id,
            category=NotificationCategory.SISTEMA,
            template_key="sistema.feedback_stato",
            template_version=1,
            params={"status": report.status, "excerpt": excerpt},
            # Un avviso per ogni cambio di stato: se la segnalazione viene riaperta e
            # richiusa l'autore deve ricevere di nuovo l'avviso.
            dedup_key=f"feedback-status:{report.id}:{report.status}:{uuid4()}",
            push=True,
            email=False,
        )

    # --- allegati -------------------------------------------------------------------

    def attachment_path(self, attachment: FeedbackAttachment) -> Path:
        return Path(self._settings.resolved_feedback_storage_path()) / attachment.stored_name

    def get_attachment(self, attachment_id: UUID) -> FeedbackAttachment:
        attachment = self._session.get(FeedbackAttachment, attachment_id)
        if attachment is None:
            raise FeedbackError("feedback_not_found", "Allegato non trovato.", status_code=404)
        return attachment

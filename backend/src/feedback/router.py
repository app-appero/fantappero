"""API delle segnalazioni: l'utente scrive, solo gli operatori leggono e gestiscono."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.models.user import User
from authorization.dependencies import require_permissions
from config.settings.loader import get_api_settings
from database.enums import Permission
from feedback import media
from feedback.models import FeedbackReport
from feedback.schemas import (
    FeedbackAdminListResponse,
    FeedbackAdminReportResponse,
    FeedbackAttachmentResponse,
    FeedbackDeletedResponse,
    FeedbackReportSummaryResponse,
    FeedbackUpdateRequest,
)
from feedback.service import FeedbackError, FeedbackService, author_name

router = APIRouter(prefix="/feedback", tags=["feedback"])
admin_router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])

_PAGE_SIZE = 20
_READ_CHUNK = 1024 * 1024


def get_feedback_service(session: Session = Depends(get_db_session)) -> FeedbackService:
    return FeedbackService(session, get_api_settings())


def _error(exc: FeedbackError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message, "code": exc.code},
    )


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Legge il file a blocchi e si ferma appena supera il limite."""
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise FeedbackError(
                "feedback_attachment_too_large",
                "Uno degli allegati è troppo pesante.",
                status_code=413,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _summary(report: FeedbackReport) -> FeedbackReportSummaryResponse:
    return FeedbackReportSummaryResponse(
        id=str(report.id),
        category=report.category,  # type: ignore[arg-type]
        message=report.message,
        status=report.status,  # type: ignore[arg-type]
        createdAt=report.created_at,
        attachmentCount=len(report.attachments),
    )


def _admin_report(
    report: FeedbackReport,
    service: FeedbackService,
    authors: dict,
) -> FeedbackAdminReportResponse:
    settings = get_api_settings()
    secret = settings.resolved_jwt_secret()
    user, profile = authors.get(report.user_id, (None, None))
    attachments = [
        FeedbackAttachmentResponse(
            id=str(item.id),
            kind=item.kind,  # type: ignore[arg-type]
            contentType=item.content_type,
            sizeBytes=item.size_bytes,
            url=(
                f"/feedback/media/{item.id}?token="
                + media.make_media_token(
                    secret,
                    item.id,
                    ttl_seconds=settings.feedback_media_link_ttl_seconds,
                )
            ),
        )
        for item in report.attachments
    ]
    return FeedbackAdminReportResponse(
        id=str(report.id),
        category=report.category,  # type: ignore[arg-type]
        message=report.message,
        status=report.status,  # type: ignore[arg-type]
        createdAt=report.created_at,
        authorUserId=str(report.user_id),
        authorName=author_name(user, profile) if user is not None else "Utente eliminato",
        authorEmail=user.email if user is not None else "",
        pageContext=report.page_context,
        platform=report.platform,  # type: ignore[arg-type]
        appVersion=report.app_version,
        userAgent=report.user_agent,
        operatorNote=report.operator_note,
        handledAt=report.handled_at,
        attachments=attachments,
    )


# --- utente ------------------------------------------------------------------------


@router.post("", response_model=FeedbackReportSummaryResponse, status_code=201)
async def create_feedback(
    request: Request,
    message: str = Form(...),
    category: str = Form("bug"),
    page_context: str | None = Form(None, alias="pageContext"),
    platform: str | None = Form(None),
    app_version: str | None = Form(None, alias="appVersion"),
    files: list[UploadFile] = File(default_factory=list),
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackReportSummaryResponse | JSONResponse:
    """Invia una segnalazione con testo e, se vuole, immagini o video."""
    settings = get_api_settings()
    try:
        if len(files) > settings.feedback_max_attachments:
            raise FeedbackError(
                "feedback_too_many_attachments",
                f"Puoi allegare al massimo {settings.feedback_max_attachments} file.",
            )
        uploads = [
            await _read_limited(
                item,
                max(settings.feedback_image_max_bytes, settings.feedback_video_max_bytes),
            )
            for item in files
        ]
        report = service.create_report(
            current_user,
            message=message,
            category=category,
            page_context=page_context,
            platform=platform,
            app_version=app_version,
            user_agent=request.headers.get("user-agent"),
            uploads=uploads,
        )
    except FeedbackError as exc:
        return _error(exc)
    return _summary(report)


@router.get("/me", response_model=list[FeedbackReportSummaryResponse])
def list_my_feedback(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: FeedbackService = Depends(get_feedback_service),
) -> list[FeedbackReportSummaryResponse]:
    """Le segnalazioni inviate dall'utente, con lo stato di lavorazione."""
    return [_summary(report) for report in service.list_for_user(current_user)]


@router.get("/media/{attachment_id}", response_model=None)
def get_feedback_media(
    attachment_id: UUID,
    token: str = Query(...),
    service: FeedbackService = Depends(get_feedback_service),
) -> FileResponse | JSONResponse:
    """Legge un allegato con il link firmato che l'operatore ha ottenuto dal dettaglio.

    Nessun header Authorization: serve a far funzionare <img>, <video> e l'apertura
    dal browser del telefono. Il link vale per quel solo file e scade in pochi minuti.
    """
    settings = get_api_settings()
    if not media.verify_media_token(settings.resolved_jwt_secret(), attachment_id, token):
        return JSONResponse(
            status_code=403,
            content={"message": "Link non valido o scaduto.", "code": "feedback_link_invalid"},
        )
    try:
        attachment = service.get_attachment(attachment_id)
    except FeedbackError as exc:
        return _error(exc)
    path = service.attachment_path(attachment)
    if not path.is_file():
        return JSONResponse(
            status_code=404,
            content={"message": "Allegato non disponibile.", "code": "feedback_not_found"},
        )
    return FileResponse(
        path,
        media_type=attachment.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


# --- operatori ----------------------------------------------------------------------


@admin_router.get("", response_model=FeedbackAdminListResponse)
def list_feedback_for_operators(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackAdminListResponse | JSONResponse:
    try:
        rows, total, new_count = service.list_for_operators(
            status=status, page=page, page_size=_PAGE_SIZE
        )
    except FeedbackError as exc:
        return _error(exc)
    authors = service.authors(rows)
    return FeedbackAdminListResponse(
        items=[_admin_report(row, service, authors) for row in rows],
        total=total,
        newCount=new_count,
        page=page,
        pageSize=_PAGE_SIZE,
    )


@admin_router.delete("/{report_id}", response_model=FeedbackDeletedResponse)
def delete_feedback(
    report_id: UUID,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackDeletedResponse | JSONResponse:
    """Elimina fisicamente la segnalazione con testo e allegati (irreversibile)."""
    try:
        service.delete_report(report_id)
    except FeedbackError as exc:
        return _error(exc)
    return FeedbackDeletedResponse(deleted=True)


@admin_router.patch("/{report_id}", response_model=FeedbackAdminReportResponse)
def update_feedback(
    report_id: UUID,
    body: FeedbackUpdateRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackAdminReportResponse | JSONResponse:
    try:
        report = service.update_report(
            report_id,
            operator=operator,
            status=body.status,
            operator_note=body.operator_note,
        )
    except FeedbackError as exc:
        return _error(exc)
    return _admin_report(report, service, service.authors([report]))

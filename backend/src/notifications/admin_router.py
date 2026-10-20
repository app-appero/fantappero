"""Sezione "Notifiche" degli operatori: destinatari, avvisi, storico, prove (EP09-06)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.models.user import User
from auth.schemas import ApiModel
from authorization.dependencies import require_permissions
from database.enums import Permission
from notifications import broadcast_service
from notifications.broadcast_service import BroadcastError
from notifications.samples import SAMPLES
from notifications.service import NotificationService
from notifications.templates import render_notification

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


class LeagueRef(ApiModel):
    id: str
    name: str


class RecipientItem(ApiModel):
    user_id: str = Field(alias="userId")
    display_name: str = Field(alias="displayName")
    email: str
    leagues: list[LeagueRef]
    push_enabled: bool = Field(alias="pushEnabled")
    is_operator: bool = Field(alias="isOperator")


class RecipientCounts(ApiModel):
    all: int
    push: int
    no_push: int = Field(alias="noPush")
    operators: int


class RecipientList(ApiModel):
    items: list[RecipientItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    counts: RecipientCounts


class BroadcastChannels(ApiModel):
    in_app: bool = Field(default=True, alias="inApp")
    push: bool = False
    email: bool = False


class BroadcastAudience(ApiModel):
    mode: Literal["all", "leagues", "users"]
    league_ids: list[UUID] = Field(default_factory=list, alias="leagueIds")
    user_ids: list[UUID] = Field(default_factory=list, alias="userIds")
    exclude_user_ids: list[UUID] = Field(default_factory=list, alias="excludeUserIds")


class CreateBroadcastRequest(ApiModel):
    kind: Literal["test", "avviso", "novita", "manutenzione"]
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    category: Literal["sistema", "formazione", "mercato", "risultati"] = "sistema"
    deep_link: str | None = Field(default=None, max_length=200, alias="deepLink")
    channels: BroadcastChannels = Field(default_factory=BroadcastChannels)
    audience: BroadcastAudience
    scheduled_at: datetime | None = Field(default=None, alias="scheduledAt")


class BroadcastCreated(ApiModel):
    id: str
    status: Literal["sent", "scheduled"]
    recipient_count: int = Field(alias="recipientCount")
    push_count: int = Field(alias="pushCount")


class BroadcastHistoryItem(ApiModel):
    id: str
    kind: str
    title: str
    audience_label: str = Field(alias="audienceLabel")
    recipient_count: int = Field(alias="recipientCount")
    delivered_count: int = Field(alias="deliveredCount")
    read_count: int = Field(alias="readCount")
    status: Literal["sent", "scheduled", "test"]
    sent_at: str | None = Field(default=None, alias="sentAt")
    scheduled_at: str | None = Field(default=None, alias="scheduledAt")


class BroadcastHistory(ApiModel):
    items: list[BroadcastHistoryItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class SampleItem(ApiModel):
    key: str
    title: str
    body: str
    category: str


class SampleList(ApiModel):
    items: list[SampleItem]


class SendSamplesRequest(ApiModel):
    sample_keys: list[str] | None = Field(default=None, alias="sampleKeys")
    user_ids: list[UUID] | None = Field(default=None, alias="userIds")


class SendSamplesResult(ApiModel):
    created_count: int = Field(alias="createdCount")
    recipient_count: int = Field(alias="recipientCount")


def _error(exc: BroadcastError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": exc.message, "code": exc.code},
    )


@router.get("/recipients", response_model=RecipientList)
def list_recipients(
    search: str | None = Query(default=None),
    league_id: UUID | None = Query(default=None, alias="leagueId"),
    push_only: bool = Query(default=False, alias="pushOnly"),
    no_push: bool = Query(default=False, alias="noPush"),
    operators_only: bool = Query(default=False, alias="operatorsOnly"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> RecipientList:
    rows, total, counts = broadcast_service.list_recipients(
        session,
        search=search,
        league_id=league_id,
        push_only=push_only,
        no_push=no_push,
        operators_only=operators_only,
        page=page,
        page_size=page_size,
    )
    return RecipientList(
        items=[
            RecipientItem(
                userId=str(row.user.id),
                displayName=row.user.display_name,
                email=row.user.email,
                leagues=[LeagueRef(id=str(lid), name=name) for lid, name in row.leagues],
                pushEnabled=row.push_enabled,
                isOperator=row.user.platform_role.value == "operator",
            )
            for row in rows
        ],
        total=total,
        page=page,
        pageSize=page_size,
        counts=RecipientCounts(
            all=counts["all"],
            push=counts["withPush"],
            noPush=counts["withoutPush"],
            operators=counts["operators"],
        ),
    )


@router.post("/broadcasts", response_model=BroadcastCreated)
def create_broadcast(
    body: CreateBroadcastRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> BroadcastCreated | JSONResponse:
    try:
        broadcast = broadcast_service.create_broadcast(
            session,
            created_by=operator.id,
            kind=body.kind,
            title=body.title,
            body=body.body,
            category=body.category,
            deep_link=body.deep_link,
            channels=body.channels.model_dump(),
            audience=body.audience.model_dump(mode="json"),
            scheduled_at=body.scheduled_at,
        )
    except BroadcastError as exc:
        return _error(exc)
    return BroadcastCreated(
        id=str(broadcast.id),
        status="scheduled" if broadcast.status == "scheduled" else "sent",
        recipientCount=broadcast.recipient_count,
        pushCount=broadcast.push_count,
    )


@router.get("/broadcasts", response_model=BroadcastHistory)
def list_broadcasts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> BroadcastHistory:
    rows, total = broadcast_service.list_history(session, page=page, page_size=page_size)
    items = [
        BroadcastHistoryItem(
            id=str(row.id),
            kind=row.kind,
            title=row.title,
            audienceLabel=row.audience_label,
            recipientCount=row.recipient_count,
            deliveredCount=delivered,
            readCount=read,
            status="test" if row.kind == "test" else row.status,  # type: ignore[arg-type]
            sentAt=row.sent_at.isoformat() if row.sent_at else None,
            scheduledAt=row.scheduled_at.isoformat() if row.scheduled_at else None,
        )
        for row, delivered, read in rows
    ]
    return BroadcastHistory(items=items, total=total, page=page, pageSize=page_size)


@router.delete(
    "/broadcasts/{broadcast_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def cancel_broadcast(
    broadcast_id: UUID,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> Response:
    if not broadcast_service.cancel_scheduled(session, broadcast_id):
        return JSONResponse(  # type: ignore[return-value]
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "message": "Avviso programmato non trovato.",
                "code": "broadcast_not_found",
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/test-samples", response_model=SampleList)
def list_samples(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> SampleList:
    items = []
    for sample in SAMPLES:
        content = render_notification(sample.template_key, sample.template_version, sample.params)
        items.append(
            SampleItem(
                key=sample.key,
                title=content.title,
                body=content.body,
                category=sample.category.value,
            )
        )
    return SampleList(items=items)


@router.post("/test-samples", response_model=SendSamplesResult)
def send_samples(
    body: SendSamplesRequest | None = None,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> SendSamplesResult | JSONResponse:
    body = body or SendSamplesRequest()
    wanted = set(body.sample_keys) if body.sample_keys else None
    samples = [s for s in SAMPLES if wanted is None or s.key in wanted]
    if wanted is not None and len(samples) != len(wanted):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "Tipo di prova sconosciuto.", "code": "unknown_sample"},
        )
    user_ids = body.user_ids or [operator.id]
    service = NotificationService(session)
    batch = uuid4()
    created = 0
    for user_id in user_ids:
        for sample in samples:
            _, was_created = service.create_notification(
                user_id=user_id,
                category=sample.category,
                template_key=sample.template_key,
                template_version=sample.template_version,
                params=sample.params,
                dedup_key=f"test-sample:{batch}:{sample.key}",
            )
            created += 1 if was_created else 0
    return SendSamplesResult(createdCount=created, recipientCount=len(user_ids))

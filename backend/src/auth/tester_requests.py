"""Richieste di accesso al pilota di chi non è ancora tester.

Flusso: l'accesso con Google di un non tester, a modalità test accesa, non crea nessun account.
Google ha già verificato l'indirizzo; il backend rilascia un gettone firmato a scadenza breve con
cui la persona può inviare il modulo (nome, cognome, telefono, motivo facoltativo). Le richieste
vivono in una tabella a parte. L'operatore approva dal pannello: l'indirizzo entra nella lista dei
tester e al prossimo accesso con Google la persona entra normalmente.

Il numero di telefono serve solo per aggiungere la persona al gruppo WhatsApp dei tester.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from auth.models.tester_request import TesterAccessRequest
from auth.tester_access import TesterAccess, normalize_tester_email

REQUEST_TOKEN_TTL_MINUTES = 30
REJECTED_RETENTION_DAYS = 30
_TOKEN_TYPE = "tester_request"
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()./-]{5,28}$")

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


def make_request_token(*, secret: str, email: str, name: str | None) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "type": _TOKEN_TYPE,
            "email": normalize_tester_email(email),
            "name": (name or "")[:160],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=REQUEST_TOKEN_TTL_MINUTES)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


def read_request_token(*, secret: str, token: str) -> dict[str, str]:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValidationAuthError(
            "La sessione di accesso è scaduta: accedi di nuovo con Google e riprova.",
            code="tester_request_token_invalid",
        ) from exc
    if payload.get("type") != _TOKEN_TYPE or not payload.get("email"):
        raise ValidationAuthError(
            "La sessione di accesso non è valida: accedi di nuovo con Google.",
            code="tester_request_token_invalid",
        )
    return {"email": str(payload["email"]), "name": str(payload.get("name") or "")}


def _clean(value: str, *, field: str, max_len: int, required: bool = True) -> str:
    text = " ".join(value.split())
    if required and not text:
        raise ValidationAuthError(f"Il campo {field} è obbligatorio.", code="invalid_request_field")
    if len(text) > max_len:
        raise ValidationAuthError(
            f"Il campo {field} è troppo lungo (massimo {max_len} caratteri).",
            code="invalid_request_field",
        )
    return text


class TesterRequestService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- stato per chi prova ad accedere --------------------------------------------------
    def find(self, email: str) -> TesterAccessRequest | None:
        return self._session.scalar(
            select(TesterAccessRequest).where(
                TesterAccessRequest.email == normalize_tester_email(email)
            )
        )

    def status_for(self, email: str) -> TesterAccessRequest | None:
        self.purge_old_rejected()
        return self.find(email)

    # --- invio ----------------------------------------------------------------------------
    def submit(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        phone: str,
        motivation: str | None,
        consent: bool,
    ) -> TesterAccessRequest:
        if not consent:
            raise ValidationAuthError(
                "Serve il consenso al trattamento dei dati per inviare la richiesta.",
                code="consent_required",
            )
        access = TesterAccess(self._session)
        if not access.is_test_mode():
            raise ValidationAuthError(
                "L'accesso al pilota è aperto: non serve nessuna richiesta.",
                code="test_mode_off",
            )
        normalized = normalize_tester_email(email)
        if access.is_listed(normalized):
            raise ValidationAuthError(
                "Sei già tra i tester: accedi con Google.", code="already_tester"
            )
        first = _clean(first_name, field="nome", max_len=80)
        last = _clean(last_name, field="cognome", max_len=80)
        phone_clean = _clean(phone, field="numero di telefono", max_len=30)
        if not _PHONE_RE.match(phone_clean):
            raise ValidationAuthError(
                "Il numero di telefono non sembra valido: usa cifre, spazi o il prefisso +39.",
                code="invalid_request_field",
            )
        note = _clean(motivation or "", field="motivazione", max_len=1000, required=False)

        self.purge_old_rejected()
        existing = self.find(normalized)
        if existing is not None:
            if existing.status == STATUS_REJECTED:
                raise ValidationAuthError(
                    "La tua richiesta è già stata valutata: riprova più avanti.",
                    code="tester_request_rejected",
                )
            if existing.status == STATUS_PENDING:
                raise ValidationAuthError(
                    "Hai già inviato una richiesta: è in valutazione.",
                    code="tester_request_pending",
                )
        now = datetime.now(UTC)
        entry = TesterAccessRequest(
            email=normalized,
            first_name=first,
            last_name=last,
            phone=phone_clean,
            motivation=note or None,
            status=STATUS_PENDING,
            consent_at=now,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    # --- pannello operatore ----------------------------------------------------------------
    def list_requests(self, status: str | None = None) -> list[TesterAccessRequest]:
        self.purge_old_rejected()
        stmt = select(TesterAccessRequest).order_by(TesterAccessRequest.created_at.desc())
        if status:
            stmt = stmt.where(TesterAccessRequest.status == status)
        return list(self._session.scalars(stmt).all())

    def _get(self, request_id: UUID) -> TesterAccessRequest:
        entry = self._session.get(TesterAccessRequest, request_id)
        if entry is None:
            raise ValidationAuthError("Richiesta non trovata.", code="tester_request_not_found")
        return entry

    def approve(self, request_id: UUID, *, actor_id: UUID) -> TesterAccessRequest:
        entry = self._get(request_id)
        TesterAccess(self._session).add(entry.email, actor_id=actor_id)
        entry.status = STATUS_APPROVED
        entry.decided_at = datetime.now(UTC)
        entry.decided_by_user_id = actor_id
        self._session.flush()
        return entry

    def reject(self, request_id: UUID, *, actor_id: UUID, note: str | None) -> TesterAccessRequest:
        entry = self._get(request_id)
        entry.status = STATUS_REJECTED
        entry.decided_at = datetime.now(UTC)
        entry.decided_by_user_id = actor_id
        entry.decision_note = _clean(note or "", field="nota", max_len=500, required=False) or None
        self._session.flush()
        return entry

    def purge_old_rejected(self, *, now: datetime | None = None) -> int:
        """Le richieste rifiutate si cancellano dopo 30 giorni (poi si può richiedere ancora)."""
        limit = (now or datetime.now(UTC)) - timedelta(days=REJECTED_RETENTION_DAYS)
        result = self._session.execute(
            delete(TesterAccessRequest).where(
                TesterAccessRequest.status == STATUS_REJECTED,
                TesterAccessRequest.decided_at.is_not(None),
                TesterAccessRequest.decided_at < limit,
            )
        )
        return int(result.rowcount or 0)

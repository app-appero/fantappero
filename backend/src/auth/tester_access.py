"""Modalità test del pilota: solo i tester (e gli operatori) possono accedere.

L'interruttore sta in `system_flags` (chiave ``test_mode``), così si cambia dal pannello senza
riavvii. La lista dei tester è per indirizzo email, anche prima del primo accesso: chi non è in
lista non crea nessun account.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from auth.exceptions import TesterOnlyError, ValidationAuthError
from auth.models.tester_allowlist import TesterAllowlistEntry
from auth.validators import validate_email
from database.enums import FlagScope, PlatformRole
from database.models.infrastructure import SystemFlag

TEST_MODE_FLAG_KEY = "test_mode"


def normalize_tester_email(email: str) -> str:
    return email.strip().lower()


class TesterAccess:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- interruttore -----------------------------------------------------------------------
    def is_test_mode(self) -> bool:
        value = self._session.scalar(
            select(SystemFlag.value).where(SystemFlag.key == TEST_MODE_FLAG_KEY)
        )
        return (value or "").strip().lower() == "true"

    def set_test_mode(self, enabled: bool) -> None:
        flag = self._session.scalar(select(SystemFlag).where(SystemFlag.key == TEST_MODE_FLAG_KEY))
        text = "true" if enabled else "false"
        if flag is None:
            self._session.add(
                SystemFlag(key=TEST_MODE_FLAG_KEY, value=text, scope=FlagScope.SYSTEM)
            )
        else:
            flag.value = text
        self._session.flush()

    # --- lista --------------------------------------------------------------------------------
    def is_listed(self, email: str) -> bool:
        return (
            self._session.scalar(
                select(TesterAllowlistEntry.id).where(
                    TesterAllowlistEntry.email == normalize_tester_email(email)
                )
            )
            is not None
        )

    def list_entries(self) -> list[TesterAllowlistEntry]:
        return list(
            self._session.scalars(
                select(TesterAllowlistEntry).order_by(TesterAllowlistEntry.email.asc())
            ).all()
        )

    def listed_emails(self) -> set[str]:
        return set(self._session.scalars(select(TesterAllowlistEntry.email)).all())

    def add(self, email: str, *, actor_id: UUID | None) -> TesterAllowlistEntry:
        normalized = normalize_tester_email(validate_email(email))
        existing = self._session.scalar(
            select(TesterAllowlistEntry).where(TesterAllowlistEntry.email == normalized)
        )
        if existing is not None:
            return existing
        entry = TesterAllowlistEntry(email=normalized, created_by_user_id=actor_id)
        self._session.add(entry)
        self._session.flush()
        return entry

    def remove(self, entry_id: UUID) -> None:
        entry = self._session.get(TesterAllowlistEntry, entry_id)
        if entry is None:
            raise ValidationAuthError("Tester non trovato.", code="tester_not_found")
        self.remove_email(entry.email)

    def remove_email(self, email: str) -> None:
        """Toglie un indirizzo dai tester e cancella le sue richieste di accesso.

        Serve quando un tester viene tolto dalla lista o l'account viene eliminato: senza questo
        l'indirizzo resterebbe abilitato e chi si registra di nuovo entrerebbe come tester.
        """
        from auth.models.tester_request import TesterAccessRequest

        normalized = normalize_tester_email(email)
        self._session.execute(
            delete(TesterAllowlistEntry).where(TesterAllowlistEntry.email == normalized)
        )
        self._session.execute(
            delete(TesterAccessRequest).where(TesterAccessRequest.email == normalized)
        )
        self._session.flush()

    # --- controllo all'accesso ----------------------------------------------------------------
    def assert_allowed(self, *, email: str, platform_role: PlatformRole | None) -> None:
        """Solleva `TesterOnlyError` se la modalità test è attiva e l'account non è autorizzato.

        Gli operatori sono sempre autorizzati (tester di default).
        """
        if not self.is_test_mode():
            return
        if platform_role == PlatformRole.OPERATOR:
            return
        if self.is_listed(email):
            return
        raise TesterOnlyError()

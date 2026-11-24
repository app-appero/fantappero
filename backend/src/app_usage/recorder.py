"""Registra quale app usa chi, dalle richieste autenticate (release 1.4, Rosario 23/11).

Cosa si ricava da una richiesta già autenticata (``auth.dependencies.get_current_user``):

- intestazioni ``X-App-Version-Code`` (e ``X-App-Version``, ``X-App-Platform``), che l'app
  manda dalla 1.4 in ogni richiesta: la versione esatta;
- ``GET /app/version`` senza intestazioni: lo chiamano solo le app dalla 1.2, quindi «app 1.2 o
  1.3, versione non nota»;
- qualsiasi altra richiesta con User-Agent ``okhttp/`` (React Native su Android) e senza
  intestazioni: «app, versione non nota» (in pratica la 1.1 o precedenti);
- il sito da un telefono Android (User-Agent di un browser con ``Android``): una riga a parte,
  piattaforma ``web-android``, perché anche loro ricevono la notifica di una nuova versione
  dell'app (Rosario 23/11); il sito da computer o da iPhone non conta.

Una fonte meno precisa non cancella mai una più precisa (``SOURCE_RANK``). Le richieste fatte
impersonando un utente non contano: sarebbe il telefono dell'operatore.

Per non scrivere nel database a ogni richiesta, ogni processo scrive al più una volta ogni
``RECORD_INTERVAL`` per utente e piattaforma, subito solo se si sa qualcosa di nuovo (versione
cambiata o fonte più precisa). La scrittura avviene dopo la risposta, in una sessione a parte:
non rallenta e non fa mai fallire la richiesta.

Rosario 24/11: dopo ogni scrittura su Android (app o sito da Android) si controlla anche se
l'utente deve ancora ricevere la notifica della versione annunciata
(``app_usage.service.notify_app_version_on_sighting``): così la riceve anche chi compare dopo
l'annuncio, una sola volta per versionCode. Un guasto lì non toglie la riga scritta.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app_usage.models import (
    ANDROID_NOTIFY_PLATFORMS,
    APP_PLATFORMS,
    PLATFORM_ANDROID,
    PLATFORM_WEB_ANDROID,
    SOURCE_BROWSER,
    SOURCE_HEADER,
    SOURCE_RANK,
    SOURCE_USER_AGENT,
    SOURCE_VERSION_CHECK,
    UserAppUsage,
)
from auth.models.user import User
from observability.logging import get_logger

APP_VERSION_HEADER = "x-app-version"
APP_VERSION_CODE_HEADER = "x-app-version-code"
APP_PLATFORM_HEADER = "x-app-platform"
#: Al più una scrittura ogni 5 minuti per utente e piattaforma (per processo).
RECORD_INTERVAL = timedelta(minutes=5)
#: Oltre questo numero di utenti in memoria si ricomincia da capo (al più una scrittura in più).
_MAX_TRACKED = 20_000
#: Come il server per la versione annunciata (``ANDROID_MAX_VERSION_CODE``).
_MAX_VERSION_CODE = 2_100_000_000
_VERSION_NAME = re.compile(r"^[0-9]+(\.[0-9]+){0,3}$")
_VERSION_PATH = "/app/version"

_logger = get_logger(__name__)


@dataclass(frozen=True)
class AppObservation:
    """Quello che una richiesta dice dell'app che l'ha fatta."""

    platform: str
    source: str
    version_name: str | None = None
    version_code: int | None = None

    @property
    def rank(self) -> int:
        return SOURCE_RANK[self.source]


def _version_code(raw: str | None) -> int | None:
    value = (raw or "").strip()
    if not value.isdigit() or len(value) > 10:
        return None
    code = int(value)
    return code if 1 <= code <= _MAX_VERSION_CODE else None


def _version_name(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value if len(value) <= 32 and _VERSION_NAME.match(value) else None


def _is_browser(user_agent: str) -> bool:
    return user_agent.startswith("Mozilla/")


def _is_android(user_agent: str) -> bool:
    return "android" in user_agent.lower()


def observe(headers: Mapping[str, str], *, method: str, path: str) -> AppObservation | None:
    """Cosa sa la richiesta dell'app (o del sito da Android); ``None`` se non conta."""
    code = _version_code(headers.get(APP_VERSION_CODE_HEADER))
    if code is not None:
        platform = (headers.get(APP_PLATFORM_HEADER) or "").strip().lower()
        return AppObservation(
            platform=platform if platform in APP_PLATFORMS else PLATFORM_ANDROID,
            source=SOURCE_HEADER,
            version_name=_version_name(headers.get(APP_VERSION_HEADER)),
            version_code=code,
        )
    user_agent = (headers.get("user-agent") or "").strip()
    if _is_browser(user_agent):
        # Il sito: conta solo da un telefono Android (per la notifica della nuova versione).
        if _is_android(user_agent):
            return AppObservation(platform=PLATFORM_WEB_ANDROID, source=SOURCE_BROWSER)
        return None
    if method.upper() == "GET" and path.rstrip("/").endswith(_VERSION_PATH):
        return AppObservation(platform=PLATFORM_ANDROID, source=SOURCE_VERSION_CHECK)
    if user_agent.lower().startswith("okhttp/"):
        return AppObservation(platform=PLATFORM_ANDROID, source=SOURCE_USER_AGENT)
    return None


@dataclass(frozen=True)
class _Known:
    written_at: datetime
    rank: int
    version_code: int | None
    version_name: str | None


class _Throttle:
    """Ultima scrittura per (utente, piattaforma) in questo processo."""

    def __init__(self) -> None:
        self._known: dict[tuple[UUID, str], _Known] = {}
        self._lock = threading.Lock()

    def should_write(self, user_id: UUID, observation: AppObservation, now: datetime) -> bool:
        key = (user_id, observation.platform)
        with self._lock:
            known = self._known.get(key)
            news = known is None or _is_news(known, observation)
            if not news and known is not None and now - known.written_at < RECORD_INTERVAL:
                return False
            if len(self._known) >= _MAX_TRACKED:
                self._known.clear()
            self._known[key] = _merge(known, observation, now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._known.clear()


def _is_news(known: _Known, observation: AppObservation) -> bool:
    if observation.source == SOURCE_HEADER:
        return (observation.version_code, observation.version_name) != (
            known.version_code,
            known.version_name,
        )
    return observation.rank > known.rank


def _merge(known: _Known | None, observation: AppObservation, now: datetime) -> _Known:
    if known is None or observation.rank >= known.rank:
        return _Known(now, observation.rank, observation.version_code, observation.version_name)
    return _Known(now, known.rank, known.version_code, known.version_name)


_throttle = _Throttle()


def reset_app_usage_throttle() -> None:
    """Dimentica le scritture recenti (per i test)."""
    _throttle.clear()


def should_record(user_id: UUID, observation: AppObservation, *, now: datetime) -> bool:
    return _throttle.should_write(user_id, observation, now)


def write_observation(
    session: Session, user_id: UUID, observation: AppObservation, *, now: datetime
) -> UserAppUsage | None:
    """Aggiorna (o crea) la riga dell'utente; non fa commit.

    Si scrive dopo la risposta: se intanto l'account è stato eliminato (es. la richiesta era
    proprio l'eliminazione) non si scrive nulla.
    """
    alive = session.scalar(select(User.id).where(User.id == user_id, User.deleted_at.is_(None)))
    if alive is None:
        return None
    session.execute(
        pg_insert(UserAppUsage)
        .values(
            user_id=user_id,
            platform=observation.platform,
            source=observation.source,
            version_name=observation.version_name,
            version_code=observation.version_code,
            first_seen_at=now,
            last_seen_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "platform"])
    )
    row = session.scalar(
        select(UserAppUsage)
        .where(
            UserAppUsage.user_id == user_id,
            UserAppUsage.platform == observation.platform,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:  # pragma: no cover - riga appena inserita o già presente
        msg = "user_app_usage row missing after upsert"
        raise RuntimeError(msg)
    if row.last_seen_at < now:
        row.last_seen_at = now
    if row.first_seen_at > now:
        row.first_seen_at = now
    if observation.source == SOURCE_HEADER:
        # La versione esatta vale sempre, anche più vecchia (app reinstallata).
        row.source = SOURCE_HEADER
        row.version_code = observation.version_code
        row.version_name = observation.version_name
    elif observation.rank > SOURCE_RANK.get(row.source, 0):
        row.source = observation.source
    session.flush()
    return row


def record_app_usage(
    session_factory: Callable[[], Session],
    user_id: UUID,
    observation: AppObservation,
    *,
    now: datetime | None = None,
) -> None:
    """Scrive in una sessione a parte. Non solleva mai: un errore si scrive solo nel log."""
    try:
        session = session_factory()
        try:
            row = write_observation(session, user_id, observation, now=now or datetime.now(UTC))
            session.commit()
            # Dopo il commit: un guasto nella notifica non toglie la riga appena scritta.
            if row is not None and observation.platform in ANDROID_NOTIFY_PLATFORMS:
                _notify_announced_version(session, user_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception:
        _logger.warning(
            "app_usage_record_failed",
            extra={"user_id": str(user_id), "source": observation.source},
            exc_info=True,
        )


def _notify_announced_version(session: Session, user_id: UUID) -> None:
    """La notifica della versione annunciata, se l'utente non l'ha ancora (Rosario 24/11).

    Non solleva mai: un errore si scrive solo nel log.
    """
    try:
        from app_usage.service import notify_app_version_on_sighting

        notify_app_version_on_sighting(session, user_id)
        session.commit()
    except Exception:
        session.rollback()
        _logger.warning(
            "app_usage_version_notify_failed", extra={"user_id": str(user_id)}, exc_info=True
        )

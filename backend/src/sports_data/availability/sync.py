"""Idempotent sync of player availability from ``/injuries`` (OQ-11).

Consuma ``ProviderEnvelope`` già scaricati (separazione I/O testabile, stesso
pattern di ``sports_data.roster.sync``). **Non genera mai una conclusione di
disponibilità**: scrive solo presenza confermata di indisponibilità. Un
atleta senza righe in questa tabella resta "sconosciuto", non "disponibile"
— verificato con un caso reale in cui il provider non segnalava un giocatore
davvero infortunato (vedi ``docs/data/api_football_open_questions.md``,
OQ-11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.availability.classify import classify_availability_reason
from sports_data.availability.models import PlayerAvailability
from sports_data.catalog.models import Club
from sports_data.fixtures.models import Fixture
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.provider.types import MappedPlayerAvailability, ProviderEnvelope
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

AVAILABILITY_SYNC_ENTITIES_TOTAL = "availability_sync_entities_total"


@dataclass
class AvailabilitySyncCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def _resolve_athlete(session: Session, provider_id: int) -> Athlete | None:
    return session.execute(
        select(Athlete).where(Athlete.provider_id == provider_id),
    ).scalar_one_or_none()


def _resolve_club(session: Session, provider_id: int | None) -> Club | None:
    if provider_id is None:
        return None
    return session.execute(
        select(Club).where(Club.provider_id == provider_id),
    ).scalar_one_or_none()


def _resolve_fixture(session: Session, provider_id: int | None) -> Fixture | None:
    if provider_id is None:
        return None
    return session.execute(
        select(Fixture).where(Fixture.provider_id == provider_id),
    ).scalar_one_or_none()


def upsert_player_availability(
    session: Session,
    mapped: MappedPlayerAvailability,
    counters: AvailabilitySyncCounters,
    *,
    synced_at: datetime | None = None,
) -> PlayerAvailability:
    """Crea o aggiorna una riga per ``provider_key`` (atleta+fixture+lega+stagione)."""
    now = synced_at or datetime.now(UTC)
    category = classify_availability_reason(mapped.reason_raw).value

    existing = session.execute(
        select(PlayerAvailability).where(
            PlayerAvailability.provider_key == mapped.provider_key,
        ),
    ).scalar_one_or_none()

    athlete = _resolve_athlete(session, mapped.athlete_provider_id)
    club = _resolve_club(session, mapped.club_provider_id)
    fixture = _resolve_fixture(session, mapped.fixture_provider_id)

    if existing is not None:
        changed = (
            existing.status_type_raw != mapped.status_type_raw
            or existing.reason_raw != mapped.reason_raw
            or existing.category != category
        )
        existing.status_type_raw = mapped.status_type_raw
        existing.reason_raw = mapped.reason_raw
        existing.category = category
        existing.athlete_id = athlete.id if athlete else existing.athlete_id
        existing.club_id = club.id if club else existing.club_id
        existing.fixture_id = fixture.id if fixture else existing.fixture_id
        existing.synced_at = now
        counters.updated += 1 if changed else 0
        counters.unchanged += 0 if changed else 1
        get_metrics().incr(
            AVAILABILITY_SYNC_ENTITIES_TOTAL,
            labels={
                "provider": PROVIDER_NAME,
                "result": "updated" if changed else "unchanged",
            },
        )
        return existing

    row = PlayerAvailability(
        athlete_id=athlete.id if athlete else None,
        athlete_provider_id=mapped.athlete_provider_id,
        club_id=club.id if club else None,
        club_provider_id=mapped.club_provider_id,
        fixture_id=fixture.id if fixture else None,
        fixture_provider_id=mapped.fixture_provider_id,
        competition_provider_id=mapped.competition_provider_id,
        season_year=mapped.season_year,
        status_type_raw=mapped.status_type_raw,
        reason_raw=mapped.reason_raw,
        category=category,
        provider_key=mapped.provider_key,
        synced_at=now,
    )
    session.add(row)
    session.flush()
    counters.created += 1
    get_metrics().incr(
        AVAILABILITY_SYNC_ENTITIES_TOTAL,
        labels={"provider": PROVIDER_NAME, "result": "created"},
    )
    return row


def sync_player_availabilities(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    competition_provider_id: int,
    season_year: int,
    counters: AvailabilitySyncCounters | None = None,
) -> AvailabilitySyncCounters:
    """Upsert di tutte le righe ``/injuries`` di un envelope già scaricato."""
    from sports_data.provider.mapping import map_player_availabilities

    result = counters or AvailabilitySyncCounters()
    mapped_rows = map_player_availabilities(
        envelope,
        competition_provider_id=competition_provider_id,
        season_year=season_year,
    )
    for mapped in mapped_rows:
        upsert_player_availability(session, mapped, result)

    logger.info(
        "availability_synced",
        extra={
            "provider": PROVIDER_NAME,
            "competition_provider_id": competition_provider_id,
            "season_year": season_year,
            "created": result.created,
            "updated": result.updated,
            "unchanged": result.unchanged,
        },
    )
    return result


def is_confirmed_unavailable(
    session: Session,
    *,
    athlete_provider_id: int,
    competition_provider_id: int,
    season_year: int,
) -> PlayerAvailability | None:
    """Ritorna l'ultima riga nota, se esiste. ``None`` significa "sconosciuto".

    Non usare il valore ``None`` di ritorno come prova di disponibilità: è
    solo assenza di un segnale positivo (vedi docstring del modulo).
    """
    return session.execute(
        select(PlayerAvailability)
        .where(
            PlayerAvailability.athlete_provider_id == athlete_provider_id,
            PlayerAvailability.competition_provider_id == competition_provider_id,
            PlayerAvailability.season_year == season_year,
        )
        .order_by(PlayerAvailability.synced_at.desc())
        .limit(1),
    ).scalar_one_or_none()

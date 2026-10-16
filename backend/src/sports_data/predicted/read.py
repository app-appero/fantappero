"""Lettura degli snapshot per il dettaglio partita e per la formazione fantasy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sports_data.predicted.models import PredictedLineupPlayer, PredictedLineupSnapshot
from sports_data.predicted.validate import (
    RELIABILITY_PARTIAL,
    RELIABILITY_VALIDATED,
    USABLE_RELIABILITY,
)


@dataclass(frozen=True)
class PredictedViewPlayer:
    athlete_id: str | None
    name: str
    shirt_number: int | None
    grid: str | None


@dataclass(frozen=True)
class PredictedViewSide:
    formation: str | None
    coach_name: str | None
    note: str
    starters: tuple[PredictedViewPlayer, ...]
    bench: tuple[PredictedViewPlayer, ...]


@dataclass(frozen=True)
class PredictedUnavailable:
    athlete_id: str | None
    name: str
    side: str
    kind: str | None
    label: str | None
    blocks_selection: bool


@dataclass(frozen=True)
class PredictedView:
    home: PredictedViewSide | None
    away: PredictedViewSide | None
    unavailable: tuple[PredictedUnavailable, ...]


@dataclass(frozen=True)
class AthleteProbable:
    hint: Literal["starter", "bench", "unavailable"]
    note: str
    blocked: bool


def latest_predicted_view(session: Session, fixture_id: UUID) -> PredictedView | None:
    snapshot = session.scalars(
        select(PredictedLineupSnapshot)
        .where(
            PredictedLineupSnapshot.fixture_id == fixture_id,
            PredictedLineupSnapshot.reliability != "rejected",
        )
        .options(selectinload(PredictedLineupSnapshot.players))
        .order_by(PredictedLineupSnapshot.fetched_at.desc())
        .limit(1)
    ).first()
    if snapshot is None:
        return None
    note = _note(snapshot.lineup_type, snapshot.reliability)
    return PredictedView(
        home=_side(snapshot, "home", snapshot.home_formation, snapshot.home_coach, note),
        away=_side(snapshot, "away", snapshot.away_formation, snapshot.away_coach, note),
        unavailable=tuple(
            PredictedUnavailable(
                athlete_id=None if player.athlete_id is None else str(player.athlete_id),
                name=player.display_name,
                side=player.side,
                kind=player.unavailability_type,
                label=player.unavailability_label,
                blocks_selection=player.blocks_selection,
            )
            for player in sorted(snapshot.players, key=lambda row: (row.side, row.sort_order))
            if player.is_unavailable
        ),
    )


def hints_for_fixtures(
    session: Session,
    fixture_ids: list[UUID],
    athlete_ids: list[UUID],
) -> dict[UUID, AthleteProbable]:
    """Indizi solo da snapshot validati o parziali, e solo se il giocatore è in rosa."""
    if not fixture_ids or not athlete_ids:
        return {}
    snapshots = session.scalars(
        select(PredictedLineupSnapshot)
        .where(
            PredictedLineupSnapshot.fixture_id.in_(fixture_ids),
            PredictedLineupSnapshot.reliability.in_(tuple(USABLE_RELIABILITY)),
        )
        .options(selectinload(PredictedLineupSnapshot.players))
        .order_by(PredictedLineupSnapshot.fetched_at.desc())
    ).all()
    latest: dict[UUID, PredictedLineupSnapshot] = {}
    for snapshot in snapshots:
        latest.setdefault(snapshot.fixture_id, snapshot)
    wanted = set(athlete_ids)
    found: dict[UUID, AthleteProbable] = {}
    for snapshot in latest.values():
        for player in snapshot.players:
            if player.athlete_id is None or player.athlete_id not in wanted:
                continue
            hint = _hint_for(player)
            if hint is None:
                continue
            current = found.get(player.athlete_id)
            if current is None or _hint_rank(hint.hint) > _hint_rank(current.hint):
                found[player.athlete_id] = hint
    return found


def _side(
    snapshot: PredictedLineupSnapshot,
    side: str,
    formation: str | None,
    coach: str | None,
    note: str,
) -> PredictedViewSide | None:
    rows = [
        player
        for player in snapshot.players
        if player.side == side and not player.is_unavailable
    ]
    if not rows and not formation:
        return None
    ordered = sorted(rows, key=lambda player: player.sort_order)

    def view(player: PredictedLineupPlayer) -> PredictedViewPlayer:
        return PredictedViewPlayer(
            athlete_id=None if player.athlete_id is None else str(player.athlete_id),
            name=player.display_name,
            shirt_number=player.shirt_number,
            grid=player.grid,
        )

    starters = tuple(view(player) for player in ordered if player.is_starter)
    bench = tuple(view(player) for player in ordered if not player.is_starter)
    if not starters and not bench:
        return None
    return PredictedViewSide(
        formation=formation,
        coach_name=coach,
        note=note,
        starters=starters,
        bench=bench,
    )


def _hint_for(player: PredictedLineupPlayer) -> AthleteProbable | None:
    if player.is_unavailable:
        label = player.unavailability_label or _absence_label(player.unavailability_type)
        return AthleteProbable(
            hint="unavailable",
            note=label,
            blocked=player.blocks_selection,
        )
    if player.is_starter:
        return AthleteProbable(hint="starter", note="Titolare probabile", blocked=False)
    return AthleteProbable(hint="bench", note="Possibile panchina", blocked=False)


def _hint_rank(hint: str) -> int:
    if hint == "unavailable":
        return 3
    if hint == "starter":
        return 2
    return 1


def _absence_label(kind: str | None) -> str:
    normalized = (kind or "").lower()
    if normalized in {"suspension", "suspended"}:
        return "Squalificato"
    if normalized in {"red", "red_card", "redcard"}:
        return "Espulso"
    if normalized == "injury":
        return "Infortunato"
    return "Indisponibile"


def _note(lineup_type: str, reliability: str) -> str:
    if lineup_type == "confirmed":
        prefix = "Formazione confermata dal provider"
    else:
        prefix = "Formazione probabile"
    if reliability == RELIABILITY_VALIDATED:
        return prefix
    if reliability == RELIABILITY_PARTIAL:
        return f"{prefix} · verifica parziale sulla rosa"
    return f"{prefix} · non verificata sulla rosa, non usata in formazione"

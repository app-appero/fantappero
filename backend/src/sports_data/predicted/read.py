"""Lettura degli snapshot per il dettaglio partita e per la formazione fantasy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fantasy_turns.models import FantasyRoundFixture
from fantasy_turns.rules import STARTED_FIXTURE_STATUSES
from sports_data.catalog.models import Club
from sports_data.fixtures.models import Fixture
from sports_data.listone.mapping import map_provider_position_to_role
from sports_data.predicted.models import PredictedLineupPlayer, PredictedLineupSnapshot
from sports_data.predicted.names import normalize_person
from sports_data.predicted.validate import (
    RELIABILITY_PARTIAL,
    RELIABILITY_VALIDATED,
    USABLE_RELIABILITY,
)
from sports_data.roster.models import Athlete, SquadMembership


@dataclass(frozen=True)
class PredictedViewPlayer:
    athlete_id: str | None
    name: str
    shirt_number: int | None
    grid: str | None
    #: Ruolo fantacalcistico (P/D/C/A), derivato dalla rosa reale quando
    #: l'atleta è stato abbinato. ``None`` se non abbinato o senza posizione
    #: nota dal provider.
    role: str | None = None
    #: Posizione nell'ordine di probabilità in panchina (1 = primo cambio).
    #: ``None`` per i titolari.
    bench_order: int | None = None


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
    #: Solo per ``unavailable``: ``suspended`` = espulso/squalificato, ``injured``, ``other``.
    absence: Literal["suspended", "injured", "other"] | None = None


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
    fixture = session.get(Fixture, fixture_id)
    note = _note(snapshot.lineup_type, snapshot.reliability)
    roles = _athlete_roles(
        session, {player.athlete_id for player in snapshot.players if player.athlete_id is not None}
    )
    return PredictedView(
        home=_side(
            session,
            snapshot,
            "home",
            snapshot.home_formation,
            snapshot.home_coach,
            note,
            roles,
            fixture=fixture,
            club_id=fixture.home_club_id if fixture is not None else None,
        ),
        away=_side(
            session,
            snapshot,
            "away",
            snapshot.away_formation,
            snapshot.away_coach,
            note,
            roles,
            fixture=fixture,
            club_id=fixture.away_club_id if fixture is not None else None,
        ),
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
    fixtures_by_id = {
        fixture.id: fixture
        for fixture in session.scalars(select(Fixture).where(Fixture.id.in_(latest.keys()))).all()
    }
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
        fixture = fixtures_by_id.get(snapshot.fixture_id)
        for side, club_id in (
            ("home", fixture.home_club_id if fixture is not None else None),
            ("away", fixture.away_club_id if fixture is not None else None),
        ):
            has_explicit_bench = any(
                row.side == side and not row.is_starter and not row.is_unavailable
                for row in snapshot.players
            )
            if has_explicit_bench:
                continue
            known_ids = {
                row.athlete_id
                for row in snapshot.players
                if row.side == side and row.athlete_id is not None
            }
            inferred_ids = _inferred_bench_ids(
                session,
                fixture=fixture,
                lineup_type=snapshot.lineup_type,
                club_id=club_id,
                known_ids=known_ids,
            )
            for athlete_id in inferred_ids & wanted:
                found.setdefault(
                    athlete_id,
                    AthleteProbable(hint="bench", note="Possibile panchina (dedotta)", blocked=False),
                )
    return found


def _inferred_bench_ids(
    session: Session,
    *,
    fixture: Fixture | None,
    lineup_type: str,
    club_id: UUID | None,
    known_ids: set[UUID],
) -> set[UUID]:
    """Panchina dedotta quando il provider non la pubblica (EP-panchina-dedotta).

    FotMob a volte restituisce solo titolari e indisponibili, senza panchina.
    In quel caso chi è in rosa reale (``SquadMembership`` attiva) e non
    rientra in nessuno dei due gruppi è *probabilmente* panchina. Vale solo
    finché la formazione non è ufficiale (``lineup_type == "predicted"``) e
    la partita non è iniziata — da lì in poi il provider pubblica sempre la
    panchina vera, quindi l'inferenza non serve più.
    """
    if lineup_type != "predicted" or fixture is None or club_id is None:
        return set()
    if (fixture.status_short or "").strip().upper() in STARTED_FIXTURE_STATUSES:
        return set()
    squad_ids = set(
        session.scalars(
            select(SquadMembership.athlete_id).where(
                SquadMembership.club_id == club_id,
                SquadMembership.sport_season_id == fixture.sport_season_id,
                SquadMembership.is_active.is_(True),
            )
        ).all()
    )
    return squad_ids - known_ids


def _side(
    session: Session,
    snapshot: PredictedLineupSnapshot,
    side: str,
    formation: str | None,
    coach: str | None,
    note: str,
    roles: dict[UUID, str],
    *,
    fixture: Fixture | None,
    club_id: UUID | None,
) -> PredictedViewSide | None:
    rows = [
        player
        for player in snapshot.players
        if player.side == side and not player.is_unavailable
    ]
    if not rows and not formation:
        return None
    ordered = sorted(rows, key=lambda player: player.sort_order)

    def view(player: PredictedLineupPlayer, *, bench_order: int | None) -> PredictedViewPlayer:
        return PredictedViewPlayer(
            athlete_id=None if player.athlete_id is None else str(player.athlete_id),
            name=player.display_name,
            shirt_number=player.shirt_number,
            grid=player.grid,
            role=None if player.athlete_id is None else roles.get(player.athlete_id),
            bench_order=bench_order,
        )

    starters = tuple(view(player, bench_order=None) for player in ordered if player.is_starter)
    # L'ordine di panchina è relativo alla panchina stessa (1 = primo cambio
    # probabile), non il ``sort_order`` grezzo che conta anche i titolari.
    bench = tuple(
        view(player, bench_order=index)
        for index, player in enumerate(
            (player for player in ordered if not player.is_starter), start=1
        )
    )
    if not bench:
        known_ids = {
            player.athlete_id
            for player in snapshot.players
            if player.side == side and player.athlete_id is not None
        }
        inferred_ids = _inferred_bench_ids(
            session,
            fixture=fixture,
            lineup_type=snapshot.lineup_type,
            club_id=club_id,
            known_ids=known_ids,
        )
        if inferred_ids:
            inferred_roles = _athlete_roles(session, inferred_ids)
            names = dict(
                session.execute(
                    select(Athlete.id, Athlete.canonical_name).where(
                        Athlete.id.in_(inferred_ids)
                    )
                ).all()
            )
            inferred_players = sorted(
                ((athlete_id, name) for athlete_id, name in names.items() if name),
                key=lambda item: item[1],
            )
            bench = tuple(
                PredictedViewPlayer(
                    athlete_id=str(athlete_id),
                    name=name,
                    shirt_number=None,
                    grid=None,
                    role=inferred_roles.get(athlete_id),
                    bench_order=index,
                )
                for index, (athlete_id, name) in enumerate(inferred_players, start=1)
            )
    if not starters and not bench:
        return None
    return PredictedViewSide(
        formation=formation,
        coach_name=coach,
        note=note,
        starters=starters,
        bench=bench,
    )


def _athlete_roles(session: Session, athlete_ids: set[UUID]) -> dict[UUID, str]:
    """Ruolo fantacalcistico (P/D/C/A) per gli atleti abbinati in questo snapshot.

    Deriva dalla posizione grezza del provider in rosa (``SquadMembership``),
    la stessa fonte già usata per il listone: non inventiamo un ruolo che il
    provider delle formazioni probabili non fornisce.
    """
    if not athlete_ids:
        return {}
    rows = session.execute(
        select(SquadMembership.athlete_id, SquadMembership.provider_position_raw).where(
            SquadMembership.athlete_id.in_(athlete_ids),
            SquadMembership.is_active.is_(True),
        )
    ).all()
    roles: dict[UUID, str] = {}
    for athlete_id, position_raw in rows:
        if athlete_id in roles:
            continue
        role = map_provider_position_to_role(position_raw)
        if role is not None:
            roles[athlete_id] = role.value
    return roles


def _hint_for(player: PredictedLineupPlayer) -> AthleteProbable | None:
    if player.is_unavailable:
        label = player.unavailability_label or _absence_label(player.unavailability_type)
        return AthleteProbable(
            hint="unavailable",
            note=label,
            blocked=player.blocks_selection,
            absence=_absence_category(player.unavailability_type, label),
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


def _absence_category(
    kind: str | None, label: str | None
) -> Literal["suspended", "injured", "other"]:
    normalized = (kind or "").strip().lower()
    if normalized in {"suspension", "suspended", "red", "red_card", "redcard"}:
        return "suspended"
    if normalized == "injury":
        return "injured"
    text = (label or "").lower()
    if "espuls" in text or "squalific" in text or "red card" in text or "suspen" in text:
        return "suspended"
    return "other"


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


@dataclass(frozen=True)
class HintDiagnosis:
    """Perché un atleta ha (o non ha) un indizio di formazione probabile.

    Solo per diagnosi operatore (pannello admin): non è sul percorso usato
    dalla formazione vera e propria, quindi può permettersi query più
    costose di ``hints_for_fixtures``.
    """

    athlete_id: UUID
    athlete_name: str
    club_name: str | None
    fixture_id: UUID | None
    hint: Literal["starter", "bench", "unavailable"] | None
    reason: Literal[
        "hinted",
        "no_active_squad",
        "no_fixture_in_round",
        "no_snapshot_yet",
        "snapshot_not_usable",
        "unmapped_in_snapshot",
    ]
    detail: str
    #: Nomi non abbinati nello snapshot che finiscono con lo stesso cognome
    #: dell'atleta — spesso è proprio lui, scaricato con un nome diverso.
    similar_unmatched_names: tuple[str, ...] = ()


def diagnose_hints(
    session: Session,
    round_id: UUID,
    athlete_ids: list[UUID],
) -> tuple[HintDiagnosis, ...]:
    if not athlete_ids:
        return ()

    athletes = {
        row.id: row
        for row in session.scalars(select(Athlete).where(Athlete.id.in_(athlete_ids))).all()
    }

    fixture_rows = session.execute(
        select(FantasyRoundFixture.fixture_id, Fixture.home_club_id, Fixture.away_club_id)
        .join(Fixture, Fixture.id == FantasyRoundFixture.fixture_id)
        .where(
            FantasyRoundFixture.round_id == round_id,
            FantasyRoundFixture.excluded_at.is_(None),
        )
    ).all()
    fixture_by_club: dict[UUID, UUID] = {}
    fixture_ids: list[UUID] = []
    for fixture_id, home_club_id, away_club_id in fixture_rows:
        fixture_by_club[home_club_id] = fixture_id
        fixture_by_club[away_club_id] = fixture_id
        fixture_ids.append(fixture_id)

    memberships = session.scalars(
        select(SquadMembership).where(
            SquadMembership.athlete_id.in_(athlete_ids),
            SquadMembership.is_active.is_(True),
        )
    ).all()
    club_by_athlete = {row.athlete_id: row.club_id for row in memberships}

    club_ids = set(fixture_by_club) | set(club_by_athlete.values())
    club_names: dict[UUID, str] = {}
    if club_ids:
        for row in session.scalars(select(Club).where(Club.id.in_(club_ids))).all():
            club_names[row.id] = row.name

    latest_by_fixture: dict[UUID, PredictedLineupSnapshot] = {}
    if fixture_ids:
        snapshots = session.scalars(
            select(PredictedLineupSnapshot)
            .where(PredictedLineupSnapshot.fixture_id.in_(fixture_ids))
            .options(selectinload(PredictedLineupSnapshot.players))
            .order_by(PredictedLineupSnapshot.fetched_at.desc())
        ).all()
        for snapshot in snapshots:
            latest_by_fixture.setdefault(snapshot.fixture_id, snapshot)

    results: list[HintDiagnosis] = []
    for athlete_id in athlete_ids:
        athlete = athletes.get(athlete_id)
        athlete_name = athlete.canonical_name if athlete is not None else str(athlete_id)
        club_id = club_by_athlete.get(athlete_id)
        club_name = club_names.get(club_id) if club_id is not None else None

        if club_id is None:
            results.append(
                HintDiagnosis(
                    athlete_id=athlete_id,
                    athlete_name=athlete_name,
                    club_name=None,
                    fixture_id=None,
                    hint=None,
                    reason="no_active_squad",
                    detail="Nessuna rosa attiva trovata per questo atleta nella stagione corrente.",
                )
            )
            continue

        fixture_id = fixture_by_club.get(club_id)
        if fixture_id is None:
            results.append(
                HintDiagnosis(
                    athlete_id=athlete_id,
                    athlete_name=athlete_name,
                    club_name=club_name,
                    fixture_id=None,
                    hint=None,
                    reason="no_fixture_in_round",
                    detail=(
                        f"Il club ({club_name or club_id}) non ha una partita collegata a "
                        "questo turno: o è fuori dalla finestra sincronizzata, o la fixture "
                        "non è ancora linkata al turno."
                    ),
                )
            )
            continue

        snapshot = latest_by_fixture.get(fixture_id)
        if snapshot is None:
            results.append(
                HintDiagnosis(
                    athlete_id=athlete_id,
                    athlete_name=athlete_name,
                    club_name=club_name,
                    fixture_id=fixture_id,
                    hint=None,
                    reason="no_snapshot_yet",
                    detail=(
                        "La partita è collegata al turno ma non è ancora stata scaricata "
                        "nessuna formazione (né FotMob né Soccer-Oracle)."
                    ),
                )
            )
            continue

        if snapshot.reliability not in USABLE_RELIABILITY:
            results.append(
                HintDiagnosis(
                    athlete_id=athlete_id,
                    athlete_name=athlete_name,
                    club_name=club_name,
                    fixture_id=fixture_id,
                    hint=None,
                    reason="snapshot_not_usable",
                    detail=(
                        f"L'ultimo snapshot ha affidabilità '{snapshot.reliability}' "
                        f"(fonte: {snapshot.source or 'sconosciuta'}), troppo bassa per "
                        "mostrare indizi su nessun giocatore di questa partita."
                    ),
                )
            )
            continue

        player_row = next(
            (player for player in snapshot.players if player.athlete_id == athlete_id),
            None,
        )
        if player_row is None:
            candidates = () if athlete is None else _similar_unmatched_names(snapshot, athlete)
            detail = "Il giocatore non è stato abbinato in questo snapshot."
            if candidates:
                detail += f" Nomi non abbinati che somigliano: {', '.join(candidates)}."
            results.append(
                HintDiagnosis(
                    athlete_id=athlete_id,
                    athlete_name=athlete_name,
                    club_name=club_name,
                    fixture_id=fixture_id,
                    hint=None,
                    reason="unmapped_in_snapshot",
                    detail=detail,
                    similar_unmatched_names=candidates,
                )
            )
            continue

        hint = _hint_for(player_row)
        hint_value = None if hint is None else hint.hint
        results.append(
            HintDiagnosis(
                athlete_id=athlete_id,
                athlete_name=athlete_name,
                club_name=club_name,
                fixture_id=fixture_id,
                hint=hint_value,
                reason="hinted" if hint_value is not None else "unmapped_in_snapshot",
                detail=(
                    f"Indizio presente: {hint_value} (fonte: {snapshot.source or 'sconosciuta'})."
                    if hint_value is not None
                    else "Il giocatore è nello snapshot ma senza un indizio derivabile."
                ),
            )
        )
    return tuple(results)


def _similar_unmatched_names(
    snapshot: PredictedLineupSnapshot, athlete: Athlete
) -> tuple[str, ...]:
    target = normalize_person(athlete.last_name or athlete.canonical_name).split()
    last = target[-1] if target else ""
    if not last:
        return ()
    seen: list[str] = []
    for player in snapshot.players:
        if player.athlete_id is not None:
            continue
        tokens = normalize_person(player.display_name).split()
        if tokens and tokens[-1] == last and player.display_name not in seen:
            seen.append(player.display_name)
    return tuple(seen)

"""Resolve roster roles/competitions and sync composition status (EP05-05)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, undefer

from database.enums import FantasyRole, LeagueState, RosterCompositionStatus
from fantasy_teams.composition import (
    MIN_ROSTER_COMPETITIONS,
    RosterCompositionLimits,
    RosterCompositionReport,
    evaluate_roster_composition,
    limits_from_rules,
    role_quota_overflow,
    would_exceed_role_quota,
)
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam, RosterOwnershipInterval
from leagues.models.league import League
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.validators import LifecycleBlocker
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import CompetitionSeasonClub, SportSeason
from sports_data.listone.generate import get_role_assignment, list_role_assignments
from sports_data.listone.mapping import map_provider_position_to_role
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.listone.overrides import effective_role_for_athlete, get_active_override
from sports_data.roster.models import Athlete, SquadMembership

logger = get_logger(__name__)

#: Regola unica dello stato salvato (``composition_status``) e delle letture della rosa:
#: una rosa incompleta è "incompleta", non "non valida", in qualunque stato della lega.
STORED_STATUS_REQUIRES_COMPLETE = False


@dataclass(frozen=True)
class EffectiveAthleteRole:
    role: FantasyRole
    club_id: UUID | None


def resolve_effective_athlete_roles(
    session: Session,
    *,
    league_id: UUID,
    athlete_ids: list[UUID],
    season_year: int,
    current_round: int = 0,
    competition_ids: set[UUID] | None = None,
) -> dict[UUID, EffectiveAthleteRole]:
    """Resolve listone assignments and league overrides in two bulk queries."""
    unique_ids = list(dict.fromkeys(athlete_ids))
    if not unique_ids:
        return {}
    assignments = list_role_assignments(
        session,
        season_year=season_year,
        athlete_ids=unique_ids,
        competition_ids=competition_ids,
    )
    overrides = session.scalars(
        select(LeagueRoleOverride).where(
            LeagueRoleOverride.league_id == league_id,
            LeagueRoleOverride.athlete_id.in_(unique_ids),
            LeagueRoleOverride.superseded_at.is_(None),
        )
    ).all()
    overrides_by_athlete = {row.athlete_id: row for row in overrides}
    resolved = {
        assignment.athlete_id: EffectiveAthleteRole(
            role=effective_role_for_athlete(
                official_role=assignment.role,
                override=overrides_by_athlete.get(assignment.athlete_id),
                current_round=current_round,
            ),
            club_id=assignment.club_id,
        )
        for assignment in assignments
    }
    # Un calciatore in rosa senza ruolo per la stagione corrente (es. listone rigenerato senza di
    # lui) resterebbe senza ruolo in formazione e bloccherebbe il salvataggio: si ricade sull'ultimo
    # ruolo ufficiale noto, di qualsiasi stagione.
    missing = [athlete_id for athlete_id in unique_ids if athlete_id not in resolved]
    if missing:
        fallback_rows = session.scalars(
            select(RoleAssignment)
            .where(RoleAssignment.athlete_id.in_(missing))
            .order_by(RoleAssignment.season_year.desc())
        ).all()
        for row in fallback_rows:
            if row.athlete_id in resolved:
                continue
            resolved[row.athlete_id] = EffectiveAthleteRole(
                role=effective_role_for_athlete(
                    official_role=row.role,
                    override=overrides_by_athlete.get(row.athlete_id),
                    current_round=current_round,
                ),
                club_id=row.club_id,
            )
        missing = [athlete_id for athlete_id in missing if athlete_id not in resolved]
    if missing:
        # Calciatori entrati in rosa dopo l'ultima generazione del listone: hanno già la scheda
        # (posizione del provider) ma nessuna assegnazione di ruolo. Il ruolo si ricava dalla
        # posizione della loro appartenenza alla squadra in stagione (stesso mapping del listone).
        memberships = session.execute(
            select(SquadMembership)
            .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
            .where(
                SquadMembership.athlete_id.in_(missing),
                SportSeason.year == season_year,
            )
            .order_by(SquadMembership.is_active.desc(), SquadMembership.updated_at.desc())
        ).scalars()
        for membership in memberships:
            if membership.athlete_id in resolved:
                continue
            role = map_provider_position_to_role(membership.provider_position_raw)
            if role is None:
                continue
            resolved[membership.athlete_id] = EffectiveAthleteRole(
                role=role,
                club_id=membership.club_id,
            )
    return resolved


def resolve_league_rules_limits(session: Session, league_id: UUID) -> RosterCompositionLimits:
    rules = session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
    if rules is None:
        return limits_from_rules(
            roster_size=35,
            goalkeepers=3,
            defenders=11,
            midfielders=11,
            forwards=10,
        )
    return limits_from_rules(
        roster_size=rules.roster_size,
        goalkeepers=rules.goalkeepers,
        defenders=rules.defenders,
        midfielders=rules.midfielders,
        forwards=rules.forwards,
    )


def league_requires_complete_rosters(league: League) -> bool:
    """Incomplete rosters are allowed only before season start (during auction)."""
    return league.state not in {LeagueState.DRAFT, LeagueState.CONFIGURING, LeagueState.AUCTION}


def resolve_effective_athlete_role(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
    season_year: int,
    current_round: int = 0,
    competition_ids: set[UUID] | None = None,
) -> FantasyRole | None:
    assignment = get_role_assignment(
        session,
        athlete_id=athlete_id,
        season_year=season_year,
        competition_ids=competition_ids,
    )
    if assignment is None:
        return None
    override = get_active_override(session, league_id=league_id, athlete_id=athlete_id)
    return effective_role_for_athlete(
        official_role=assignment.role,
        override=override,
        current_round=current_round,
    )


def resolve_club_competition_ids(
    session: Session,
    *,
    club_ids: set[UUID],
    season_year: int,
    league_competition_ids: set[UUID],
) -> dict[UUID, set[UUID]]:
    """Map club → competition ids intersecting the league catalog for the season year."""
    if not club_ids or not league_competition_ids:
        return {}
    rows = session.execute(
        select(CompetitionSeasonClub.club_id, SportSeason.competition_id)
        .join(SportSeason, SportSeason.id == CompetitionSeasonClub.sport_season_id)
        .where(
            CompetitionSeasonClub.club_id.in_(club_ids),
            SportSeason.year == season_year,
            SportSeason.competition_id.in_(league_competition_ids),
        )
    ).all()
    mapping: dict[UUID, set[UUID]] = {}
    for club_id, competition_id in rows:
        mapping.setdefault(club_id, set()).add(competition_id)
    return mapping


def evaluate_team_composition(
    session: Session,
    team: FantasyTeam,
    *,
    league: League,
    require_complete: bool | None = None,
    effective_roles: dict[UUID, EffectiveAthleteRole] | None = None,
    exclude_athlete_ids: Collection[UUID] = (),
) -> RosterCompositionReport:
    """Valuta la rosa della squadra.

    ``exclude_athlete_ids`` toglie dal conteggio i calciatori indicati (ruoli, slot
    occupati e campionati): serve a valutare la rosa senza gli esuberi di uno scambio
    (vedi `roster_allows_lineup`).
    """
    limits = resolve_league_rules_limits(session, league.id)
    must_complete = (
        league_requires_complete_rosters(league) if require_complete is None else require_complete
    )
    league_competition_ids = _league_competition_ids(session, league.id)

    slots = list(
        session.scalars(
            select(FantasyRosterSlot)
            .where(FantasyRosterSlot.fantasy_team_id == team.id)
            .order_by(FantasyRosterSlot.slot_index.asc())
        ).all()
    )

    excluded = set(exclude_athlete_ids)
    athlete_ids = [
        slot.athlete_id
        for slot in slots
        if slot.athlete_id is not None and slot.athlete_id not in excluded
    ]
    resolved = effective_roles
    if resolved is None:
        resolved = resolve_effective_athlete_roles(
            session,
            league_id=league.id,
            athlete_ids=athlete_ids,
            season_year=league.season_year,
        )
    athletes = set(athlete_ids)
    club_ids = {
        item.club_id
        for athlete_id, item in resolved.items()
        if athlete_id in athletes and item.club_id is not None
    }
    club_competitions = resolve_club_competition_ids(
        session,
        club_ids=club_ids,
        season_year=league.season_year,
        league_competition_ids=league_competition_ids,
    )
    return _composition_report(
        limits=limits,
        require_complete=must_complete,
        athlete_ids=athlete_ids,
        resolved=resolved,
        club_competitions=club_competitions,
    )


def _league_competition_ids(session: Session, league_id: UUID) -> set[UUID]:
    return {
        row.competition_id
        for row in session.scalars(
            select(LeagueCompetition).where(LeagueCompetition.league_id == league_id)
        ).all()
    }


def _composition_report(
    *,
    limits: RosterCompositionLimits,
    require_complete: bool,
    athlete_ids: Sequence[UUID],
    resolved: Mapping[UUID, EffectiveAthleteRole],
    club_competitions: Mapping[UUID, set[UUID]],
) -> RosterCompositionReport:
    """Valutazione di una rosa a ruoli e campionati dei club già risolti (nessuna query)."""
    roles = [resolved[athlete_id].role for athlete_id in athlete_ids if athlete_id in resolved]
    competition_ids: set[UUID] = set()
    for athlete_id in athlete_ids:
        item = resolved.get(athlete_id)
        if item is not None and item.club_id is not None:
            competition_ids.update(club_competitions.get(item.club_id, ()))
    return evaluate_roster_composition(
        limits=limits,
        roles=roles,
        competition_ids=competition_ids,
        require_complete=require_complete,
        unresolved_role_count=len(athlete_ids) - len(roles),
    )


def evaluate_league_team_compositions(
    session: Session,
    league: League,
    teams: Sequence[FantasyTeam],
) -> tuple[dict[UUID, RosterCompositionReport], dict[UUID, EffectiveAthleteRole]]:
    """Valuta le rose di più squadre della lega in un numero fisso di query (``/squadre``).

    Stesso risultato di `evaluate_team_composition` con la regola dello stato salvato
    (``require_complete=False``), squadra per squadra, ma con i ruoli e i campionati dei club
    risolti una volta sola per tutta la lega. Usa ``team.slots`` già caricati. Ritorna i report
    per squadra e i ruoli risolti (per `composition_needs_refresh`).
    """
    limits = resolve_league_rules_limits(session, league.id)
    athlete_ids_by_team = {
        team.id: [slot.athlete_id for slot in team.slots if slot.athlete_id is not None]
        for team in teams
    }
    resolved = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=[athlete_id for ids in athlete_ids_by_team.values() for athlete_id in ids],
        season_year=league.season_year,
    )
    club_ids = {item.club_id for item in resolved.values() if item.club_id is not None}
    club_competitions = (
        resolve_club_competition_ids(
            session,
            club_ids=club_ids,
            season_year=league.season_year,
            league_competition_ids=_league_competition_ids(session, league.id),
        )
        if club_ids
        else {}
    )
    reports = {
        team_id: _composition_report(
            limits=limits,
            require_complete=STORED_STATUS_REQUIRES_COMPLETE,
            athlete_ids=athlete_ids,
            resolved=resolved,
            club_competitions=club_competitions,
        )
        for team_id, athlete_ids in athlete_ids_by_team.items()
    }
    return reports, resolved


#: Possesso non registrato: conta come l'acquisto più vecchio.
_UNKNOWN_ACQUISITION = datetime.min.replace(tzinfo=UTC)


def flag_role_quota_overflow(
    session: Session,
    team: FantasyTeam,
    *,
    league: League,
) -> list[FantasyRosterSlot]:
    """Auto-riparazione: segna ``exceeds_role_quota`` sugli esuberi di ruolo rimasti senza flag.

    Un ruolo può trovarsi oltre quota senza nessun calciatore segnato (KO-A, QA 19/11:
    11 attaccanti su 10, nessuno slot in esubero) se un'operazione l'ha portato lì senza
    passare dal controllo di quota, per esempio un cambio di ruolo nel listone o un
    override di lega. In quello stato `roster_allows_lineup` non trova esuberi da
    togliere e blocca la formazione per sempre.

    Per ogni ruolo restano in quota al massimo ``limite`` calciatori non segnati; quelli
    in più si segnano, in quest'ordine: prima l'acquisto più recente (``acquired_at``
    del possesso attivo dello slot), poi lo slot più alto. Uno slot senza possesso
    registrato (dati precedenti allo storico dei possessi) conta come il più vecchio.
    I ruoli sono quelli della valutazione della rosa (`evaluate_team_composition`), così
    dopo la riparazione la rosa senza esuberi non è più oltre quota.

    Non toglie mai un flag (lo fa `reconcile_roster_overflow` quando l'esubero rientra)
    ed è idempotente: con gli esuberi già segnati non cambia nulla. Fa flush e lascia
    il commit al chiamante. Ritorna gli slot appena segnati.
    """
    slots = list(
        session.scalars(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
            .options(undefer(FantasyRosterSlot.exceeds_role_quota))
        ).all()
    )
    unflagged = [slot for slot in slots if not slot.exceeds_role_quota]
    limits = resolve_league_rules_limits(session, league.id)
    if len(unflagged) <= min(limits.for_role(role) for role in FantasyRole):
        # Nessun ruolo può superare la quota con così pochi calciatori.
        return []
    roles = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=[slot.athlete_id for slot in unflagged if slot.athlete_id is not None],
        season_year=league.season_year,
    )
    acquired_at = {
        (slot_index, athlete_id): acquired
        for slot_index, athlete_id, acquired in session.execute(
            select(
                RosterOwnershipInterval.slot_index,
                RosterOwnershipInterval.athlete_id,
                RosterOwnershipInterval.acquired_at,
            ).where(
                RosterOwnershipInterval.fantasy_team_id == team.id,
                RosterOwnershipInterval.released_at.is_(None),
            )
        ).all()
    }

    def arrival_order(slot: FantasyRosterSlot) -> tuple[bool, datetime, int]:
        # Dal più vecchio al più recente: gli ultimi oltre quota sono gli esuberi.
        acquired = acquired_at.get((slot.slot_index, slot.athlete_id))
        return (acquired is not None, acquired or _UNKNOWN_ACQUISITION, slot.slot_index)

    overflow = role_quota_overflow(
        limits=limits,
        items=[
            (slot, roles[slot.athlete_id].role)
            for slot in sorted(unflagged, key=arrival_order)
            if slot.athlete_id in roles
        ],
    )
    flagged: list[FantasyRosterSlot] = []
    for slot, role in overflow:
        # UPDATE condizionato: se nel frattempo lo slot ha cambiato calciatore (svincolo o
        # scambio concorrente) non si segna, per non lasciare un flag su chi non c'entra.
        result = session.execute(
            update(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.id == slot.id,
                FantasyRosterSlot.athlete_id == slot.athlete_id,
                FantasyRosterSlot.exceeds_role_quota.is_(False),
            )
            .values(exceeds_role_quota=True)
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount:
            flagged.append(slot)
            logger.warning(
                "fantasy_roster_role_overflow_flagged",
                extra={
                    "fantasy_team_id": str(team.id),
                    "slot_index": slot.slot_index,
                    "athlete_id": str(slot.athlete_id),
                    "role": role.value,
                },
            )
    if flagged:
        session.flush()
        get_metrics().incr(
            "fantasy_roster_role_overflow_flagged_total",
            labels={"result": "self_healed"},
            amount=len(flagged),
        )
    return flagged


def sync_team_composition_status(
    session: Session,
    team: FantasyTeam,
    *,
    league: League,
) -> RosterCompositionReport:
    """Unico punto che scrive ``composition_status``: la fonte unica dello stato della rosa.

    ``/squadre``, ``/rosa`` e la vista admin della squadra mostrano lo stato salvato, quindi
    lo si valuta sempre con la stessa regola delle loro letture
    (``STORED_STATUS_REQUIRES_COMPLETE``): una rosa a 34/35 è "incompleta", non "non valida",
    in qualunque stato della lega. I controlli per l'avvio della stagione (rosa completa e
    tre campionati) non leggono lo stato salvato e valutano a parte.
    """
    # Chi scrive lo stato della rosa ripara anche gli esuberi senza flag: la valutazione
    # resta la stessa (gli esuberi contano), ma la rosa mostra chi è in più e la
    # formazione si può schierare senza di lui (vedi `roster_allows_lineup`). Vale anche
    # per una rosa salvata come convalidata ma ormai oltre quota (stato scaduto).
    flag_role_quota_overflow(session, team, league=league)
    report = evaluate_team_composition(
        session,
        team,
        league=league,
        require_complete=STORED_STATUS_REQUIRES_COMPLETE,
    )
    previous = team.composition_status
    team.composition_status = report.status
    if report.status == RosterCompositionStatus.VALIDATED:
        if team.validated_at is None or previous != RosterCompositionStatus.VALIDATED:
            team.validated_at = datetime.now(UTC)
    else:
        team.validated_at = None
    if previous == RosterCompositionStatus.VALIDATED and report.status != previous:
        logger.info(
            "fantasy_roster_composition_invalidated",
            extra={"fantasy_team_id": str(team.id), "status": report.status.value},
        )
    return report


def composition_needs_refresh(
    team: FantasyTeam,
    report: RosterCompositionReport,
    *,
    effective_roles: Mapping[UUID, EffectiveAthleteRole],
) -> bool:
    """True se stato salvato o flag di esubero non corrispondono alla valutazione ``report``.

    Controllo in memoria, senza query, sugli slot già caricati (``team.slots`` con
    ``exceeds_role_quota``) e sui ruoli già risolti: le letture della rosa lo usano per
    riallineare (`refresh_team_composition`) solo le squadre rimaste indietro, per esempio
    una rosa salvata come convalidata prima che un cambio di ruolo la portasse oltre quota
    (QA 20/11, qa-04 e qa-08). Scaduto vuol dire:

    - lo stato salvato (o ``validated_at``) diverso da quello valutato;
    - un ruolo oltre quota con meno segnati dell'eccedenza (lo segnerebbe
      `flag_role_quota_overflow`);
    - un flag non più giustificato o uno slot extra da ricompattare (li toglierebbe
      `reconcile_roster_overflow`, stesso conteggio).
    """
    if team.composition_status != report.status:
        return True
    if (report.status == RosterCompositionStatus.VALIDATED) != (team.validated_at is not None):
        return True
    limits = report.limits
    occupied = [slot for slot in team.slots if slot.athlete_id is not None]
    counts: Counter[FantasyRole] = Counter()
    unflagged: Counter[FantasyRole] = Counter()
    flagged: Counter[FantasyRole] = Counter()
    for slot in occupied:
        resolved = effective_roles.get(slot.athlete_id) if slot.athlete_id else None
        if resolved is None:
            continue
        counts[resolved.role] += 1
        (flagged if slot.exceeds_role_quota else unflagged)[resolved.role] += 1
    if any(unflagged[role] > limits.for_role(role) for role in FantasyRole):
        return True
    # Stessi due passi di `reconcile_roster_overflow`: prima la quota di ruolo, poi la misura.
    kept_for_role = {
        role: min(flagged[role], max(0, counts[role] - limits.for_role(role)))
        for role in FantasyRole
    }
    capacity_candidates = sum(flagged[role] - kept_for_role[role] for role in FantasyRole)
    capacity_over = max(0, len(occupied) - limits.roster_size)
    if capacity_candidates > capacity_over:
        return True
    if not occupied:
        return False
    has_free_slot = any(
        slot.athlete_id is None and slot.slot_index < limits.roster_size for slot in team.slots
    )
    return any(
        slot.slot_index >= limits.roster_size
        and (slot.athlete_id is None or (not slot.exceeds_role_quota and has_free_slot))
        for slot in team.slots
    )


def refresh_team_composition(
    session: Session,
    team: FantasyTeam,
    *,
    league: League,
) -> RosterCompositionReport:
    """Riallinea flag di esubero e stato salvato alla rosa e ai ruoli di oggi.

    Toglie i flag non più giustificati (`reconcile_roster_overflow`), segna gli esuberi
    rimasti senza flag e riscrive lo stato (`sync_team_composition_status`). Gira dopo un
    cambio di ruolo (override di lega, aggiornamento del listone:
    `resync_team_compositions`) e nelle letture della rosa (``/squadre``, ``/rosa``, vista
    admin) che trovano uno stato scaduto (`composition_needs_refresh`). Non gira in lettura
    né in salvataggio della formazione, che si fidano dello stato salvato
    (`roster_allows_lineup`); chi è già in campo e bloccato resta comunque schierabile per
    il turno anche se segnato qui (`FantasyLineupService._keep_fielded_locked_excess`).

    La squadra si blocca (``FOR UPDATE``) come nelle scritture di rosa, così una lettura
    non riscrive lo stato con una rosa vecchia mentre un'assegnazione è in corso. Fa flush
    e lascia il commit al chiamante.
    """
    session.execute(select(FantasyTeam.id).where(FantasyTeam.id == team.id).with_for_update())
    has_flags = session.scalar(
        select(FantasyRosterSlot.id)
        .where(
            FantasyRosterSlot.fantasy_team_id == team.id,
            FantasyRosterSlot.exceeds_role_quota.is_(True),
        )
        .limit(1)
    )
    if has_flags is not None:
        reconcile_roster_overflow(session, league=league, team=team)
    report = sync_team_composition_status(session, team, league=league)
    session.flush()
    return report


#: Leghe ferme: niente override (vedi `LOCKED_OVERRIDE_STATES`) e rose non più da ricalcolare.
_FROZEN_LEAGUE_STATES = frozenset({LeagueState.CONCLUDED, LeagueState.ARCHIVED})

#: Quanti calciatori per query nella ricerca delle squadre da ricalcolare.
_RESYNC_ATHLETE_CHUNK = 1000


def resync_team_compositions(
    session: Session,
    *,
    athlete_ids: Collection[UUID],
    league_id: UUID | None = None,
    season_year: int | None = None,
) -> int:
    """Ricalcola le rose che contengono i calciatori il cui ruolo è appena cambiato.

    Con ``league_id`` (override di lega impostato o tolto) solo le squadre di quella lega;
    con ``season_year`` (listone ufficiale rigenerato o aggiornato, che vale per tutte le
    leghe della stagione) le squadre di ogni lega di quell'anno non conclusa né archiviata.
    Ogni squadra è bloccata (``FOR UPDATE``, in ordine di id) come nelle scritture di rosa,
    poi `refresh_team_composition`: una rosa che il nuovo ruolo porta oltre quota diventa
    ``invalid`` con l'esubero segnato (prima l'arrivo più recente), una che ci rientra perde
    il flag. Fa flush e lascia il commit al chiamante. Ritorna quante squadre ha ricalcolato.
    """
    ids = list(dict.fromkeys(athlete_ids))
    if not ids or (league_id is None and season_year is None):
        return 0
    team_ids: set[UUID] = set()
    for start in range(0, len(ids), _RESYNC_ATHLETE_CHUNK):
        chunk = ids[start : start + _RESYNC_ATHLETE_CHUNK]
        stmt = select(FantasyRosterSlot.fantasy_team_id).where(
            FantasyRosterSlot.athlete_id.in_(chunk)
        )
        if league_id is not None:
            stmt = stmt.where(FantasyRosterSlot.league_id == league_id)
        else:
            stmt = stmt.join(League, League.id == FantasyRosterSlot.league_id).where(
                League.season_year == season_year
            )
        team_ids.update(session.scalars(stmt.distinct()).all())
    if not team_ids:
        return 0
    teams = list(
        session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.id.in_(team_ids))
            .order_by(FantasyTeam.id.asc())
            .with_for_update()
        ).all()
    )
    leagues = {
        row.id: row
        for row in session.scalars(
            select(League).where(League.id.in_({team.league_id for team in teams}))
        ).all()
    }
    refreshed = 0
    for team in teams:
        league = leagues.get(team.league_id)
        if league is None or league.state in _FROZEN_LEAGUE_STATES:
            continue
        refresh_team_composition(session, team, league=league)
        refreshed += 1
    logger.info(
        "fantasy_roster_composition_resynced",
        extra={
            "league_id": str(league_id) if league_id else None,
            "season_year": season_year,
            "athletes": len(ids),
            "teams": refreshed,
        },
    )
    get_metrics().incr(
        "fantasy_roster_composition_resynced_total",
        labels={"scope": "league" if league_id is not None else "season"},
        amount=refreshed,
    )
    return refreshed


#: Problemi che bloccano la formazione anche dopo aver tolto gli esuberi dalla rosa.
_LINEUP_BLOCKING_ISSUES = frozenset({"role_quota_exceeded", "role_unresolved"})


def roster_allows_lineup(session: Session, team: FantasyTeam, *, league: League) -> bool:
    """True se la squadra può schierare la formazione.

    Vale sempre per una rosa convalidata. Uno scambio sbilanciato (2 per 1, un D per
    un C) lascia invece la rosa ``invalid`` per il ruolo in esubero, anche se il
    calciatore in più è già segnato ``exceeds_role_quota`` e quindi escluso dalla
    formazione (EP08-10): la squadra deve poter giocare con gli altri. Con calciatori
    in esubero la formazione è ammessa se:

    - gli slot occupati (esuberi compresi) sono almeno quanti la misura della rosa:
      una rosa con uno slot vuoto resta bloccata, come dopo uno svincolo;
    - tolti gli esuberi, nessun ruolo supera la quota e ogni ruolo è risolvibile;
    - tolti gli esuberi, la rosa rappresenta ancora almeno 3 campionati (stessa
      regola della convalida, ``MIN_ROSTER_COMPETITIONS``).

    Conta solo gli esuberi già segnati: chi la usa per sbloccare la formazione chiama
    prima `flag_role_quota_overflow`, che segna quelli rimasti senza flag (KO-A).
    """
    if team.composition_status == RosterCompositionStatus.VALIDATED:
        return True
    rows = session.execute(
        select(FantasyRosterSlot.athlete_id, FantasyRosterSlot.exceeds_role_quota).where(
            FantasyRosterSlot.fantasy_team_id == team.id,
            FantasyRosterSlot.athlete_id.is_not(None),
        )
    ).all()
    flagged = {athlete_id for athlete_id, exceeds in rows if exceeds}
    if not flagged:
        return False
    limits = resolve_league_rules_limits(session, league.id)
    if len(rows) < limits.roster_size:
        return False
    report = evaluate_team_composition(
        session,
        team,
        league=league,
        require_complete=False,
        exclude_athlete_ids=flagged,
    )
    if any(issue.code in _LINEUP_BLOCKING_ISSUES for issue in report.issues):
        return False
    return report.competition_count >= MIN_ROSTER_COMPETITIONS


_ROLE_UNRESOLVED_MESSAGE = "Il calciatore non ha un ruolo listone valido (P–D–C–A)."


def _role_quota_check(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    athlete_id: UUID,
    slot_index: int,
    require_listone: bool,
) -> tuple[FantasyRole, str | None]:
    """Ruolo di chi entra nello slot e, se supera la quota, il messaggio del rifiuto.

    I ruoli sono quelli della valutazione della rosa (`evaluate_team_composition`), per chi
    entra e per chi c'è già: stesso risolutore, quindi anche le stagioni precedenti e la
    posizione nel club per chi non è più nel listone di quest'anno. Prima il controllo usava
    solo il listone corrente: un attaccante uscito dal listone non contava e ne entrava un
    altro oltre quota, che la valutazione poi vedeva (QA 20/11, qa-04 e qa-08).

    Chi in rosa non ha un ruolo nemmeno così (``role_unresolved`` nella valutazione, che
    rende la rosa ``invalid``) non è mai un posto libero: conta come se avesse il ruolo di
    chi entra. L'ingresso passa solo se la quota regge qualunque ruolo riceva poi.

    ``require_listone``: chi entra in lega da fuori (assegnazione dell'admin, import, aste)
    deve essere nel listone della stagione e dei campionati della lega (``role_unresolved``
    altrimenti, come prima). Chi si scambia è già nella lega: vale il ruolo con cui lo conta
    la rosa che lo cede.
    """
    from auth.exceptions import ValidationAuthError
    from fantasy_teams.composition import ROLE_LABEL_IT

    if require_listone and (
        get_role_assignment(
            session,
            athlete_id=athlete_id,
            season_year=league.season_year,
            competition_ids={competition.id for competition in league.competitions},
        )
        is None
    ):
        raise ValidationAuthError(_ROLE_UNRESOLVED_MESSAGE, code="role_unresolved")

    slots = list(
        session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all()
    )
    roles = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=[athlete_id, *(slot.athlete_id for slot in slots if slot.athlete_id)],
        season_year=league.season_year,
    )
    incoming = roles.get(athlete_id)
    if incoming is None:
        raise ValidationAuthError(_ROLE_UNRESOLVED_MESSAGE, code="role_unresolved")
    new_role = incoming.role

    current_roles: list[FantasyRole | None] = []
    without_role: list[UUID] = []
    replacing: FantasyRole | None = None
    for slot in slots:
        resolved = roles.get(slot.athlete_id) if slot.athlete_id else None
        role = resolved.role if resolved is not None else None
        if slot.slot_index == slot_index:
            replacing = role
            continue
        if role is None and slot.athlete_id is not None:
            without_role.append(slot.athlete_id)
            continue
        current_roles.append(role)

    limits = resolve_league_rules_limits(session, league.id)
    if not would_exceed_role_quota(
        limits=limits,
        current_roles=[*current_roles, *([new_role] * len(without_role))],
        new_role=new_role,
        replacing_role=replacing,
    ):
        return new_role, None
    message = f"Limite {ROLE_LABEL_IT[new_role]} raggiunto ({limits.for_role(new_role)})."
    if without_role and not would_exceed_role_quota(
        limits=limits,
        current_roles=current_roles,
        new_role=new_role,
        replacing_role=replacing,
    ):
        # Il limite lo superano solo contando chi non ha un ruolo: lo si dice per nome.
        names = list(
            session.scalars(
                select(Athlete.canonical_name)
                .where(Athlete.id.in_(without_role))
                .order_by(Athlete.canonical_name.asc())
            ).all()
        )
        if len(names) == 1:
            detail = f"{names[0]} non ha un ruolo nel listone e finché non lo riceve conta"
        else:
            detail = (
                f"{', '.join(names)} non hanno un ruolo nel listone e finché non lo ricevono "
                "contano"
            )
        message = (
            f"Limite {ROLE_LABEL_IT[new_role]} raggiunto ({limits.for_role(new_role)}): "
            f"{detail} tra i {ROLE_LABEL_IT[new_role]}."
        )
    return new_role, message


def assert_assignment_respects_role_quota(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    athlete_id: UUID,
    slot_index: int,
    require_listone: bool = True,
) -> FantasyRole:
    """Reject assignments that would exceed configurable role limits.

    Stessi ruoli della valutazione della rosa e chi non ha ruolo conta come chi entra:
    vedi `_role_quota_check`.
    """
    from auth.exceptions import ValidationAuthError

    role, refusal = _role_quota_check(
        session,
        league=league,
        team=team,
        athlete_id=athlete_id,
        slot_index=slot_index,
        require_listone=require_listone,
    )
    if refusal is not None:
        raise ValidationAuthError(refusal, code="role_quota_exceeded")
    return role


def assign_allowing_role_quota_overflow(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    athlete_id: UUID,
    slot_index: int,
    require_listone: bool = True,
) -> tuple[FantasyRole, bool]:
    """Like `assert_assignment_respects_role_quota`, but a quota overflow is allowed
    through instead of rejected — for trade acceptance only (EP08-10): the system
    revalidates everything else at acceptance time ("nessuna operazione parziale"),
    but a role already at its cap must not sink an otherwise-agreed trade. Returns
    `(role, exceeds_quota)`; the caller marks the slot so the player counts as
    owned but stays unavailable to field until released.
    """
    role, refusal = _role_quota_check(
        session,
        league=league,
        team=team,
        athlete_id=athlete_id,
        slot_index=slot_index,
        require_listone=require_listone,
    )
    return role, refusal is not None


def reconcile_roster_overflow(session: Session, *, league: League, team: FantasyTeam) -> bool:
    """Clear `exceeds_role_quota` on any slot that is no longer actually in excess —
    called after anything that can change a team's roster composition (releasing a
    player, a trade). A slot can be flagged for two different reasons (EP08-10):

    - its role is over the per-role quota (e.g. a 4th goalkeeper);
    - the team's total headcount is over the roster size (an unbalanced trade with
      no free slot creates one extra slot rather than blocking the trade).

    Either reason can stop applying because the flagged player's own slot was
    released, or because a *different* player (of that role, or anywhere in the
    roster) left, freeing the limit for the one still flagged.
    """
    from fantasy_teams.factory import resolve_roster_size

    limits = resolve_league_rules_limits(session, league.id)
    roster_size = resolve_roster_size(session, league.id)
    slots = list(
        session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.athlete_id.isnot(None),
            )
        ).all()
    )
    if not slots:
        return False
    athlete_ids = [slot.athlete_id for slot in slots if slot.athlete_id is not None]
    roles = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=athlete_ids,
        season_year=league.season_year,
        competition_ids={competition.id for competition in league.competitions},
    )
    changed = False
    role_counts: dict[FantasyRole, int] = {}
    flagged_by_role: dict[FantasyRole, list[FantasyRosterSlot]] = {}
    for slot in slots:
        resolved = roles.get(slot.athlete_id)
        if resolved is None:
            continue
        role_counts[resolved.role] = role_counts.get(resolved.role, 0) + 1
        if slot.exceeds_role_quota:
            flagged_by_role.setdefault(resolved.role, []).append(slot)

    # Step 1: role-quota reason. Keep exactly `over` flagged per role (still
    # genuinely in excess); the rest stay candidates for the capacity reason below.
    still_flagged_ids: set[UUID] = set()
    capacity_candidates: list[FantasyRosterSlot] = []
    for role, flagged_slots in flagged_by_role.items():
        over = max(0, role_counts.get(role, 0) - limits.for_role(role))
        for slot in flagged_slots[:over]:
            still_flagged_ids.add(slot.id)
        capacity_candidates.extend(flagged_slots[over:])

    # Step 2: total-capacity reason. Keep exactly as many of the remaining
    # flagged slots as the team is still over its roster size (regardless of role).
    capacity_over = max(0, len(slots) - roster_size)
    for slot in capacity_candidates[:capacity_over]:
        still_flagged_ids.add(slot.id)

    for flagged_slots in flagged_by_role.values():
        for slot in flagged_slots:
            keep = slot.id in still_flagged_ids
            if slot.exceeds_role_quota != keep:
                slot.exceeds_role_quota = keep
                changed = True
    if _compact_extra_slots(session, team=team, roster_size=roster_size):
        changed = True
    return changed


def _compact_extra_slots(session: Session, *, team: FantasyTeam, roster_size: int) -> bool:
    """Rimette la rosa alla sua misura quando l'esubero è rientrato.

    Gli slot oltre ``roster_size`` nascono solo per ospitare un calciatore in più. Quando
    non è più in esubero (flag tolto) si sposta nel primo slot libero entro la misura
    della rosa, portandosi dietro prezzo e storico di possesso, e lo slot extra sparisce.
    """
    from fantasy_teams.ownership import find_active_interval_for_slot

    extras = list(
        session.scalars(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.slot_index >= roster_size,
            )
            .order_by(FantasyRosterSlot.slot_index.asc())
            .with_for_update()
        ).all()
    )
    if not extras:
        return False
    free_slots = list(
        session.scalars(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.slot_index < roster_size,
                FantasyRosterSlot.athlete_id.is_(None),
            )
            .order_by(FantasyRosterSlot.slot_index.asc())
            .with_for_update()
        ).all()
    )
    changed = False
    for extra in extras:
        if extra.athlete_id is None:
            session.delete(extra)
            changed = True
            continue
        if extra.exceeds_role_quota or not free_slots:
            continue
        target = free_slots.pop(0)
        interval = find_active_interval_for_slot(
            session, fantasy_team_id=team.id, slot_index=extra.slot_index, for_update=True
        )
        athlete_id, purchase = extra.athlete_id, extra.purchase_credits
        extra.athlete_id = None
        extra.purchase_credits = None
        session.flush()
        target.athlete_id = athlete_id
        target.purchase_credits = purchase
        target.exceeds_role_quota = False
        if interval is not None:
            interval.slot_index = target.slot_index
        session.delete(extra)
        changed = True
    session.flush()
    return changed


def activation_roster_and_credit_blockers(
    session: Session,
    league: League,
) -> list[LifecycleBlocker]:
    """Real season-start blockers replacing EP03-05 placeholders (EP05-05)."""
    from sqlalchemy.orm import selectinload

    from fantasy_teams.ledger import find_account_for_team

    blockers: list[LifecycleBlocker] = []
    memberships = list(
        session.scalars(
            select(LeagueMembership).where(LeagueMembership.league_id == league.id)
        ).all()
    )
    teams = {
        team.membership_id: team
        for team in session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.league_id == league.id)
            .options(
                selectinload(FantasyTeam.slots),
                selectinload(FantasyTeam.credit_account),
            )
        ).all()
    }

    missing_teams = 0
    invalid_rosters = 0
    missing_credits = 0
    for membership in memberships:
        team = teams.get(membership.id)
        if team is None:
            missing_teams += 1
            continue
        report = evaluate_team_composition(
            session,
            team,
            league=league,
            require_complete=True,
        )
        if not report.is_valid_for_season_start:
            invalid_rosters += 1
        account = team.credit_account or find_account_for_team(session, team.id)
        if account is None or account.balance < 0:
            missing_credits += 1

    if missing_teams or invalid_rosters:
        detail_parts: list[str] = []
        if missing_teams:
            detail_parts.append(f"{missing_teams} squadre mancanti")
        if invalid_rosters:
            detail_parts.append(f"{invalid_rosters} rose non valide o incomplete")
        blockers.append(
            LifecycleBlocker(
                code="fantasy_teams_not_configured",
                message=(
                    "Completa squadre e rose prima di avviare la stagione "
                    f"({'; '.join(detail_parts)})."
                ),
                action_hint="teams",
            )
        )
    if missing_credits:
        blockers.append(
            LifecycleBlocker(
                code="credits_not_configured",
                message=(
                    "Verifica i crediti di tutte le squadre prima di avviare la stagione "
                    f"({missing_credits} conti assenti o non validi)."
                ),
                action_hint="teams",
            )
        )
    return blockers


def league_rosters_complete(session: Session, league: League) -> bool:
    """True se ogni membership ha una squadra con rosa completa e valida.

    Stesso controllo di composizione usato per sbloccare l'avvio stagione
    (`activation_roster_and_credit_blockers`), ma senza il vincolo sui
    crediti: qui serve solo sapere se le rose sono pronte per generare il
    calendario H2H (EP13-P04) — le rose si possono completare anche senza
    passare per lo stato "asta" (es. assegnazione manuale/random IA in
    Amministrazione lega), quindi il prerequisito è sulle rose stesse, non
    sullo stato macro della lega.
    """
    memberships = list(
        session.scalars(
            select(LeagueMembership).where(LeagueMembership.league_id == league.id)
        ).all()
    )
    if not memberships:
        return False
    teams = {
        team.membership_id: team
        for team in session.scalars(
            select(FantasyTeam).where(FantasyTeam.league_id == league.id)
        ).all()
    }
    for membership in memberships:
        team = teams.get(membership.id)
        if team is None:
            return False
        report = evaluate_team_composition(session, team, league=league, require_complete=True)
        if not report.is_valid_for_season_start:
            return False
    return True

"""Preview builder for roster CSV import (EP05-04)."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fantasy_teams.csv_import import (
    AthleteCandidate,
    ParsedCsvRow,
    PreviewRow,
    PreviewRowIssue,
    normalize_athlete_name,
    normalize_team_key,
)
from fantasy_teams.factory import resolve_roster_size
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from sports_data.listone.generate import get_role_assignment
from sports_data.roster.models import Athlete


def build_preview_rows(
    session: Session,
    *,
    league_id: UUID,
    season_year: int,
    parsed_rows: list[ParsedCsvRow],
) -> list[PreviewRow]:
    teams = list(
        session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.league_id == league_id)
            .options(selectinload(FantasyTeam.slots))
        ).all()
    )
    teams_by_key: dict[str, list[FantasyTeam]] = defaultdict(list)
    for team in teams:
        teams_by_key[normalize_team_key(team.name)].append(team)

    roster_size = resolve_roster_size(session, league_id)
    free_slots: dict[UUID, list[int]] = {}
    for team in teams:
        free: list[int] = []
        for slot in sorted(team.slots, key=lambda row: row.slot_index):
            if slot.athlete_id is None:
                free.append(slot.slot_index)
        free_slots[team.id] = free

    owned_elsewhere: dict[UUID, FantasyTeam] = {}
    owned_slots = session.scalars(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.league_id == league_id,
            FantasyRosterSlot.athlete_id.is_not(None),
        )
        .options(selectinload(FantasyRosterSlot.fantasy_team))
    ).all()
    for slot in owned_slots:
        if slot.athlete_id is not None:
            owned_elsewhere[slot.athlete_id] = slot.fantasy_team

    balances: dict[UUID, int] = {}
    for team in teams:
        account = find_account_for_team(session, team.id)
        balances[team.id] = account.balance if account is not None else 0

    provider_ids = {row.provider_id for row in parsed_rows if row.provider_id is not None}
    athletes_by_provider: dict[int, Athlete] = {}
    if provider_ids:
        for athlete in session.scalars(
            select(Athlete).where(Athlete.provider_id.in_(provider_ids))
        ).all():
            athletes_by_provider[athlete.provider_id] = athlete

    names = {normalize_athlete_name(row.nome) for row in parsed_rows if row.nome}
    athletes_by_name: dict[str, list[Athlete]] = defaultdict(list)
    if names:
        lowered = list(names)
        for athlete in session.scalars(
            select(Athlete).where(func.lower(Athlete.canonical_name).in_(lowered))
        ).all():
            athletes_by_name[normalize_athlete_name(athlete.canonical_name)].append(athlete)

    seen_athletes: dict[UUID, int] = {}
    claimed_slots: dict[UUID, list[int]] = {
        team.id: list(free_slots.get(team.id, [])) for team in teams
    }
    projected_spend: dict[UUID, int] = defaultdict(int)

    preview_rows: list[PreviewRow] = []
    for parsed in parsed_rows:
        row = PreviewRow(
            row_number=parsed.row_number,
            squadra=parsed.squadra,
            provider_id=parsed.provider_id,
            nome=parsed.nome,
            crediti=parsed.crediti,
            status="ok",
        )
        _validate_basic_fields(row, parsed)
        team = _resolve_team(row, teams_by_key)
        athlete = _resolve_athlete(
            session,
            row,
            season_year=season_year,
            athletes_by_provider=athletes_by_provider,
            athletes_by_name=athletes_by_name,
        )

        if team is not None:
            row.fantasy_team_id = str(team.id)
            row.fantasy_team_name = team.name

        if athlete is not None:
            row.athlete_id = str(athlete.id)
            row.athlete_name = athlete.canonical_name
            if athlete.id in seen_athletes:
                row.issues.append(
                    PreviewRowIssue(
                        code="duplicate_athlete_in_file",
                        message=(
                            f"Calciatore già presente alla riga {seen_athletes[athlete.id]}."
                        ),
                        severity="error",
                    )
                )
            else:
                seen_athletes[athlete.id] = parsed.row_number

            owner = owned_elsewhere.get(athlete.id)
            if owner is not None and (team is None or owner.id != team.id):
                row.issues.append(
                    PreviewRowIssue(
                        code="athlete_already_owned",
                        message=(
                            f"Il calciatore appartiene già alla squadra «{owner.name}»."
                        ),
                        severity="error",
                    )
                )
            elif owner is not None and team is not None and owner.id == team.id:
                row.issues.append(
                    PreviewRowIssue(
                        code="athlete_already_on_team",
                        message="Il calciatore è già nella rosa di questa squadra.",
                        severity="error",
                    )
                )

        if team is not None and row.status != "ambiguous" and not any(
            issue.severity == "error" for issue in row.issues
        ):
            available = claimed_slots.get(team.id, [])
            if not available:
                row.issues.append(
                    PreviewRowIssue(
                        code="roster_full",
                        message=f"Nessuno slot libero (capacità {roster_size}).",
                        severity="error",
                    )
                )
            else:
                slot_index = available.pop(0)
                row.slot_index = slot_index
                if row.crediti is not None and row.crediti > 0 and athlete is not None:
                    projected_spend[team.id] += row.crediti
                    remaining = balances[team.id] - projected_spend[team.id]
                    if remaining < 0:
                        row.issues.append(
                            PreviewRowIssue(
                                code="insufficient_credits",
                                message=(
                                    "I crediti di acquisto supererebbero il saldo "
                                    f"disponibile ({balances[team.id]})."
                                ),
                                severity="error",
                            )
                        )

        if any(issue.severity == "error" for issue in row.issues):
            row.status = "error"
        elif row.status != "ambiguous":
            row.status = "ok"
        preview_rows.append(row)

    return preview_rows


def _validate_basic_fields(row: PreviewRow, parsed: ParsedCsvRow) -> None:
    if not parsed.squadra:
        row.issues.append(
            PreviewRowIssue(
                code="missing_team",
                message="Nome squadra mancante.",
                severity="error",
            )
        )
    if "_provider_id_invalid" in parsed.raw:
        row.issues.append(
            PreviewRowIssue(
                code="invalid_provider_id",
                message="provider_id non numerico.",
                severity="error",
            )
        )
    if "_crediti_invalid" in parsed.raw:
        row.issues.append(
            PreviewRowIssue(
                code="invalid_purchase_credits",
                message="Crediti non numerici.",
                severity="error",
            )
        )
    elif parsed.crediti is None:
        row.issues.append(
            PreviewRowIssue(
                code="missing_purchase_credits",
                message="Crediti di acquisto mancanti.",
                severity="error",
            )
        )
    elif parsed.crediti < 0:
        row.issues.append(
            PreviewRowIssue(
                code="invalid_purchase_credits",
                message="Il credito di acquisto non può essere negativo.",
                severity="error",
            )
        )
    if not parsed.provider_id and not parsed.nome and "_provider_id_invalid" not in parsed.raw:
        row.issues.append(
            PreviewRowIssue(
                code="missing_athlete_key",
                message="Indica provider_id oppure nome calciatore.",
                severity="error",
            )
        )


def _resolve_team(
    row: PreviewRow,
    teams_by_key: dict[str, list[FantasyTeam]],
) -> FantasyTeam | None:
    if not row.squadra:
        return None
    matches = teams_by_key.get(normalize_team_key(row.squadra), [])
    if not matches:
        row.issues.append(
            PreviewRowIssue(
                code="team_not_found",
                message=f"Nessuna squadra fantasy corrisponde a «{row.squadra}».",
                severity="error",
            )
        )
        return None
    if len(matches) > 1:
        row.issues.append(
            PreviewRowIssue(
                code="ambiguous_team_name",
                message=f"Più squadre corrispondono a «{row.squadra}».",
                severity="error",
            )
        )
        return None
    return matches[0]


def _resolve_athlete(
    session: Session,
    row: PreviewRow,
    *,
    season_year: int,
    athletes_by_provider: dict[int, Athlete],
    athletes_by_name: dict[str, list[Athlete]],
) -> Athlete | None:
    if row.provider_id is not None:
        athlete = athletes_by_provider.get(row.provider_id)
        if athlete is None:
            row.issues.append(
                PreviewRowIssue(
                    code="athlete_not_found",
                    message=f"Nessun calciatore con provider_id {row.provider_id}.",
                    severity="error",
                )
            )
            return None
        if row.nome and normalize_athlete_name(row.nome) != normalize_athlete_name(
            athlete.canonical_name
        ):
            row.issues.append(
                PreviewRowIssue(
                    code="name_mismatch",
                    message=(
                        f"Il nome «{row.nome}» non coincide con "
                        f"«{athlete.canonical_name}» (usato provider_id)."
                    ),
                    severity="warning",
                )
            )
        _warn_if_not_on_listone(session, row, athlete_id=athlete.id, season_year=season_year)
        return athlete

    if not row.nome:
        return None

    matches = athletes_by_name.get(normalize_athlete_name(row.nome), [])
    if not matches:
        row.issues.append(
            PreviewRowIssue(
                code="athlete_not_found",
                message=f"Nessun calciatore trovato per il nome «{row.nome}».",
                severity="error",
            )
        )
        return None
    if len(matches) > 1:
        row.status = "ambiguous"
        row.candidates = [
            AthleteCandidate(
                athlete_id=str(athlete.id),
                provider_id=athlete.provider_id,
                canonical_name=athlete.canonical_name,
            )
            for athlete in matches[:20]
        ]
        row.issues.append(
            PreviewRowIssue(
                code="ambiguous_athlete_name",
                message="Nome ambiguo: seleziona il calciatore corretto.",
                severity="error",
            )
        )
        return None

    athlete = matches[0]
    _warn_if_not_on_listone(session, row, athlete_id=athlete.id, season_year=season_year)
    return athlete


def _warn_if_not_on_listone(
    session: Session,
    row: PreviewRow,
    *,
    athlete_id: UUID,
    season_year: int,
) -> None:
    assignment = get_role_assignment(session, athlete_id=athlete_id, season_year=season_year)
    if assignment is None:
        row.issues.append(
            PreviewRowIssue(
                code="athlete_not_on_listone",
                message="Calciatore assente dal listone della stagione (avviso).",
                severity="warning",
            )
        )


def count_preview_issues(rows: list[PreviewRow]) -> tuple[int, int]:
    errors = sum(
        1
        for row in rows
        if row.status in {"error", "ambiguous"}
        or any(issue.severity == "error" for issue in row.issues)
    )
    warnings = sum(
        1 for row in rows for issue in row.issues if issue.severity == "warning"
    )
    return errors, warnings


def recompute_slot_assignments(
    session: Session,
    *,
    league_id: UUID,
    rows: list[PreviewRow],
) -> list[PreviewRow]:
    """Re-assign free slots and credit checks after ambiguity resolutions."""
    teams = {
        team.id: team
        for team in session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.league_id == league_id)
            .options(selectinload(FantasyTeam.slots))
        ).all()
    }
    roster_size = resolve_roster_size(session, league_id)
    claimed_slots: dict[UUID, list[int]] = {}
    balances: dict[UUID, int] = {}
    for team in teams.values():
        claimed_slots[team.id] = [
            slot.slot_index
            for slot in sorted(team.slots, key=lambda row: row.slot_index)
            if slot.athlete_id is None
        ]
        account = find_account_for_team(session, team.id)
        balances[team.id] = account.balance if account is not None else 0

    projected_spend: dict[UUID, int] = defaultdict(int)
    for row in rows:
        row.slot_index = None
        row.issues = [
            issue
            for issue in row.issues
            if issue.code not in {"roster_full", "insufficient_credits"}
        ]
        if row.status == "ambiguous" or any(issue.severity == "error" for issue in row.issues):
            if any(issue.severity == "error" for issue in row.issues):
                row.status = "error"
            continue
        if not row.fantasy_team_id or not row.athlete_id or row.crediti is None:
            row.status = "error"
            continue
        team_id = UUID(row.fantasy_team_id)
        available = claimed_slots.get(team_id, [])
        if not available:
            row.issues.append(
                PreviewRowIssue(
                    code="roster_full",
                    message=f"Nessuno slot libero (capacità {roster_size}).",
                    severity="error",
                )
            )
            row.status = "error"
            continue
        row.slot_index = available.pop(0)
        if row.crediti > 0:
            projected_spend[team_id] += row.crediti
            if balances[team_id] - projected_spend[team_id] < 0:
                row.issues.append(
                    PreviewRowIssue(
                        code="insufficient_credits",
                        message=(
                            "I crediti di acquisto supererebbero il saldo "
                            f"disponibile ({balances[team_id]})."
                        ),
                        severity="error",
                    )
                )
                row.status = "error"
                continue
        row.status = "ok"
    return rows

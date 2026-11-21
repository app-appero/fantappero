"""Preview builder for roster CSV import (EP05-04)."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.text_folding import repair_provider_text
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from fantasy_teams.csv_import import (
    AthleteCandidate,
    ParsedCsvRow,
    PreviewRow,
    PreviewRowIssue,
    normalize_athlete_name,
    normalize_team_key,
    select_name_matches,
    surname_lookup_keys,
)
from fantasy_teams.factory import resolve_roster_size
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.competition import Competition
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.listone.generate import _competition_filter_clause, get_role_assignment
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


def build_preview_rows(
    session: Session,
    *,
    league_id: UUID,
    season_year: int,
    parsed_rows: list[ParsedCsvRow],
    competition_ids: set[UUID] | None = None,
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
    athletes_by_surname: dict[str, list[Athlete]] = defaultdict(list)

    def index_athletes(rows: list[Athlete]) -> None:
        for athlete in rows:
            athletes_by_name[normalize_athlete_name(athlete.canonical_name)].append(athlete)
            for surname_key in surname_lookup_keys(athlete.canonical_name, athlete.last_name):
                athletes_by_surname[surname_key].append(athlete)

    if names:
        # Per nome si cerca solo nel listone della lega (stagione e campionati scelti):
        # i candidati presi da tutto il catalogo rendevano ambiguo un nome unico nel
        # listone, e scegliere un omonimo fuori listone faceva fallire la conferma con
        # `role_unresolved` (QA 19/11). Il provider_id resta cercato su tutto il catalogo.
        listone_athlete_ids = select(RoleAssignment.athlete_id).where(
            RoleAssignment.season_year == season_year
        )
        if competition_ids:
            listone_athlete_ids = listone_athlete_ids.where(
                _competition_filter_clause(season_year=season_year, competition_ids=competition_ids)
            )
        # Il confronto con la chiave normalizzata (senza accenti e maiuscole, spazi
        # singoli, İ e ı turche) gira sempre su tutto il listone della lega (QA 18/11;
        # campionati dal 19/11). Prima partiva solo per i nomi che la ricerca SQL "come
        # scritto" non trovava: se quella trovava un solo omonimo, l'altro con l'accento
        # restava fuori e "toni fernandez" finiva in silenzio su uno dei due Toni
        # Fernández invece di diventare ambiguo (QA 19-20/11). Si leggono solo id e
        # nomi; le schede complete solo dei calciatori che combaciano.
        matching_ids = [
            athlete_id
            for athlete_id, canonical_name, last_name in session.execute(
                select(Athlete.id, Athlete.canonical_name, Athlete.last_name).where(
                    Athlete.id.in_(listone_athlete_ids)
                )
            ).all()
            if normalize_athlete_name(canonical_name) in names
            or surname_lookup_keys(canonical_name, last_name) & names
        ]
        if matching_ids:
            index_athletes(
                list(
                    session.scalars(
                        select(Athlete)
                        .where(Athlete.id.in_(matching_ids))
                        .order_by(Athlete.canonical_name.asc(), Athlete.provider_id.asc())
                    ).all()
                )
            )

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
            athletes_by_surname=athletes_by_surname,
            competition_ids=competition_ids,
        )

        if team is not None:
            row.fantasy_team_id = str(team.id)
            row.fantasy_team_name = team.name

        if athlete is not None:
            row.athlete_id = str(athlete.id)
            # Il nome salvato può essere ancora rovinato ("D. O&apos;Shea", QA 21/11): l'anteprima
            # lo mostra riparato.
            row.athlete_name = repair_provider_text(athlete.canonical_name)
            if athlete.id in seen_athletes:
                row.issues.append(
                    PreviewRowIssue(
                        code="duplicate_athlete_in_file",
                        message=(f"Calciatore già presente alla riga {seen_athletes[athlete.id]}."),
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
                        message=(f"Il calciatore appartiene già alla squadra «{owner.name}»."),
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

        if (
            team is not None
            and row.status != "ambiguous"
            and not any(issue.severity == "error" for issue in row.issues)
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

    _describe_candidates(
        session,
        preview_rows,
        league_id=league_id,
        season_year=season_year,
        competition_ids=competition_ids,
    )
    return preview_rows


def _describe_candidates(
    session: Session,
    rows: list[PreviewRow],
    *,
    league_id: UUID,
    season_year: int,
    competition_ids: set[UUID] | None,
) -> None:
    """Ruolo nella lega, squadra e campionato dei candidati di un nome ambiguo.

    Decisione 19-20/11: con due omonimi (es. Toni Fernández del Barcelona e del
    Venezia) chi importa deve poter scegliere quello giusto, su web e mobile.
    """
    athlete_ids = list(
        dict.fromkeys(UUID(candidate.athlete_id) for row in rows for candidate in row.candidates)
    )
    if not athlete_ids:
        return
    roles = resolve_effective_athlete_roles(
        session,
        league_id=league_id,
        athlete_ids=athlete_ids,
        season_year=season_year,
        competition_ids=competition_ids,
    )
    club_ids = {item.club_id for item in roles.values() if item.club_id is not None}
    club_names: dict[UUID, str] = {}
    competitions: dict[UUID, list[str]] = defaultdict(list)
    if club_ids:
        club_names = {
            club_id: name
            for club_id, name in session.execute(
                select(Club.id, Club.name).where(Club.id.in_(club_ids))
            ).all()
        }
        competition_stmt = (
            select(CompetitionSeasonClub.club_id, Competition.name)
            .join(SportSeason, SportSeason.id == CompetitionSeasonClub.sport_season_id)
            .join(Competition, Competition.id == SportSeason.competition_id)
            .where(
                CompetitionSeasonClub.club_id.in_(club_ids),
                SportSeason.year == season_year,
            )
            .order_by(Competition.name.asc())
        )
        if competition_ids:
            competition_stmt = competition_stmt.where(
                SportSeason.competition_id.in_(competition_ids)
            )
        for club_id, competition_name in session.execute(competition_stmt).all():
            if competition_name not in competitions[club_id]:
                competitions[club_id].append(competition_name)
    for row in rows:
        for candidate in row.candidates:
            effective = roles.get(UUID(candidate.athlete_id))
            if effective is None:
                continue
            candidate.role = effective.role.value
            if effective.club_id is not None:
                candidate.club_name = club_names.get(effective.club_id)
                candidate.competition_name = ", ".join(competitions[effective.club_id]) or None


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
    athletes_by_surname: dict[str, list[Athlete]],
    competition_ids: set[UUID] | None = None,
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
                        f"«{repair_provider_text(athlete.canonical_name)}» (usato provider_id)."
                    ),
                    severity="warning",
                )
            )
        _warn_if_not_on_listone(
            session,
            row,
            athlete_id=athlete.id,
            season_year=season_year,
            competition_ids=competition_ids,
        )
        return athlete

    if not row.nome:
        return None

    matches, match_mode = select_name_matches(
        row.nome,
        by_exact=athletes_by_name,
        by_surname=athletes_by_surname,
    )
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
                canonical_name=repair_provider_text(athlete.canonical_name),
            )
            for athlete in matches[:20]
        ]
        row.issues.append(
            PreviewRowIssue(
                code="ambiguous_athlete_name",
                message="Nome ambiguo: seleziona il calciatore corretto.",
                # Avviso, non errore: la riga resta "ambiguous" e si sblocca
                # scegliendo un candidato in conferma (QA 18/11).
                severity="warning",
            )
        )
        return None

    athlete = matches[0]
    if match_mode == "surname":
        row.issues.append(
            PreviewRowIssue(
                code="matched_by_surname",
                message=(
                    f"Riconosciuto come «{repair_provider_text(athlete.canonical_name)}» "
                    "dal cognome."
                ),
                severity="warning",
            )
        )
    _warn_if_not_on_listone(
        session,
        row,
        athlete_id=athlete.id,
        season_year=season_year,
        competition_ids=competition_ids,
    )
    return athlete


def _warn_if_not_on_listone(
    session: Session,
    row: PreviewRow,
    *,
    athlete_id: UUID,
    season_year: int,
    competition_ids: set[UUID] | None = None,
) -> None:
    assignment = get_role_assignment(
        session,
        athlete_id=athlete_id,
        season_year=season_year,
        competition_ids=competition_ids,
    )
    if assignment is None:
        row.issues.append(
            PreviewRowIssue(
                code="athlete_not_on_listone",
                message="Calciatore assente dal listone della stagione (avviso).",
                severity="warning",
            )
        )


_UNMATCHED_ATHLETE_CODES = frozenset({"athlete_not_found", "missing_athlete_key"})


def skip_unmatched_excel_rows(rows: list[PreviewRow]) -> None:
    """Leave the roster unchanged when Excel names no athlete of the listone.

    Un nome di più calciatori invece non si ignora: la riga resta `ambiguous`, con
    ruolo, squadra e campionato dei candidati, e chi importa sceglie quello giusto
    prima di confermare, su web e mobile (decisione 19-20/11).
    """
    for row in rows:
        if row.athlete_id is not None or row.fantasy_team_id is None:
            continue
        if row.status == "ambiguous" or row.candidates:
            continue
        if not any(issue.code in _UNMATCHED_ATHLETE_CODES for issue in row.issues):
            continue
        row.status = "skipped"
        row.slot_index = None
        row.athlete_id = None
        row.athlete_name = None
        row.candidates = []
        row.issues = [
            PreviewRowIssue(
                code="athlete_not_found",
                message="Calciatore non trovato: riga ignorata. Aggiungilo a mano se serve.",
                severity="warning",
            )
        ]


def count_preview_issues(rows: list[PreviewRow]) -> tuple[int, int]:
    """Righe con errori bloccanti e numero di avvisi.

    Un nome ambiguo non è un errore: è un avviso (QA 18/11) che si risolve scegliendo
    il candidato in conferma, quindi non entra in `errorCount` (QA 19-20/11). Le righe
    ancora da scegliere le conta `count_unresolved_ambiguities`.
    """
    errors = sum(
        1
        for row in rows
        if row.status == "error" or any(issue.severity == "error" for issue in row.issues)
    )
    warnings = sum(1 for row in rows for issue in row.issues if issue.severity == "warning")
    return errors, warnings


def count_unresolved_ambiguities(rows: list[PreviewRow]) -> int:
    """Righe con un nome di più calciatori ancora senza scelta."""
    return sum(1 for row in rows if row.status == "ambiguous")


def has_unresolved_ambiguities(rows: list[PreviewRow]) -> bool:
    """La conferma resta bloccata finché ogni nome ambiguo non ha il suo calciatore."""
    return count_unresolved_ambiguities(rows) > 0


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
        if row.status == "skipped":
            continue
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

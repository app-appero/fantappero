"""Ruoli del listone ufficiale dal pannello operatore (22/11).

I ruoli ufficiali sono congelati per la stagione (`generate._upsert_assignment`): cambiano
solo con un'azione esplicita dell'operatore, da qui.

- «Ripristina i ruoli cambiati da un aggiornamento» (`restore_roles`): dopo l'aggiornamento
  del 21/11 su pilota, che ha cambiato ruoli già nelle rose, ricostruisce il ruolo di prima
  dalle risposte del fornitore salvate (`reconstruct_roles_before`) e lo riapplica.
- «Aggiorna anche i ruoli dal fornitore» (`provider_roles`): anteprima dei ruoli che il
  fornitore cambierebbe oggi (`compute_provider_role_changes`, le stesse differenze che
  l'aggiornamento conta in ``roleChangesSkipped``) e, dopo la conferma, la loro applicazione.

Ogni modifica ricalcola le rose che contengono i calciatori toccati
(`resync_team_compositions`) e lascia una riga di audit di piattaforma.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from admin.schemas import (
    AdminListoneProviderRoleEntry,
    AdminListoneProviderRolesCounts,
    AdminListoneProviderRolesResponse,
    AdminListoneRoleRestoreCounts,
    AdminListoneRoleRestoreEntry,
    AdminListoneRoleRestoreResponse,
)
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from database.enums import FantasyRole, LeagueAuditAction, LeagueState
from fantasy_teams.composition_service import (
    resolve_effective_athlete_roles,
    resolve_league_rules_limits,
    resync_team_compositions,
)
from fantasy_teams.models import FantasyRosterSlot
from leagues.listone_refresh_progress import load_active_job_id, load_progress
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from observability.logging import get_logger
from sports_data.catalog.models import Club
from sports_data.listone.generate import compute_provider_role_changes
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.listone.overrides import effective_role_for_athlete
from sports_data.listone.reconstruct import reconstruct_roles_before
from sports_data.roster.models import Athlete

_logger = get_logger(__name__)

#: Leghe ferme: le rose non si ricalcolano (come `resync_team_compositions`).
_FROZEN_LEAGUE_STATES = (LeagueState.CONCLUDED, LeagueState.ARCHIVED)
_CHUNK = 1000


@dataclass(frozen=True)
class RosterImpact:
    #: Nomi delle leghe (non concluse) in cui il calciatore è in rosa.
    in_rosters: dict[UUID, list[str]]
    rosters_over_quota_now: int
    rosters_over_quota_after: int


def roster_impact(
    session: Session,
    *,
    season_year: int,
    new_roles: Mapping[UUID, FantasyRole],
) -> RosterImpact:
    """Dove sono in rosa i calciatori e quante rose sono fuori quota ora e con i nuovi ruoli.

    Stessi ruoli della valutazione della rosa (`resolve_effective_athlete_roles`, override di
    lega compresi); una rosa è fuori quota se un ruolo supera il limite del regolamento.
    """
    ids = list(new_roles)
    in_rosters: dict[UUID, set[str]] = {}
    teams_by_league: dict[UUID, set[UUID]] = {}
    for start in range(0, len(ids), _CHUNK):
        chunk = ids[start : start + _CHUNK]
        rows = session.execute(
            select(
                FantasyRosterSlot.athlete_id,
                FantasyRosterSlot.fantasy_team_id,
                League.id,
                League.name,
            )
            .join(League, League.id == FantasyRosterSlot.league_id)
            .where(
                FantasyRosterSlot.athlete_id.in_(chunk),
                League.season_year == season_year,
                League.state.not_in(_FROZEN_LEAGUE_STATES),
            )
        ).all()
        for athlete_id, team_id, league_id, league_name in rows:
            in_rosters.setdefault(athlete_id, set()).add(league_name)
            teams_by_league.setdefault(league_id, set()).add(team_id)

    over_now = 0
    over_after = 0
    for league_id, team_ids in teams_by_league.items():
        athletes_by_team: dict[UUID, list[UUID]] = {}
        for team_id, athlete_id in session.execute(
            select(FantasyRosterSlot.fantasy_team_id, FantasyRosterSlot.athlete_id).where(
                FantasyRosterSlot.fantasy_team_id.in_(team_ids),
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all():
            athletes_by_team.setdefault(team_id, []).append(athlete_id)
        resolved = resolve_effective_athlete_roles(
            session,
            league_id=league_id,
            athlete_ids=[a for athletes in athletes_by_team.values() for a in athletes],
            season_year=season_year,
        )
        overrides = {
            row.athlete_id: row
            for row in session.scalars(
                select(LeagueRoleOverride).where(
                    LeagueRoleOverride.league_id == league_id,
                    LeagueRoleOverride.athlete_id.in_(ids),
                    LeagueRoleOverride.superseded_at.is_(None),
                )
            ).all()
        }
        limits = resolve_league_rules_limits(session, league_id)
        for athletes in athletes_by_team.values():
            now: Counter[FantasyRole] = Counter()
            after: Counter[FantasyRole] = Counter()
            for athlete_id in athletes:
                item = resolved.get(athlete_id)
                if item is not None:
                    now[item.role] += 1
                if athlete_id in new_roles:
                    after[
                        effective_role_for_athlete(
                            official_role=new_roles[athlete_id],
                            override=overrides.get(athlete_id),
                            current_round=0,
                        )
                    ] += 1
                elif item is not None:
                    after[item.role] += 1
            if any(now[role] > limits.for_role(role) for role in FantasyRole):
                over_now += 1
            if any(after[role] > limits.for_role(role) for role in FantasyRole):
                over_after += 1
    return RosterImpact(
        in_rosters={athlete_id: sorted(names) for athlete_id, names in in_rosters.items()},
        rosters_over_quota_now=over_now,
        rosters_over_quota_after=over_after,
    )


def _ensure_no_refresh_running() -> None:
    # Import locale: admin.listone_service usa questo modulo per l'anteprima dei ruoli.
    from admin.listone_service import PLATFORM_JOB_SCOPE

    job_id = load_active_job_id(PLATFORM_JOB_SCOPE)
    progress = load_progress(job_id) if job_id else None
    if progress is not None and progress.status in {"queued", "running"}:
        raise ValidationAuthError(
            "C'è un aggiornamento del listone in corso: riprova quando è finito.",
            code="listone_refresh_running",
        )


class AdminListoneRolesService:
    """Cambi espliciti dei ruoli ufficiali del listone, solo operatore (``global:operate``)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _names(self, athlete_ids: Collection[UUID]) -> dict[UUID, str]:
        ids = list(athlete_ids)
        out: dict[UUID, str] = {}
        for start in range(0, len(ids), _CHUNK):
            out.update(
                self._session.execute(
                    select(Athlete.id, Athlete.canonical_name).where(
                        Athlete.id.in_(ids[start : start + _CHUNK])
                    )
                ).all()
            )
        return out

    def _club_names(self, club_ids: Collection[UUID | None]) -> dict[UUID, str]:
        ids = [club_id for club_id in set(club_ids) if club_id is not None]
        if not ids:
            return {}
        return dict(self._session.execute(select(Club.id, Club.name).where(Club.id.in_(ids))).all())

    def _audit(self, *, actor: User, operation: str, details: dict[str, object]) -> None:
        self._session.add(
            LeagueAuditEvent(
                league_id=None,
                actor_id=actor.id,
                action=LeagueAuditAction.LEAGUE_LISTONE_REFRESHED,
                details={"operation": operation, **details},
            )
        )
        self._session.flush()

    def restore_roles(
        self,
        *,
        actor: User,
        season_year: int,
        before: datetime,
        dry_run: bool,
        athlete_ids: Collection[str] | None = None,
    ) -> AdminListoneRoleRestoreResponse:
        """Riporta al ruolo di prima di ``before`` chi l'ha cambiato dopo ``before``.

        Candidati: le assegnazioni della stagione aggiornate dopo ``before`` il cui ruolo
        ricostruito dalle risposte del fornitore salvate prima è diverso. Un calciatore che
        aveva già l'assegnazione prima di ``before`` ma non è ricostruibile si elenca come
        «non ricostruibile» e non si tocca. Con ``dry_run`` non scrive nulla; altrimenti
        applica i ruoli (solo ``athlete_ids`` se indicati: quelli dell'anteprima confermata),
        ricalcola le rose e lascia l'audit. Idempotente: dopo il ripristino il ruolo coincide
        con quello ricostruito e il calciatore non è più un candidato.
        """
        if not dry_run:
            _ensure_no_refresh_running()
        rows = list(
            self._session.execute(
                select(RoleAssignment).where(
                    RoleAssignment.season_year == season_year,
                    RoleAssignment.updated_at > before,
                )
            ).scalars()
        )
        reconstructed = reconstruct_roles_before(
            self._session,
            season_year=season_year,
            before=before,
            athlete_ids=[row.athlete_id for row in rows],
        )
        to_restore = []
        not_reconstructible = []
        for row in rows:
            found = reconstructed.get(row.athlete_id)
            if found is None:
                if row.created_at <= before:
                    not_reconstructible.append(row)
                continue
            if found.role != row.role:
                to_restore.append((row, found))

        names = self._names([row.athlete_id for row in rows])
        clubs = self._club_names(
            [row.club_id for row in rows] + [found.club_id for _, found in to_restore]
        )
        impact = roster_impact(
            self._session,
            season_year=season_year,
            new_roles={row.athlete_id: found.role for row, found in to_restore},
        )
        entries = [
            AdminListoneRoleRestoreEntry(
                athleteId=str(row.athlete_id),
                name=names.get(row.athlete_id, ""),
                club=clubs.get(row.club_id) if row.club_id else None,
                currentRole=row.role.value,  # type: ignore[arg-type]
                restoredRole=found.role.value,  # type: ignore[arg-type]
                reconstructible=True,
                restoredPosition=found.provider_position_raw,
                restoredClub=clubs.get(found.club_id),
                restoredSource=found.source,
                inRosters=impact.in_rosters.get(row.athlete_id, []),
            )
            for row, found in to_restore
        ]
        not_reconstructible_impact = roster_impact(
            self._session,
            season_year=season_year,
            new_roles={row.athlete_id: row.role for row in not_reconstructible},
        )
        entries += [
            AdminListoneRoleRestoreEntry(
                athleteId=str(row.athlete_id),
                name=names.get(row.athlete_id, ""),
                club=clubs.get(row.club_id) if row.club_id else None,
                currentRole=row.role.value,  # type: ignore[arg-type]
                restoredRole=None,
                reconstructible=False,
                inRosters=not_reconstructible_impact.in_rosters.get(row.athlete_id, []),
            )
            for row in not_reconstructible
        ]
        entries.sort(key=lambda entry: (not entry.reconstructible, entry.name.casefold()))

        selected = set(athlete_ids) if athlete_ids is not None else None
        applied = [
            (row, found)
            for row, found in to_restore
            if selected is None or str(row.athlete_id) in selected
        ]
        restored = 0
        resynced = 0
        if not dry_run and applied:
            changes = [
                {"athleteId": str(row.athlete_id), "from": row.role.value, "to": found.role.value}
                for row, found in applied
            ]
            for row, found in applied:
                row.role = found.role
                row.provider_position_raw = found.provider_position_raw
            self._session.flush()
            restored = len(applied)
            resynced = resync_team_compositions(
                self._session,
                athlete_ids=[row.athlete_id for row, _ in applied],
                season_year=season_year,
            )
            self._audit(
                actor=actor,
                operation="listone_roles_restored",
                details={
                    "seasonYear": season_year,
                    "before": before.isoformat(),
                    "restored": restored,
                    "rostersResynced": resynced,
                    "changes": changes,
                },
            )
        if not dry_run:
            _logger.info(
                "admin_listone_roles_restored",
                extra={
                    "event": "admin_listone_roles_restored",
                    "actor_id": str(actor.id),
                    "season_year": season_year,
                    "before": before.isoformat(),
                    "restored": restored,
                    "not_reconstructible": len(not_reconstructible),
                    "rosters_resynced": resynced,
                    "athlete_ids": [str(row.athlete_id) for row, _ in applied],
                },
            )
        return AdminListoneRoleRestoreResponse(
            seasonYear=season_year,
            before=before,
            dryRun=dry_run,
            entries=entries,
            counts=AdminListoneRoleRestoreCounts(
                toRestore=len(to_restore),
                notReconstructible=len(not_reconstructible),
                restored=restored,
                rostersOverQuotaNow=impact.rosters_over_quota_now,
                rostersOverQuotaAfter=impact.rosters_over_quota_after,
                rostersResynced=resynced,
            ),
        )

    def provider_roles(
        self,
        *,
        actor: User | None,
        season_year: int,
        dry_run: bool,
        athlete_ids: Collection[str] | None = None,
    ) -> AdminListoneProviderRolesResponse:
        """Ruoli ufficiali da allineare alla posizione del fornitore di oggi.

        Con ``dry_run`` (anteprima, anche nel risultato di «Aggiorna listone» con
        ``updateRoles``) elenca chi cambierebbe ruolo, dove è in rosa e quante rose
        andrebbero fuori quota. Con la conferma applica i ruoli (solo ``athlete_ids`` se
        indicati: quelli dell'anteprima), ricalcola le rose e scrive l'audit. Idempotente.
        """
        if not dry_run:
            _ensure_no_refresh_running()
        changes = compute_provider_role_changes(self._session, season_year=season_year)
        names = self._names([change.assignment.athlete_id for change in changes])
        clubs = self._club_names([change.membership.club_id for change in changes])
        impact = roster_impact(
            self._session,
            season_year=season_year,
            new_roles={change.assignment.athlete_id: change.new_role for change in changes},
        )
        entries = sorted(
            (
                AdminListoneProviderRoleEntry(
                    athleteId=str(change.assignment.athlete_id),
                    name=names.get(change.assignment.athlete_id, ""),
                    club=clubs.get(change.membership.club_id),
                    currentRole=change.assignment.role.value,  # type: ignore[arg-type]
                    newRole=change.new_role.value,  # type: ignore[arg-type]
                    providerPositionRaw=change.membership.provider_position_raw,
                    inRosters=impact.in_rosters.get(change.assignment.athlete_id, []),
                )
                for change in changes
            ),
            key=lambda entry: entry.name.casefold(),
        )
        selected = set(athlete_ids) if athlete_ids is not None else None
        applied = [
            change
            for change in changes
            if selected is None or str(change.assignment.athlete_id) in selected
        ]
        resynced = 0
        if not dry_run and applied:
            audit_changes = [
                {
                    "athleteId": str(change.assignment.athlete_id),
                    "from": change.assignment.role.value,
                    "to": change.new_role.value,
                }
                for change in applied
            ]
            for change in applied:
                change.assignment.role = change.new_role
                change.assignment.provider_position_raw = change.membership.provider_position_raw
                change.assignment.squad_membership_id = change.membership.id
                change.assignment.club_id = change.membership.club_id
            self._session.flush()
            resynced = resync_team_compositions(
                self._session,
                athlete_ids=[change.assignment.athlete_id for change in applied],
                season_year=season_year,
            )
            if actor is not None:
                self._audit(
                    actor=actor,
                    operation="listone_roles_from_provider",
                    details={
                        "seasonYear": season_year,
                        "applied": len(applied),
                        "rostersResynced": resynced,
                        "changes": audit_changes,
                    },
                )
            _logger.info(
                "admin_listone_roles_from_provider",
                extra={
                    "event": "admin_listone_roles_from_provider",
                    "actor_id": str(actor.id) if actor is not None else None,
                    "season_year": season_year,
                    "applied": len(applied),
                    "rosters_resynced": resynced,
                    "athlete_ids": [str(change.assignment.athlete_id) for change in applied],
                },
            )
        return AdminListoneProviderRolesResponse(
            seasonYear=season_year,
            dryRun=dry_run,
            entries=entries,
            counts=AdminListoneProviderRolesCounts(
                changes=len(changes),
                applied=0 if dry_run else len(applied),
                rostersOverQuotaNow=impact.rosters_over_quota_now,
                rostersOverQuotaAfter=impact.rosters_over_quota_after,
                rostersResynced=resynced,
            ),
        )

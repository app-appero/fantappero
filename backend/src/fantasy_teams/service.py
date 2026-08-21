"""Fantasy team domain service with exclusivity and credit ledger (EP05-01/02/03/06)."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    CreditLedgerReason,
    FantasyRole,
    LeagueAuditAction,
    LeagueMemberRole,
    RosterCompositionStatus,
    RosterImportStatus,
    RosterOwnershipSource,
    UserType,
)
from fantasy_teams.composition import RosterCompositionReport
from fantasy_teams.composition_service import (
    assert_assignment_respects_role_quota,
    evaluate_team_composition,
    resolve_effective_athlete_role,
    resolve_league_rules_limits,
    sync_team_composition_status,
)
from fantasy_teams.csv_import import (
    apply_resolutions,
    csv_template_bytes,
    parse_roster_csv,
    preview_row_from_dict,
    preview_row_to_dict,
    sha256_hex,
)
from fantasy_teams.csv_preview import (
    build_preview_rows,
    count_preview_issues,
    recompute_slot_assignments,
)
from fantasy_teams.factory import (
    ensure_team_for_membership,
    find_team_by_id,
    find_team_for_membership,
    resolve_roster_size,
)
from fantasy_teams.ledger import (
    apply_ledger_movement,
    ensure_credit_account_for_team,
    find_account_for_team,
    reconstruct_balance,
)
from fantasy_teams.models import (
    CreditAccount,
    CreditLedgerEntry,
    FantasyRosterSlot,
    FantasyTeam,
    RosterImportSession,
    RosterOwnershipInterval,
)
from fantasy_teams.ownership import (
    create_turn_snapshot,
    find_snapshot,
    intervals_as_of,
    list_ownership_intervals,
    list_snapshots,
    parse_as_of,
    resolve_slot_role,
    sync_ownership_on_assign,
    sync_ownership_on_release,
)
from fantasy_teams.schemas import (
    AdminCreditMovementRequest,
    AssignRosterSlotRequest,
    CreateRosterTurnSnapshotRequest,
    CreditAccountResponse,
    CreditLedgerEntryResponse,
    CreditLedgerListResponse,
    EnsureFantasyTeamsResponse,
    FantasyRosterSlotResponse,
    FantasyTeamResponse,
    FantasyTeamSummaryResponse,
    RosterAsOfResponse,
    RosterAsOfSlotResponse,
    RosterCompositionCountsResponse,
    RosterCompositionIssueResponse,
    RosterCompositionLimitsResponse,
    RosterCompositionResponse,
    RosterImportAthleteCandidateResponse,
    RosterImportConfirmRequest,
    RosterImportConfirmResponse,
    RosterImportIssueResponse,
    RosterImportPreviewResponse,
    RosterImportRowResponse,
    RosterOccupancyEntryResponse,
    RosterOwnershipHistoryResponse,
    RosterOwnershipIntervalResponse,
    RosterTurnSnapshotDetailResponse,
    RosterTurnSnapshotEntryResponse,
    RosterTurnSnapshotSummaryResponse,
    TeamRosterPlayerResponse,
)
from fantasy_teams.validators import (
    validate_athlete_not_owned_in_league,
    validate_purchase_credits,
    validate_slot_index,
)
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import Club
from sports_data.listone.generate import get_role_assignment
from sports_data.listone.models import RoleAssignment
from sports_data.listone.overrides import effective_role_for_athlete, get_active_override
from sports_data.roster.models import Athlete

logger = get_logger(__name__)


class FantasyTeamService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_my_team(self, league_access: LeagueAccess) -> FantasyTeamResponse:
        membership = self._require_membership(league_access)
        team, created = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access.user, membership),
            actor_id=league_access.user.id,
        )
        if created:
            self._add_audit(
                league_access.league.id,
                league_access.user.id,
                LeagueAuditAction.FANTASY_TEAM_CREATED,
                details={"fantasyTeamId": str(team.id), "membershipId": str(membership.id)},
            )
            get_metrics().incr("fantasy_team_created_total", labels={"result": "success"})
            logger.info("fantasy_team_created", extra={"result": "success"})
            account = find_account_for_team(self._session, team.id)
            if account is not None:
                self._add_audit(
                    league_access.league.id,
                    league_access.user.id,
                    LeagueAuditAction.CREDIT_ACCOUNT_INITIALIZED,
                    details={
                        "fantasyTeamId": str(team.id),
                        "balance": account.balance,
                    },
                )
        self._session.commit()
        team = find_team_for_membership(self._session, membership.id, with_slots=True)
        assert team is not None
        return self._to_team_response(team)

    def list_teams(self, league_access: LeagueAccess) -> list[FantasyTeamSummaryResponse]:
        teams = self._session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.league_id == league_access.league.id)
            .options(
                selectinload(FantasyTeam.slots),
                selectinload(FantasyTeam.membership).selectinload(LeagueMembership.user),
            )
            .order_by(FantasyTeam.created_at.asc())
        ).all()
        roster_size = resolve_roster_size(self._session, league_access.league.id)
        return [self._to_summary(team, roster_size=roster_size) for team in teams]

    def get_team_for_admin(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
    ) -> FantasyTeamResponse:
        """Return a full roster for admin manual assignment (EP05-03)."""
        team = find_team_by_id(
            self._session,
            league_id=league_access.league.id,
            team_id=team_id,
            with_slots=True,
        )
        if team is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        return self._to_team_response(team)

    def get_team_credits_for_admin(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
    ) -> CreditLedgerListResponse:
        """Return credit balance and ledger for any participant team (admin)."""
        team = find_team_by_id(
            self._session,
            league_id=league_access.league.id,
            team_id=team_id,
            with_slots=False,
        )
        if team is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        account, _ = ensure_credit_account_for_team(
            self._session, team, actor_id=league_access.user.id
        )
        self._session.commit()
        entries = self._session.scalars(
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.account_id == account.id)
            .order_by(CreditLedgerEntry.created_at.asc(), CreditLedgerEntry.id.asc())
        ).all()
        return CreditLedgerListResponse(
            fantasyTeamId=str(team.id),
            balance=account.balance,
            version=account.version,
            entries=[self._to_ledger_entry(entry) for entry in entries],
        )

    def ensure_all_teams(self, league_access: LeagueAccess) -> EnsureFantasyTeamsResponse:
        league = self._lock_league(league_access.league.id)
        memberships = self._session.scalars(
            select(LeagueMembership)
            .where(LeagueMembership.league_id == league.id)
            .options(selectinload(LeagueMembership.user).selectinload(User.profile))
            .order_by(LeagueMembership.created_at.asc())
            .with_for_update()
        ).all()
        roster_size = resolve_roster_size(self._session, league.id)
        created = 0
        existing = 0
        summaries: list[FantasyTeamSummaryResponse] = []
        for membership in memberships:
            name = self._default_team_name(membership.user, membership)
            team, was_created = ensure_team_for_membership(
                self._session,
                membership,
                name=name,
                roster_size=roster_size,
                actor_id=league_access.user.id,
            )
            if was_created:
                created += 1
                self._add_audit(
                    league.id,
                    league_access.user.id,
                    LeagueAuditAction.FANTASY_TEAM_CREATED,
                    details={"fantasyTeamId": str(team.id), "membershipId": str(membership.id)},
                )
                account = find_account_for_team(self._session, team.id)
                if account is not None:
                    self._add_audit(
                        league.id,
                        league_access.user.id,
                        LeagueAuditAction.CREDIT_ACCOUNT_INITIALIZED,
                        details={
                            "fantasyTeamId": str(team.id),
                            "balance": account.balance,
                        },
                    )
            else:
                existing += 1
            team = find_team_for_membership(self._session, membership.id, with_slots=True)
            assert team is not None
            summaries.append(self._to_summary(team, roster_size=roster_size))

        self._session.commit()
        get_metrics().incr(
            "fantasy_teams_ensured_total",
            labels={"result": "success"},
        )
        logger.info(
            "fantasy_teams_ensured",
            extra={"created": created, "existing": existing},
        )
        return EnsureFantasyTeamsResponse(created=created, existing=existing, teams=summaries)

    def assign_random_ai_roster(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
        *,
        purchase_credits: int = 0,
    ) -> FantasyTeamResponse:
        """Fill empty slots of an AI manager roster with random free listone athletes."""
        if not self._is_league_admin(league_access):
            raise ValidationAuthError(
                "Solo l'amministratore di lega può assegnare una rosa random.",
                code="admin_required",
            )

        league = self._lock_league(league_access.league.id)
        team = self._get_team_for_update(league.id, team_id)
        membership = self._session.scalar(
            select(LeagueMembership)
            .where(LeagueMembership.id == team.membership_id)
            .options(selectinload(LeagueMembership.user))
            .with_for_update()
        )
        if membership is None or membership.user is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        if membership.user.user_type != UserType.AI:
            raise ValidationAuthError(
                "La rosa random è disponibile solo per i fantallenatori IA.",
                code="not_ai_manager",
            )

        slots = list(
            self._session.scalars(
                select(FantasyRosterSlot)
                .where(FantasyRosterSlot.fantasy_team_id == team.id)
                .order_by(FantasyRosterSlot.slot_index.asc())
                .with_for_update()
            ).all()
        )
        team.slots = slots

        empty_slots = [slot for slot in slots if slot.athlete_id is None]
        if not empty_slots:
            get_metrics().incr("fantasy_roster_random_ai_total", labels={"result": "noop"})
            refreshed = find_team_by_id(
                self._session,
                league_id=league.id,
                team_id=team.id,
                with_slots=True,
            )
            assert refreshed is not None
            return self._to_team_response(refreshed)

        limits = resolve_league_rules_limits(self._session, league.id)
        purchase_credits = validate_purchase_credits(purchase_credits)

        filled_by_role: dict[FantasyRole, int] = {
            FantasyRole.P: 0,
            FantasyRole.D: 0,
            FantasyRole.C: 0,
            FantasyRole.A: 0,
        }
        for slot in slots:
            if slot.athlete_id is None:
                continue
            role = resolve_effective_athlete_role(
                self._session,
                league_id=league.id,
                athlete_id=slot.athlete_id,
                season_year=league.season_year,
            )
            if role is not None:
                filled_by_role[role] += 1

        needed_by_role: dict[FantasyRole, int] = {}
        for role in FantasyRole:
            needed = limits.for_role(role) - filled_by_role[role]
            if needed > 0:
                needed_by_role[role] = needed

        if not needed_by_role:
            get_metrics().incr("fantasy_roster_random_ai_total", labels={"result": "noop"})
            refreshed = find_team_by_id(
                self._session,
                league_id=league.id,
                team_id=team.id,
                with_slots=True,
            )
            assert refreshed is not None
            return self._to_team_response(refreshed)

        owned_athlete_ids = select(FantasyRosterSlot.athlete_id).where(
            FantasyRosterSlot.league_id == league.id,
            FantasyRosterSlot.athlete_id.is_not(None),
        )
        free_rows = self._session.execute(
            select(RoleAssignment.athlete_id, RoleAssignment.role).where(
                RoleAssignment.season_year == league.season_year,
                RoleAssignment.athlete_id.not_in(owned_athlete_ids),
            )
        ).all()

        pool: dict[FantasyRole, list[UUID]] = {
            FantasyRole.P: [],
            FantasyRole.D: [],
            FantasyRole.C: [],
            FantasyRole.A: [],
        }
        for athlete_id, role in free_rows:
            pool[role].append(athlete_id)

        rng = random.Random()
        picks: list[tuple[FantasyRole, UUID]] = []
        for role, needed in needed_by_role.items():
            candidates = list(pool[role])
            if len(candidates) < needed:
                raise ValidationAuthError(
                    (
                        f"Calciatori liberi insufficienti per ruolo {role.value}: "
                        f"servono {needed}, disponibili {len(candidates)}."
                    ),
                    code="insufficient_free_athletes",
                )
            rng.shuffle(candidates)
            for athlete_id in candidates[:needed]:
                picks.append((role, athlete_id))

        if len(picks) > len(empty_slots):
            raise ValidationAuthError(
                "Slot liberi insufficienti per completare la rosa.",
                code="insufficient_empty_slots",
            )

        assigned = 0
        for slot, (_role, athlete_id) in zip(empty_slots, picks, strict=False):
            self._apply_assignment_without_commit(
                league_access,
                team=team,
                slot_index=slot.slot_index,
                athlete_id=athlete_id,
                purchase_credits=purchase_credits,
                skip_per_row_audit=True,
                ownership_source=RosterOwnershipSource.ADMIN,
                ledger_tx_prefix="random-ai",
                audit_source="random_ai",
            )
            assigned += 1

        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.FANTASY_ROSTER_SLOT_ASSIGNED,
            details={
                "fantasyTeamId": str(team.id),
                "source": "random_ai",
                "assignedCount": assigned,
                "purchaseCredits": purchase_credits,
            },
        )
        report = self._sync_composition(team, league, actor_id=league_access.user.id)
        self._session.commit()
        get_metrics().incr("fantasy_roster_random_ai_total", labels={"result": "success"})
        logger.info(
            "fantasy_roster_random_ai_assigned",
            extra={"assigned": assigned, "team_id": str(team.id)},
        )
        refreshed = find_team_by_id(
            self._session,
            league_id=league.id,
            team_id=team.id,
            with_slots=True,
        )
        assert refreshed is not None
        return self._to_team_response(refreshed, composition=report)

    def get_my_credits(self, league_access: LeagueAccess) -> CreditAccountResponse:
        membership = self._require_membership(league_access)
        team, _ = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access.user, membership),
            actor_id=league_access.user.id,
        )
        account = ensure_credit_account_for_team(
            self._session, team, actor_id=league_access.user.id
        )[0]
        self._session.commit()
        reconstructed = reconstruct_balance(self._session, account.id)
        return CreditAccountResponse(
            fantasyTeamId=str(team.id),
            balance=account.balance,
            version=account.version,
            reconstructedBalance=reconstructed,
        )

    def list_my_credit_movements(self, league_access: LeagueAccess) -> CreditLedgerListResponse:
        membership = self._require_membership(league_access)
        team, _ = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access.user, membership),
            actor_id=league_access.user.id,
        )
        account = ensure_credit_account_for_team(
            self._session, team, actor_id=league_access.user.id
        )[0]
        self._session.commit()
        entries = self._session.scalars(
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.account_id == account.id)
            .order_by(CreditLedgerEntry.created_at.asc(), CreditLedgerEntry.id.asc())
        ).all()
        return CreditLedgerListResponse(
            fantasyTeamId=str(team.id),
            balance=account.balance,
            version=account.version,
            entries=[self._to_ledger_entry(entry) for entry in entries],
        )

    def admin_post_credit_movement(
        self,
        league_access: LeagueAccess,
        payload: AdminCreditMovementRequest,
    ) -> CreditLedgerListResponse:
        league = self._lock_league(league_access.league.id)
        try:
            team_id = UUID(payload.fantasy_team_id)
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo squadra non valido.",
                code="invalid_fantasy_team_id",
            ) from exc

        team = self._get_team_for_update(league.id, team_id)
        account = find_account_for_team(self._session, team.id, for_update=True)
        if account is None:
            account, initialized = ensure_credit_account_for_team(
                self._session, team, actor_id=league_access.user.id
            )
            if initialized:
                self._add_audit(
                    league.id,
                    league_access.user.id,
                    LeagueAuditAction.CREDIT_ACCOUNT_INITIALIZED,
                    details={"fantasyTeamId": str(team.id), "balance": account.balance},
                )
            account = find_account_for_team(self._session, team.id, for_update=True)
            assert account is not None

        entry, created = apply_ledger_movement(
            self._session,
            account,
            amount=payload.amount,
            reason=CreditLedgerReason.ADMIN_ADJUSTMENT,
            transaction_id=payload.transaction_id,
            actor_id=league_access.user.id,
            note=payload.note,
        )
        if created:
            self._add_audit(
                league.id,
                league_access.user.id,
                LeagueAuditAction.CREDIT_LEDGER_ENTRY_POSTED,
                details={
                    "fantasyTeamId": str(team.id),
                    "amount": entry.amount,
                    "reason": entry.reason.value,
                    "transactionId": entry.transaction_id,
                    "balanceAfter": entry.balance_after,
                },
            )
            get_metrics().incr(
                "credit_ledger_post_total",
                labels={"result": "success", "reason": entry.reason.value},
            )
            logger.info(
                "credit_ledger_entry_posted",
                extra={"result": "success", "amount": entry.amount},
            )
        else:
            get_metrics().incr(
                "credit_ledger_post_total",
                labels={"result": "idempotent", "reason": entry.reason.value},
            )

        self._session.commit()
        entries = self._session.scalars(
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.account_id == account.id)
            .order_by(CreditLedgerEntry.created_at.asc(), CreditLedgerEntry.id.asc())
        ).all()
        self._session.refresh(account)
        return CreditLedgerListResponse(
            fantasyTeamId=str(team.id),
            balance=account.balance,
            version=account.version,
            entries=[self._to_ledger_entry(row) for row in entries],
        )

    def list_roster_occupancy(
        self,
        league_access: LeagueAccess,
    ) -> list[RosterOccupancyEntryResponse]:
        slots = self._session.scalars(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.league_id == league_access.league.id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
            .options(
                selectinload(FantasyRosterSlot.fantasy_team),
                selectinload(FantasyRosterSlot.athlete),
            )
            .order_by(FantasyRosterSlot.slot_index.asc())
        ).all()
        return [
            RosterOccupancyEntryResponse(
                athleteId=str(slot.athlete_id),
                fantasyTeamId=str(slot.fantasy_team_id),
                teamName=slot.fantasy_team.name,
                athleteName=slot.athlete.canonical_name if slot.athlete is not None else None,
                slotIndex=slot.slot_index,
                purchaseCredits=slot.purchase_credits,
            )
            for slot in slots
            if slot.athlete_id is not None
        ]

    def list_team_players_for_trade(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
    ) -> list[TeamRosterPlayerResponse]:
        """Rosa corrente di una squadra della lega (sola lettura, per proposte di scambio)."""
        team = find_team_by_id(
            self._session,
            league_id=league_access.league.id,
            team_id=team_id,
            with_slots=True,
        )
        if team is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        players: list[TeamRosterPlayerResponse] = []
        for slot in sorted(team.slots, key=lambda row: row.slot_index):
            if slot.athlete_id is None:
                continue
            athlete = slot.athlete
            players.append(
                TeamRosterPlayerResponse(
                    athleteId=str(slot.athlete_id),
                    athleteName=athlete.canonical_name if athlete is not None else "Giocatore",
                    slotIndex=slot.slot_index,
                    purchaseCredits=slot.purchase_credits,
                )
            )
        return players

    def assign_slot(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
        slot_index: int,
        payload: AssignRosterSlotRequest,
    ) -> FantasyTeamResponse:
        league = self._lock_league(league_access.league.id)
        team = self._get_team_for_update(league.id, team_id)
        self._assert_can_edit_team(league_access, team)
        roster_size = resolve_roster_size(self._session, league.id)
        validate_slot_index(slot_index=slot_index, roster_size=roster_size)
        purchase_credits = validate_purchase_credits(payload.purchase_credits)

        try:
            athlete_id = UUID(payload.athlete_id)
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo calciatore non valido.",
                code="invalid_athlete_id",
            ) from exc

        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            self._fail_assign(
                "Calciatore non trovato.",
                code="athlete_not_found",
                result="not_found",
            )

        owner_slot = self._session.scalar(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.league_id == league.id,
                FantasyRosterSlot.athlete_id == athlete_id,
            )
            .with_for_update()
        )
        if owner_slot is not None:
            validate_athlete_not_owned_in_league(
                existing_team_id=owner_slot.fantasy_team_id,
                target_team_id=team.id,
            )

        slot = self._session.scalar(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.slot_index == slot_index,
            )
            .with_for_update()
        )
        if slot is None:
            self._fail_assign("Slot non trovato.", code="slot_not_found", result="slot_not_found")

        assert_assignment_respects_role_quota(
            self._session,
            league=league,
            team=team,
            athlete_id=athlete_id,
            slot_index=slot_index,
        )

        previous_athlete_id = slot.athlete_id
        previous_purchase = slot.purchase_credits
        if previous_athlete_id == athlete_id and previous_purchase == purchase_credits:
            get_metrics().incr("fantasy_roster_assign_total", labels={"result": "noop"})
            self._session.commit()
            refreshed = find_team_for_membership(self._session, team.membership_id, with_slots=True)
            assert refreshed is not None
            return self._to_team_response(refreshed)

        account, _ = ensure_credit_account_for_team(
            self._session, team, actor_id=league_access.user.id
        )
        account = find_account_for_team(self._session, team.id, for_update=True)
        assert account is not None

        if previous_athlete_id is not None and previous_athlete_id != athlete_id:
            previous = self._session.get(Athlete, previous_athlete_id)
            self._refund_purchase(
                account,
                team_id=team.id,
                slot_index=slot_index,
                athlete_id=previous_athlete_id,
                athlete_name=previous.canonical_name if previous is not None else "Calciatore",
                purchase_credits=previous_purchase,
                actor_id=league_access.user.id,
            )

        try:
            with self._session.begin_nested():
                slot.athlete_id = athlete_id
                slot.purchase_credits = purchase_credits
                self._session.flush()
        except IntegrityError as exc:
            get_metrics().incr(
                "fantasy_roster_assign_total",
                labels={"result": "athlete_already_owned"},
            )
            raise ValidationAuthError(
                "Il calciatore appartiene già a un'altra squadra in questa lega.",
                code="athlete_already_owned",
            ) from exc

        if purchase_credits > 0 and previous_athlete_id != athlete_id:
            apply_ledger_movement(
                self._session,
                account,
                amount=-purchase_credits,
                reason=CreditLedgerReason.ROSTER_PURCHASE,
                transaction_id=f"purchase:{team.id}:{slot_index}:{athlete_id}",
                actor_id=league_access.user.id,
                note=f"Acquisto {athlete.canonical_name}",
            )
        elif (
            purchase_credits > 0
            and previous_athlete_id == athlete_id
            and (previous_purchase or 0) != purchase_credits
        ):
            delta = purchase_credits - (previous_purchase or 0)
            if delta != 0:
                apply_ledger_movement(
                    self._session,
                    account,
                    amount=-delta,
                    reason=CreditLedgerReason.ROSTER_PURCHASE,
                    transaction_id=f"purchase-adjust:{team.id}:{slot_index}:{athlete_id}:{purchase_credits}",
                    actor_id=league_access.user.id,
                    note=f"Rettifica prezzo {athlete.canonical_name}",
                )

        ownership = sync_ownership_on_assign(
            self._session,
            league_id=league.id,
            fantasy_team_id=team.id,
            slot_index=slot_index,
            athlete_id=athlete_id,
            purchase_credits=purchase_credits,
            source=self._ownership_source(league_access, csv_import=False),
            previous_athlete_id=previous_athlete_id,
        )
        if ownership.closed is not None:
            self._add_audit(
                league.id,
                league_access.user.id,
                LeagueAuditAction.FANTASY_ROSTER_OWNERSHIP_CLOSED,
                details={
                    "fantasyTeamId": str(team.id),
                    "slotIndex": slot_index,
                    "athleteId": str(ownership.closed.athlete_id),
                    "releasedAt": (
                        ownership.closed.released_at.isoformat()
                        if ownership.closed.released_at
                        else None
                    ),
                    "reason": "replaced",
                },
            )
            get_metrics().incr(
                "fantasy_roster_ownership_total",
                labels={"result": "closed"},
            )
        if ownership.opened is not None:
            get_metrics().incr(
                "fantasy_roster_ownership_total",
                labels={"result": "opened"},
            )
        elif ownership.updated is not None:
            get_metrics().incr(
                "fantasy_roster_ownership_total",
                labels={"result": "updated"},
            )

        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.FANTASY_ROSTER_SLOT_ASSIGNED,
            details={
                "fantasyTeamId": str(team.id),
                "slotIndex": slot_index,
                "athleteId": str(athlete_id),
                "purchaseCredits": purchase_credits,
                "previousAthleteId": str(previous_athlete_id) if previous_athlete_id else None,
            },
        )
        report = self._sync_composition(team, league, actor_id=league_access.user.id)
        self._session.commit()
        get_metrics().incr("fantasy_roster_assign_total", labels={"result": "success"})
        logger.info("fantasy_roster_slot_assigned", extra={"result": "success"})
        refreshed = find_team_for_membership(self._session, team.membership_id, with_slots=True)
        assert refreshed is not None
        return self._to_team_response(refreshed, composition=report)

    def release_slot(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
        slot_index: int,
    ) -> FantasyTeamResponse:
        league = self._lock_league(league_access.league.id)
        team = self._get_team_for_update(league.id, team_id)
        self._assert_can_edit_team(league_access, team)
        roster_size = resolve_roster_size(self._session, league.id)
        validate_slot_index(slot_index=slot_index, roster_size=roster_size)

        slot = self._session.scalar(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.slot_index == slot_index,
            )
            .with_for_update()
        )
        if slot is None:
            raise ValidationAuthError("Slot non trovato.", code="slot_not_found")

        previous_athlete_id = slot.athlete_id
        previous_purchase = slot.purchase_credits
        if previous_athlete_id is None:
            get_metrics().incr("fantasy_roster_release_total", labels={"result": "noop"})
            self._session.commit()
            refreshed = find_team_for_membership(self._session, team.membership_id, with_slots=True)
            assert refreshed is not None
            return self._to_team_response(refreshed)

        account, _ = ensure_credit_account_for_team(
            self._session, team, actor_id=league_access.user.id
        )
        account = find_account_for_team(self._session, team.id, for_update=True)
        assert account is not None
        athlete = self._session.get(Athlete, previous_athlete_id)
        athlete_name = athlete.canonical_name if athlete is not None else "Calciatore"
        self._refund_purchase(
            account,
            team_id=team.id,
            slot_index=slot_index,
            athlete_id=previous_athlete_id,
            athlete_name=athlete_name,
            purchase_credits=previous_purchase,
            actor_id=league_access.user.id,
        )

        slot.athlete_id = None
        slot.purchase_credits = None
        closed = sync_ownership_on_release(
            self._session,
            fantasy_team_id=team.id,
            slot_index=slot_index,
        )
        if closed is not None:
            self._add_audit(
                league.id,
                league_access.user.id,
                LeagueAuditAction.FANTASY_ROSTER_OWNERSHIP_CLOSED,
                details={
                    "fantasyTeamId": str(team.id),
                    "slotIndex": slot_index,
                    "athleteId": str(closed.athlete_id),
                    "releasedAt": closed.released_at.isoformat() if closed.released_at else None,
                    "reason": "released",
                },
            )
            get_metrics().incr(
                "fantasy_roster_ownership_total",
                labels={"result": "closed"},
            )
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.FANTASY_ROSTER_SLOT_RELEASED,
            details={
                "fantasyTeamId": str(team.id),
                "slotIndex": slot_index,
                "athleteId": str(previous_athlete_id),
                "refundedCredits": previous_purchase,
            },
        )
        report = self._sync_composition(team, league, actor_id=league_access.user.id)
        self._session.commit()
        get_metrics().incr("fantasy_roster_release_total", labels={"result": "success"})
        logger.info("fantasy_roster_slot_released", extra={"result": "success"})
        refreshed = find_team_for_membership(self._session, team.membership_id, with_slots=True)
        assert refreshed is not None
        return self._to_team_response(refreshed, composition=report)

    def list_my_ownership_history(
        self,
        league_access: LeagueAccess,
        *,
        active_only: bool = False,
    ) -> RosterOwnershipHistoryResponse:
        membership = self._require_membership(league_access)
        team, _ = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access.user, membership),
            actor_id=league_access.user.id,
        )
        self._session.commit()
        return self._ownership_history_response(team.id, active_only=active_only)

    def list_team_ownership_history(
        self,
        league_access: LeagueAccess,
        team_id: UUID,
        *,
        active_only: bool = False,
    ) -> RosterOwnershipHistoryResponse:
        team = find_team_by_id(
            self._session,
            league_id=league_access.league.id,
            team_id=team_id,
            with_slots=False,
        )
        if team is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        return self._ownership_history_response(team.id, active_only=active_only)

    def get_my_roster_as_of(
        self,
        league_access: LeagueAccess,
        *,
        at: str | None,
    ) -> RosterAsOfResponse:
        membership = self._require_membership(league_access)
        team, _ = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access.user, membership),
            actor_id=league_access.user.id,
        )
        self._session.commit()
        moment = parse_as_of(at)
        rows = intervals_as_of(self._session, fantasy_team_id=team.id, at=moment)
        league = league_access.league
        slots = [
            RosterAsOfSlotResponse(
                slotIndex=row.slot_index,
                athleteId=str(row.athlete_id),
                athleteName=row.athlete.canonical_name if row.athlete is not None else None,
                purchaseCredits=row.purchase_credits,
                acquiredAt=row.acquired_at.isoformat(),
                role=resolve_slot_role(
                    self._session,
                    league_id=league.id,
                    athlete_id=row.athlete_id,
                    season_year=league.season_year,
                ),
            )
            for row in rows
        ]
        return RosterAsOfResponse(
            fantasyTeamId=str(team.id),
            asOf=moment.isoformat(),
            filledSlots=len(slots),
            slots=slots,
        )

    def list_turn_snapshots(
        self,
        league_access: LeagueAccess,
    ) -> list[RosterTurnSnapshotSummaryResponse]:
        snapshots = list_snapshots(self._session, league_id=league_access.league.id)
        return [self._to_snapshot_summary(row) for row in snapshots]

    def get_turn_snapshot(
        self,
        league_access: LeagueAccess,
        round_number: int,
        *,
        team_id: UUID | None = None,
    ) -> RosterTurnSnapshotDetailResponse:
        snapshot = find_snapshot(
            self._session,
            league_id=league_access.league.id,
            round_number=round_number,
            with_entries=True,
        )
        if snapshot is None:
            raise ValidationAuthError(
                "Snapshot del turno non trovato.",
                code="roster_snapshot_not_found",
            )
        return self._to_snapshot_detail(snapshot, created=False, team_id=team_id)

    def create_turn_snapshot_for_league(
        self,
        league_access: LeagueAccess,
        payload: CreateRosterTurnSnapshotRequest,
    ) -> RosterTurnSnapshotDetailResponse:
        league = self._lock_league(league_access.league.id)
        snapshot, created = create_turn_snapshot(
            self._session,
            league_id=league.id,
            round_number=payload.round_number,
            season_year=league.season_year,
            actor_id=league_access.user.id,
        )
        if created:
            self._add_audit(
                league.id,
                league_access.user.id,
                LeagueAuditAction.FANTASY_ROSTER_TURN_SNAPSHOT_CREATED,
                details={
                    "snapshotId": str(snapshot.id),
                    "roundNumber": snapshot.round_number,
                    "entryCount": snapshot.entry_count,
                },
            )
            get_metrics().incr(
                "fantasy_roster_snapshot_total",
                labels={"result": "created"},
            )
            logger.info(
                "fantasy_roster_turn_snapshot_created",
                extra={"result": "created", "round_number": snapshot.round_number},
            )
        else:
            get_metrics().incr(
                "fantasy_roster_snapshot_total",
                labels={"result": "noop"},
            )
        self._session.commit()
        refreshed = find_snapshot(
            self._session,
            league_id=league.id,
            round_number=payload.round_number,
            with_entries=True,
        )
        assert refreshed is not None
        return self._to_snapshot_detail(refreshed, created=created)

    def download_csv_template(self) -> bytes:
        return csv_template_bytes()

    def preview_csv_import(
        self,
        league_access: LeagueAccess,
        *,
        data: bytes,
        filename: str | None,
    ) -> RosterImportPreviewResponse:
        league = self._lock_league(league_access.league.id)
        parsed = parse_roster_csv(data)
        rows = build_preview_rows(
            self._session,
            league_id=league.id,
            season_year=league.season_year,
            parsed_rows=parsed,
            competition_ids={competition.id for competition in league.competitions},
        )
        error_count, warning_count = count_preview_issues(rows)
        payload = {
            "rows": [preview_row_to_dict(row) for row in rows],
        }
        session = RosterImportSession(
            league_id=league.id,
            actor_id=league_access.user.id,
            status=RosterImportStatus.DRAFT,
            file_sha256=sha256_hex(data),
            original_filename=(filename or "")[:255] or None,
            preview_payload=payload,
            row_count=len(rows),
            error_count=error_count,
            warning_count=warning_count,
        )
        self._session.add(session)
        self._session.commit()
        get_metrics().incr(
            "fantasy_roster_csv_preview_total",
            labels={"result": "success" if error_count == 0 else "with_errors"},
        )
        logger.info(
            "fantasy_roster_csv_preview",
            extra={
                "result": "success",
                "row_count": len(rows),
                "error_count": error_count,
                "warning_count": warning_count,
            },
        )
        return self._to_import_preview(session)

    def confirm_csv_import(
        self,
        league_access: LeagueAccess,
        import_id: UUID,
        payload: RosterImportConfirmRequest,
    ) -> RosterImportConfirmResponse:
        league = self._lock_league(league_access.league.id)
        session = self._session.scalars(
            select(RosterImportSession)
            .where(
                RosterImportSession.id == import_id,
                RosterImportSession.league_id == league.id,
            )
            .with_for_update()
        ).first()
        if session is None:
            raise ValidationAuthError(
                "Sessione di import non trovata.",
                code="import_not_found",
            )

        if session.status == RosterImportStatus.CONFIRMED:
            get_metrics().incr(
                "fantasy_roster_csv_confirm_total",
                labels={"result": "noop"},
            )
            confirmed_at = session.confirmed_at or datetime.now(UTC)
            return RosterImportConfirmResponse(
                importId=str(session.id),
                status=session.status.value,
                assignedCount=int(session.preview_payload.get("assignedCount") or 0),
                teamsTouched=int(session.preview_payload.get("teamsTouched") or 0),
                confirmedAt=confirmed_at.isoformat(),
                preview=self._to_import_preview(session),
            )

        rows = [
            preview_row_from_dict(item)
            for item in (session.preview_payload.get("rows") or [])
            if isinstance(item, dict)
        ]
        resolutions: dict[int, UUID] = {}
        for item in payload.resolutions:
            try:
                resolutions[item.row_number] = UUID(item.athlete_id)
            except ValueError as exc:
                raise ValidationAuthError(
                    "Identificativo calciatore non valido nella risoluzione.",
                    code="invalid_athlete_id",
                ) from exc

        rows = apply_resolutions(rows, resolutions)
        rows = recompute_slot_assignments(self._session, league_id=league.id, rows=rows)
        error_count, warning_count = count_preview_issues(rows)
        session.preview_payload = {"rows": [preview_row_to_dict(row) for row in rows]}
        session.error_count = error_count
        session.warning_count = warning_count
        session.row_count = len(rows)

        if error_count > 0:
            self._session.commit()
            get_metrics().incr(
                "fantasy_roster_csv_confirm_total",
                labels={"result": "blocked"},
            )
            raise ValidationAuthError(
                "L'anteprima contiene errori bloccanti: correggi il file o risolvi le ambiguità.",
                code="import_has_errors",
            )

        ok_rows = [row for row in rows if row.status == "ok"]
        if not ok_rows:
            raise ValidationAuthError(
                "Nessuna riga valida da importare.",
                code="import_empty",
            )

        assigned = 0
        teams_touched: set[UUID] = set()
        for row in ok_rows:
            assert row.fantasy_team_id and row.athlete_id and row.slot_index is not None
            assert row.crediti is not None
            team_id = UUID(row.fantasy_team_id)
            athlete_id = UUID(row.athlete_id)
            team = self._get_team_for_update(league.id, team_id)
            self._apply_assignment_without_commit(
                league_access,
                team=team,
                slot_index=row.slot_index,
                athlete_id=athlete_id,
                purchase_credits=row.crediti,
                skip_per_row_audit=True,
            )
            assigned += 1
            teams_touched.add(team_id)

        for team_id in teams_touched:
            team = self._get_team_for_update(league.id, team_id)
            self._sync_composition(team, league, actor_id=league_access.user.id)

        now = datetime.now(UTC)
        session.status = RosterImportStatus.CONFIRMED
        session.confirmed_at = now
        session.preview_payload = {
            "rows": [preview_row_to_dict(row) for row in rows],
            "assignedCount": assigned,
            "teamsTouched": len(teams_touched),
        }
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.FANTASY_ROSTER_CSV_IMPORTED,
            details={
                "importId": str(session.id),
                "fileSha256": session.file_sha256,
                "assignedCount": assigned,
                "teamsTouched": len(teams_touched),
                "rowCount": len(rows),
            },
        )
        self._session.commit()
        get_metrics().incr(
            "fantasy_roster_csv_confirm_total",
            labels={"result": "success"},
        )
        logger.info(
            "fantasy_roster_csv_imported",
            extra={
                "result": "success",
                "assigned_count": assigned,
                "teams_touched": len(teams_touched),
            },
        )
        self._session.refresh(session)
        return RosterImportConfirmResponse(
            importId=str(session.id),
            status=session.status.value,
            assignedCount=assigned,
            teamsTouched=len(teams_touched),
            confirmedAt=now.isoformat(),
            preview=self._to_import_preview(session),
        )

    def _apply_assignment_without_commit(
        self,
        league_access: LeagueAccess,
        *,
        team: FantasyTeam,
        slot_index: int,
        athlete_id: UUID,
        purchase_credits: int,
        skip_per_row_audit: bool = False,
        ownership_source: RosterOwnershipSource = RosterOwnershipSource.CSV_IMPORT,
        ledger_tx_prefix: str = "csv-purchase",
        audit_source: str = "csv_import",
    ) -> None:
        """Assign one athlete inside an open transaction (used by CSV confirm / random AI)."""
        roster_size = resolve_roster_size(self._session, team.league_id)
        validate_slot_index(slot_index=slot_index, roster_size=roster_size)
        purchase_credits = validate_purchase_credits(purchase_credits)

        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            raise ValidationAuthError("Calciatore non trovato.", code="athlete_not_found")

        owner_slot = self._session.scalar(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.league_id == team.league_id,
                FantasyRosterSlot.athlete_id == athlete_id,
            )
            .with_for_update()
        )
        if owner_slot is not None:
            validate_athlete_not_owned_in_league(
                existing_team_id=owner_slot.fantasy_team_id,
                target_team_id=team.id,
            )

        slot = self._session.scalar(
            select(FantasyRosterSlot)
            .where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.slot_index == slot_index,
            )
            .with_for_update()
        )
        if slot is None:
            raise ValidationAuthError("Slot non trovato.", code="slot_not_found")
        if slot.athlete_id is not None:
            raise ValidationAuthError(
                "Lo slot previsto dall'anteprima non è più libero.",
                code="slot_occupied",
            )

        league = self._session.get(League, team.league_id)
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        assert_assignment_respects_role_quota(
            self._session,
            league=league,
            team=team,
            athlete_id=athlete_id,
            slot_index=slot_index,
        )

        account, _ = ensure_credit_account_for_team(
            self._session, team, actor_id=league_access.user.id
        )
        account = find_account_for_team(self._session, team.id, for_update=True)
        assert account is not None

        try:
            with self._session.begin_nested():
                slot.athlete_id = athlete_id
                slot.purchase_credits = purchase_credits
                self._session.flush()
        except IntegrityError as exc:
            raise ValidationAuthError(
                "Il calciatore appartiene già a un'altra squadra in questa lega.",
                code="athlete_already_owned",
            ) from exc

        if purchase_credits > 0:
            apply_ledger_movement(
                self._session,
                account,
                amount=-purchase_credits,
                reason=CreditLedgerReason.ROSTER_PURCHASE,
                transaction_id=f"{ledger_tx_prefix}:{team.id}:{slot_index}:{athlete_id}",
                actor_id=league_access.user.id,
                note=f"Assegnazione {athlete.canonical_name}",
            )

        sync_ownership_on_assign(
            self._session,
            league_id=team.league_id,
            fantasy_team_id=team.id,
            slot_index=slot_index,
            athlete_id=athlete_id,
            purchase_credits=purchase_credits,
            source=ownership_source,
            previous_athlete_id=None,
        )
        get_metrics().incr(
            "fantasy_roster_ownership_total",
            labels={"result": "opened"},
        )

        if not skip_per_row_audit:
            self._add_audit(
                team.league_id,
                league_access.user.id,
                LeagueAuditAction.FANTASY_ROSTER_SLOT_ASSIGNED,
                details={
                    "fantasyTeamId": str(team.id),
                    "slotIndex": slot_index,
                    "athleteId": str(athlete_id),
                    "purchaseCredits": purchase_credits,
                    "source": audit_source,
                },
            )

    def _to_import_preview(self, session: RosterImportSession) -> RosterImportPreviewResponse:
        rows_payload = session.preview_payload.get("rows") or []
        rows: list[RosterImportRowResponse] = []
        if isinstance(rows_payload, list):
            for item in rows_payload:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    RosterImportRowResponse(
                        rowNumber=int(item.get("rowNumber") or 0),
                        squadra=str(item.get("squadra") or ""),
                        providerId=item.get("providerId"),  # type: ignore[arg-type]
                        nome=str(item.get("nome") or ""),
                        crediti=item.get("crediti"),  # type: ignore[arg-type]
                        status=str(item.get("status") or "error"),
                        fantasyTeamId=item.get("fantasyTeamId"),  # type: ignore[arg-type]
                        fantasyTeamName=item.get("fantasyTeamName"),  # type: ignore[arg-type]
                        athleteId=item.get("athleteId"),  # type: ignore[arg-type]
                        athleteName=item.get("athleteName"),  # type: ignore[arg-type]
                        slotIndex=item.get("slotIndex"),  # type: ignore[arg-type]
                        issues=[
                            RosterImportIssueResponse(
                                code=str(issue.get("code") or "unknown"),
                                message=str(issue.get("message") or ""),
                                severity=str(issue.get("severity") or "error"),
                            )
                            for issue in (item.get("issues") or [])
                            if isinstance(issue, dict)
                        ],
                        candidates=[
                            RosterImportAthleteCandidateResponse(
                                athleteId=str(candidate["athleteId"]),
                                providerId=int(candidate["providerId"]),
                                canonicalName=str(candidate["canonicalName"]),
                            )
                            for candidate in (item.get("candidates") or [])
                            if isinstance(candidate, dict)
                        ],
                    )
                )
        return RosterImportPreviewResponse(
            importId=str(session.id),
            status=session.status.value,
            fileSha256=session.file_sha256,
            originalFilename=session.original_filename,
            canConfirm=session.status == RosterImportStatus.DRAFT and session.error_count == 0,
            rowCount=session.row_count,
            errorCount=session.error_count,
            warningCount=session.warning_count,
            rows=rows,
            confirmedAt=session.confirmed_at.isoformat() if session.confirmed_at else None,
        )

    def _refund_purchase(
        self,
        account: CreditAccount,
        *,
        team_id: UUID,
        slot_index: int,
        athlete_id: UUID,
        athlete_name: str,
        purchase_credits: int | None,
        actor_id: UUID,
    ) -> None:
        if not purchase_credits or purchase_credits <= 0:
            return
        apply_ledger_movement(
            self._session,
            account,
            amount=purchase_credits,
            reason=CreditLedgerReason.ROSTER_RELEASE_REFUND,
            transaction_id=f"refund:{team_id}:{slot_index}:{athlete_id}",
            actor_id=actor_id,
            note=f"Rimborso {athlete_name}",
        )

    def _is_league_admin(self, league_access: LeagueAccess) -> bool:
        if league_access.operator_bypass:
            return True
        return league_access.membership_role == LeagueMemberRole.OWNER

    def _ownership_source(
        self,
        league_access: LeagueAccess,
        *,
        csv_import: bool,
    ) -> RosterOwnershipSource:
        if csv_import:
            return RosterOwnershipSource.CSV_IMPORT
        if self._is_league_admin(league_access):
            return RosterOwnershipSource.ADMIN
        return RosterOwnershipSource.MANUAL

    def _ownership_history_response(
        self,
        fantasy_team_id: UUID,
        *,
        active_only: bool,
    ) -> RosterOwnershipHistoryResponse:
        intervals = list_ownership_intervals(
            self._session,
            fantasy_team_id=fantasy_team_id,
            active_only=active_only,
        )
        return RosterOwnershipHistoryResponse(
            fantasyTeamId=str(fantasy_team_id),
            intervals=[self._to_ownership_interval(row) for row in intervals],
        )

    def _to_ownership_interval(
        self,
        row: RosterOwnershipInterval,
    ) -> RosterOwnershipIntervalResponse:
        return RosterOwnershipIntervalResponse(
            id=str(row.id),
            fantasyTeamId=str(row.fantasy_team_id),
            athleteId=str(row.athlete_id),
            athleteName=row.athlete.canonical_name if row.athlete is not None else None,
            slotIndex=row.slot_index,
            purchaseCredits=row.purchase_credits,
            acquiredAt=row.acquired_at.isoformat(),
            releasedAt=row.released_at.isoformat() if row.released_at else None,
            source=row.source.value,
            active=row.released_at is None,
        )

    def _to_snapshot_summary(self, snapshot) -> RosterTurnSnapshotSummaryResponse:
        return RosterTurnSnapshotSummaryResponse(
            id=str(snapshot.id),
            leagueId=str(snapshot.league_id),
            roundNumber=snapshot.round_number,
            capturedAt=snapshot.captured_at.isoformat(),
            entryCount=snapshot.entry_count,
            actorId=str(snapshot.actor_id) if snapshot.actor_id else None,
        )

    def _to_snapshot_detail(
        self,
        snapshot,
        *,
        created: bool,
        team_id: UUID | None = None,
    ) -> RosterTurnSnapshotDetailResponse:
        entries = snapshot.entries
        if team_id is not None:
            entries = [row for row in entries if row.fantasy_team_id == team_id]
        return RosterTurnSnapshotDetailResponse(
            id=str(snapshot.id),
            leagueId=str(snapshot.league_id),
            roundNumber=snapshot.round_number,
            capturedAt=snapshot.captured_at.isoformat(),
            entryCount=snapshot.entry_count,
            actorId=str(snapshot.actor_id) if snapshot.actor_id else None,
            created=created,
            entries=[
                RosterTurnSnapshotEntryResponse(
                    fantasyTeamId=str(row.fantasy_team_id),
                    teamName=row.fantasy_team.name if row.fantasy_team is not None else "",
                    slotIndex=row.slot_index,
                    athleteId=str(row.athlete_id),
                    athleteName=row.athlete.canonical_name if row.athlete is not None else None,
                    purchaseCredits=row.purchase_credits,
                    role=row.role,
                )
                for row in entries
            ],
        )

    def _assert_can_edit_team(self, league_access: LeagueAccess, team: FantasyTeam) -> None:
        if self._is_league_admin(league_access):
            return
        membership = self._require_membership(league_access)
        if team.membership_id != membership.id:
            raise ValidationAuthError(
                "Puoi modificare solo la tua rosa.",
                code="roster_edit_forbidden",
            )

    def _require_membership(self, league_access: LeagueAccess) -> LeagueMembership:
        membership = self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_access.league.id,
                LeagueMembership.user_id == league_access.user.id,
            )
        )
        if membership is None:
            raise ValidationAuthError(
                "Devi essere partecipante della lega per consultare la rosa.",
                code="membership_required",
            )
        return membership

    def _get_team_for_update(self, league_id: UUID, team_id: UUID) -> FantasyTeam:
        team = self._session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.id == team_id, FantasyTeam.league_id == league_id)
            .with_for_update()
        ).first()
        if team is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        return team

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League).where(League.id == league_id).with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

    def _default_team_name(self, user: User, membership: LeagueMembership) -> str:
        if membership.historical_display_name:
            return membership.historical_display_name
        return user.display_name

    def _add_audit(
        self,
        league_id: UUID,
        actor_id: UUID,
        action: LeagueAuditAction,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=actor_id,
                action=action,
                correlation_id=get_correlation_id(),
                details=details,
            )
        )

    def _fail_assign(self, message: str, *, code: str, result: str) -> NoReturn:
        get_metrics().incr("fantasy_roster_assign_total", labels={"result": result})
        raise ValidationAuthError(message, code=code)

    def _sync_composition(
        self,
        team: FantasyTeam,
        league: League,
        *,
        actor_id: UUID | None = None,
    ) -> RosterCompositionReport:
        previous = team.composition_status
        report = sync_team_composition_status(
            self._session,
            team,
            league=league,
            require_complete=False,
        )
        if (
            report.status == RosterCompositionStatus.VALIDATED
            and previous != RosterCompositionStatus.VALIDATED
            and actor_id is not None
        ):
            self._add_audit(
                league.id,
                actor_id,
                LeagueAuditAction.FANTASY_ROSTER_COMPOSITION_VALIDATED,
                details={
                    "fantasyTeamId": str(team.id),
                    "filledSlots": report.filled_slots,
                    "competitionCount": report.competition_count,
                    "counts": report.counts,
                },
            )
            get_metrics().incr(
                "fantasy_roster_composition_validated_total",
                labels={"result": "success"},
            )
        return report

    def _composition_response(
        self,
        team: FantasyTeam,
        report: RosterCompositionReport,
    ) -> RosterCompositionResponse:
        return RosterCompositionResponse(
            status=report.status.value,
            filledSlots=report.filled_slots,
            competitionCount=report.competition_count,
            requireComplete=report.require_complete,
            validatedAt=team.validated_at.isoformat() if team.validated_at else None,
            limits=RosterCompositionLimitsResponse(
                rosterSize=report.limits.roster_size,
                goalkeepers=report.limits.goalkeepers,
                defenders=report.limits.defenders,
                midfielders=report.limits.midfielders,
                forwards=report.limits.forwards,
            ),
            counts=RosterCompositionCountsResponse(
                P=report.counts.get("P", 0),
                D=report.counts.get("D", 0),
                C=report.counts.get("C", 0),
                A=report.counts.get("A", 0),
            ),
            issues=[
                RosterCompositionIssueResponse(code=issue.code, message=issue.message)
                for issue in report.issues
            ],
        )

    def _to_summary(
        self,
        team: FantasyTeam,
        *,
        roster_size: int,
    ) -> FantasyTeamSummaryResponse:
        filled = sum(1 for slot in team.slots if slot.athlete_id is not None)
        user = team.membership.user
        return FantasyTeamSummaryResponse(
            id=str(team.id),
            leagueId=str(team.league_id),
            membershipId=str(team.membership_id),
            userId=str(team.membership.user_id),
            userType=user.user_type.value if user is not None else UserType.HUMAN.value,
            name=team.name,
            rosterSize=roster_size,
            filledSlots=filled,
            compositionStatus=team.composition_status.value,
        )

    def _to_team_response(
        self,
        team: FantasyTeam,
        *,
        composition: RosterCompositionReport | None = None,
    ) -> FantasyTeamResponse:
        roster_size = resolve_roster_size(self._session, team.league_id)
        league = self._session.get(League, team.league_id)
        season_year = league.season_year if league is not None else 0
        slots = [
            self._to_slot_response(slot, season_year=season_year)
            for slot in sorted(team.slots, key=lambda row: row.slot_index)
        ]
        filled = sum(1 for slot in slots if slot.athlete_id is not None)
        report = composition
        if report is None and league is not None:
            report = evaluate_team_composition(
                self._session,
                team,
                league=league,
                require_complete=False,
            )
        composition_payload = (
            self._composition_response(team, report) if report is not None else None
        )
        status_value = report.status.value if report is not None else team.composition_status.value
        user = team.membership.user
        return FantasyTeamResponse(
            id=str(team.id),
            leagueId=str(team.league_id),
            membershipId=str(team.membership_id),
            userId=str(team.membership.user_id),
            userType=user.user_type.value if user is not None else UserType.HUMAN.value,
            name=team.name,
            rosterSize=roster_size,
            filledSlots=filled,
            compositionStatus=status_value,
            composition=composition_payload,
            slots=slots,
        )

    def _to_slot_response(
        self,
        slot: FantasyRosterSlot,
        *,
        season_year: int,
    ) -> FantasyRosterSlotResponse:
        club_name: str | None = None
        role: str | None = None
        if slot.athlete_id is not None:
            assignment = get_role_assignment(
                self._session,
                athlete_id=slot.athlete_id,
                season_year=season_year,
            )
            if assignment is not None:
                override = get_active_override(
                    self._session,
                    league_id=slot.league_id,
                    athlete_id=slot.athlete_id,
                )
                role = effective_role_for_athlete(
                    official_role=assignment.role,
                    override=override,
                    current_round=0,
                ).value
                if assignment.club_id is not None:
                    club = self._session.get(Club, assignment.club_id)
                    club_name = club.name if club is not None else None
        return FantasyRosterSlotResponse(
            id=str(slot.id),
            slotIndex=slot.slot_index,
            athleteId=str(slot.athlete_id) if slot.athlete_id else None,
            athleteName=slot.athlete.canonical_name if slot.athlete is not None else None,
            clubName=club_name,
            role=role,
            purchaseCredits=slot.purchase_credits,
        )

    def _to_ledger_entry(self, entry: CreditLedgerEntry) -> CreditLedgerEntryResponse:
        return CreditLedgerEntryResponse(
            id=str(entry.id),
            amount=entry.amount,
            reason=entry.reason.value,
            transactionId=entry.transaction_id,
            balanceAfter=entry.balance_after,
            note=entry.note,
            actorId=str(entry.actor_id) if entry.actor_id else None,
            createdAt=entry.created_at.isoformat(),
        )

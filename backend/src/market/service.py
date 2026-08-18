"""Market session service: create/close sessions and submit sealed bids (EP08-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    MarketBidStatus,
    MarketSessionKind,
    MarketSessionStatus,
)
from fantasy_teams.factory import ensure_team_for_membership, find_team_for_membership
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from market.assignment import assign_winning_bid, assign_winning_waiver_bid
from market.models import MarketBid, MarketSession
from market.schemas import (
    CreateMarketSessionRequest,
    MarketBidListResponse,
    MarketBidResponse,
    MarketResolutionOutcomeResponse,
    MarketResolutionResponse,
    MarketSessionResponse,
    SubmitMarketBidRequest,
)
from market.validators import (
    validate_amount_within_balance,
    validate_athlete_is_free_agent,
    validate_bid_amount,
    validate_bid_targets_session_athlete,
    validate_release_athlete_not_allowed,
    validate_release_athlete_owned_by_team,
    validate_release_athlete_required,
    validate_session_window,
    validate_team_eligible_for_session,
    validate_team_has_free_slot,
)
from market.windows import effective_status, is_open_for_bids
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

# Parity rule for the initial auction is an open decision in the functional spec
# (Doc §20 "Parità nell'asta iniziale e nello spareggio mercato"). Default: reopen a
# 24h tiebreak session scoped to the tied teams and the contested athlete.
TIEBREAK_WINDOW = timedelta(hours=24)


def _parse_required_datetime(value: str, *, field: str) -> datetime:
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationAuthError(
            f"Il campo {field} non è una data ISO-8601 valida.",
            code="invalid_datetime",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class MarketService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- sessions ---------------------------------------------------------

    def create_auction_session(
        self,
        league_access: LeagueAccess,
        payload: CreateMarketSessionRequest,
    ) -> MarketSessionResponse:
        return self._create_session(
            league_access, payload, kind=MarketSessionKind.INITIAL_AUCTION
        )

    def create_waiver_session(
        self,
        league_access: LeagueAccess,
        payload: CreateMarketSessionRequest,
    ) -> MarketSessionResponse:
        return self._create_session(league_access, payload, kind=MarketSessionKind.WAIVER)

    def _create_session(
        self,
        league_access: LeagueAccess,
        payload: CreateMarketSessionRequest,
        *,
        kind: MarketSessionKind,
    ) -> MarketSessionResponse:
        league = self._lock_league(league_access.league.id)
        opens_at = _parse_required_datetime(payload.opens_at, field="opensAt")
        closes_at = _parse_required_datetime(payload.closes_at, field="closesAt")
        validate_session_window(opens_at=opens_at, closes_at=closes_at)

        existing = self._session.scalar(
            select(MarketSession).where(
                MarketSession.league_id == league.id,
                MarketSession.kind == kind,
                MarketSession.parent_session_id.is_(None),
                MarketSession.status.in_(
                    (MarketSessionStatus.SCHEDULED, MarketSessionStatus.OPEN)
                ),
            )
        )
        if existing is not None and effective_status(existing, now=datetime.now(UTC)) in (
            MarketSessionStatus.SCHEDULED,
            MarketSessionStatus.OPEN,
        ):
            raise ValidationAuthError(
                "Esiste già una sessione di questo tipo attiva per questa lega.",
                code="market_session_already_active",
            )

        market_session = MarketSession(
            league_id=league.id,
            kind=kind,
            status=MarketSessionStatus.SCHEDULED,
            opens_at=opens_at,
            closes_at=closes_at,
            created_by=league_access.user.id,
        )
        self._session.add(market_session)
        self._session.flush()
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_SESSION_CREATED,
            details={
                "sessionId": str(market_session.id),
                "kind": kind.value,
                "opensAt": opens_at.isoformat(),
                "closesAt": closes_at.isoformat(),
            },
        )
        self._session.commit()
        get_metrics().incr("market_session_created_total", labels={"kind": kind.value})
        return self._to_session_response(market_session)

    def close_session(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
    ) -> MarketSessionResponse:
        league = self._lock_league(league_access.league.id)
        market_session = self._get_session_for_update(league.id, session_id)
        if market_session.status == MarketSessionStatus.RESOLVED:
            raise ValidationAuthError(
                "La sessione è già stata risolta.",
                code="market_session_already_resolved",
            )
        market_session.status = MarketSessionStatus.CLOSED
        self._session.flush()
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_SESSION_CLOSED,
            details={"sessionId": str(market_session.id)},
        )
        self._session.commit()
        get_metrics().incr("market_session_closed_total")
        return self._to_session_response(market_session)

    def list_sessions(
        self,
        league_access: LeagueAccess,
        *,
        kind: MarketSessionKind | None = None,
    ) -> list[MarketSessionResponse]:
        stmt = select(MarketSession).where(MarketSession.league_id == league_access.league.id)
        if kind is not None:
            stmt = stmt.where(MarketSession.kind == kind)
        rows = self._session.scalars(stmt.order_by(MarketSession.opens_at.desc())).all()
        return [self._to_session_response(row) for row in rows]

    def get_session(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
    ) -> MarketSessionResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        return self._to_session_response(market_session)

    # -- resolution -----------------------------------------------------------

    def resolve_session(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
    ) -> MarketResolutionResponse:
        """Resolve a closed session: highest bid wins, ties reopen a tiebreak session.

        Atomic and idempotent: replaying against an already-resolved session just
        returns the persisted outcome without recomputing or re-charging anyone.
        """
        league = self._lock_league(league_access.league.id)
        market_session = self._get_session_for_update(league.id, session_id)
        now = datetime.now(UTC)

        if market_session.status == MarketSessionStatus.RESOLVED:
            return self._resolution_summary(market_session)

        if effective_status(market_session, now=now) != MarketSessionStatus.CLOSED:
            raise ValidationAuthError(
                "La sessione deve essere chiusa prima di poter essere risolta.",
                code="market_session_not_closed",
            )
        market_session.status = MarketSessionStatus.CLOSED

        bids = self._session.scalars(
            select(MarketBid)
            .options(selectinload(MarketBid.athlete), selectinload(MarketBid.fantasy_team))
            .where(
                MarketBid.session_id == market_session.id,
                MarketBid.status == MarketBidStatus.SUBMITTED,
            )
            .with_for_update()
        ).all()

        by_athlete: dict[UUID, list[MarketBid]] = {}
        for bid in bids:
            by_athlete.setdefault(bid.athlete_id, []).append(bid)

        candidates: list[MarketBid] = []
        tie_groups: dict[UUID, list[MarketBid]] = {}
        for athlete_id, group in by_athlete.items():
            group.sort(key=lambda row: (-row.amount_credits, row.submitted_at))
            top_amount = group[0].amount_credits
            top_bids = [row for row in group if row.amount_credits == top_amount]
            for loser in group:
                if loser not in top_bids:
                    loser.status = MarketBidStatus.LOST
            if len(top_bids) == 1:
                candidates.append(top_bids[0])
            else:
                tie_groups[athlete_id] = top_bids

        # Deterministic, reconstructable order: highest amount first league-wide, so a
        # team that wins several athletes spends on its most valuable bids first.
        candidates.sort(key=lambda row: (-row.amount_credits, row.submitted_at))

        for bid in candidates:
            transaction_id = f"market:{market_session.id}:{bid.fantasy_team_id}:{bid.athlete_id}"
            if market_session.kind == MarketSessionKind.WAIVER:
                slot = (
                    assign_winning_waiver_bid(
                        self._session,
                        league=league,
                        team=bid.fantasy_team,
                        acquire_athlete_id=bid.athlete_id,
                        release_athlete_id=bid.release_athlete_id,
                        amount_credits=bid.amount_credits,
                        transaction_id=transaction_id,
                        actor_id=league_access.user.id,
                    )
                    if bid.release_athlete_id is not None
                    else None
                )
            else:
                slot = assign_winning_bid(
                    self._session,
                    league=league,
                    team=bid.fantasy_team,
                    athlete_id=bid.athlete_id,
                    amount_credits=bid.amount_credits,
                    transaction_id=transaction_id,
                    actor_id=league_access.user.id,
                )
            bid.status = MarketBidStatus.WON if slot is not None else MarketBidStatus.LOST

        tiebreak_count = 0
        for athlete_id, tied_bids in tie_groups.items():
            for bid in tied_bids:
                bid.status = MarketBidStatus.EXPIRED
            eligible_team_ids = [str(bid.fantasy_team_id) for bid in tied_bids]
            child = MarketSession(
                league_id=league.id,
                kind=market_session.kind,
                status=MarketSessionStatus.OPEN,
                opens_at=now,
                closes_at=now + TIEBREAK_WINDOW,
                created_by=league_access.user.id,
                parent_session_id=market_session.id,
                target_athlete_id=athlete_id,
                eligible_team_ids=eligible_team_ids,
            )
            self._session.add(child)
            self._session.flush()
            tiebreak_count += 1
            self._add_audit(
                league.id,
                league_access.user.id,
                LeagueAuditAction.MARKET_TIEBREAK_OPENED,
                details={
                    "parentSessionId": str(market_session.id),
                    "tiebreakSessionId": str(child.id),
                    "athleteId": str(athlete_id),
                    "tiedAmountCredits": tied_bids[0].amount_credits,
                    "teamIds": eligible_team_ids,
                },
            )

        market_session.status = MarketSessionStatus.RESOLVED
        market_session.resolved_at = now
        self._session.flush()
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_SESSION_RESOLVED,
            details={
                "sessionId": str(market_session.id),
                "assigned": sum(1 for bid in candidates if bid.status == MarketBidStatus.WON),
                "tiebreaksOpened": tiebreak_count,
            },
        )
        self._session.commit()
        get_metrics().incr("market_session_resolved_total")
        return self._resolution_summary(market_session)

    def _resolution_summary(self, market_session: MarketSession) -> MarketResolutionResponse:
        bids = self._session.scalars(
            select(MarketBid)
            .options(selectinload(MarketBid.athlete))
            .where(MarketBid.session_id == market_session.id)
        ).all()
        children = self._session.scalars(
            select(MarketSession).where(MarketSession.parent_session_id == market_session.id)
        ).all()
        tiebreak_by_athlete = {child.target_athlete_id: child for child in children}

        by_athlete: dict[UUID, list[MarketBid]] = {}
        for bid in bids:
            by_athlete.setdefault(bid.athlete_id, []).append(bid)

        outcomes: list[MarketResolutionOutcomeResponse] = []
        for athlete_id, group in by_athlete.items():
            athlete = group[0].athlete
            won = next((row for row in group if row.status == MarketBidStatus.WON), None)
            if won is not None:
                outcomes.append(
                    MarketResolutionOutcomeResponse(
                        athleteId=str(athlete_id),
                        athleteName=athlete.canonical_name,
                        outcome="assigned",
                        winningTeamId=str(won.fantasy_team_id),
                        amountCredits=won.amount_credits,
                    )
                )
            elif athlete_id in tiebreak_by_athlete:
                outcomes.append(
                    MarketResolutionOutcomeResponse(
                        athleteId=str(athlete_id),
                        athleteName=athlete.canonical_name,
                        outcome="tiebreak",
                        tiebreakSessionId=str(tiebreak_by_athlete[athlete_id].id),
                    )
                )
            else:
                outcomes.append(
                    MarketResolutionOutcomeResponse(
                        athleteId=str(athlete_id),
                        athleteName=athlete.canonical_name,
                        outcome="unassigned",
                    )
                )
        return MarketResolutionResponse(
            sessionId=str(market_session.id),
            status=market_session.status.value,
            outcomes=outcomes,
        )

    # -- bids ---------------------------------------------------------------

    def submit_bid(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
        athlete_id: UUID,
        payload: SubmitMarketBidRequest,
    ) -> MarketBidResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        now = datetime.now(UTC)
        if not is_open_for_bids(market_session, now=now):
            raise ValidationAuthError(
                "La sessione non è aperta alle offerte in questo momento.",
                code="market_session_not_open",
            )
        amount = validate_bid_amount(payload.amount_credits)
        validate_bid_targets_session_athlete(
            target_athlete_id=market_session.target_athlete_id, athlete_id=athlete_id
        )

        team = self._my_team(league_access)
        validate_team_eligible_for_session(
            eligible_team_ids=market_session.eligible_team_ids, fantasy_team_id=team.id
        )
        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            raise ValidationAuthError("Calciatore non trovato.", code="athlete_not_found")

        owner_slot = self._session.scalar(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.league_id == league_access.league.id,
                FantasyRosterSlot.athlete_id == athlete_id,
            )
        )
        validate_athlete_is_free_agent(
            owner_team_id=owner_slot.fantasy_team_id if owner_slot is not None else None
        )

        account = find_account_for_team(self._session, team.id)
        balance = account.balance if account is not None else 0
        validate_amount_within_balance(amount_credits=amount, balance=balance)

        release_athlete_id: UUID | None
        if market_session.kind == MarketSessionKind.WAIVER:
            raw_release_id = payload.release_athlete_id
            try:
                release_athlete_id = validate_release_athlete_required(
                    UUID(raw_release_id) if raw_release_id else None
                )
            except ValueError as exc:
                raise ValidationAuthError(
                    "Identificativo del calciatore da svincolare non valido.",
                    code="invalid_release_athlete_id",
                ) from exc
            release_slot = self._session.scalar(
                select(FantasyRosterSlot).where(
                    FantasyRosterSlot.league_id == league_access.league.id,
                    FantasyRosterSlot.athlete_id == release_athlete_id,
                )
            )
            validate_release_athlete_owned_by_team(
                owner_team_id=release_slot.fantasy_team_id if release_slot is not None else None,
                team_id=team.id,
            )
        else:
            validate_release_athlete_not_allowed(payload.release_athlete_id)
            release_athlete_id = None
            has_free_slot = (
                self._session.scalar(
                    select(FantasyRosterSlot).where(
                        FantasyRosterSlot.fantasy_team_id == team.id,
                        FantasyRosterSlot.athlete_id.is_(None),
                    )
                )
                is not None
            )
            validate_team_has_free_slot(has_free_slot=has_free_slot)

        existing_bid = self._session.scalar(
            select(MarketBid)
            .where(
                MarketBid.session_id == market_session.id,
                MarketBid.fantasy_team_id == team.id,
                MarketBid.athlete_id == athlete_id,
            )
            .with_for_update()
        )
        if existing_bid is not None:
            existing_bid.amount_credits = amount
            existing_bid.release_athlete_id = release_athlete_id
            existing_bid.status = MarketBidStatus.SUBMITTED
            bid = existing_bid
            self._session.flush()
        else:
            bid = MarketBid(
                session_id=market_session.id,
                fantasy_team_id=team.id,
                athlete_id=athlete_id,
                amount_credits=amount,
                release_athlete_id=release_athlete_id,
            )
            try:
                with self._session.begin_nested():
                    self._session.add(bid)
                    self._session.flush()
            except IntegrityError as exc:
                replayed = self._session.scalar(
                    select(MarketBid).where(
                        MarketBid.session_id == market_session.id,
                        MarketBid.fantasy_team_id == team.id,
                        MarketBid.athlete_id == athlete_id,
                    )
                )
                if replayed is None:
                    raise ValidationAuthError(
                        "Conflitto durante l'invio dell'offerta.",
                        code="market_bid_conflict",
                    ) from exc
                replayed.amount_credits = amount
                bid = replayed
                self._session.flush()

        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_BID_SUBMITTED,
            details={
                "sessionId": str(market_session.id),
                "fantasyTeamId": str(team.id),
                "athleteId": str(athlete_id),
                "amountCredits": amount,
                "releaseAthleteId": str(release_athlete_id) if release_athlete_id else None,
            },
        )
        self._session.commit()
        get_metrics().incr("market_bid_submitted_total", labels={"kind": market_session.kind.value})
        self._session.refresh(bid)
        release_athlete = (
            self._session.get(Athlete, release_athlete_id) if release_athlete_id else None
        )
        return self._to_bid_response(bid, athlete=athlete, release_athlete=release_athlete)

    def withdraw_bid(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
        athlete_id: UUID,
    ) -> None:
        market_session = self._find_session(league_access.league.id, session_id)
        now = datetime.now(UTC)
        if not is_open_for_bids(market_session, now=now):
            raise ValidationAuthError(
                "La sessione non è aperta: impossibile ritirare l'offerta.",
                code="market_session_not_open",
            )
        team = self._my_team(league_access)
        bid = self._session.scalar(
            select(MarketBid)
            .where(
                MarketBid.session_id == market_session.id,
                MarketBid.fantasy_team_id == team.id,
                MarketBid.athlete_id == athlete_id,
            )
            .with_for_update()
        )
        if bid is None:
            raise ValidationAuthError("Offerta non trovata.", code="market_bid_not_found")
        bid.status = MarketBidStatus.CANCELLED
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_BID_WITHDRAWN,
            details={
                "sessionId": str(market_session.id),
                "fantasyTeamId": str(team.id),
                "athleteId": str(athlete_id),
            },
        )
        self._session.commit()
        get_metrics().incr("market_bid_withdrawn_total")

    def list_my_bids(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
    ) -> MarketBidListResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        team = self._my_team(league_access)
        rows = self._session.scalars(
            select(MarketBid)
            .options(
                selectinload(MarketBid.athlete),
                selectinload(MarketBid.release_athlete),
            )
            .where(
                MarketBid.session_id == market_session.id,
                MarketBid.fantasy_team_id == team.id,
            )
            .order_by(MarketBid.submitted_at.desc())
        ).all()
        return MarketBidListResponse(
            sessionId=str(market_session.id),
            fantasyTeamId=str(team.id),
            bids=[
                self._to_bid_response(row, athlete=row.athlete, release_athlete=row.release_athlete)
                for row in rows
            ],
        )

    # -- helpers --------------------------------------------------------------

    def _my_team(self, league_access: LeagueAccess) -> FantasyTeam:
        membership = self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_access.league.id,
                LeagueMembership.user_id == league_access.user.id,
            )
        )
        if membership is None:
            raise ValidationAuthError(
                "Devi essere partecipante della lega per operare sul mercato.",
                code="membership_required",
            )
        team, _ = ensure_team_for_membership(
            self._session,
            membership,
            name=league_access.user.display_name or "Squadra",
            actor_id=league_access.user.id,
        )
        refreshed = find_team_for_membership(self._session, membership.id)
        assert refreshed is not None
        return refreshed

    def _find_session(self, league_id: UUID, session_id: UUID) -> MarketSession:
        market_session = self._session.scalar(
            select(MarketSession).where(
                MarketSession.id == session_id,
                MarketSession.league_id == league_id,
            )
        )
        if market_session is None:
            raise ValidationAuthError(
                "Sessione di mercato non trovata.",
                code="market_session_not_found",
            )
        return market_session

    def _get_session_for_update(self, league_id: UUID, session_id: UUID) -> MarketSession:
        market_session = self._session.scalars(
            select(MarketSession)
            .where(MarketSession.id == session_id, MarketSession.league_id == league_id)
            .with_for_update()
        ).first()
        if market_session is None:
            raise ValidationAuthError(
                "Sessione di mercato non trovata.",
                code="market_session_not_found",
            )
        return market_session

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League).where(League.id == league_id).with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

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
                details=details,
            )
        )
        self._session.flush()

    def _to_session_response(self, market_session: MarketSession) -> MarketSessionResponse:
        now = datetime.now(UTC)
        status = effective_status(market_session, now=now)
        bid_count = None
        if status in (MarketSessionStatus.CLOSED, MarketSessionStatus.RESOLVED):
            # Bid amounts stay sealed even after closing; a plain count is not (§FR-AST-01).
            bid_count = int(
                self._session.scalar(
                    select(func.count(MarketBid.id)).where(
                        MarketBid.session_id == market_session.id
                    )
                )
                or 0
            )
        return MarketSessionResponse(
            id=str(market_session.id),
            leagueId=str(market_session.league_id),
            kind=market_session.kind.value,
            status=status.value,
            opensAt=market_session.opens_at.isoformat(),
            closesAt=market_session.closes_at.isoformat(),
            bidCount=bid_count,
            parentSessionId=(
                str(market_session.parent_session_id)
                if market_session.parent_session_id
                else None
            ),
            targetAthleteId=(
                str(market_session.target_athlete_id)
                if market_session.target_athlete_id
                else None
            ),
        )

    def _to_bid_response(
        self,
        bid: MarketBid,
        *,
        athlete: Athlete,
        release_athlete: Athlete | None = None,
    ) -> MarketBidResponse:
        return MarketBidResponse(
            id=str(bid.id),
            sessionId=str(bid.session_id),
            fantasyTeamId=str(bid.fantasy_team_id),
            athleteId=str(bid.athlete_id),
            athleteName=athlete.canonical_name,
            amountCredits=bid.amount_credits,
            status=bid.status.value,
            submittedAt=bid.submitted_at.isoformat(),
            releaseAthleteId=str(bid.release_athlete_id) if bid.release_athlete_id else None,
            releaseAthleteName=release_athlete.canonical_name if release_athlete else None,
        )

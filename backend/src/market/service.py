"""Market session service: create/close sessions and submit sealed bids (EP08-01)."""

from __future__ import annotations

from datetime import UTC, datetime
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
from market.models import MarketBid, MarketSession
from market.schemas import (
    CreateMarketSessionRequest,
    MarketBidListResponse,
    MarketBidResponse,
    MarketSessionResponse,
    SubmitMarketBidRequest,
)
from market.validators import (
    validate_amount_within_balance,
    validate_athlete_is_free_agent,
    validate_bid_amount,
    validate_session_window,
    validate_team_has_free_slot,
)
from market.windows import effective_status, is_open_for_bids
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.roster.models import Athlete

logger = get_logger(__name__)


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
        league = self._lock_league(league_access.league.id)
        opens_at = _parse_required_datetime(payload.opens_at, field="opensAt")
        closes_at = _parse_required_datetime(payload.closes_at, field="closesAt")
        validate_session_window(opens_at=opens_at, closes_at=closes_at)

        existing = self._session.scalar(
            select(MarketSession).where(
                MarketSession.league_id == league.id,
                MarketSession.kind == MarketSessionKind.INITIAL_AUCTION,
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
                "Esiste già una sessione d'asta attiva per questa lega.",
                code="market_session_already_active",
            )

        market_session = MarketSession(
            league_id=league.id,
            kind=MarketSessionKind.INITIAL_AUCTION,
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
                "opensAt": opens_at.isoformat(),
                "closesAt": closes_at.isoformat(),
            },
        )
        self._session.commit()
        get_metrics().incr("market_session_created_total", labels={"kind": "initial_auction"})
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

    def list_sessions(self, league_access: LeagueAccess) -> list[MarketSessionResponse]:
        rows = self._session.scalars(
            select(MarketSession)
            .where(MarketSession.league_id == league_access.league.id)
            .order_by(MarketSession.opens_at.desc())
        ).all()
        return [self._to_session_response(row) for row in rows]

    def get_session(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
    ) -> MarketSessionResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        return self._to_session_response(market_session)

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

        team = self._my_team(league_access)
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
            existing_bid.status = MarketBidStatus.SUBMITTED
            bid = existing_bid
            self._session.flush()
        else:
            bid = MarketBid(
                session_id=market_session.id,
                fantasy_team_id=team.id,
                athlete_id=athlete_id,
                amount_credits=amount,
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
            },
        )
        self._session.commit()
        get_metrics().incr("market_bid_submitted_total")
        self._session.refresh(bid)
        return self._to_bid_response(bid, athlete=athlete)

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
            .options(selectinload(MarketBid.athlete))
            .where(
                MarketBid.session_id == market_session.id,
                MarketBid.fantasy_team_id == team.id,
            )
            .order_by(MarketBid.submitted_at.desc())
        ).all()
        return MarketBidListResponse(
            sessionId=str(market_session.id),
            fantasyTeamId=str(team.id),
            bids=[self._to_bid_response(row, athlete=row.athlete) for row in rows],
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
        )

    def _to_bid_response(self, bid: MarketBid, *, athlete: Athlete) -> MarketBidResponse:
        return MarketBidResponse(
            id=str(bid.id),
            sessionId=str(bid.session_id),
            fantasyTeamId=str(bid.fantasy_team_id),
            athleteId=str(bid.athlete_id),
            athleteName=athlete.canonical_name,
            amountCredits=bid.amount_credits,
            status=bid.status.value,
            submittedAt=bid.submitted_at.isoformat(),
        )

"""Live/ascending auction service: sessions, lots, raises (EP08-09).

Deliberately a separate service from ``MarketService`` (sealed-bid), even
though both operate on the shared ``MarketSession`` table — the two modes
have incompatible visibility rules (sealed bids stay hidden until
resolution; live raises are visible the instant they are placed) and
incompatible resolution timing (one atomic pass at the end vs. one lot at a
time while the session runs). A handful of small helpers below intentionally
duplicate ``MarketService``'s private helpers (``_my_team``, session lookup,
audit) to keep the two code paths fully isolated: a bug in one can never
reach the other.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    MarketLiveLotStatus,
    MarketLiveNominationMode,
    MarketSessionKind,
    MarketSessionStatus,
    NotificationCategory,
)
from fantasy_teams.composition import ROLE_LABEL_IT
from fantasy_teams.composition_service import (
    resolve_effective_athlete_role,
    resolve_effective_athlete_roles,
)
from fantasy_teams.factory import ensure_team_for_membership, find_team_for_membership
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from market.assignment import assign_winning_bid, resolve_live_swap
from market.live_models import MarketLiveLot, MarketLiveNominationQueueEntry, MarketLiveRaise
from market.live_schemas import (
    ConfigureLiveAuctionSessionRequest,
    CreateLiveAuctionSessionRequest,
    LiveAuctionSessionResponse,
    LiveLotListResponse,
    LiveLotResponse,
    LiveLotStateResponse,
    LiveRaiseResponse,
    LiveSwapCandidateResponse,
    NominateLotRequest,
    PendingSwapResponse,
    PlaceRaiseRequest,
    ResolveSwapRequest,
)
from market.live_validators import (
    compute_minimum_next_amount,
    validate_live_session_config,
    validate_not_current_leader,
    validate_raise_amount,
)
from market.live_windows import lot_is_expired, lot_window_is_open
from market.models import MarketSession
from market.validators import (
    validate_amount_within_balance,
    validate_athlete_is_free_agent,
    validate_session_window,
)
from market.windows import effective_status
from notifications.recipients import user_ids_for_league, user_ids_for_teams
from notifications.service import NotificationService
from observability.metrics import get_metrics
from sports_data.roster.models import Athlete


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


class LiveMarketService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- session lifecycle --------------------------------------------------

    def create_session(
        self,
        league_access: LeagueAccess,
        payload: CreateLiveAuctionSessionRequest,
    ) -> LiveAuctionSessionResponse:
        league = self._lock_league(league_access.league.id)
        opens_at = _parse_required_datetime(payload.opens_at, field="opensAt")
        closes_at = _parse_required_datetime(payload.closes_at, field="closesAt")
        validate_session_window(opens_at=opens_at, closes_at=closes_at)
        validate_live_session_config(
            min_increment_credits=payload.min_increment_credits,
            soft_close_seconds=payload.soft_close_seconds,
            lot_duration_seconds=payload.lot_duration_seconds,
        )
        try:
            nomination_mode = MarketLiveNominationMode(payload.nomination_mode)
        except ValueError as exc:
            raise ValidationAuthError(
                "Modalità di chiamata non valida.",
                code="invalid_nomination_mode",
            ) from exc

        queue_ids_raw = payload.nomination_queue_athlete_ids or []
        if nomination_mode == MarketLiveNominationMode.SEQUENTIAL and not queue_ids_raw:
            raise ValidationAuthError(
                "Indica l'elenco dei calciatori per la modalità a lista.",
                code="nomination_queue_required",
            )
        if nomination_mode == MarketLiveNominationMode.MANUAL and queue_ids_raw:
            raise ValidationAuthError(
                "La lista di chiamata è prevista solo in modalità sequenziale.",
                code="nomination_queue_not_allowed",
            )

        operator_user_id = self._resolve_operator(league.id, payload.operator_user_id)
        self._assert_no_conflicting_initial_auction(league.id)

        market_session = MarketSession(
            league_id=league.id,
            kind=MarketSessionKind.LIVE_AUCTION,
            status=MarketSessionStatus.SCHEDULED,
            opens_at=opens_at,
            closes_at=closes_at,
            created_by=league_access.user.id,
            nomination_mode=nomination_mode,
            min_increment_credits=payload.min_increment_credits,
            soft_close_seconds=payload.soft_close_seconds,
            lot_duration_seconds=payload.lot_duration_seconds,
            operator_user_id=operator_user_id,
        )
        self._session.add(market_session)
        self._session.flush()

        if nomination_mode == MarketLiveNominationMode.SEQUENTIAL:
            self._set_nomination_queue(market_session.id, queue_ids_raw)

        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_SESSION_CREATED,
            details={
                "sessionId": str(market_session.id),
                "nominationMode": nomination_mode.value,
                "operatorUserId": str(operator_user_id) if operator_user_id else None,
            },
        )
        self._session.commit()
        get_metrics().incr("market_live_session_created_total")
        return self._to_session_response(market_session)

    def configure_session(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
        payload: ConfigureLiveAuctionSessionRequest,
    ) -> LiveAuctionSessionResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        if market_session.status != MarketSessionStatus.SCHEDULED:
            raise ValidationAuthError(
                "La sessione è già avviata: non è più configurabile.",
                code="market_live_session_not_configurable",
            )

        min_increment = payload.min_increment_credits or market_session.min_increment_credits
        soft_close = payload.soft_close_seconds or market_session.soft_close_seconds
        lot_duration = payload.lot_duration_seconds or market_session.lot_duration_seconds
        validate_live_session_config(
            min_increment_credits=min_increment,
            soft_close_seconds=soft_close,
            lot_duration_seconds=lot_duration,
        )
        market_session.min_increment_credits = min_increment
        market_session.soft_close_seconds = soft_close
        market_session.lot_duration_seconds = lot_duration

        if payload.operator_user_id is not None:
            market_session.operator_user_id = self._resolve_operator(
                market_session.league_id, payload.operator_user_id or None
            )

        if payload.nomination_queue_athlete_ids is not None:
            if market_session.nomination_mode != MarketLiveNominationMode.SEQUENTIAL:
                raise ValidationAuthError(
                    "La lista di chiamata è prevista solo in modalità sequenziale.",
                    code="nomination_queue_not_allowed",
                )
            self._set_nomination_queue(market_session.id, payload.nomination_queue_athlete_ids)

        self._session.flush()
        self._session.commit()
        return self._to_session_response(market_session)

    def list_sessions(self, league_access: LeagueAccess) -> list[LiveAuctionSessionResponse]:
        rows = self._session.scalars(
            select(MarketSession)
            .where(
                MarketSession.league_id == league_access.league.id,
                MarketSession.kind == MarketSessionKind.LIVE_AUCTION,
            )
            .order_by(MarketSession.opens_at.desc())
        ).all()
        return [self._to_session_response(row) for row in rows]

    def get_session(
        self, league_access: LeagueAccess, session_id: UUID
    ) -> LiveAuctionSessionResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        return self._to_session_response(market_session)

    def start_session(
        self, league_access: LeagueAccess, session_id: UUID
    ) -> LiveAuctionSessionResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        if market_session.status != MarketSessionStatus.SCHEDULED:
            raise ValidationAuthError(
                "La sessione è già avviata.",
                code="market_live_session_already_started",
            )
        market_session.status = MarketSessionStatus.OPEN
        self._session.flush()
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_SESSION_STARTED,
            details={"sessionId": str(market_session.id)},
        )
        self._notify_session_started(market_session)
        self._session.commit()
        get_metrics().incr("market_live_session_started_total")
        return self._to_session_response(market_session)

    def end_session(
        self, league_access: LeagueAccess, session_id: UUID
    ) -> LiveAuctionSessionResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        if market_session.status == MarketSessionStatus.RESOLVED:
            return self._to_session_response(market_session)
        open_lot = self._session.scalar(
            select(MarketLiveLot).where(
                MarketLiveLot.session_id == market_session.id,
                MarketLiveLot.status == MarketLiveLotStatus.OPEN,
            )
        )
        if open_lot is not None:
            raise ValidationAuthError(
                "Chiudi il lotto in corso prima di terminare la sessione.",
                code="market_live_lot_still_open",
            )
        self._auto_decline_pending_swaps(league_access, market_session)
        market_session.status = MarketSessionStatus.RESOLVED
        market_session.resolved_at = datetime.now(UTC)
        self._session.flush()
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_SESSION_ENDED,
            details={"sessionId": str(market_session.id)},
        )
        self._session.commit()
        get_metrics().incr("market_live_session_ended_total")
        return self._to_session_response(market_session)

    def _auto_decline_pending_swaps(
        self, league_access: LeagueAccess, market_session: MarketSession
    ) -> None:
        """Ending the session must never leave a swap decision dangling (EP08-09)."""
        pending_lots = self._session.scalars(
            select(MarketLiveLot)
            .where(
                MarketLiveLot.session_id == market_session.id,
                MarketLiveLot.status == MarketLiveLotStatus.PENDING_SWAP,
            )
            .with_for_update()
        ).all()
        now = datetime.now(UTC)
        for lot in pending_lots:
            lot.status = MarketLiveLotStatus.PASSED
            lot.closed_at = now
            self._add_audit(
                market_session.league_id,
                league_access.user.id,
                LeagueAuditAction.MARKET_LIVE_LOT_SWAP_DECLINED,
                details={"lotId": str(lot.id), "reason": "session_ended"},
            )
        if pending_lots:
            self._session.flush()

    # -- lots -----------------------------------------------------------------

    def nominate_lot(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
        payload: NominateLotRequest,
    ) -> LiveLotResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        self._tick_current_lot(league_access, market_session)
        if market_session.status != MarketSessionStatus.OPEN:
            raise ValidationAuthError(
                "La sessione non è aperta.",
                code="market_live_session_not_open",
            )

        existing_open = self._session.scalar(
            select(MarketLiveLot).where(
                MarketLiveLot.session_id == market_session.id,
                MarketLiveLot.status == MarketLiveLotStatus.OPEN,
            )
        )
        if existing_open is not None:
            raise ValidationAuthError(
                "C'è già un lotto in corso: chiudilo prima di chiamarne un altro.",
                code="market_live_lot_already_open",
            )

        queue_entry: MarketLiveNominationQueueEntry | None = None
        if market_session.nomination_mode == MarketLiveNominationMode.SEQUENTIAL:
            queue_entry = self._session.scalar(
                select(MarketLiveNominationQueueEntry)
                .where(
                    MarketLiveNominationQueueEntry.session_id == market_session.id,
                    MarketLiveNominationQueueEntry.consumed_at.is_(None),
                )
                .order_by(MarketLiveNominationQueueEntry.position.asc())
            )
            if queue_entry is None:
                raise ValidationAuthError(
                    "Non ci sono altri calciatori nella lista di chiamata.",
                    code="market_live_queue_empty",
                )
            athlete_id = queue_entry.athlete_id
        else:
            if not payload.athlete_id:
                raise ValidationAuthError(
                    "Indica il calciatore da chiamare.",
                    code="market_live_athlete_required",
                )
            try:
                athlete_id = UUID(payload.athlete_id)
            except ValueError as exc:
                raise ValidationAuthError(
                    "Identificativo calciatore non valido.",
                    code="invalid_athlete_id",
                ) from exc

        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            raise ValidationAuthError("Calciatore non trovato.", code="athlete_not_found")

        owner_slot = self._session.scalar(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.league_id == market_session.league_id,
                FantasyRosterSlot.athlete_id == athlete_id,
            )
        )
        validate_athlete_is_free_agent(
            owner_team_id=owner_slot.fantasy_team_id if owner_slot is not None else None
        )

        next_sequence = (
            self._session.scalar(
                select(func.coalesce(func.max(MarketLiveLot.sequence_number), 0)).where(
                    MarketLiveLot.session_id == market_session.id
                )
            )
            or 0
        ) + 1
        now = datetime.now(UTC)
        lot = MarketLiveLot(
            session_id=market_session.id,
            athlete_id=athlete_id,
            sequence_number=next_sequence,
            status=MarketLiveLotStatus.OPEN,
            opened_at=now,
            closes_at=now + timedelta(seconds=market_session.lot_duration_seconds),
            min_increment_credits=market_session.min_increment_credits,
            current_amount_credits=0,
        )
        try:
            with self._session.begin_nested():
                self._session.add(lot)
                self._session.flush()
        except IntegrityError as exc:
            raise ValidationAuthError(
                "Questo calciatore è già in nomina o è già stato aggiudicato.",
                code="market_live_athlete_conflict",
            ) from exc

        if queue_entry is not None:
            queue_entry.consumed_at = now
            self._session.flush()

        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_LOT_NOMINATED,
            details={"lotId": str(lot.id), "sessionId": str(market_session.id), "athleteId": str(athlete_id)},
        )
        self._session.commit()
        get_metrics().incr("market_live_lot_nominated_total")
        return self._to_lot_response(lot, athlete=athlete)

    def place_raise(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
        lot_id: UUID,
        payload: PlaceRaiseRequest,
    ) -> LiveLotResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        self._tick_current_lot(league_access, market_session)

        team = self._my_team(league_access)

        lot = self._session.scalars(
            select(MarketLiveLot)
            .where(MarketLiveLot.id == lot_id, MarketLiveLot.session_id == market_session.id)
            .with_for_update()
        ).first()
        if lot is None:
            raise ValidationAuthError("Lotto non trovato.", code="market_live_lot_not_found")
        now = datetime.now(UTC)
        if not lot_window_is_open(lot, now=now):
            raise ValidationAuthError(
                "Il lotto non è più aperto ai rilanci.",
                code="market_live_lot_closed",
            )

        validate_not_current_leader(
            current_leader_team_id=lot.current_leader_team_id, team_id=team.id
        )
        validate_raise_amount(
            amount_credits=payload.amount_credits,
            current_amount_credits=lot.current_amount_credits,
            has_leader=lot.current_leader_team_id is not None,
            min_increment_credits=lot.min_increment_credits,
        )
        account = find_account_for_team(self._session, team.id)
        balance = account.balance if account is not None else 0
        validate_amount_within_balance(amount_credits=payload.amount_credits, balance=balance)
        # No roster-full gate here (unlike sealed bids): a full roster is resolved
        # at win time via the swap prompt (EP08-09), not by blocking the raise.

        previous_leader_team_id = lot.current_leader_team_id
        lot.current_leader_team_id = team.id
        lot.current_amount_credits = payload.amount_credits
        if lot.closes_at - now <= timedelta(seconds=market_session.soft_close_seconds):
            lot.closes_at = now + timedelta(seconds=market_session.soft_close_seconds)
        self._session.add(
            MarketLiveRaise(lot_id=lot.id, fantasy_team_id=team.id, amount_credits=payload.amount_credits)
        )
        self._session.flush()

        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_RAISE_PLACED,
            details={
                "lotId": str(lot.id),
                "fantasyTeamId": str(team.id),
                "amountCredits": payload.amount_credits,
            },
        )
        if previous_leader_team_id is not None and previous_leader_team_id != team.id:
            self._notify_outbid(previous_leader_team_id, lot)
        self._session.commit()
        get_metrics().incr("market_live_raise_placed_total")

        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        return self._to_lot_response(lot, athlete=athlete)

    def force_sell_lot(
        self, league_access: LeagueAccess, session_id: UUID, lot_id: UUID
    ) -> LiveLotResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        lot = self._get_open_lot_for_update(market_session.id, lot_id)
        if lot.current_leader_team_id is None:
            raise ValidationAuthError(
                "Nessun rilancio su questo lotto: usa 'salta'.",
                code="market_live_lot_no_bids",
            )
        now = datetime.now(UTC)
        self._sell_lot(league_access, market_session, lot, now=now)
        self._session.commit()
        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        return self._to_lot_response(lot, athlete=athlete)

    def pass_lot(
        self, league_access: LeagueAccess, session_id: UUID, lot_id: UUID
    ) -> LiveLotResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        lot = self._get_open_lot_for_update(market_session.id, lot_id)
        now = datetime.now(UTC)
        self._pass_lot_internal(league_access, market_session, lot, now=now)
        self._session.commit()
        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        return self._to_lot_response(lot, athlete=athlete)

    def cancel_lot(
        self, league_access: LeagueAccess, session_id: UUID, lot_id: UUID
    ) -> LiveLotResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        lot = self._get_open_lot_for_update(market_session.id, lot_id)
        if lot.current_leader_team_id is not None:
            raise ValidationAuthError(
                "Il lotto ha già rilanci: usa 'salta' o 'aggiudica'.",
                code="market_live_lot_has_raises",
            )
        now = datetime.now(UTC)
        lot.status = MarketLiveLotStatus.CANCELLED
        lot.closed_at = now
        self._session.flush()
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_LOT_CANCELLED,
            details={"lotId": str(lot.id)},
        )
        self._session.commit()
        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        return self._to_lot_response(lot, athlete=athlete)

    def resolve_swap(
        self,
        league_access: LeagueAccess,
        session_id: UUID,
        lot_id: UUID,
        payload: ResolveSwapRequest,
    ) -> LiveLotResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        lot = self._get_pending_swap_lot_for_update(market_session.id, lot_id)
        team = self._assert_swap_owner(league_access, lot)
        league = self._session.get(League, market_session.league_id)
        assert league is not None
        try:
            release_athlete_id = UUID(payload.release_athlete_id)
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo calciatore non valido.", code="invalid_athlete_id"
            ) from exc

        now = datetime.now(UTC)
        # Kept short: fantasy_teams.validators.validate_transaction_id caps ids at
        # 128 chars, and three UUIDs plus a descriptive prefix blows past that.
        transaction_id = f"live-swap-acquire:{lot.id}"
        refund_transaction_id = f"live-swap-release:{lot.id}:{release_athlete_id}"
        updated = resolve_live_swap(
            self._session,
            league=league,
            team=team,
            release_athlete_id=release_athlete_id,
            acquire_athlete_id=lot.athlete_id,
            amount_credits=lot.current_amount_credits,
            transaction_id=transaction_id,
            refund_transaction_id=refund_transaction_id,
            actor_id=league_access.user.id,
        )
        if updated is None:
            raise ValidationAuthError(
                "Impossibile completare lo scambio: la rosa è cambiata nel frattempo.",
                code="market_live_swap_failed",
            )
        lot.status = MarketLiveLotStatus.SOLD
        lot.closed_at = now
        self._session.flush()
        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_LOT_SWAP_RESOLVED,
            details={
                "lotId": str(lot.id),
                "athleteId": str(lot.athlete_id),
                "fantasyTeamId": str(team.id),
                "releasedAthleteId": str(release_athlete_id),
                "amountCredits": lot.current_amount_credits,
            },
        )
        self._notify_lot_sold(lot, team=team, athlete=athlete)
        self._session.commit()
        get_metrics().incr("market_live_swap_resolved_total")
        return self._to_lot_response(lot, athlete=athlete)

    def decline_swap(
        self, league_access: LeagueAccess, session_id: UUID, lot_id: UUID
    ) -> LiveLotResponse:
        market_session = self._get_session_for_update(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        lot = self._get_pending_swap_lot_for_update(market_session.id, lot_id)
        team = self._assert_swap_owner(league_access, lot)
        now = datetime.now(UTC)
        lot.status = MarketLiveLotStatus.PASSED
        lot.closed_at = now
        self._session.flush()
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_LOT_SWAP_DECLINED,
            details={"lotId": str(lot.id), "fantasyTeamId": str(team.id)},
        )
        self._session.commit()
        get_metrics().incr("market_live_swap_declined_total")
        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        return self._to_lot_response(lot, athlete=athlete)

    def _get_pending_swap_lot_for_update(self, session_id: UUID, lot_id: UUID) -> MarketLiveLot:
        lot = self._session.scalars(
            select(MarketLiveLot)
            .where(MarketLiveLot.id == lot_id, MarketLiveLot.session_id == session_id)
            .with_for_update()
        ).first()
        if lot is None:
            raise ValidationAuthError("Lotto non trovato.", code="market_live_lot_not_found")
        if lot.status != MarketLiveLotStatus.PENDING_SWAP:
            raise ValidationAuthError(
                "Questo lotto non è in attesa di uno scambio.",
                code="market_live_lot_not_pending_swap",
            )
        return lot

    def _assert_swap_owner(self, league_access: LeagueAccess, lot: MarketLiveLot) -> FantasyTeam:
        team = self._my_team(league_access)
        if lot.current_leader_team_id != team.id:
            raise ValidationAuthError(
                "Solo la squadra aggiudicataria può risolvere questo scambio.",
                code="market_live_swap_not_owner",
            )
        return team

    def get_state(self, league_access: LeagueAccess, session_id: UUID) -> LiveLotStateResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        if market_session.status == MarketSessionStatus.OPEN:
            if self._tick_current_lot(league_access, market_session):
                self._session.refresh(market_session)

        current_lot = self._session.scalars(
            select(MarketLiveLot)
            .options(
                selectinload(MarketLiveLot.athlete),
                selectinload(MarketLiveLot.current_leader_team),
            )
            .where(
                MarketLiveLot.session_id == market_session.id,
                MarketLiveLot.status == MarketLiveLotStatus.OPEN,
            )
        ).first()

        recent_raises: list[LiveRaiseResponse] = []
        seconds_remaining: int | None = None
        if current_lot is not None:
            now = datetime.now(UTC)
            seconds_remaining = max(0, int((current_lot.closes_at - now).total_seconds()))
            raises = self._session.scalars(
                select(MarketLiveRaise)
                .options(selectinload(MarketLiveRaise.fantasy_team))
                .where(MarketLiveRaise.lot_id == current_lot.id)
                .order_by(MarketLiveRaise.placed_at.desc())
                .limit(20)
            ).all()
            recent_raises = [self._to_raise_response(row) for row in raises]

        return LiveLotStateResponse(
            session=self._to_session_response(market_session),
            currentLot=(
                self._to_lot_response(current_lot, athlete=current_lot.athlete)
                if current_lot is not None
                else None
            ),
            recentRaises=recent_raises,
            secondsRemaining=seconds_remaining,
            pendingSwap=self._my_pending_swap(league_access, market_session),
        )

    def _my_pending_swap(
        self, league_access: LeagueAccess, market_session: MarketSession
    ) -> PendingSwapResponse | None:
        team = self._my_team(league_access)
        lot = self._session.scalars(
            select(MarketLiveLot)
            .options(selectinload(MarketLiveLot.athlete))
            .where(
                MarketLiveLot.session_id == market_session.id,
                MarketLiveLot.status == MarketLiveLotStatus.PENDING_SWAP,
                MarketLiveLot.current_leader_team_id == team.id,
            )
        ).first()
        if lot is None:
            return None
        league = self._session.get(League, market_session.league_id)
        assert league is not None
        candidates = self._pending_swap_candidates(league, team, lot.athlete_id)
        target_role = resolve_effective_athlete_role(
            self._session,
            league_id=league.id,
            athlete_id=lot.athlete_id,
            season_year=league.season_year,
            competition_ids={competition.id for competition in league.competitions},
        )
        return PendingSwapResponse(
            lotId=str(lot.id),
            athleteId=str(lot.athlete_id),
            athleteName=lot.athlete.canonical_name,
            amountCredits=lot.current_amount_credits,
            role=target_role.value if target_role is not None else "",
            roleLabel=ROLE_LABEL_IT.get(target_role, "") if target_role is not None else "",
            candidates=[
                LiveSwapCandidateResponse(
                    slotIndex=slot.slot_index,
                    athleteId=str(athlete.id),
                    athleteName=athlete.canonical_name,
                    purchaseCredits=slot.purchase_credits or 0,
                )
                for slot, athlete in candidates
            ],
        )

    def list_lots(self, league_access: LeagueAccess, session_id: UUID) -> LiveLotListResponse:
        market_session = self._find_session(league_access.league.id, session_id)
        self._assert_is_live(market_session)
        rows = self._session.scalars(
            select(MarketLiveLot)
            .options(
                selectinload(MarketLiveLot.athlete),
                selectinload(MarketLiveLot.current_leader_team),
            )
            .where(MarketLiveLot.session_id == market_session.id)
            .order_by(MarketLiveLot.sequence_number.asc())
        ).all()
        return LiveLotListResponse(
            sessionId=str(market_session.id),
            lots=[self._to_lot_response(row, athlete=row.athlete) for row in rows],
        )

    # -- internal: lazy finalization -------------------------------------------

    def _tick_current_lot(self, league_access: LeagueAccess, market_session: MarketSession) -> bool:
        """Finalize the current lot if its window has passed. Returns True if it did."""
        now = datetime.now(UTC)
        lot = self._session.scalars(
            select(MarketLiveLot)
            .where(
                MarketLiveLot.session_id == market_session.id,
                MarketLiveLot.status == MarketLiveLotStatus.OPEN,
            )
            .with_for_update()
        ).first()
        if lot is None or not lot_is_expired(lot, now=now):
            return False
        if lot.current_leader_team_id is not None:
            self._sell_lot(league_access, market_session, lot, now=now)
        else:
            self._pass_lot_internal(league_access, market_session, lot, now=now)
        self._session.commit()
        return True

    def _sell_lot(
        self,
        league_access: LeagueAccess,
        market_session: MarketSession,
        lot: MarketLiveLot,
        *,
        now: datetime,
    ) -> None:
        league = self._session.get(League, market_session.league_id)
        assert league is not None
        team = self._session.get(FantasyTeam, lot.current_leader_team_id)
        assert team is not None

        account = find_account_for_team(self._session, team.id)
        if account is None or account.balance < lot.current_amount_credits:
            self._pass_lot_internal(
                league_access, market_session, lot, now=now, reason="insufficient_credits"
            )
            return

        transaction_id = f"market-live:{lot.id}:{team.id}:{lot.athlete_id}"
        slot = assign_winning_bid(
            self._session,
            league=league,
            team=team,
            athlete_id=lot.athlete_id,
            amount_credits=lot.current_amount_credits,
            transaction_id=transaction_id,
            actor_id=league_access.user.id,
        )
        if slot is None:
            # Budget was fine, so the failure is roster-full or role-quota: offer
            # the coach a same-role swap instead of silently discarding the win.
            candidates = self._pending_swap_candidates(league, team, lot.athlete_id)
            if candidates:
                lot.status = MarketLiveLotStatus.PENDING_SWAP
                self._session.flush()
                self._add_audit(
                    market_session.league_id,
                    league_access.user.id,
                    LeagueAuditAction.MARKET_LIVE_LOT_SWAP_PENDING,
                    details={
                        "lotId": str(lot.id),
                        "athleteId": str(lot.athlete_id),
                        "fantasyTeamId": str(team.id),
                    },
                )
                athlete = self._session.get(Athlete, lot.athlete_id)
                assert athlete is not None
                self._notify_pending_swap(lot, team=team, athlete=athlete)
                return
            # No same-role player to release either (rare) — a legitimate pass,
            # not a fatal error (mirrors sealed resolution's own "lost bid" outcome).
            self._pass_lot_internal(league_access, market_session, lot, now=now, reason="assignment_failed")
            return
        lot.status = MarketLiveLotStatus.SOLD
        lot.closed_at = now
        self._session.flush()
        athlete = self._session.get(Athlete, lot.athlete_id)
        assert athlete is not None
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_LOT_SOLD,
            details={
                "lotId": str(lot.id),
                "athleteId": str(lot.athlete_id),
                "fantasyTeamId": str(team.id),
                "amountCredits": lot.current_amount_credits,
            },
        )
        self._notify_lot_sold(lot, team=team, athlete=athlete)

    def _pending_swap_candidates(
        self, league: League, team: FantasyTeam, athlete_id: UUID
    ) -> list[tuple[FantasyRosterSlot, Athlete]]:
        """Team's occupied slots holding a player of the same role as ``athlete_id``."""
        target_role = resolve_effective_athlete_role(
            self._session,
            league_id=league.id,
            athlete_id=athlete_id,
            season_year=league.season_year,
            competition_ids={competition.id for competition in league.competitions},
        )
        if target_role is None:
            return []
        slots = list(
            self._session.scalars(
                select(FantasyRosterSlot).where(
                    FantasyRosterSlot.fantasy_team_id == team.id,
                    FantasyRosterSlot.athlete_id.is_not(None),
                )
            ).all()
        )
        if not slots:
            return []
        roles = resolve_effective_athlete_roles(
            self._session,
            league_id=league.id,
            athlete_ids=[slot.athlete_id for slot in slots if slot.athlete_id is not None],
            season_year=league.season_year,
        )
        matches: list[tuple[FantasyRosterSlot, Athlete]] = []
        for slot in slots:
            assert slot.athlete_id is not None
            resolved = roles.get(slot.athlete_id)
            if resolved is None or resolved.role != target_role:
                continue
            athlete = self._session.get(Athlete, slot.athlete_id)
            assert athlete is not None
            matches.append((slot, athlete))
        return matches

    def _pass_lot_internal(
        self,
        league_access: LeagueAccess,
        market_session: MarketSession,
        lot: MarketLiveLot,
        *,
        now: datetime,
        reason: str | None = None,
    ) -> None:
        lot.status = MarketLiveLotStatus.PASSED
        lot.closed_at = now
        self._session.flush()
        self._add_audit(
            market_session.league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_LIVE_LOT_PASSED,
            details={"lotId": str(lot.id), "reason": reason},
        )

    def _get_open_lot_for_update(self, session_id: UUID, lot_id: UUID) -> MarketLiveLot:
        lot = self._session.scalars(
            select(MarketLiveLot)
            .where(MarketLiveLot.id == lot_id, MarketLiveLot.session_id == session_id)
            .with_for_update()
        ).first()
        if lot is None:
            raise ValidationAuthError("Lotto non trovato.", code="market_live_lot_not_found")
        if lot.status != MarketLiveLotStatus.OPEN:
            raise ValidationAuthError("Il lotto non è più aperto.", code="market_live_lot_closed")
        return lot

    # -- helpers ----------------------------------------------------------------

    def _resolve_operator(self, league_id: UUID, raw_operator_user_id: str | None) -> UUID | None:
        if not raw_operator_user_id:
            return None
        try:
            operator_user_id = UUID(raw_operator_user_id)
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo delegato non valido.",
                code="invalid_operator_user_id",
            ) from exc
        membership = self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.user_id == operator_user_id,
            )
        )
        if membership is None:
            raise ValidationAuthError(
                "Il delegato deve essere un partecipante della lega.",
                code="operator_not_member",
            )
        return operator_user_id

    def _set_nomination_queue(self, session_id: UUID, athlete_ids_raw: list[str]) -> None:
        self._session.execute(
            delete(MarketLiveNominationQueueEntry).where(
                MarketLiveNominationQueueEntry.session_id == session_id
            )
        )
        seen: set[UUID] = set()
        position = 0
        for raw in athlete_ids_raw:
            try:
                athlete_id = UUID(raw)
            except ValueError as exc:
                raise ValidationAuthError(
                    "Identificativo calciatore non valido nella lista di chiamata.",
                    code="invalid_nomination_athlete_id",
                ) from exc
            if athlete_id in seen:
                continue
            seen.add(athlete_id)
            self._session.add(
                MarketLiveNominationQueueEntry(
                    session_id=session_id, athlete_id=athlete_id, position=position
                )
            )
            position += 1
        self._session.flush()

    def _assert_no_conflicting_initial_auction(self, league_id: UUID) -> None:
        """A league cannot run both auction mechanisms for the initial auction."""
        existing_sealed = self._session.scalar(
            select(MarketSession).where(
                MarketSession.league_id == league_id,
                MarketSession.kind == MarketSessionKind.INITIAL_AUCTION,
                MarketSession.parent_session_id.is_(None),
                MarketSession.status.in_(
                    (MarketSessionStatus.SCHEDULED, MarketSessionStatus.OPEN)
                ),
            )
        )
        if existing_sealed is not None and effective_status(
            existing_sealed, now=datetime.now(UTC)
        ) in (MarketSessionStatus.SCHEDULED, MarketSessionStatus.OPEN):
            raise ValidationAuthError(
                "Esiste già un'asta iniziale a buste chiuse attiva per questa lega.",
                code="market_session_already_active",
            )

    def _assert_is_live(self, market_session: MarketSession) -> None:
        if market_session.kind != MarketSessionKind.LIVE_AUCTION:
            raise ValidationAuthError(
                "Sessione di mercato non trovata.",
                code="market_session_not_found",
            )

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

    def _count_queue_remaining(self, session_id: UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count(MarketLiveNominationQueueEntry.id)).where(
                    MarketLiveNominationQueueEntry.session_id == session_id,
                    MarketLiveNominationQueueEntry.consumed_at.is_(None),
                )
            )
            or 0
        )

    def _notify_session_started(self, market_session: MarketSession) -> None:
        notifications = NotificationService(self._session)
        for _team_id, user_id in user_ids_for_league(self._session, market_session.league_id):
            notifications.create_notification(
                user_id=user_id,
                category=NotificationCategory.MERCATO,
                template_key="mercato.asta_live_iniziata",
                template_version=1,
                params={},
                dedup_key=f"market_live_session_started:{market_session.id}:{user_id}",
            )

    def _notify_lot_sold(self, lot: MarketLiveLot, *, team: FantasyTeam, athlete: Athlete) -> None:
        recipient_id = user_ids_for_teams(self._session, [team.id]).get(team.id)
        if recipient_id is None:
            return
        NotificationService(self._session).create_notification(
            user_id=recipient_id,
            category=NotificationCategory.MERCATO,
            template_key="mercato.asta_live_aggiudicato",
            template_version=1,
            params={
                "athlete_name": athlete.canonical_name,
                "amount_credits": lot.current_amount_credits,
            },
            dedup_key=f"market_live_lot_sold:{lot.id}",
        )

    def _notify_pending_swap(
        self, lot: MarketLiveLot, *, team: FantasyTeam, athlete: Athlete
    ) -> None:
        recipient_id = user_ids_for_teams(self._session, [team.id]).get(team.id)
        if recipient_id is None:
            return
        NotificationService(self._session).create_notification(
            user_id=recipient_id,
            category=NotificationCategory.MERCATO,
            template_key="mercato.asta_live_scambio_richiesto",
            template_version=1,
            params={"athlete_name": athlete.canonical_name},
            dedup_key=f"market_live_lot_swap_pending:{lot.id}",
        )

    def _notify_outbid(self, previous_leader_team_id: UUID, lot: MarketLiveLot) -> None:
        recipient_id = user_ids_for_teams(self._session, [previous_leader_team_id]).get(
            previous_leader_team_id
        )
        if recipient_id is None:
            return
        athlete = self._session.get(Athlete, lot.athlete_id)
        NotificationService(self._session).create_notification(
            user_id=recipient_id,
            category=NotificationCategory.MERCATO,
            template_key="mercato.asta_live_sorpassato",
            template_version=1,
            params={"athlete_name": athlete.canonical_name if athlete else "un giocatore"},
            dedup_key=f"market_live_outbid:{lot.id}:{previous_leader_team_id}:{lot.current_amount_credits}",
        )

    def _to_session_response(self, market_session: MarketSession) -> LiveAuctionSessionResponse:
        assert market_session.nomination_mode is not None
        assert market_session.min_increment_credits is not None
        assert market_session.soft_close_seconds is not None
        assert market_session.lot_duration_seconds is not None
        return LiveAuctionSessionResponse(
            id=str(market_session.id),
            leagueId=str(market_session.league_id),
            status=market_session.status.value,
            opensAt=market_session.opens_at.isoformat(),
            closesAt=market_session.closes_at.isoformat(),
            nominationMode=market_session.nomination_mode.value,
            minIncrementCredits=market_session.min_increment_credits,
            softCloseSeconds=market_session.soft_close_seconds,
            lotDurationSeconds=market_session.lot_duration_seconds,
            operatorUserId=(
                str(market_session.operator_user_id) if market_session.operator_user_id else None
            ),
            queueRemaining=self._count_queue_remaining(market_session.id),
            pendingSwapCount=self._count_pending_swaps(market_session.id),
        )

    def _count_pending_swaps(self, session_id: UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count(MarketLiveLot.id)).where(
                    MarketLiveLot.session_id == session_id,
                    MarketLiveLot.status == MarketLiveLotStatus.PENDING_SWAP,
                )
            )
            or 0
        )

    def _to_lot_response(self, lot: MarketLiveLot, *, athlete: Athlete) -> LiveLotResponse:
        minimum_next = compute_minimum_next_amount(
            current_amount_credits=lot.current_amount_credits,
            has_leader=lot.current_leader_team_id is not None,
            min_increment_credits=lot.min_increment_credits,
        )
        leader_name = (
            lot.current_leader_team.name
            if lot.current_leader_team_id is not None and lot.current_leader_team is not None
            else None
        )
        return LiveLotResponse(
            id=str(lot.id),
            sessionId=str(lot.session_id),
            athleteId=str(lot.athlete_id),
            athleteName=athlete.canonical_name,
            sequenceNumber=lot.sequence_number,
            status=lot.status.value,
            openedAt=lot.opened_at.isoformat(),
            closesAt=lot.closes_at.isoformat(),
            minIncrementCredits=lot.min_increment_credits,
            currentLeaderTeamId=(
                str(lot.current_leader_team_id) if lot.current_leader_team_id else None
            ),
            currentLeaderTeamName=leader_name,
            currentAmountCredits=lot.current_amount_credits,
            minimumNextAmountCredits=minimum_next,
            closedAt=lot.closed_at.isoformat() if lot.closed_at else None,
        )

    def _to_raise_response(self, row: MarketLiveRaise) -> LiveRaiseResponse:
        return LiveRaiseResponse(
            id=str(row.id),
            lotId=str(row.lot_id),
            fantasyTeamId=str(row.fantasy_team_id),
            fantasyTeamName=row.fantasy_team.name,
            amountCredits=row.amount_credits,
            placedAt=row.placed_at.isoformat(),
        )

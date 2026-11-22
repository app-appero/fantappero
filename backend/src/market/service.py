"""Market session service: create/close sessions and submit sealed bids (EP08-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.text_folding import repair_provider_text
from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import (
    CreditLedgerReason,
    LeagueAuditAction,
    LeagueMemberRole,
    MarketBidStatus,
    MarketReleaseReason,
    MarketSessionKind,
    MarketSessionStatus,
    NotificationCategory,
)
from fantasy_teams.composition_service import (
    assert_assignment_respects_role_quota,
    reconcile_roster_overflow,
    resolve_effective_athlete_role,
    sync_team_composition_status,
)
from fantasy_teams.factory import ensure_team_for_membership, find_team_for_membership
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_teams.ownership import sync_ownership_on_release
from leagues.capacity import assert_league_full_for_market
from leagues.market_open import write_market_open
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from market.assignment import assign_winning_bid, assign_winning_waiver_bid
from market.gate import assert_market_open, market_status
from market.models import MarketBid, MarketSession
from market.schemas import (
    CreateMarketSessionRequest,
    MarketBidListResponse,
    MarketBidResponse,
    MarketGateResponse,
    MarketReleasePreviewResponse,
    MarketReleaseResultResponse,
    MarketResolutionOutcomeResponse,
    MarketResolutionResponse,
    MarketSessionResponse,
    SetMarketGateRequest,
    SubmitMarketBidRequest,
)
from market.validators import (
    compute_release_refund,
    validate_amount_within_balance,
    validate_athlete_is_free_agent,
    validate_bid_amount,
    validate_bid_targets_session_athlete,
    validate_release_athlete_not_allowed,
    validate_release_athlete_owned_by_team,
    validate_release_athlete_required,
    validate_session_window,
    validate_slot_has_athlete,
    validate_team_eligible_for_session,
)
from market.windows import effective_status, is_open_for_bids
from notifications.league_context import league_params
from notifications.recipients import user_ids_for_teams
from notifications.service import NotificationService
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

# Regola di parità (Doc §20 "Parità nell'asta iniziale e nello spareggio mercato"), decisa da
# Rosario il 19/11, uguale per buste e svincolati: la parità sull'offerta più alta apre UN SOLO
# spareggio di 24 ore, riservato alle squadre in parità e al calciatore conteso. Se anche lo
# spareggio finisce in parità non se ne apre un altro: il calciatore va all'offerta in parità
# inviata per prima (conta l'ultimo invio; a pari orario decide l'id dell'offerta). Se quella
# non si può assegnare (crediti, rosa o ruolo) si passa alla successiva in parità, poi alle
# offerte più basse come in ogni risoluzione. Senza offerte nello spareggio non si assegna nulla.
TIEBREAK_WINDOW = timedelta(hours=24)
TIEBREAK_RULE_FIRST_BID = "first_bid"


MAX_SLOT_INDEX = 1000  # oltre non esiste nessuna rosa: evita int fuori range nel database


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
    try:
        return parsed.astimezone(UTC)
    except (OverflowError, ValueError) as exc:  # es. 0001-01-01T00:00:00+14:00
        raise ValidationAuthError(
            f"Il campo {field} non è una data valida.",
            code="invalid_datetime",
        ) from exc


class MarketService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_gate(self, league_access: LeagueAccess) -> MarketGateResponse:
        return self._gate_response(league_access.league.id)

    def set_gate(
        self,
        league_access: LeagueAccess,
        payload: SetMarketGateRequest,
    ) -> MarketGateResponse:
        if payload.open:
            # Decisione del 20/11: l'interruttore si accende solo a lega al completo (il blocco
            # della lega serializza con gli ingressi e le uscite). Spegnerlo resta sempre possibile.
            self._lock_league(league_access.league.id)
            assert_league_full_for_market(self._session, league_access.league.id)
        write_market_open(self._session, league_access.league.id, payload.open)
        self._pause_or_resume_live_lots(league_access.league.id, resume=payload.open)
        self._session.add(
            LeagueAuditEvent(
                league_id=league_access.league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.MARKET_GATE_TOGGLED,
                details={"open": payload.open},
            )
        )
        try:
            self._session.commit()
        except SQLAlchemyError:
            logger.exception("market_gate_audit_commit_failed")
            self._session.rollback()
            write_market_open(self._session, league_access.league.id, payload.open)
            self._session.commit()
        get_metrics().incr(
            "market_gate_toggled_total",
            labels={"open": "true" if payload.open else "false"},
        )
        return self._gate_response(league_access.league.id)

    def _gate_response(self, league_id: UUID) -> MarketGateResponse:
        status = market_status(self._session, league_id)
        return MarketGateResponse(
            marketOpen=status.market_open,
            memberCount=status.member_count,
            participantCount=status.participant_count,
            leagueFull=status.league_full,
            marketBlockedReason=status.blocked_reason,
            pendingInviteCount=status.pending_invite_count,
        )

    def _pause_or_resume_live_lots(self, league_id: UUID, *, resume: bool) -> None:
        """Chiusura del mercato: il timer del lotto live si ferma; riapertura: riparte."""
        from database.enums import MarketLiveLotStatus
        from market.live_models import MarketLiveLot

        now = datetime.now(UTC)
        lots = self._session.scalars(
            select(MarketLiveLot)
            .join(MarketSession, MarketSession.id == MarketLiveLot.session_id)
            .where(
                MarketSession.league_id == league_id,
                MarketLiveLot.status == MarketLiveLotStatus.OPEN,
            )
            .with_for_update(of=MarketLiveLot)
        ).all()
        for lot in lots:
            if resume and lot.paused_at is not None:
                lot.closes_at = lot.closes_at + (now - lot.paused_at)
                lot.paused_at = None
            elif not resume and lot.paused_at is None:
                lot.paused_at = now

    # -- sessions ---------------------------------------------------------

    def create_auction_session(
        self,
        league_access: LeagueAccess,
        payload: CreateMarketSessionRequest,
    ) -> MarketSessionResponse:
        return self._create_session(league_access, payload, kind=MarketSessionKind.INITIAL_AUCTION)

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
        assert_market_open(league)
        opens_at = _parse_required_datetime(payload.opens_at, field="opensAt")
        closes_at = _parse_required_datetime(payload.closes_at, field="closesAt")
        validate_session_window(opens_at=opens_at, closes_at=closes_at, now=datetime.now(UTC))

        now = datetime.now(UTC)
        active_states = (MarketSessionStatus.SCHEDULED, MarketSessionStatus.OPEN)
        # Si guardano TUTTE le righe ancora "aperte" nel database: una sessione scaduta ma non
        # chiusa a mano non deve nascondere quelle davvero attive.
        same_kind = self._session.scalars(
            select(MarketSession).where(
                MarketSession.league_id == league.id,
                MarketSession.kind == kind,
                MarketSession.parent_session_id.is_(None),
                MarketSession.status.in_(active_states),
            )
        ).all()
        if any(effective_status(row, now=now) in active_states for row in same_kind):
            raise ValidationAuthError(
                "Esiste già una sessione di questo tipo attiva per questa lega.",
                code="market_session_already_active",
            )
        # Uno spareggio ancora aperto (sessione figlia) blocca ogni nuova sessione: altrimenti
        # un altro partecipante potrebbe vincere il calciatore contestato nel frattempo.
        tiebreaks = self._session.scalars(
            select(MarketSession).where(
                MarketSession.league_id == league.id,
                MarketSession.parent_session_id.is_not(None),
                MarketSession.status.in_(active_states),
            )
        ).all()
        if any(effective_status(row, now=now) in active_states for row in tiebreaks):
            raise ValidationAuthError(
                "C'è uno spareggio in corso: concludilo prima di creare una nuova sessione.",
                code="market_session_already_active",
            )
        if kind == MarketSessionKind.INITIAL_AUCTION:
            # A league cannot run both auction mechanisms for the initial auction
            # at once (EP08-09): reject sealed creation while a live session is active.
            live_rows = self._session.scalars(
                select(MarketSession).where(
                    MarketSession.league_id == league.id,
                    MarketSession.kind == MarketSessionKind.LIVE_AUCTION,
                    MarketSession.status.in_(active_states),
                )
            ).all()
            if any(effective_status(row, now=now) in active_states for row in live_rows):
                raise ValidationAuthError(
                    "Esiste già una sessione d'asta a rilanci attiva per questa lega.",
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

        Lo spareggio è uno solo: una nuova parità dentro lo spareggio va all'offerta in
        parità inviata per prima (vedi ``TIEBREAK_WINDOW``), senza aprire altre sessioni.

        Atomic and idempotent: replaying against an already-resolved session just
        returns the persisted outcome without recomputing or re-charging anyone.
        """
        league = self._lock_league(league_access.league.id)
        market_session = self._get_session_for_update(league.id, session_id)
        now = datetime.now(UTC)

        if market_session.status != MarketSessionStatus.RESOLVED:
            # N-2.8: a mercato chiuso non si assegna né si addebita nulla. Una sessione già
            # risolta continua a restituire l'esito salvato (replay idempotente).
            assert_market_open(league)

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

        is_tiebreak = market_session.parent_session_id is not None
        candidates: list[MarketBid] = []
        tie_groups: dict[UUID, list[MarketBid]] = {}
        # Parità dentro uno spareggio: non si riapre nulla, decide l'ordine d'invio.
        repeated_ties: dict[UUID, list[MarketBid]] = {}
        for athlete_id, group in by_athlete.items():
            # A parità d'importo vale l'orario d'invio (aggiornato a ogni nuovo invio), poi l'id:
            # l'ordine è sempre lo stesso, anche con due offerte arrivate nello stesso istante.
            group.sort(key=lambda row: (-row.amount_credits, row.submitted_at, row.id))
            top_amount = group[0].amount_credits
            top_bids = [row for row in group if row.amount_credits == top_amount]
            for loser in group:
                if loser not in top_bids:
                    loser.status = MarketBidStatus.LOST
            if len(top_bids) == 1:
                candidates.append(top_bids[0])
            elif is_tiebreak:
                repeated_ties[athlete_id] = top_bids
            else:
                tie_groups[athlete_id] = top_bids

        # Deterministic, reconstructable order: highest amount first league-wide, so a
        # team that wins several athletes spends on its most valuable bids first.
        candidates.sort(key=lambda row: (-row.amount_credits, row.submitted_at))

        # Offerte più alte che non si sono potute assegnare (crediti, rosa o ruolo): la notifica
        # non deve dire "offerta inferiore".
        unassignable_bid_ids: set[UUID] = set()

        def try_assign(bid: MarketBid) -> bool:
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
                    allow_overflow=True,
                )
            bid.status = MarketBidStatus.WON if slot is not None else MarketBidStatus.LOST
            return slot is not None

        failed_top_bids: list[MarketBid] = []
        for bid in candidates:
            if not try_assign(bid):
                unassignable_bid_ids.add(bid.id)
                failed_top_bids.append(bid)

        # Se l'offerta più alta non si può assegnare (crediti o rosa), il calciatore va alla
        # seconda offerta più alta che ha crediti e posto; a parità vince chi ha offerto prima.
        for failed in failed_top_bids:
            runners_up = [
                row
                for row in by_athlete[failed.athlete_id]
                if row.id != failed.id and row.status == MarketBidStatus.LOST
            ]
            for runner_up in runners_up:
                if try_assign(runner_up):
                    break

        # Spareggio finito di nuovo in parità (regola "first_bid"): si prova l'offerta in parità
        # inviata per prima, poi le altre in parità nello stesso ordine, poi le offerte più basse.
        # Chi resta fuori perché un'offerta uguale è arrivata prima lo dice la notifica.
        lost_on_tie_bid_ids: set[UUID] = set()
        tiebreak_results: list[dict[str, object]] = []
        for athlete_id, tied_bids in repeated_ties.items():
            winner: MarketBid | None = None
            for bid in tied_bids:
                if try_assign(bid):
                    winner = bid
                    break
                unassignable_bid_ids.add(bid.id)
            for bid in tied_bids:
                if bid.status == MarketBidStatus.SUBMITTED:
                    bid.status = MarketBidStatus.LOST
                    lost_on_tie_bid_ids.add(bid.id)
            if winner is None:
                tied_ids = {bid.id for bid in tied_bids}
                for runner_up in by_athlete[athlete_id]:
                    if runner_up.id in tied_ids or runner_up.status != MarketBidStatus.LOST:
                        continue
                    if try_assign(runner_up):
                        winner = runner_up
                        break
            tiebreak_results.append(
                {
                    "athleteId": str(athlete_id),
                    "tiedAmountCredits": tied_bids[0].amount_credits,
                    "teamIds": [str(bid.fantasy_team_id) for bid in tied_bids],
                    "winnerTeamId": str(winner.fantasy_team_id) if winner is not None else None,
                }
            )

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

        bidder_user_ids = user_ids_for_teams(self._session, (bid.fantasy_team_id for bid in bids))
        notifications = NotificationService(self._session)
        # Spareggio "orfano": il calciatore conteso è finito nel frattempo in una rosa (per
        # esempio assegnato a mano dall'amministratore) e nessuna offerta dello spareggio l'ha
        # vinto. Si guarda sempre il calciatore dello spareggio, anche se nessuno ha offerto.
        target_athlete_id = market_session.target_athlete_id
        tiebreak_owner_team_id: UUID | None = None
        tiebreak_cancelled = False
        if is_tiebreak and target_athlete_id is not None:
            tiebreak_owner_team_id = self._session.scalar(
                select(FantasyRosterSlot.fantasy_team_id).where(
                    FantasyRosterSlot.league_id == market_session.league_id,
                    FantasyRosterSlot.athlete_id == target_athlete_id,
                )
            )
            tiebreak_cancelled = tiebreak_owner_team_id is not None and not any(
                bid.athlete_id == target_athlete_id and bid.status == MarketBidStatus.WON
                for bid in bids
            )
        for bid in bids:
            if tiebreak_cancelled and bid.athlete_id == target_athlete_id:
                continue  # l'annullamento si comunica sotto, una volta per squadra in parità
            # Le offerte in parità (EXPIRED) vanno allo spareggio: anche loro vanno avvisate.
            if bid.status not in (
                MarketBidStatus.WON,
                MarketBidStatus.LOST,
                MarketBidStatus.EXPIRED,
            ):
                continue
            recipient_id = bidder_user_ids.get(bid.fantasy_team_id)
            if recipient_id is None:
                continue
            if bid.status == MarketBidStatus.WON:
                outcome = "assigned"
            elif bid.status == MarketBidStatus.EXPIRED:
                outcome = "tiebreak"
            else:
                outcome = "lost"
            notifications.create_notification(
                user_id=recipient_id,
                category=NotificationCategory.MERCATO,
                template_key="mercato.esito_busta",
                template_version=1,
                params={
                    "outcome": outcome,
                    "athlete_name": bid.athlete.canonical_name,
                    "amount_credits": bid.amount_credits,
                    "not_assignable": bid.id in unassignable_bid_ids,
                    "lost_on_tie": bid.id in lost_on_tie_bid_ids,
                    # Asta a buste o svincolati: titoli, testi e link dipendono dal tipo.
                    "session_kind": market_session.kind.value,
                    **league_params(self._session, market_session.league_id),
                },
                dedup_key=f"market_bid_outcome:{bid.id}",
            )
        if tiebreak_cancelled:
            self._notify_tiebreak_cancelled(
                notifications, market_session, owner_team_id=tiebreak_owner_team_id
            )

        market_session.status = MarketSessionStatus.RESOLVED
        market_session.resolved_at = now
        self._session.flush()
        # Tutte le assegnazioni, anche quelle andate a un'offerta successiva o decise dalla
        # regola dello spareggio: lo storico mostra l'evento alle squadre vincitrici.
        won_bids = sorted(
            (bid for bid in bids if bid.status == MarketBidStatus.WON),
            key=lambda row: (-row.amount_credits, row.submitted_at, row.id),
        )
        winners = [
            {
                "fantasyTeamId": str(bid.fantasy_team_id),
                "athleteId": str(bid.athlete_id),
                "amountCredits": bid.amount_credits,
            }
            for bid in won_bids
        ]
        resolution_details: dict[str, object] = {
            "sessionId": str(market_session.id),
            "assigned": len(winners),
            "tiebreaksOpened": tiebreak_count,
            "winners": winners,
        }
        if tiebreak_results:
            resolution_details["tiebreakRule"] = TIEBREAK_RULE_FIRST_BID
            resolution_details["tiebreakResults"] = tiebreak_results
        if tiebreak_cancelled:
            resolution_details["tiebreakCancelled"] = True
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_SESSION_RESOLVED,
            details=resolution_details,
        )
        self._session.commit()
        get_metrics().incr("market_session_resolved_total")
        return self._resolution_summary(market_session)

    def _notify_tiebreak_cancelled(
        self,
        notifications: NotificationService,
        market_session: MarketSession,
        *,
        owner_team_id: UUID | None,
    ) -> None:
        """Avviso «Spareggio annullato» a ogni squadra ammessa allo spareggio, abbia offerto o no.

        Non lo riceve la squadra che ora ha il calciatore (se era fra quelle in parità).
        """
        team_ids: list[UUID] = []
        for raw_team_id in market_session.eligible_team_ids or []:
            try:
                team_id = UUID(str(raw_team_id))
            except ValueError:
                continue
            if team_id != owner_team_id and team_id not in team_ids:
                team_ids.append(team_id)
        if not team_ids:
            return
        athlete = (
            self._session.get(Athlete, market_session.target_athlete_id)
            if market_session.target_athlete_id is not None
            else None
        )
        recipients = user_ids_for_teams(self._session, team_ids)
        params = {
            "outcome": "lost",
            "athlete_name": athlete.canonical_name if athlete is not None else "un giocatore",
            "tiebreak_cancelled": True,
            "session_kind": market_session.kind.value,
            **league_params(self._session, market_session.league_id),
        }
        for team_id in team_ids:
            recipient_id = recipients.get(team_id)
            if recipient_id is None:
                continue
            notifications.create_notification(
                user_id=recipient_id,
                category=NotificationCategory.MERCATO,
                template_key="mercato.esito_busta",
                template_version=1,
                params=params,
                dedup_key=f"market_tiebreak_cancelled:{market_session.id}:{team_id}",
            )

    def _resolution_summary(self, market_session: MarketSession) -> MarketResolutionResponse:
        bids = self._session.scalars(
            select(MarketBid)
            .options(selectinload(MarketBid.athlete))
            .where(
                MarketBid.session_id == market_session.id,
                # Un'offerta ritirata non fa parte dell'esito: non compare come "non assegnata".
                MarketBid.status != MarketBidStatus.CANCELLED,
            )
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
        league = self._lock_league(league_access.league.id)
        assert_market_open(league)
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
        if market_session.parent_session_id is not None:
            # Spareggio: si può pareggiare o rilanciare l'importo del pareggio, non scendere.
            tied_amount = self._session.scalar(
                select(func.max(MarketBid.amount_credits)).where(
                    MarketBid.session_id == market_session.parent_session_id,
                    MarketBid.athlete_id == athlete_id,
                )
            )
            if tied_amount is not None and amount < tied_amount:
                raise ValidationAuthError(
                    f"Nello spareggio l'offerta deve essere almeno {tied_amount} crediti.",
                    code="tiebreak_bid_below_tied_amount",
                )

        team = self._my_team(league_access)
        validate_team_eligible_for_session(
            eligible_team_ids=market_session.eligible_team_ids, fantasy_team_id=team.id
        )
        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            raise ValidationAuthError("Calciatore non trovato.", code="athlete_not_found")

        # 2.7: senza ruolo nel listone l'offerta non potrebbe mai essere assegnata.
        bid_league = league_access.league
        if (
            resolve_effective_athlete_role(
                self._session,
                league_id=bid_league.id,
                athlete_id=athlete_id,
                season_year=bid_league.season_year,
                competition_ids={competition.id for competition in bid_league.competitions},
            )
            is None
        ):
            raise ValidationAuthError(
                "Il calciatore non ha un ruolo valido nel listone: non si può fare un'offerta.",
                code="role_unresolved",
            )

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
            # La risoluzione waiver rispetta la quota di ruolo: se il cambio la supera,
            # l'offerta non potrebbe mai essere assegnata, quindi si rifiuta subito.
            if release_slot is not None:
                try:
                    assert_assignment_respects_role_quota(
                        self._session,
                        league=league_access.league,
                        team=team,
                        athlete_id=athlete_id,
                        slot_index=release_slot.slot_index,
                    )
                except ValidationAuthError as exc:
                    if exc.code != "role_quota_exceeded":
                        raise
                    raise ValidationAuthError(
                        f"{exc.message} Svincola un calciatore dello stesso ruolo "
                        "per fare questa offerta.",
                        code="waiver_role_quota_exceeded",
                    ) from exc
        else:
            validate_release_athlete_not_allowed(payload.release_athlete_id)
            release_athlete_id = None
            # Rosa piena o ruolo al completo non bloccano più l'offerta: se la
            # vinci, il calciatore entra in rosa bloccato finché non liberi
            # spazio (EP08-10 bis), come per gli scambi.

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
            # A parità d'importo vince chi ha offerto prima: un nuovo invio riparte da adesso.
            existing_bid.submitted_at = datetime.now(UTC)
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
        # Come l'invio: a mercato chiuso (o turno in corso) non si ritira nulla.
        league = self._lock_league(league_access.league.id)
        assert_market_open(league)
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
        if bid.status == MarketBidStatus.CANCELLED:
            return  # già ritirata: nessun secondo evento nello storico
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

    # -- voluntary release / refund (EP08-04 / FR-MKT-02) ----------------------

    def preview_release(
        self,
        league_access: LeagueAccess,
        slot_index: int,
        reason_raw: str,
    ) -> MarketReleasePreviewResponse:
        if not 0 <= slot_index <= MAX_SLOT_INDEX:
            raise ValidationAuthError("Slot non trovato.", code="slot_not_found")
        team = self._my_team(league_access)
        reason, percent = self._resolve_release_reason(league_access, reason_raw)
        slot = self._session.scalar(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.slot_index == slot_index,
            )
        )
        if slot is None:
            raise ValidationAuthError("Slot non trovato.", code="slot_not_found")
        athlete_id = validate_slot_has_athlete(slot.athlete_id)
        athlete = self._session.get(Athlete, athlete_id)
        assert athlete is not None
        purchase_credits = slot.purchase_credits or 0
        refund = compute_release_refund(purchase_credits=purchase_credits, refund_percent=percent)
        return MarketReleasePreviewResponse(
            fantasyTeamId=str(team.id),
            slotIndex=slot_index,
            athleteId=str(athlete_id),
            athleteName=athlete.canonical_name,
            purchaseCredits=purchase_credits,
            reason=reason.value,
            refundPercent=percent,
            refundCredits=refund,
        )

    def apply_release(
        self,
        league_access: LeagueAccess,
        slot_index: int,
        reason_raw: str,
        *,
        expected_athlete_id: str | None = None,
    ) -> MarketReleaseResultResponse:
        if not 0 <= slot_index <= MAX_SLOT_INDEX:
            raise ValidationAuthError("Slot non trovato.", code="slot_not_found")
        league = self._lock_league(league_access.league.id)
        # Lo svincolo dell'amministratore vale anche a lega incompleta e a interruttore
        # spento; si ferma solo a turno in corso (20/11).
        assert_market_open(league, actor_is_admin=self._is_league_admin(league_access))
        team = self._my_team(league_access)
        reason, percent = self._resolve_release_reason(league_access, reason_raw)

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
        athlete_id = validate_slot_has_athlete(slot.athlete_id)
        if expected_athlete_id is not None and expected_athlete_id != str(athlete_id):
            # La rosa si è riordinata (o la richiesta è stata ripetuta): nessuno svincolo.
            raise ValidationAuthError(
                "Nello slot c'è un altro calciatore: ricarica la rosa e riprova.",
                code="release_athlete_mismatch",
            )
        athlete = self._session.get(Athlete, athlete_id)
        assert athlete is not None
        purchase_credits = slot.purchase_credits or 0
        refund = compute_release_refund(purchase_credits=purchase_credits, refund_percent=percent)

        account = find_account_for_team(self._session, team.id, for_update=True)
        if account is None:
            raise ValidationAuthError("Conto crediti non trovato.", code="credit_account_not_found")

        slot.athlete_id = None
        slot.purchase_credits = None
        slot.exceeds_role_quota = False
        sync_ownership_on_release(
            self._session,
            fantasy_team_id=team.id,
            slot_index=slot_index,
            athlete_id=athlete_id,
            actor_id=league_access.user.id,
        )
        if refund > 0:
            # Il nome come arriva dal fornitore può avere la codifica rovinata (QA 21-22/11).
            athlete_name = repair_provider_text(athlete.canonical_name)
            apply_ledger_movement(
                self._session,
                account,
                amount=refund,
                reason=CreditLedgerReason.MARKET_RELEASE_REFUND,
                transaction_id=f"release:{team.id}:{slot_index}:{athlete_id}:v{account.version}",
                actor_id=league_access.user.id,
                note=f"Svincolo {athlete_name} ({reason.value}, {percent}%)",
            )
        # Chi era in esubero (di ruolo o di rosa) può rientrare: ripulisce i flag e gli slot extra.
        reconcile_roster_overflow(self._session, league=league, team=team)
        sync_team_composition_status(self._session, team, league=league)
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.FANTASY_ROSTER_SLOT_RELEASED,
            details={
                "fantasyTeamId": str(team.id),
                "slotIndex": slot_index,
                "athleteId": str(athlete_id),
                "reason": reason.value,
                "refundPercent": percent,
                "purchaseCredits": purchase_credits,
                "refundCredits": refund,
            },
        )
        self._session.commit()
        get_metrics().incr("market_release_applied_total", labels={"reason": reason.value})
        self._session.refresh(account)
        return MarketReleaseResultResponse(
            fantasyTeamId=str(team.id),
            slotIndex=slot_index,
            athleteId=str(athlete_id),
            athleteName=athlete.canonical_name,
            purchaseCredits=purchase_credits,
            reason=reason.value,
            refundPercent=percent,
            refundCredits=refund,
            balance=account.balance,
        )

    @staticmethod
    def _is_league_admin(league_access: LeagueAccess) -> bool:
        return (
            league_access.operator_bypass or league_access.membership_role == LeagueMemberRole.OWNER
        )

    def _resolve_release_reason(
        self, league_access: LeagueAccess, reason_raw: str
    ) -> tuple[MarketReleaseReason, int]:
        league_id = league_access.league.id
        try:
            reason = MarketReleaseReason(reason_raw)
        except ValueError as exc:
            raise ValidationAuthError(
                "Causa dello svincolo non valida.",
                code="invalid_release_reason",
            ) from exc
        if reason == MarketReleaseReason.LEAGUE_EXIT and not (
            league_access.operator_bypass or league_access.membership_role == LeagueMemberRole.OWNER
        ):
            # N6: lo svincolo "uscita dai 5 campionati" è una decisione dell'amministratore.
            raise ValidationAuthError(
                "Solo l'amministratore può svincolare per uscita dai 5 campionati.",
                code="release_reason_forbidden",
            )
        rules = self._session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
        if reason == MarketReleaseReason.LEAGUE_EXIT:
            percent = rules.league_exit_refund_percent if rules else 100
        else:
            percent = rules.voluntary_release_refund_percent if rules else 50
        return reason, percent

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
                        MarketBid.session_id == market_session.id,
                        # Le offerte ritirate non contano.
                        MarketBid.status != MarketBidStatus.CANCELLED,
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
                str(market_session.parent_session_id) if market_session.parent_session_id else None
            ),
            targetAthleteId=(
                str(market_session.target_athlete_id) if market_session.target_athlete_id else None
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
            photoUrl=athlete.photo_url,
            amountCredits=bid.amount_credits,
            status=bid.status.value,
            submittedAt=bid.submitted_at.isoformat(),
            releaseAthleteId=str(bid.release_athlete_id) if bid.release_athlete_id else None,
            releaseAthleteName=release_athlete.canonical_name if release_athlete else None,
        )

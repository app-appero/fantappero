"""Sostituto dopo uno scambio sbilanciato: lettura, liberi del ruolo, acquisto (1.5, 25/11).

È solo un completamento della rosa, non un'asta: non passa dal blocco del mercato (lega al
completo, interruttore dell'amministratore) e quindi vale anche a mercato chiuso. Rispetta però
il blocco delle rose a turno in corso, come ogni altra operazione di rosa (anche quelle
dell'amministratore): in quel caso si sceglie dopo il calcolo del turno.

Il prezzo è il Valore del calciatore in questa lega (lo stesso numero «Valore» del listone,
`market.valuation_service.load_market_info`), il minimo previsto se il Valore manca. Compra solo
il proprietario della squadra, per la propria squadra; il diritto viene solo dagli scambi
(`market.trade_replacement`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.text_folding import repair_provider_text, strip_accents
from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.atomic import rollback_on_error
from database.enums import (
    CreditLedgerReason,
    FantasyRole,
    LeagueAuditAction,
    RosterCompositionStatus,
    RosterOwnershipSource,
    TradeReplacementStatus,
)
from fantasy_teams.composition_service import (
    assert_assignment_respects_role_quota,
    resolve_effective_athlete_roles,
    sync_team_composition_status,
)
from fantasy_teams.factory import find_team_for_membership, resolve_roster_size
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_teams.ownership import sync_ownership_on_assign
from fantasy_teams.schemas import RosterUnderQuotaRoleResponse
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from market.assignment import next_free_slot_or_overflow
from market.models import TradeProposal, TradeReplacement
from market.round_freeze import ROUND_IN_PROGRESS_CODE, league_round_in_progress
from market.trade_replacement import (
    ROLE_NOUN_IT,
    can_afford_replacements,
    committed_athlete_ids,
    free_athletes_for_roles,
    free_replacement_prices,
    open_replacements,
    replacement_costs,
    replacement_price,
    role_counts,
    team_under_quota_roles,
)
from market.trade_replacement_schemas import (
    TradeReplacementCandidateListResponse,
    TradeReplacementCandidateResponse,
    TradeReplacementPendingResponse,
    TradeReplacementPurchaseRequest,
    TradeReplacementPurchaseResponse,
    TradeReplacementStatusResponse,
)
from market.trade_schemas import TradeMissingRoleResponse, TradeReplacementCostResponse
from market.valuation_service import load_market_info
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import Club
from sports_data.listone.generate import list_role_assignments
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

#: Ordinamenti dell'elenco dei liberi (``ordine``): per Valore (dal più alto, predefinito o dal
#: più basso) o per nome.
CANDIDATE_ORDERS = frozenset({"valore", "valore-crescente", "nome"})
DEFAULT_CANDIDATE_LIMIT = 300
MAX_CANDIDATE_LIMIT = 1000

#: Nota del movimento di crediti e motivo leggibile nello storico (es. «Sostituto dopo lo
#: scambio: N. Zortea»). La causale resta «Acquisto rosa»: le app già installate la conoscono.
REPLACEMENT_LEDGER_NOTE = "Sostituto dopo lo scambio"

NO_REPLACEMENT_CODE = "replacement_not_available"
NO_REPLACEMENT_MESSAGE = (
    "Non hai sostituti da scegliere: il sostituto spetta solo a chi resta con la rosa incompleta "
    "dopo uno scambio."
)


def _fold(value: str | None) -> str:
    return strip_accents(repair_provider_text(value or "")).casefold()


def replacement_round_block_message(round_number: int) -> str:
    return (
        f"Il turno {round_number} è in corso e le rose sono ferme: potrai scegliere il sostituto "
        f"appena il turno {round_number} sarà calcolato."
    )


class TradeReplacementService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- letture -----------------------------------------------------------------

    def get_status(self, league_access: LeagueAccess) -> TradeReplacementStatusResponse:
        team = self._my_team(league_access)
        return self._status(league_access.league, team)

    def list_candidates(
        self,
        league_access: LeagueAccess,
        *,
        role: str | None,
        search: str | None,
        order: str,
        limit: int,
    ) -> TradeReplacementCandidateListResponse:
        """I calciatori liberi del ruolo che manca, con Valore e media, cercabili e ordinabili.

        Liberi = nel listone della stagione e dei campionati della lega, in nessuna rosa della
        lega e non impegnati in un'asta o negli svincolati ancora da risolvere.
        """
        league = league_access.league
        team = self._my_team(league_access)
        pending = open_replacements(self._session, team.id)
        if not pending:
            raise ValidationAuthError(NO_REPLACEMENT_MESSAGE, code=NO_REPLACEMENT_CODE)
        wanted = self._parse_role(role) if role else pending[0].role
        if wanted not in {row.role for row in pending}:
            raise ValidationAuthError(
                self._wrong_role_message(pending), code="replacement_wrong_role"
            )
        if order not in CANDIDATE_ORDERS:
            raise ValidationAuthError(
                "Ordine non valido: usa «valore», «valore-crescente» o «nome».",
                code="invalid_replacement_order",
            )

        free = free_athletes_for_roles(self._session, league, {wanted})
        athletes = (
            {
                athlete.id: athlete
                for athlete in self._session.scalars(
                    select(Athlete).where(Athlete.id.in_([row.athlete_id for row in free]))
                ).all()
            }
            if free
            else {}
        )
        club_ids = {row.club_id for row in free if row.club_id is not None}
        clubs = (
            dict(
                self._session.execute(select(Club.id, Club.name).where(Club.id.in_(club_ids))).all()
            )
            if club_ids
            else {}
        )
        needle = _fold(search).strip() if search else ""
        if needle:
            free = [
                row
                for row in free
                if needle
                in _fold(
                    athletes[row.athlete_id].canonical_name if row.athlete_id in athletes else ""
                )
                or needle in _fold(clubs.get(row.club_id) if row.club_id else None)
            ]
        market = load_market_info(
            self._session,
            league_id=league.id,
            athlete_ids=[row.athlete_id for row in free],
            league=league,
        )
        balance = self._balance(team.id)
        candidates: list[TradeReplacementCandidateResponse] = []
        for row in free:
            athlete = athletes.get(row.athlete_id)
            info = market.get(row.athlete_id)
            price = self._price(info.market_value if info is not None else None)
            candidates.append(
                TradeReplacementCandidateResponse(
                    athleteId=str(row.athlete_id),
                    name=athlete.canonical_name if athlete is not None else "Calciatore",
                    photoUrl=athlete.photo_url if athlete is not None else None,
                    clubName=clubs.get(row.club_id) if row.club_id else None,
                    role=wanted.value,
                    marketValue=price,
                    seasonAverage=info.season_average if info is not None else None,
                    affordable=price <= balance,
                )
            )
        if order == "nome":
            candidates.sort(key=lambda item: _fold(item.name))
        elif order == "valore-crescente":
            candidates.sort(key=lambda item: (item.market_value, _fold(item.name)))
        else:
            candidates.sort(key=lambda item: (-item.market_value, _fold(item.name)))
        return TradeReplacementCandidateListResponse(
            role=wanted.value,
            balance=balance,
            total=len(candidates),
            candidates=candidates[: max(1, min(limit, MAX_CANDIDATE_LIMIT))],
        )

    # -- acquisto ----------------------------------------------------------------

    @rollback_on_error
    def purchase(
        self,
        league_access: LeagueAccess,
        payload: TradeReplacementPurchaseRequest,
    ) -> TradeReplacementPurchaseResponse:
        """Compra il sostituto: un calciatore libero del ruolo che manca, al suo Valore.

        Stesse protezioni delle altre assegnazioni: la lega è bloccata (``FOR UPDATE``) come
        nelle assegnazioni dell'admin, quindi due acquisti sullo stesso libero si mettono in
        fila e il secondo trova il calciatore già preso; l'indice unico «un calciatore per lega»
        resta l'ultima difesa. Nessun controllo del mercato aperto: solo il turno in corso.
        """
        league = self._lock_league(league_access.league.id)
        block = league_round_in_progress(self._session, league.id)
        if block is not None:
            raise ValidationAuthError(
                replacement_round_block_message(block.number), code=ROUND_IN_PROGRESS_CODE
            )
        team = self._my_team(league_access, for_update=True)
        # Prima il conto, poi i sostituti: stesso ordine dello scambio (conti, slot, sostituti) e
        # delle altre assegnazioni, così un acquisto e uno scambio concorrenti non si bloccano.
        account = find_account_for_team(self._session, team.id, for_update=True)
        pending = open_replacements(self._session, team.id, for_update=True)
        if not pending:
            raise ValidationAuthError(NO_REPLACEMENT_MESSAGE, code=NO_REPLACEMENT_CODE)
        try:
            athlete_id = UUID(payload.athlete_id)
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo calciatore non valido.", code="invalid_athlete_id"
            ) from exc
        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            raise ValidationAuthError("Calciatore non trovato.", code="athlete_not_found")
        name = repair_provider_text(athlete.canonical_name)

        listone = list_role_assignments(
            self._session,
            season_year=league.season_year,
            athlete_ids=[athlete_id],
            competition_ids={competition.id for competition in league.competitions},
        )
        resolved = resolve_effective_athlete_roles(
            self._session,
            league_id=league.id,
            athlete_ids=[athlete_id],
            season_year=league.season_year,
        ).get(athlete_id)
        if not listone or resolved is None:
            raise ValidationAuthError(
                f"{name} non è nel listone della lega: scegline un altro.",
                code="role_unresolved",
            )
        row = next((item for item in pending if item.role == resolved.role), None)
        if row is None:
            raise ValidationAuthError(
                self._wrong_role_message(pending), code="replacement_wrong_role"
            )

        owner = self._session.scalar(
            select(FantasyRosterSlot.fantasy_team_id).where(
                FantasyRosterSlot.league_id == league.id,
                FantasyRosterSlot.athlete_id == athlete_id,
            )
        )
        if owner == team.id:
            raise ValidationAuthError(f"{name} è già nella tua rosa.", code="athlete_already_owned")
        if owner is not None:
            raise self._already_taken(name)
        if athlete_id in committed_athlete_ids(self._session, league.id):
            raise ValidationAuthError(
                f"{name} è in un'asta o negli svincolati ancora aperti: scegline un altro.",
                code="athlete_in_open_auction",
            )

        market = load_market_info(
            self._session, league_id=league.id, athlete_ids=[athlete_id], league=league
        ).get(athlete_id)
        price = self._price(market.market_value if market is not None else None)
        balance = account.balance if account is not None else 0
        if account is None or price > balance:
            raise ValidationAuthError(
                f"{name} costa {price} crediti, più dei tuoi crediti ({balance}): "
                "scegline un altro.",
                code="insufficient_credits",
            )

        slot, overflow = next_free_slot_or_overflow(
            self._session, team_id=team.id, league_id=league.id
        )
        assert_assignment_respects_role_quota(
            self._session,
            league=league,
            team=team,
            athlete_id=athlete_id,
            slot_index=slot.slot_index,
        )
        try:
            with self._session.begin_nested():
                slot.athlete_id = athlete_id
                slot.purchase_credits = price
                slot.exceeds_role_quota = overflow
                self._session.flush()
        except IntegrityError as exc:
            raise self._already_taken(name) from exc

        apply_ledger_movement(
            self._session,
            account,
            amount=-price,
            reason=CreditLedgerReason.ROSTER_PURCHASE,
            transaction_id=f"trade-replacement:{row.id}",
            actor_id=league_access.user.id,
            note=f"{REPLACEMENT_LEDGER_NOTE}: {name}",
        )
        sync_ownership_on_assign(
            self._session,
            league_id=league.id,
            fantasy_team_id=team.id,
            slot_index=slot.slot_index,
            athlete_id=athlete_id,
            purchase_credits=price,
            source=RosterOwnershipSource.MARKET,
            previous_athlete_id=None,
            actor_id=league_access.user.id,
        )
        row.status = TradeReplacementStatus.CHOSEN
        row.athlete_id = athlete_id
        row.price_credits = price
        row.chosen_at = datetime.now(UTC)
        self._session.flush()

        previous_status = team.composition_status
        report = sync_team_composition_status(self._session, team, league=league)
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.MARKET_TRADE_REPLACEMENT_PURCHASED,
                details={
                    "fantasyTeamId": str(team.id),
                    "athleteId": str(athlete_id),
                    "role": row.role.value,
                    "priceCredits": price,
                    "proposalId": str(row.trade_proposal_id),
                    "replacementId": str(row.id),
                    "slotIndex": slot.slot_index,
                },
            )
        )
        if (
            report.status == RosterCompositionStatus.VALIDATED
            and previous_status != RosterCompositionStatus.VALIDATED
        ):
            self._session.add(
                LeagueAuditEvent(
                    league_id=league.id,
                    actor_id=league_access.user.id,
                    action=LeagueAuditAction.FANTASY_ROSTER_COMPOSITION_VALIDATED,
                    details={
                        "fantasyTeamId": str(team.id),
                        "filledSlots": report.filled_slots,
                        "competitionCount": report.competition_count,
                        "counts": report.counts,
                    },
                )
            )
        self._session.commit()
        get_metrics().incr("trade_replacement_purchased_total", labels={"role": row.role.value})
        logger.info(
            "trade_replacement_purchased",
            extra={
                "league_id": str(league.id),
                "fantasy_team_id": str(team.id),
                "athlete_id": str(athlete_id),
                "price_credits": price,
            },
        )
        return TradeReplacementPurchaseResponse(
            athleteId=str(athlete_id),
            athleteName=name,
            role=row.role.value,
            priceCredits=price,
            balance=account.balance,
            status=self._status(league, team),
        )

    # -- aiuti ---------------------------------------------------------------------

    def _status(self, league: League, team: FantasyTeam) -> TradeReplacementStatusResponse:
        pending = open_replacements(self._session, team.id)
        filled = len(
            self._session.scalars(
                select(FantasyRosterSlot.id).where(
                    FantasyRosterSlot.fantasy_team_id == team.id,
                    FantasyRosterSlot.athlete_id.is_not(None),
                )
            ).all()
        )
        latest = max(pending, key=lambda row: (row.created_at, str(row.id))) if pending else None
        proposal = (
            self._session.get(TradeProposal, latest.trade_proposal_id)
            if latest is not None
            else None
        )
        other_name: str | None = None
        received_names: list[str] = []
        received_credits = 0
        if proposal is not None:
            is_proposer = proposal.proposer_team_id == team.id
            received_ids = [
                UUID(value)
                for value in (
                    proposal.requested_athlete_ids if is_proposer else proposal.offered_athlete_ids
                )
            ]
            received_credits = (
                proposal.requested_credits if is_proposer else proposal.offered_credits
            )
            names = (
                dict(
                    self._session.execute(
                        select(Athlete.id, Athlete.canonical_name).where(
                            Athlete.id.in_(received_ids)
                        )
                    ).all()
                )
                if received_ids
                else {}
            )
            received_names = [
                names[athlete_id] for athlete_id in received_ids if athlete_id in names
            ]
            other = self._session.get(
                FantasyTeam,
                proposal.recipient_team_id if is_proposer else proposal.proposer_team_id,
            )
            other_name = other.name if other is not None else None
        block = league_round_in_progress(self._session, league.id) if pending else None
        balance = self._balance(team.id)
        missing = [row.role for row in pending]
        costs = (
            replacement_costs(missing, free_replacement_prices(self._session, league, set(missing)))
            if missing
            else ()
        )
        cheapest = [cost.cheapest_price for cost in costs if cost.cheapest_price is not None]
        return TradeReplacementStatusResponse(
            teamId=str(team.id),
            rosterSize=resolve_roster_size(self._session, league.id),
            filledSlots=filled,
            balance=balance,
            pending=[
                TradeReplacementPendingResponse(
                    id=str(row.id),
                    role=row.role.value,
                    tradeProposalId=str(row.trade_proposal_id),
                    createdAt=row.created_at.isoformat(),
                )
                for row in pending
            ],
            missingRoles=[
                TradeMissingRoleResponse(role=role.value, count=count)
                for role, count in role_counts(row.role for row in pending)
            ],
            tradeProposalId=str(proposal.id) if proposal is not None else None,
            otherTeamName=other_name,
            receivedAthleteNames=received_names,
            receivedCredits=received_credits,
            blockedReason="round_in_progress" if block is not None else None,
            blockedMessage=(
                replacement_round_block_message(block.number) if block is not None else None
            ),
            canAffordReplacement=can_afford_replacements(balance, costs),
            cheapestReplacementPrice=min(cheapest) if cheapest else None,
            replacementCosts=[
                TradeReplacementCostResponse(
                    role=cost.role.value,
                    count=cost.count,
                    cheapestPrice=cost.cheapest_price,
                    totalPrice=cost.total_price,
                )
                for cost in costs
            ],
            underQuotaRoles=[
                RosterUnderQuotaRoleResponse(
                    role=item.role.value, count=item.count, quota=item.quota
                )
                for item in team_under_quota_roles(self._session, league, team.id)
            ],
        )

    def _my_team(self, league_access: LeagueAccess, *, for_update: bool = False) -> FantasyTeam:
        """La squadra di chi chiama: compra solo il proprietario, per sé (mai l'operatore)."""
        membership = self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_access.league.id,
                LeagueMembership.user_id == league_access.user.id,
            )
        )
        if membership is None:
            raise ValidationAuthError(
                "Devi essere partecipante della lega per scegliere il sostituto.",
                code="membership_required",
            )
        team = find_team_for_membership(self._session, membership.id)
        if team is None:
            raise ValidationAuthError(
                "Non hai ancora una squadra in questa lega.", code="fantasy_team_not_found"
            )
        if for_update:
            self._session.execute(
                select(FantasyTeam.id).where(FantasyTeam.id == team.id).with_for_update()
            )
        return team

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League).where(League.id == league_id).with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

    def _balance(self, team_id: UUID) -> int:
        account = find_account_for_team(self._session, team_id)
        return account.balance if account is not None else 0

    @staticmethod
    def _price(market_value: int | None) -> int:
        return replacement_price(market_value)

    @staticmethod
    def _parse_role(raw: str) -> FantasyRole:
        try:
            return FantasyRole(raw.strip().upper())
        except ValueError as exc:
            raise ValidationAuthError(
                "Ruolo non valido: usa P, D, C o A.", code="invalid_role"
            ) from exc

    @staticmethod
    def _wrong_role_message(pending: list[TradeReplacement]) -> str:
        roles = [role for role, _count in role_counts(row.role for row in pending)]
        names = " o ".join(ROLE_NOUN_IT[role][0] for role in roles)
        return f"Dopo lo scambio ti manca un {names}: puoi scegliere solo un {names}."

    @staticmethod
    def _already_taken(name: str) -> ValidationAuthError:
        return ValidationAuthError(
            f"{name} è già nella rosa di un'altra squadra della lega: scegline un altro.",
            code="athlete_already_owned",
        )

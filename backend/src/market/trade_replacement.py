"""Sostituto dopo uno scambio sbilanciato: regole e registro (1.5, decisione del 25/11).

Uno scambio che lascia una squadra sotto la misura della rosa (es. 2 per 1: 34/35) la
bloccherebbe senza uscita: con meno giocatori della misura non si schiera la formazione
(`roster_allows_lineup`) e negli svincolati lo svincolo è obbligatorio. Appena lo scambio
diventa effettivo (accettato, o approvato dall'admin) la squadra ha il diritto di comprare,
anche a mercato chiuso, un calciatore libero del ruolo che le manca, al suo Valore.

La verità è qui, lato server:

- il diritto nasce SOLO da uno scambio eseguito: una riga ``trade_replacements`` per ogni posto
  che lo scambio ha lasciato vuoto (al massimo i giocatori ceduti in più, al massimo i posti
  vuoti). Una rosa incompleta per altri motivi (asta, svincolo, rimozione dell'admin) non dà
  nessun diritto, altrimenti a mercato chiuso si comprerebbe aggirando l'asta;
- il ruolo è quello che manca secondo le quote per ruolo della lega (le stesse della
  composizione della rosa); a parità di scelta, o se nessun ruolo è sotto quota, il ruolo del
  giocatore ceduto in più;
- le righe aperte seguono la rosa: ogni scrittura dello stato della rosa
  (`sync_team_composition_status`) le riallinea, così se la squadra torna alla misura in altro
  modo (scambio 1 per 2, assegnazione dell'admin) si chiudono da sole (``cancelled``).

Avvisi in più (suggerimenti della corsa Mercato, 25/11), senza cambiare nessuna regola: i crediti
dopo lo scambio confrontati con il libero più economico del ruolo che manca (stesso prezzo e
stessi liberi dell'acquisto) e i ruoli che restano sotto la quota della lega anche a rosa alla
misura.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from database.enums import (
    FantasyRole,
    MarketBidStatus,
    MarketLiveLotStatus,
    MarketSessionStatus,
    TradeReplacementStatus,
)
from fantasy_teams.composition import RosterCompositionLimits, UnderQuotaRole, under_quota_roles
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from market.models import MarketBid, MarketSession, TradeProposal, TradeReplacement
from market.valuation import MIN_LEAGUE_CREDITS
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)

#: Ordine dei ruoli nei conteggi e nei testi (P, D, C, A).
ROLE_ORDER: tuple[FantasyRole, ...] = (
    FantasyRole.P,
    FantasyRole.D,
    FantasyRole.C,
    FantasyRole.A,
)

#: Nome del ruolo al singolare e al plurale, come nei testi di sito e app («1 Difensore»).
ROLE_NOUN_IT: dict[FantasyRole, tuple[str, str]] = {
    FantasyRole.P: ("Portiere", "Portieri"),
    FantasyRole.D: ("Difensore", "Difensori"),
    FantasyRole.C: ("Centrocampista", "Centrocampisti"),
    FantasyRole.A: ("Attaccante", "Attaccanti"),
}


def role_count_label(role: FantasyRole, count: int) -> str:
    """«1 Difensore» / «2 Difensori»."""
    singular, plural = ROLE_NOUN_IT[role]
    return f"{count} {singular if count == 1 else plural}"


def role_counts(roles: Iterable[FantasyRole]) -> list[tuple[FantasyRole, int]]:
    """Ruoli raggruppati nell'ordine P, D, C, A: ``[(D, 2), (C, 1)]``."""
    counter = Counter(roles)
    return [(role, counter[role]) for role in ROLE_ORDER if counter[role] > 0]


def missing_roles_label(roles: Iterable[FantasyRole]) -> str:
    """«1 Difensore», «2 Difensori», «1 Difensore e 1 Centrocampista»."""
    parts = [role_count_label(role, count) for role, count in role_counts(roles)]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return f"{', '.join(parts[:-1])} e {parts[-1]}"


def net_outgoing_roles(
    outgoing: Sequence[FantasyRole | None], incoming: Sequence[FantasyRole | None]
) -> list[FantasyRole]:
    """I ruoli ceduti «in più»: quelli usciti meno quelli entrati, nell'ordine dei ceduti."""
    still_incoming = Counter(role for role in incoming if role is not None)
    result: list[FantasyRole] = []
    for role in outgoing:
        if role is None:
            continue
        if still_incoming[role] > 0:
            still_incoming[role] -= 1
            continue
        result.append(role)
    return result


def plan_replacement_roles(
    *,
    limits: RosterCompositionLimits,
    roster_roles: Iterable[FantasyRole | None],
    roster_count: int,
    cap: int,
    preferred: Sequence[FantasyRole] = (),
) -> list[FantasyRole]:
    """I ruoli dei sostituti da scegliere, al massimo ``cap`` e mai più dei posti vuoti.

    ``roster_roles`` sono i ruoli dei calciatori in rosa (anche quelli in esubero: contano
    nella quota come nella valutazione della rosa), ``roster_count`` quanti sono (anche chi non
    ha un ruolo). Un ruolo si può scegliere tante volte quante mancano alla sua quota. Prima i
    ruoli in ``preferred`` (i diritti già aperti, poi i ceduti in più), poi gli altri ruoli
    sotto quota nell'ordine P, D, C, A. Se nessun ruolo è sotto quota (quote che non arrivano
    alla misura della rosa) vale il ruolo del giocatore ceduto in più.
    """
    count = max(0, min(cap, limits.roster_size - roster_count))
    if count == 0:
        return []
    counts = Counter(role for role in roster_roles if role is not None)
    remaining = {role: max(0, limits.for_role(role) - counts[role]) for role in ROLE_ORDER}
    chosen: list[FantasyRole] = []
    for role in preferred:
        if len(chosen) >= count:
            break
        if remaining[role] > 0:
            chosen.append(role)
            remaining[role] -= 1
    for role in ROLE_ORDER:
        while len(chosen) < count and remaining[role] > 0:
            chosen.append(role)
            remaining[role] -= 1
    fallback = list(preferred)
    while len(chosen) < count and fallback:
        chosen.append(fallback[len(chosen) % len(fallback)])
    return chosen


_TABLE_READY_KEY = "trade_replacements_ready"


def replacements_table_ready(session: Session) -> bool:
    """La tabella ``trade_replacements`` c'è (migrazione ``c3e8a5f17b24`` applicata).

    Il codice nuovo può girare un momento prima della migrazione (deploy a rotazione) o su un
    database più vecchio (il test delle migrazioni popola il database un passo prima della
    testa): allora non ci sono sostituti e tutto il resto (scambi, rose, formazioni) va avanti
    come prima. La prova gira in un savepoint, così un errore non rovina la transazione, e il
    risultato resta in memoria per la sessione.
    """
    cached = session.info.get(_TABLE_READY_KEY)
    if cached is not None:
        return bool(cached)
    try:
        with session.begin_nested():
            session.execute(select(TradeReplacement.id).limit(0))
        ready = True
    except ProgrammingError:
        ready = False
    session.info[_TABLE_READY_KEY] = ready
    return ready


def open_replacements(
    session: Session, team_id: UUID, *, for_update: bool = False
) -> list[TradeReplacement]:
    """I sostituti ancora da scegliere della squadra, dal più vecchio."""
    if not replacements_table_ready(session):
        return []
    stmt = (
        select(TradeReplacement)
        .where(
            TradeReplacement.fantasy_team_id == team_id,
            TradeReplacement.status == TradeReplacementStatus.PENDING,
        )
        .order_by(TradeReplacement.created_at.asc(), TradeReplacement.id.asc())
    )
    if for_update:
        stmt = stmt.with_for_update()
    return list(session.scalars(stmt).all())


def has_open_replacements(session: Session, team_id: UUID) -> bool:
    if not replacements_table_ready(session):
        return False
    return (
        session.scalar(
            select(TradeReplacement.id)
            .where(
                TradeReplacement.fantasy_team_id == team_id,
                TradeReplacement.status == TradeReplacementStatus.PENDING,
            )
            .limit(1)
        )
        is not None
    )


def _occupied_athlete_ids(session: Session, team_id: UUID) -> list[UUID]:
    return [
        athlete_id
        for athlete_id in session.scalars(
            select(FantasyRosterSlot.athlete_id)
            .where(
                FantasyRosterSlot.fantasy_team_id == team_id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
            .order_by(FantasyRosterSlot.slot_index.asc())
        ).all()
        if athlete_id is not None
    ]


def _roles_of(
    session: Session, league: League, athlete_ids: Sequence[UUID]
) -> dict[UUID, FantasyRole]:
    from fantasy_teams.composition_service import resolve_effective_athlete_roles

    resolved = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=list(athlete_ids),
        season_year=league.season_year,
    )
    return {athlete_id: item.role for athlete_id, item in resolved.items()}


def team_under_quota_roles(session: Session, league: League, team_id: UUID) -> list[UnderQuotaRole]:
    """I ruoli sotto la quota della lega nella rosa di adesso (avviso, nessuna regola)."""
    from fantasy_teams.composition_service import resolve_league_rules_limits

    occupied = _occupied_athlete_ids(session, team_id)
    roles = _roles_of(session, league, occupied)
    counts = Counter(roles[athlete_id] for athlete_id in occupied if athlete_id in roles)
    return under_quota_roles(resolve_league_rules_limits(session, league.id), counts)


def reconcile_trade_replacements(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    trade: TradeProposal | None = None,
    new_allowance: int = 0,
    preferred_roles: Sequence[FantasyRole] = (),
) -> list[TradeReplacement]:
    """Allinea i sostituti aperti della squadra alla rosa di adesso; con ``trade`` ne crea.

    Senza ``trade`` (ogni scrittura dello stato della rosa) non nasce nessun diritto nuovo: le
    righe aperte restano quante ne servono ancora, al massimo i posti vuoti. Una riga il cui
    ruolo non manca più prende un ruolo che manca, se c'è; le altre si chiudono come
    ``cancelled`` (la rosa è tornata alla misura in altro modo).

    Con ``trade`` (scambio appena eseguito, `market.trade_execution.execute_trade`) si
    aggiungono al massimo ``new_allowance`` righe nuove (i giocatori ceduti in più), sempre
    entro i posti vuoti. Ritorna le righe create. Fa flush e lascia il commit al chiamante.
    """
    from fantasy_teams.composition_service import resolve_league_rules_limits

    session.flush()  # la sessione non fa autoflush: le letture sotto devono vedere la rosa nuova
    if not replacements_table_ready(session):
        return []
    existing = open_replacements(session, team.id, for_update=True)
    if not existing and (trade is None or new_allowance <= 0):
        return []
    limits = resolve_league_rules_limits(session, league.id)
    occupied = _occupied_athlete_ids(session, team.id)
    roles = _roles_of(session, league, occupied)
    needed = plan_replacement_roles(
        limits=limits,
        roster_roles=[roles.get(athlete_id) for athlete_id in occupied],
        roster_count=len(occupied),
        cap=len(existing) + (max(0, new_allowance) if trade is not None else 0),
        preferred=[*(row.role for row in existing), *preferred_roles],
    )
    still_needed = Counter(needed)
    unmatched: list[TradeReplacement] = []
    for row in existing:
        if still_needed[row.role] > 0:
            still_needed[row.role] -= 1
        else:
            unmatched.append(row)
    leftover: list[FantasyRole] = []
    for role in needed:
        if still_needed[role] > 0:
            leftover.append(role)
            still_needed[role] -= 1
    now = datetime.now(UTC)
    cancelled = 0
    for row in unmatched:
        if leftover:
            row.role = leftover.pop(0)
        else:
            row.status = TradeReplacementStatus.CANCELLED
            row.cancelled_at = now
            cancelled += 1
    created: list[TradeReplacement] = []
    if trade is not None:
        for role in leftover:
            row = TradeReplacement(
                league_id=league.id,
                fantasy_team_id=team.id,
                trade_proposal_id=trade.id,
                role=role,
                status=TradeReplacementStatus.PENDING,
            )
            session.add(row)
            created.append(row)
    if created or cancelled or unmatched:
        session.flush()
    if cancelled:
        logger.info(
            "trade_replacement_cancelled",
            extra={"fantasy_team_id": str(team.id), "count": cancelled},
        )
        get_metrics().incr("trade_replacement_cancelled_total", amount=cancelled)
    if created:
        logger.info(
            "trade_replacement_created",
            extra={
                "fantasy_team_id": str(team.id),
                "trade_proposal_id": str(trade.id) if trade is not None else None,
                "roles": [row.role.value for row in created],
            },
        )
        get_metrics().incr("trade_replacement_created_total", amount=len(created))
    return created


def replacement_price(market_value: int | None) -> int:
    """Prezzo del sostituto: il Valore del calciatore in questa lega, il minimo se manca."""
    return market_value if market_value is not None and market_value > 0 else MIN_LEAGUE_CREDITS


@dataclass(frozen=True)
class FreeAthlete:
    """Un calciatore libero che si può scegliere come sostituto."""

    athlete_id: UUID
    club_id: UUID | None
    role: FantasyRole


def free_athletes_for_roles(
    session: Session, league: League, roles: Iterable[FantasyRole]
) -> list[FreeAthlete]:
    """I liberi dei ruoli dati, nell'ordine del listone.

    Liberi = nel listone della stagione e dei campionati della lega, in nessuna rosa della lega e
    non impegnati in un'asta o negli svincolati ancora da risolvere. È l'elenco della finestra
    «Scegli il sostituto» e la base dei prezzi più bassi degli avvisi: stesse regole, così un
    avviso non conta un calciatore che poi non si può prendere.
    """
    from fantasy_teams.composition_service import resolve_effective_athlete_roles
    from sports_data.listone.generate import list_role_assignments

    wanted = set(roles)
    if not wanted:
        return []
    assignments = list_role_assignments(
        session,
        season_year=league.season_year,
        competition_ids={competition.id for competition in league.competitions},
    )
    resolved = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=[row.athlete_id for row in assignments],
        season_year=league.season_year,
    )
    owned = set(
        session.scalars(
            select(FantasyRosterSlot.athlete_id).where(
                FantasyRosterSlot.league_id == league.id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all()
    )
    busy = committed_athlete_ids(session, league.id)
    result: list[FreeAthlete] = []
    for row in assignments:
        item = resolved.get(row.athlete_id)
        if item is None or item.role not in wanted:
            continue
        if row.athlete_id in owned or row.athlete_id in busy:
            continue
        result.append(FreeAthlete(athlete_id=row.athlete_id, club_id=row.club_id, role=item.role))
    return result


def free_replacement_prices(
    session: Session, league: League, roles: Iterable[FantasyRole]
) -> dict[FantasyRole, list[int]]:
    """I prezzi dei liberi di ogni ruolo dato, dal più basso (Valore, il minimo se manca)."""
    from market.valuation_service import load_market_info

    wanted = set(roles)
    prices: dict[FantasyRole, list[int]] = {role: [] for role in wanted}
    free = free_athletes_for_roles(session, league, wanted)
    if not free:
        return prices
    market = load_market_info(
        session,
        league_id=league.id,
        athlete_ids=[item.athlete_id for item in free],
        league=league,
    )
    for item in free:
        info = market.get(item.athlete_id)
        prices[item.role].append(replacement_price(info.market_value if info is not None else None))
    for values in prices.values():
        values.sort()
    return prices


@dataclass(frozen=True)
class ReplacementCost:
    """Quanto costano i sostituti di un ruolo che manca, ai prezzi dei liberi di adesso."""

    role: FantasyRole
    #: Quanti sostituti di questo ruolo.
    count: int
    #: Il libero più economico del ruolo; ``None`` se non ce n'è nessuno.
    cheapest_price: int | None
    #: I ``count`` liberi più economici insieme; ``None`` se non ce ne sono abbastanza.
    total_price: int | None


def replacement_costs(
    missing: Iterable[FantasyRole], prices: dict[FantasyRole, list[int]]
) -> tuple[ReplacementCost, ...]:
    """Il costo più basso dei sostituti da scegliere, ruolo per ruolo (ordine P, D, C, A)."""
    costs: list[ReplacementCost] = []
    for role, count in role_counts(missing):
        values = prices.get(role, [])
        costs.append(
            ReplacementCost(
                role=role,
                count=count,
                cheapest_price=values[0] if values else None,
                total_price=sum(values[:count]) if len(values) >= count else None,
            )
        )
    return tuple(costs)


def can_afford_replacements(balance: int, costs: Sequence[ReplacementCost]) -> bool:
    """La squadra può prendere da sola tutti i sostituti con i suoi crediti.

    Vero senza sostituti da scegliere; falso se per un ruolo non ci sono abbastanza liberi o se i
    più economici insieme costano più dei crediti. Solo un avviso: l'acquisto controlla da sé.
    """
    total = 0
    for cost in costs:
        if cost.total_price is None:
            return False
        total += cost.total_price
    return total <= balance


@dataclass(frozen=True)
class RosterAfterTrade:
    """Come resterebbe la rosa di una squadra dopo uno scambio (avviso prima di accettare)."""

    team_id: UUID
    size_after: int
    roster_size: int
    #: I sostituti da scegliere subito dopo lo scambio: i diritti già aperti che restano e quelli
    #: che lo scambio crea. Vuoto se la rosa resta alla misura (o se manca qualcuno per altri
    #: motivi, che non danno diritto al sostituto).
    missing_roles: tuple[FantasyRole, ...] = field(default_factory=tuple)
    #: Crediti dopo lo scambio, con i crediti offerti o chiesti nella proposta.
    balance_after: int = 0
    #: Il prezzo più basso dei sostituti, ruolo per ruolo (vuoto senza sostituti).
    replacement_costs: tuple[ReplacementCost, ...] = field(default_factory=tuple)
    #: ``False`` se con i crediti di dopo lo scambio non può prendere da sola i sostituti.
    can_afford_replacement: bool = True
    #: Ruoli sotto la quota della lega subito dopo lo scambio (prima dei sostituti), anche a
    #: rosa alla misura: solo un avviso.
    under_quota: tuple[UnderQuotaRole, ...] = field(default_factory=tuple)


class RosterAfterTradeCalculator:
    """Rosa dopo lo scambio per più proposte della stessa lega, con le letture in cache."""

    def __init__(self, session: Session, league: League) -> None:
        from fantasy_teams.composition_service import resolve_league_rules_limits

        self._session = session
        self._league = league
        self._limits = resolve_league_rules_limits(session, league.id)
        self._occupied: dict[UUID, list[UUID]] = {}
        self._open_roles: dict[UUID, list[FantasyRole]] = {}
        self._roles: dict[UUID, FantasyRole | None] = {}
        self._balances: dict[UUID, int] = {}
        self._prices: dict[FantasyRole, list[int]] = {}

    def _team_roster(self, team_id: UUID) -> list[UUID]:
        if team_id not in self._occupied:
            self._occupied[team_id] = _occupied_athlete_ids(self._session, team_id)
        return self._occupied[team_id]

    def _team_open_roles(self, team_id: UUID) -> list[FantasyRole]:
        if team_id not in self._open_roles:
            self._open_roles[team_id] = [
                row.role for row in open_replacements(self._session, team_id)
            ]
        return self._open_roles[team_id]

    def _team_balance(self, team_id: UUID) -> int:
        if team_id not in self._balances:
            from fantasy_teams.ledger import find_account_for_team

            account = find_account_for_team(self._session, team_id)
            self._balances[team_id] = account.balance if account is not None else 0
        return self._balances[team_id]

    def _role_prices(self, roles: Iterable[FantasyRole]) -> dict[FantasyRole, list[int]]:
        """Prezzi dei liberi, letti una volta per ruolo: lo scambio non cambia i liberi."""
        missing = {role for role in roles if role not in self._prices}
        if missing:
            self._prices.update(free_replacement_prices(self._session, self._league, missing))
        return self._prices

    def _resolve(self, athlete_ids: Iterable[UUID]) -> None:
        missing = [athlete_id for athlete_id in athlete_ids if athlete_id not in self._roles]
        if not missing:
            return
        resolved = _roles_of(self._session, self._league, missing)
        for athlete_id in missing:
            self._roles[athlete_id] = resolved.get(athlete_id)

    def after(
        self,
        team_id: UUID,
        *,
        outgoing: Sequence[UUID],
        incoming: Sequence[UUID],
        credits_out: int = 0,
        credits_in: int = 0,
    ) -> RosterAfterTrade:
        """La rosa di ``team_id`` se cede ``outgoing`` e ``credits_out`` e riceve ``incoming`` e
        ``credits_in``."""
        roster = self._team_roster(team_id)
        leaving = set(outgoing)
        present = set(roster)
        after = [athlete_id for athlete_id in roster if athlete_id not in leaving]
        after.extend(athlete_id for athlete_id in incoming if athlete_id not in present)
        self._resolve([*after, *outgoing, *incoming])
        open_roles = self._team_open_roles(team_id)
        gone = [athlete_id for athlete_id in outgoing if athlete_id in present]
        after_roles = [self._roles.get(athlete_id) for athlete_id in after]
        missing = plan_replacement_roles(
            limits=self._limits,
            roster_roles=after_roles,
            roster_count=len(after),
            cap=len(open_roles) + max(0, len(gone) - len(incoming)),
            preferred=[
                *open_roles,
                *net_outgoing_roles(
                    [self._roles.get(athlete_id) for athlete_id in gone],
                    [self._roles.get(athlete_id) for athlete_id in incoming],
                ),
            ],
        )
        balance_after = self._team_balance(team_id) - max(0, credits_out) + max(0, credits_in)
        costs = replacement_costs(missing, self._role_prices(missing)) if missing else ()
        counts = Counter(role for role in after_roles if role is not None)
        return RosterAfterTrade(
            team_id=team_id,
            size_after=len(after),
            roster_size=self._limits.roster_size,
            missing_roles=tuple(sorted(missing, key=ROLE_ORDER.index)),
            balance_after=balance_after,
            replacement_costs=costs,
            can_afford_replacement=can_afford_replacements(balance_after, costs),
            under_quota=tuple(under_quota_roles(self._limits, counts)),
        )


def committed_athlete_ids(session: Session, league_id: UUID) -> set[UUID]:
    """Calciatori impegnati in un'asta o negli svincolati non ancora risolti della lega.

    Offerte a buste (asta iniziale, svincolati, spareggi) ancora in gioco in una sessione non
    risolta, e lotti dell'asta a rilanci aperti o in attesa dello scambio di rosa: il sostituto
    non può «rubarli» a chi sta offrendo.
    """
    from market.live_models import MarketLiveLot

    bids = set(
        session.scalars(
            select(MarketBid.athlete_id)
            .join(MarketSession, MarketSession.id == MarketBid.session_id)
            .where(
                MarketSession.league_id == league_id,
                MarketSession.status != MarketSessionStatus.RESOLVED,
                MarketBid.status == MarketBidStatus.SUBMITTED,
            )
        ).all()
    )
    tiebreaks = set(
        session.scalars(
            select(MarketSession.target_athlete_id).where(
                MarketSession.league_id == league_id,
                MarketSession.status != MarketSessionStatus.RESOLVED,
                MarketSession.target_athlete_id.is_not(None),
            )
        ).all()
    )
    lots = set(
        session.scalars(
            select(MarketLiveLot.athlete_id)
            .join(MarketSession, MarketSession.id == MarketLiveLot.session_id)
            .where(
                MarketSession.league_id == league_id,
                MarketLiveLot.status.in_(
                    (MarketLiveLotStatus.OPEN, MarketLiveLotStatus.PENDING_SWAP)
                ),
            )
        ).all()
    )
    return {athlete_id for athlete_id in bids | tiebreaks | lots if athlete_id is not None}

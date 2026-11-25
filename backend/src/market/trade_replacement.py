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
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import (
    FantasyRole,
    MarketBidStatus,
    MarketLiveLotStatus,
    MarketSessionStatus,
    TradeReplacementStatus,
)
from fantasy_teams.composition import RosterCompositionLimits
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from market.models import MarketBid, MarketSession, TradeProposal, TradeReplacement
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


def open_replacements(
    session: Session, team_id: UUID, *, for_update: bool = False
) -> list[TradeReplacement]:
    """I sostituti ancora da scegliere della squadra, dal più vecchio."""
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

    def _resolve(self, athlete_ids: Iterable[UUID]) -> None:
        missing = [athlete_id for athlete_id in athlete_ids if athlete_id not in self._roles]
        if not missing:
            return
        resolved = _roles_of(self._session, self._league, missing)
        for athlete_id in missing:
            self._roles[athlete_id] = resolved.get(athlete_id)

    def after(
        self, team_id: UUID, *, outgoing: Sequence[UUID], incoming: Sequence[UUID]
    ) -> RosterAfterTrade:
        roster = self._team_roster(team_id)
        leaving = set(outgoing)
        present = set(roster)
        after = [athlete_id for athlete_id in roster if athlete_id not in leaving]
        after.extend(athlete_id for athlete_id in incoming if athlete_id not in present)
        self._resolve([*after, *outgoing, *incoming])
        open_roles = self._team_open_roles(team_id)
        gone = [athlete_id for athlete_id in outgoing if athlete_id in present]
        missing = plan_replacement_roles(
            limits=self._limits,
            roster_roles=[self._roles.get(athlete_id) for athlete_id in after],
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
        return RosterAfterTrade(
            team_id=team_id,
            size_after=len(after),
            roster_size=self._limits.roster_size,
            missing_roles=tuple(sorted(missing, key=ROLE_ORDER.index)),
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

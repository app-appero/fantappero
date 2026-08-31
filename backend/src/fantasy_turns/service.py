"""European fantasy turn generation and lifecycle (EP06-01)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from config.settings.loader import get_api_settings
from database.enums import (
    FantasyRoundFixtureReason,
    FantasyRoundHomologationStatus,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueMemberRole,
    LeagueState,
)
from fantasy_lineups.models import EffectiveLineup, LineupSubmission
from fantasy_turns.live_view import (
    PROVIDER_FEED_LABELS,
    FixtureFreshness,
    fixture_feed_state,
)
from fantasy_turns.coverage import (
    RosteredPlayer,
    clubs_playing_between,
    coverage_by_team,
    coverage_threshold_for,
    load_league_rosters,
    window_is_valid,
)
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import (
    DEFAULT_LEAGUE_TZ,
    EligibleFixtureRef,
    TimeWindow,
    aggregate_turn_status,
    apply_cutoff_recalculation,
    assert_modification_allowed,
    compute_cutoff,
    derive_effective_status,
    ensure_utc,
    evaluate_threshold,
    full_season_turn_specs,
    is_modification_allowed,
    kickoff_counts_for_cutoff,
    reconcile_fixture_kickoff_lock,
    select_eligible_from_candidates,
    upcoming_turn_specs,
    window_for_kind,
)
from fantasy_turns.schemas import (
    EnsureFantasyTurnsResponse,
    ExcludeFantasyTurnFixtureRequest,
    FantasyCalendarRefreshResultResponse,
    FantasyTurnDetailResponse,
    FantasyTurnFixtureResponse,
    FantasyTurnPreviewResponse,
    FantasyTurnSummaryResponse,
    GenerateFantasyTurnRequest,
    PendingFixtureResponse,
)
from fantasy_turns.validators import validate_anchor_date, validate_turn_kind
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.fixtures.models import Fixture as _FixtureModel  # noqa: F401
from sports_data.fixtures.models import OfficialLineup
from sports_data.fixtures.sync import (
    FixtureDetailBatch,
    FixtureSyncCounters,
    FixtureSyncResult,
    sync_fixtures,
    sync_mvp_fixtures_with_client,
)
from sports_data.provider.client import ApiFootballClient, build_client_from_settings
from sports_data.provider.errors import ProviderConfigError

logger = get_logger(__name__)
_ = (User, Club)

#: Stati provider di una partita conclusa.
FINISHED_FIXTURE_STATUSES = ("FT", "AET", "PEN")


@dataclass(frozen=True)
class EnsureWindowResult:
    outcome: str  # created | upgraded | duplicate | waiting
    round_id: UUID | None = None
    opened: bool = False


def load_league_candidate_fixtures(session: Session, league: League) -> list[EligibleFixtureRef]:
    """Fixture della stagione per le competizioni scelte dalla lega.

    Condiviso con la pianificazione del calendario H2H (EP13-P03): entrambi
    devono guardare esattamente lo stesso insieme di partite, altrimenti la
    preview delle finestre e i turni realmente generati divergono.
    """
    competition_ids = session.scalars(
        select(LeagueCompetition.competition_id).where(LeagueCompetition.league_id == league.id)
    ).all()
    if not competition_ids:
        return []
    season_ids = session.scalars(
        select(SportSeason.id).where(
            SportSeason.competition_id.in_(competition_ids),
            SportSeason.year == league.season_year,
        )
    ).all()
    if not season_ids:
        return []
    rows = session.execute(
        select(Fixture.id, Fixture.kickoff_at, Fixture.status_short).where(
            Fixture.sport_season_id.in_(season_ids),
            Fixture.kickoff_at.is_not(None),
        )
    ).all()
    result: list[EligibleFixtureRef] = []
    for fixture_id, kickoff_at, status_short in rows:
        if kickoff_at is None:
            continue
        result.append(
            EligibleFixtureRef(
                fixture_id=fixture_id,
                kickoff_at=kickoff_at,
                status_short=status_short,
            )
        )
    return result


class FantasyTurnService:
    def __init__(self, session: Session) -> None:
        self._session = session
        # Rose per lega: il backfill stagionale valuta molte finestre di
        # seguito e la rosa non cambia durante quel ciclo.
        self._rosters_cache: dict[UUID, dict[UUID, list[RosteredPlayer]]] = {}

    def list_turns(self, league_access: LeagueAccess) -> list[FantasyTurnSummaryResponse]:
        now = datetime.now(UTC)
        rounds = self._session.scalars(
            select(FantasyRound)
            .where(FantasyRound.league_id == league_access.league.id)
            .order_by(FantasyRound.number.asc())
        ).all()
        return [self._to_summary(row, now=now) for row in rounds]

    def list_pending_fixtures(self, league_access: LeagueAccess) -> list[PendingFixtureResponse]:
        """Fixture note (competizione/squadre/round) ma senza data/ora dal provider.

        Non possono appartenere a nessuna finestra (non hanno un kickoff da
        confrontare), quindi restano fuori dai Turni Europei finché il
        provider non pubblica una data — vengono mostrate a parte come "Da
        aggiornare" invece di sparire in silenzio.
        """
        league = league_access.league
        competition_ids = self._session.scalars(
            select(LeagueCompetition.competition_id).where(
                LeagueCompetition.league_id == league.id
            )
        ).all()
        if not competition_ids:
            return []
        season_ids = self._session.scalars(
            select(SportSeason.id).where(
                SportSeason.competition_id.in_(competition_ids),
                SportSeason.year == league.season_year,
            )
        ).all()
        if not season_ids:
            return []
        rows = self._session.scalars(
            select(Fixture)
            .where(
                Fixture.sport_season_id.in_(season_ids),
                Fixture.kickoff_at.is_(None),
            )
            .options(
                selectinload(Fixture.home_club),
                selectinload(Fixture.away_club),
                selectinload(Fixture.sport_season).selectinload(SportSeason.competition),
            )
            .order_by(Fixture.round_label.asc())
        ).all()
        result: list[PendingFixtureResponse] = []
        for fixture in rows:
            competition = None
            if fixture.sport_season and fixture.sport_season.competition:
                competition = fixture.sport_season.competition.name
            result.append(
                PendingFixtureResponse(
                    fixtureId=str(fixture.id),
                    competitionName=competition,
                    roundLabel=fixture.round_label,
                    homeClubName=fixture.home_club.name if fixture.home_club else "?",
                    awayClubName=fixture.away_club.name if fixture.away_club else "?",
                    statusShort=fixture.status_short,
                )
            )
        return result

    def get_turn(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
        *,
        reconcile_cutoff: bool = True,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=False)
        now = datetime.now(UTC)
        if reconcile_cutoff and fantasy_round.status != FantasyTurnStatus.SKIPPED:
            changed = self._reconcile_cutoff(
                fantasy_round,
                now=now,
                actor_id=league_access.user.id,
                commit=True,
            )
            if changed:
                fantasy_round = self._load_round(
                    league_access.league.id, round_id, for_update=False
                )
        return self._to_detail(fantasy_round, now=now)

    def preview(
        self,
        league_access: LeagueAccess,
        payload: GenerateFantasyTurnRequest,
    ) -> FantasyTurnPreviewResponse:
        kind = validate_turn_kind(payload.kind)
        anchor = validate_anchor_date(payload.anchor_date)
        window = window_for_kind(kind, anchor)
        rules = self._load_rules(league_access.league.id)
        min_required = rules.min_fixtures_per_round if rules is not None else 25
        candidates = self._load_candidate_fixtures(league_access.league)
        assigned = self._active_assigned_fixture_ids(league_access.league.id)
        selected = select_eligible_from_candidates(
            candidates,
            window,
            already_assigned_ids=assigned,
        )
        threshold = evaluate_threshold(len(selected), min_required)
        cutoff = compute_cutoff([row.kickoff_at for row in selected])
        fixture_payloads = [
            self._fixture_preview_row(
                row.fixture_id, kickoff=row.kickoff_at, status=row.status_short
            )
            for row in selected
        ]
        return FantasyTurnPreviewResponse(
            kind=kind.value,
            windowStartAt=window.start_at,
            windowEndAt=window.end_at,
            timezone=window.timezone,
            eligibleCount=threshold.eligible_count,
            minRequired=threshold.min_required,
            thresholdOk=threshold.ok,
            skipReason=threshold.skip_reason,
            cutoffAt=cutoff,
            fixtures=fixture_payloads,
        )

    def generate(
        self,
        league_access: LeagueAccess,
        payload: GenerateFantasyTurnRequest,
        *,
        persist_skipped: bool = True,
        auto_open: bool = False,
    ) -> FantasyTurnDetailResponse:
        league = self._lock_league(league_access.league.id)
        kind = validate_turn_kind(payload.kind)
        anchor = validate_anchor_date(payload.anchor_date)
        result = self._materialize_window(
            league,
            kind=kind,
            anchor=anchor,
            actor_id=league_access.user.id,
            persist_skipped=persist_skipped,
            auto_open=auto_open,
            raise_on_duplicate=True,
        )
        if result.outcome == "waiting":
            raise ValidationAuthError(
                "Soglia partite non raggiunta e persistenza skipped disabilitata.",
                code="turn_threshold_not_met",
            )
        if result.outcome == "empty" or result.round_id is None:
            # La finestra non permette a tutti i fantallenatori di schierare
            # la formazione (o non contiene partite): non è un turno valido.
            raise ValidationAuthError(
                "In questa finestra i fantallenatori non possono schierare una "
                "formazione valida: non è un turno disputabile.",
                code="turn_coverage_not_met",
            )
        self._session.commit()
        return self.get_turn(league_access, result.round_id, reconcile_cutoff=False)

    def ensure_upcoming_for_league(
        self,
        league: League,
        *,
        reference_date: date | None = None,
        horizon_days: int = 14,
        auto_open: bool = True,
        actor_id: UUID | None = None,
    ) -> EnsureFantasyTurnsResponse:
        """Idempotently create upcoming weekend/midweek turns from league fixtures."""
        locked = self._lock_league(league.id)
        ref = reference_date or datetime.now(UTC).date()
        system_actor = actor_id or self._league_owner_id(locked.id)
        if system_actor is None:
            raise ValidationAuthError(
                "Impossibile generare turni: la lega non ha un owner.",
                code="league_owner_missing",
            )
        created = opened = upgraded = duplicates = waiting = 0
        for kind, anchor in upcoming_turn_specs(ref, horizon_days=horizon_days):
            result = self._materialize_window(
                locked,
                kind=kind,
                anchor=anchor,
                actor_id=system_actor,
                persist_skipped=False,
                auto_open=auto_open,
                raise_on_duplicate=False,
            )
            if result.outcome == "created":
                created += 1
            elif result.outcome == "upgraded":
                upgraded += 1
            elif result.outcome == "duplicate":
                duplicates += 1
            elif result.outcome == "waiting":
                waiting += 1
            if result.opened:
                opened += 1
        reconciled = self._reconcile_existing_rounds(
            locked.id,
            now=datetime.now(UTC),
            actor_id=system_actor,
        )
        self._session.commit()
        get_metrics().incr("fantasy_turn_ensure_total", labels={"result": "ok"})
        logger.info(
            "fantasy_turns_ensured",
            extra={
                "league_id": str(locked.id),
                "created": created,
                "opened": opened,
                "upgraded": upgraded,
                "duplicates": duplicates,
                "waiting": waiting,
                "reconciled": reconciled,
                "horizon_days": horizon_days,
            },
        )
        return EnsureFantasyTurnsResponse(
            leagueId=str(locked.id),
            created=created,
            opened=opened,
            upgraded=upgraded,
            duplicates=duplicates,
            waiting=waiting,
            horizonDays=horizon_days,
        )

    def ensure_upcoming_for_active_leagues(
        self,
        *,
        reference_date: date | None = None,
        horizon_days: int = 14,
        auto_open: bool = True,
    ) -> dict[str, int]:
        leagues = list(
            self._session.scalars(
                select(League)
                .where(League.state == LeagueState.ACTIVE)
                .order_by(League.created_at.asc())
            ).all()
        )
        totals = {
            "leagues": len(leagues),
            "created": 0,
            "opened": 0,
            "upgraded": 0,
            "duplicates": 0,
            "waiting": 0,
        }
        for league in leagues:
            summary = self.ensure_upcoming_for_league(
                league,
                reference_date=reference_date,
                horizon_days=horizon_days,
                auto_open=auto_open,
                actor_id=None,
            )
            totals["created"] += summary.created
            totals["opened"] += summary.opened
            totals["upgraded"] += summary.upgraded
            totals["duplicates"] += summary.duplicates
            totals["waiting"] += summary.waiting
        return totals

    def ensure_upcoming_for_league_access(
        self,
        league_access: LeagueAccess,
        *,
        horizon_days: int = 14,
        auto_open: bool = True,
    ) -> EnsureFantasyTurnsResponse:
        return self.ensure_upcoming_for_league(
            league_access.league,
            horizon_days=horizon_days,
            auto_open=auto_open,
            actor_id=league_access.user.id,
        )

    def refresh_full_calendar_for_active_leagues(self) -> dict[str, int]:
        """Giro periodico automatico del comando "Aggiorna calendario" (§11/§26).

        Il pulsante admin resta disponibile per un aggiornamento immediato, ma
        non deve essere l'unico modo per far entrare in un turno una fixture
        che riceve la sua data definitiva lontano dall'orizzonte coperto da
        `ensure_upcoming` (oggi±N giorni). Un fallimento provider su una lega
        (rate limit, chiave assente) non deve bloccare le altre — viene
        registrato e si prosegue.
        """
        leagues = list(
            self._session.scalars(
                select(League)
                .where(League.state == LeagueState.ACTIVE)
                .order_by(League.created_at.asc())
            ).all()
        )
        totals = {
            "leagues": len(leagues),
            "refreshed": 0,
            "failed": 0,
            "fixturesCreated": 0,
            "fixturesUpdated": 0,
            "roundsRealigned": 0,
            "roundsRemoved": 0,
        }
        for league in leagues:
            try:
                result = self.refresh_full_calendar(league, actor_id=None)
            except Exception:
                totals["failed"] += 1
                logger.exception(
                    "fantasy_calendar_refresh_periodic_failed",
                    extra={"league_id": str(league.id)},
                )
                self._session.rollback()
                continue
            totals["refreshed"] += 1
            totals["fixturesCreated"] += result.fixtures_created
            totals["fixturesUpdated"] += result.fixtures_updated
            totals["roundsRealigned"] += result.rounds_realigned
            totals["roundsRemoved"] += result.rounds_removed
        logger.info("fantasy_calendar_refresh_periodic_done", extra=totals)
        return totals

    def ensure_window_number(
        self,
        league: League,
        *,
        kind: FantasyTurnKind,
        anchor: date,
        actor_id: UUID | None,
    ) -> int:
        """Numero assoluto del Turno Europeo che ospita questa finestra.

        Usato dal Calendario fantallenatori per allineare la propria
        numerazione a quella dei Turni Europei: stessa finestra reale, stesso
        numero mostrato in entrambe le sezioni. Materializza il turno se non
        esiste ancora (idempotente, stessa logica di `_materialize_window`).
        """
        result = self._materialize_window(
            league,
            kind=kind,
            anchor=anchor,
            actor_id=actor_id,
            persist_skipped=True,
            auto_open=False,
            raise_on_duplicate=False,
        )
        if result.round_id is None:
            raise ValidationAuthError(
                "Impossibile determinare il turno europeo per questa finestra.",
                code="turn_window_not_materialized",
            )
        fantasy_round = self._session.get(FantasyRound, result.round_id)
        assert fantasy_round is not None
        return fantasy_round.number

    def earliest_round_number_for_window(
        self,
        league_id: UUID,
        *,
        window_start_at: datetime,
    ) -> int | None:
        """Numero del primo Turno Europeo della lega dalla finestra data in poi.

        Usato per determinare da quale numero deve partire il Calendario
        fantallenatori quando la lega è stata creata a stagione iniziata.
        """
        return self._session.scalar(
            select(func.min(FantasyRound.number)).where(
                FantasyRound.league_id == league_id,
                FantasyRound.window_start_at >= window_start_at,
            )
        )

    def turn_numbers_before_creation(
        self, league_id: UUID, *, before_number: int, created_at: datetime
    ) -> list[int]:
        """Numeri dei Turni Europei che precedono davvero la creazione della lega.

        Usato per mostrare "Lega creata dopo questo turno" nel Calendario
        fantallenatori. Non basta `number < before_number`: un turno può
        avere un numero più basso del primo turno H2H giocabile semplicemente
        perché è "Non disputato" per soglia non raggiunta (una pausa del
        campionato), pur essendo successivo alla creazione della lega — in
        quel caso non deve comparire come segnaposto, semplicemente non è un
        turno H2H giocabile.
        """
        return list(
            self._session.scalars(
                select(FantasyRound.number)
                .where(
                    FantasyRound.league_id == league_id,
                    FantasyRound.number < before_number,
                    FantasyRound.window_start_at < created_at,
                )
                .order_by(FantasyRound.number.asc())
            ).all()
        )

    def refresh_full_calendar(
        self,
        league: League,
        *,
        actor_id: UUID | None = None,
        client: ApiFootballClient | None = None,
        on_progress: Callable[[int, str, str], None] | None = None,
    ) -> FantasyCalendarRefreshResultResponse:
        """Comando unico "Aggiorna calendario": sync provider + backfill stagionale.

        A differenza di `ensure_upcoming_for_league` (orizzonte oggi±N
        giorni, pensato per il refresh automatico giornaliero), questo copre
        l'intera stagione dall'inizio alla fine, così un Turno Europeo già
        concluso prima che la lega/il sistema lo importasse risulta comunque
        "Turno 1 — COMPLETATO" invece di ottenere un numero più alto solo per
        essere stato importato più tardi. Il riallineamento cronologico dei
        numeri (`_renumber_league_rounds`, già invocato da
        `_materialize_window` ad ogni finestra) è anche il meccanismo di
        auto-riparazione per leghe con turni già mal numerati.
        """

        def report(percent: int, stage: str, message: str) -> None:
            if on_progress is not None:
                on_progress(max(0, min(100, percent)), stage, message)

        locked = self._lock_league(league.id)
        system_actor = actor_id or self._league_owner_id(locked.id)
        if system_actor is None:
            raise ValidationAuthError(
                "Impossibile aggiornare il calendario: la lega non ha un owner.",
                code="league_owner_missing",
            )

        before_numbers = dict(
            self._session.execute(
                select(FantasyRound.id, FantasyRound.number).where(
                    FantasyRound.league_id == locked.id
                )
            ).all()
        )

        report(2, "fixtures", "Recupero fixture dal provider…")
        sync_result = self._sync_league_fixtures_from_provider(locked, client=client)

        # Storico: risultati/stati arrivano con la sincronizzazione qui sopra,
        # ma formazioni ed eventi delle partite già concluse no — quelli lo
        # scheduler li chiede solo nella finestra di polling attorno alla
        # partita. Senza questo passaggio una partita "Finita" resta senza
        # formazione e senza cronologia per sempre.
        report(12, "dettagli", "Recupero formazioni ed eventi delle partite concluse…")
        details_backfilled = self.backfill_match_details(locked, client=client)

        candidates = self._load_candidate_fixtures(locked)
        if candidates:
            kickoffs = [row.kickoff_at for row in candidates]
            season_start = min(kickoffs).date()
            season_end = max(kickoffs).date()
        else:
            # Nessuna fixture datata ancora nota: intervallo di stagione
            # europea standard come base, il prossimo refresh lo affinerà
            # quando il provider pubblica le date.
            season_start = date(locked.season_year, 7, 1)
            season_end = date(locked.season_year + 1, 6, 30)

        report(20, "turni", "Ricostruzione turni dall'inizio della stagione…")
        specs = full_season_turn_specs(season_start, season_end)
        rounds_created = 0
        rounds_updated = 0
        total = len(specs) or 1
        for index, (kind, anchor) in enumerate(specs):
            result = self._materialize_window(
                locked,
                kind=kind,
                anchor=anchor,
                actor_id=system_actor,
                persist_skipped=True,
                auto_open=True,
                raise_on_duplicate=False,
            )
            if result.outcome == "created":
                rounds_created += 1
            elif result.outcome == "upgraded":
                rounds_updated += 1
            report(
                20 + int(((index + 1) / total) * 70),
                "turni",
                f"Turno {index + 1}/{total} elaborato…",
            )

        report(92, "turni", "Rimozione turni non validi…")
        rounds_removed = self._prune_invalid_rounds(locked)
        if rounds_removed:
            self._renumber_league_rounds(locked.id)

        after_numbers = dict(
            self._session.execute(
                select(FantasyRound.id, FantasyRound.number).where(
                    FantasyRound.league_id == locked.id
                )
            ).all()
        )
        rounds_realigned = sum(
            1
            for round_id, number in after_numbers.items()
            if round_id in before_numbers and before_numbers[round_id] != number
        )
        # Il Calendario fantallenatori porta lo stesso numero del Turno
        # Europeo: dopo una rinumerazione va riportato in asse, altrimenti
        # resta ancorato a numeri che non esistono più.
        # Ultimo anello della catena: partite reali -> Turni Europei ->
        # giornate dei fantallenatori. Un'unica azione le copre tutte, invece
        # di lasciare all'utente due pulsanti in due schermate diverse.
        report(95, "calendario", "Generazione calendario fantallenatori…")
        from leagues.calendar_service import LeagueCalendarService

        calendar_service = LeagueCalendarService(self._session)
        calendar_service.realign_round_numbers(locked)
        calendar_outcome = calendar_service.sync_with_european_turns(locked, system_actor)
        fixtures_needing_date = self._count_fixtures_needing_date(locked)
        self._session.commit()

        message = (
            f"Fixture nuove: {sync_result.counters.fixtures_created}, "
            f"aggiornate: {sync_result.counters.fixtures_updated}, "
            f"invariate: {sync_result.counters.fixtures_unchanged}, "
            f"da aggiornare: {fixtures_needing_date}. "
            f"Formazioni/eventi recuperati: {details_backfilled}. "
            f"Calendario fantallenatori: {calendar_outcome}. "
            f"Turni riallineati: {rounds_realigned}, rimossi (senza partite): {rounds_removed}."
        )
        report(100, "completed", message)
        logger.info(
            "fantasy_calendar_refreshed",
            extra={
                "league_id": str(locked.id),
                "fixtures_created": sync_result.counters.fixtures_created,
                "fixtures_updated": sync_result.counters.fixtures_updated,
                "fixtures_unchanged": sync_result.counters.fixtures_unchanged,
                "fixtures_needing_date": fixtures_needing_date,
                "details_backfilled": details_backfilled,
                "calendar_outcome": calendar_outcome,
                "rounds_created": rounds_created,
                "rounds_updated": rounds_updated,
                "rounds_realigned": rounds_realigned,
                "rounds_removed": rounds_removed,
            },
        )
        return FantasyCalendarRefreshResultResponse(
            leagueId=str(locked.id),
            fixturesCreated=sync_result.counters.fixtures_created,
            fixturesUpdated=sync_result.counters.fixtures_updated,
            fixturesUnchanged=sync_result.counters.fixtures_unchanged,
            fixturesNeedingDate=fixtures_needing_date,
            roundsCreated=rounds_created,
            roundsUpdated=rounds_updated,
            roundsRealigned=rounds_realigned,
            roundsRemoved=rounds_removed,
            message=message,
        )

    def open_turn(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        now = datetime.now(UTC)
        self._open_round(fantasy_round, now=now, actor_id=league_access.user.id)
        self._session.commit()
        get_metrics().incr("fantasy_turn_opened_total", labels={"result": "success"})
        return self._to_detail(fantasy_round, now=now)

    def exclude_fixture(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
        payload: ExcludeFantasyTurnFixtureRequest,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        now = datetime.now(UTC)
        assert_modification_allowed(
            stored=fantasy_round.status,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        link = self._session.scalars(
            select(FantasyRoundFixture)
            .where(
                FantasyRoundFixture.round_id == fantasy_round.id,
                FantasyRoundFixture.fixture_id == payload.fixture_id,
            )
            .with_for_update()
        ).first()
        if link is None:
            raise ValidationAuthError(
                "Partita non presente nel turno.",
                code="fixture_not_in_turn",
            )
        if link.excluded_at is not None:
            get_metrics().incr(
                "fantasy_turn_fixture_excluded_total",
                labels={"result": "noop"},
            )
            return self._to_detail(fantasy_round, now=now)

        link.excluded_at = now
        link.excluded_by_user_id = league_access.user.id
        self._session.flush()
        self._reconcile_cutoff(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=False,
        )
        self._add_audit(
            league_id=league_access.league.id,
            actor_id=league_access.user.id,
            action=LeagueAuditAction.FANTASY_TURN_FIXTURE_EXCLUDED,
            details={
                "roundId": str(fantasy_round.id),
                "fixtureId": str(payload.fixture_id),
            },
        )
        self._session.commit()
        get_metrics().incr(
            "fantasy_turn_fixture_excluded_total",
            labels={"result": "success"},
        )
        return self.get_turn(league_access, round_id, reconcile_cutoff=False)

    def recalculate_cutoff(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        now = datetime.now(UTC)
        if fantasy_round.status == FantasyTurnStatus.SKIPPED:
            raise ValidationAuthError(
                "Un turno saltato non ha cutoff.",
                code="turn_skipped",
            )
        changed = self._reconcile_cutoff(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=True,
            force_audit=True,
        )
        get_metrics().incr(
            "fantasy_turn_cutoff_recalculated_total",
            labels={"result": "updated" if changed else "noop"},
        )
        return self._to_detail(fantasy_round, now=now)

    def _materialize_window(
        self,
        league: League,
        *,
        kind: FantasyTurnKind,
        anchor: date,
        actor_id: UUID | None,
        persist_skipped: bool,
        auto_open: bool,
        raise_on_duplicate: bool,
    ) -> EnsureWindowResult:
        window = window_for_kind(kind, anchor)
        rules = self._load_rules(league.id)
        min_required = rules.min_fixtures_per_round if rules is not None else 25
        existing = self._session.scalars(
            select(FantasyRound)
            .where(
                FantasyRound.league_id == league.id,
                FantasyRound.window_start_at == window.start_at,
                FantasyRound.window_end_at == window.end_at,
                FantasyRound.kind == kind,
            )
            .with_for_update()
        ).first()

        candidates = self._load_candidate_fixtures(league)
        already_linked = self._existing_fixture_ids(existing.id) if existing is not None else set()
        assigned = self._active_assigned_fixture_ids(league.id) - already_linked
        selected = select_eligible_from_candidates(
            candidates,
            window,
            already_assigned_ids=assigned,
        )
        threshold = evaluate_threshold(len(selected), min_required)
        now = datetime.now(UTC)

        # Regola di validità del turno (EP-turni-copertura): il numero di
        # partite è solo un pre-filtro; ciò che rende un turno giocabile è
        # che ogni fantallenatore possa schierare la formazione. Una finestra
        # che non la supera non diventa un turno del tutto — niente turni
        # numerati "Non disputato" che sfalsano la numerazione.
        if not self._window_meets_coverage(league, window):
            if existing is None:
                return EnsureWindowResult(outcome="empty", round_id=None)
            if existing.status == FantasyTurnStatus.SKIPPED:
                return EnsureWindowResult(outcome="waiting", round_id=existing.id)

        if existing is None and not selected:
            # Finestra genuinamente vuota per le competizioni scelte (es. pausa
            # internazionale): non materializzare un turno-fantasma senza
            # nessuna partita reale — non c'è nulla da mostrare all'utente.
            return EnsureWindowResult(outcome="empty", round_id=None)

        if existing is not None:
            if existing.status != FantasyTurnStatus.SKIPPED:
                if raise_on_duplicate:
                    get_metrics().incr(
                        "fantasy_turn_generated_total",
                        labels={"result": "duplicate_window"},
                    )
                    raise ValidationAuthError(
                        "Esiste già un turno per questa finestra.",
                        code="turn_window_exists",
                    )
                return EnsureWindowResult(outcome="duplicate", round_id=existing.id)
            if not threshold.ok:
                # Sotto soglia per il fantasy, ma le partite reali già note
                # devono comunque comparire nel calendario (§ "il calendario
                # con i risultati" anche per un turno "Non disputato").
                linked = self._link_new_fixtures(existing.id, league.id, selected, already_linked)
                if linked or existing.skip_reason != threshold.skip_reason:
                    existing.skip_reason = threshold.skip_reason
                    self._session.flush()
                return EnsureWindowResult(outcome="waiting", round_id=existing.id)
            cutoff = compute_cutoff([row.kickoff_at for row in selected])
            existing.status = FantasyTurnStatus.SCHEDULED
            existing.skip_reason = None
            existing.cutoff_at = cutoff
            existing.generated_at = now
            self._link_new_fixtures(existing.id, league.id, selected, already_linked)
            self._renumber_league_rounds(league.id)
            self._add_audit(
                league_id=league.id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_TURN_GENERATED,
                details={
                    "roundId": str(existing.id),
                    "number": existing.number,
                    "status": FantasyTurnStatus.SCHEDULED.value,
                    "fixtureCount": len(selected),
                    "cutoffAt": cutoff.isoformat() if cutoff else None,
                    "upgradedFromSkipped": True,
                },
            )
            did_open = False
            if auto_open:
                did_open = self._try_auto_open(existing, now=now, actor_id=actor_id)
            self._session.flush()
            get_metrics().incr("fantasy_turn_generated_total", labels={"result": "upgraded"})
            return EnsureWindowResult(
                outcome="upgraded",
                round_id=existing.id,
                opened=did_open,
            )

        if not threshold.ok:
            if not persist_skipped:
                return EnsureWindowResult(outcome="waiting", round_id=None)
            placeholder_number = self._next_round_number(league.id)
            fantasy_round = FantasyRound(
                league_id=league.id,
                number=placeholder_number,
                kind=kind,
                window_start_at=window.start_at,
                window_end_at=window.end_at,
                cutoff_at=None,
                status=FantasyTurnStatus.SKIPPED,
                skip_reason=threshold.skip_reason,
                generated_at=now,
            )
            self._session.add(fantasy_round)
            self._session.flush()
            self._link_new_fixtures(fantasy_round.id, league.id, selected, set())
            self._renumber_league_rounds(league.id)
            self._add_audit(
                league_id=league.id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_TURN_GENERATED,
                details={
                    "roundId": str(fantasy_round.id),
                    "number": fantasy_round.number,
                    "status": FantasyTurnStatus.SKIPPED.value,
                    "eligibleCount": threshold.eligible_count,
                    "minRequired": threshold.min_required,
                },
            )
            get_metrics().incr("fantasy_turn_generated_total", labels={"result": "skipped"})
            logger.info(
                "fantasy_turn_skipped",
                extra={
                    "league_id": str(league.id),
                    "round_number": fantasy_round.number,
                    "eligible_count": threshold.eligible_count,
                    "min_required": threshold.min_required,
                },
            )
            self._session.flush()
            return EnsureWindowResult(outcome="created", round_id=fantasy_round.id)

        cutoff = compute_cutoff([row.kickoff_at for row in selected])
        placeholder_number = self._next_round_number(league.id)
        fantasy_round = FantasyRound(
            league_id=league.id,
            number=placeholder_number,
            kind=kind,
            window_start_at=window.start_at,
            window_end_at=window.end_at,
            cutoff_at=cutoff,
            status=FantasyTurnStatus.SCHEDULED,
            skip_reason=None,
            generated_at=now,
        )
        self._session.add(fantasy_round)
        self._session.flush()
        self._link_new_fixtures(fantasy_round.id, league.id, selected, set())
        self._renumber_league_rounds(league.id)
        self._add_audit(
            league_id=league.id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_TURN_GENERATED,
            details={
                "roundId": str(fantasy_round.id),
                "number": fantasy_round.number,
                "status": FantasyTurnStatus.SCHEDULED.value,
                "fixtureCount": len(selected),
                "cutoffAt": cutoff.isoformat() if cutoff else None,
            },
        )
        did_open = False
        if auto_open:
            did_open = self._try_auto_open(fantasy_round, now=now, actor_id=actor_id)
        self._session.flush()
        get_metrics().incr("fantasy_turn_generated_total", labels={"result": "success"})
        logger.info(
            "fantasy_turn_generated",
            extra={
                "league_id": str(league.id),
                "round_id": str(fantasy_round.id),
                "round_number": fantasy_round.number,
                "fixture_count": len(selected),
            },
        )
        return EnsureWindowResult(
            outcome="created",
            round_id=fantasy_round.id,
            opened=did_open,
        )

    def _try_auto_open(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID | None,
    ) -> bool:
        if fantasy_round.status != FantasyTurnStatus.SCHEDULED:
            return False
        if fantasy_round.cutoff_at is not None and ensure_utc(now) >= ensure_utc(
            fantasy_round.cutoff_at
        ):
            return False
        fantasy_round.status = FantasyTurnStatus.OPEN
        fantasy_round.opens_at = now
        self._add_audit(
            league_id=fantasy_round.league_id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_TURN_OPENED,
            details={
                "roundId": str(fantasy_round.id),
                "number": fantasy_round.number,
                "auto": True,
            },
        )
        get_metrics().incr("fantasy_turn_opened_total", labels={"result": "auto"})
        return True

    def _open_round(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID | None,
    ) -> None:
        if fantasy_round.status == FantasyTurnStatus.SKIPPED:
            raise ValidationAuthError(
                "Un turno saltato non può essere aperto.",
                code="turn_skipped",
            )
        if fantasy_round.status == FantasyTurnStatus.OPEN:
            get_metrics().incr("fantasy_turn_opened_total", labels={"result": "noop"})
            return
        if fantasy_round.status == FantasyTurnStatus.LOCKED:
            raise ValidationAuthError(
                "Il turno è già chiuso.",
                code="turn_locked",
            )
        if fantasy_round.status != FantasyTurnStatus.SCHEDULED:
            raise ValidationAuthError(
                "Solo un turno programmato può essere aperto.",
                code="invalid_turn_status",
            )
        self._reconcile_cutoff(fantasy_round, now=now, actor_id=actor_id, commit=False)
        effective = derive_effective_status(
            FantasyTurnStatus.OPEN,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        if effective == FantasyTurnStatus.LOCKED:
            raise ValidationAuthError(
                "Il cutoff è già trascorso: impossibile aprire il turno.",
                code="turn_modification_closed",
            )
        fantasy_round.status = FantasyTurnStatus.OPEN
        fantasy_round.opens_at = now
        self._add_audit(
            league_id=fantasy_round.league_id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_TURN_OPENED,
            details={"roundId": str(fantasy_round.id), "number": fantasy_round.number},
        )

    def _reconcile_cutoff(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID | None,
        commit: bool,
        force_audit: bool = False,
    ) -> bool:
        active_links = [
            link
            for link in self._load_round_fixtures(fantasy_round.id)
            if link.excluded_at is None and link.fixture is not None
        ]
        fixture_changes: list[dict[str, object]] = []
        live_kickoffs: list[datetime] = []
        for link in active_links:
            fixture = link.fixture
            assert fixture is not None
            previous_observed = link.observed_kickoff_at
            previous_latched = link.lock_latched_at
            state = reconcile_fixture_kickoff_lock(
                now=now,
                current_kickoff_at=fixture.kickoff_at,
                status_short=fixture.status_short,
                observed_kickoff_at=link.observed_kickoff_at,
                lock_latched_at=link.lock_latched_at,
            )
            link.observed_kickoff_at = state.observed_kickoff_at
            link.lock_latched_at = state.lock_latched_at
            if kickoff_counts_for_cutoff(
                kickoff_at=fixture.kickoff_at,
                status_short=fixture.status_short,
                now=now,
            ):
                assert fixture.kickoff_at is not None
                live_kickoffs.append(fixture.kickoff_at)
            if (
                previous_observed != state.observed_kickoff_at
                or previous_latched != state.lock_latched_at
                or state.just_latched
            ):
                fixture_changes.append(
                    {
                        "fixtureId": str(link.fixture_id),
                        "statusShort": fixture.status_short,
                        "previousObservedKickoffAt": (
                            previous_observed.isoformat() if previous_observed else None
                        ),
                        "observedKickoffAt": (
                            state.observed_kickoff_at.isoformat()
                            if state.observed_kickoff_at
                            else None
                        ),
                        "lockLatchedAt": (
                            state.lock_latched_at.isoformat() if state.lock_latched_at else None
                        ),
                        "justLatched": state.just_latched,
                    }
                )

        candidate = compute_cutoff(live_kickoffs)
        previous = fantasy_round.cutoff_at
        new_cutoff = apply_cutoff_recalculation(
            previous_cutoff=previous,
            candidate_cutoff=candidate,
            now=now,
        )
        previous_utc = ensure_utc(previous) if previous is not None else None
        changed = previous_utc != new_cutoff or bool(fixture_changes)
        latched = (
            previous_utc is not None
            and new_cutoff == previous_utc
            and (candidate is None or ensure_utc(candidate) != previous_utc)
            and ensure_utc(now) >= previous_utc
        )
        if not changed and not force_audit:
            return False
        fantasy_round.cutoff_at = new_cutoff
        if fantasy_round.status == FantasyTurnStatus.OPEN and new_cutoff is not None:
            if (
                derive_effective_status(
                    FantasyTurnStatus.OPEN,
                    now=now,
                    cutoff_at=new_cutoff,
                )
                == FantasyTurnStatus.LOCKED
            ):
                fantasy_round.status = FantasyTurnStatus.LOCKED
                if fantasy_round.closes_at is None:
                    fantasy_round.closes_at = now
        if changed or force_audit:
            self._add_audit(
                league_id=fantasy_round.league_id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_TURN_CUTOFF_RECALCULATED,
                details={
                    "roundId": str(fantasy_round.id),
                    "previousCutoffAt": previous.isoformat() if previous else None,
                    "cutoffAt": new_cutoff.isoformat() if new_cutoff else None,
                    "candidateCutoffAt": candidate.isoformat() if candidate else None,
                    "latched": latched,
                    "fixtureChanges": fixture_changes,
                },
            )
            logger.info(
                "fantasy_turn_cutoff_recalculated",
                extra={
                    "round_id": str(fantasy_round.id),
                    "latched": latched,
                    "changed": changed,
                    "fixture_change_count": len(fixture_changes),
                },
            )
        if commit:
            self._session.commit()
        else:
            self._session.flush()
        return changed

    def _reconcile_existing_rounds(
        self,
        league_id: UUID,
        *,
        now: datetime,
        actor_id: UUID | None,
    ) -> int:
        """Recompute cutoff/lock for persisted turns after provider kickoff changes."""
        rounds = self._session.scalars(
            select(FantasyRound)
            .where(
                FantasyRound.league_id == league_id,
                FantasyRound.status != FantasyTurnStatus.SKIPPED,
            )
            .order_by(FantasyRound.number.asc())
            .with_for_update()
        ).all()
        updated = 0
        for fantasy_round in rounds:
            if self._reconcile_cutoff(
                fantasy_round,
                now=now,
                actor_id=actor_id,
                commit=False,
            ):
                updated += 1
        return updated

    def _load_candidate_fixtures(self, league: League) -> list[EligibleFixtureRef]:
        return load_league_candidate_fixtures(self._session, league)

    def _window_meets_coverage(self, league: League, window: TimeWindow) -> bool:
        """La finestra permette a ogni fantallenatore di schierare la formazione?

        Le rose sono lette una sola volta per lega (il backfill stagionale
        valuta decine di finestre di fila) e riusate per tutte le finestre.
        """
        rosters = self._rosters_cache.get(league.id)
        if rosters is None:
            rosters = load_league_rosters(self._session, league)
            self._rosters_cache[league.id] = rosters
        if not rosters:
            # Nessuna rosa assegnata (asta non svolta): nessun turno.
            return False
        rules = self._load_rules(league.id)
        threshold = coverage_threshold_for(
            rules.turn_coverage_threshold if rules is not None else None
        )
        playing_clubs = clubs_playing_between(
            self._session,
            league,
            window_start_at=window.start_at,
            window_end_at=window.end_at,
        )
        coverages = coverage_by_team(rosters, playing_clubs)
        return window_is_valid(list(coverages.values()), threshold)

    def _sync_league_fixtures_from_provider(
        self,
        league: League,
        *,
        client: ApiFootballClient | None = None,
    ) -> FixtureSyncResult:
        """Sync calendario (date/orari/stato/round) per le sole competizioni della lega.

        Non richiede eventi/lineup/player stats: quelli restano di competenza
        dei poll periodici PRE/LIVE/POST già esistenti (`sports_data.scheduler`).
        """
        competition_ids = self._session.scalars(
            select(LeagueCompetition.competition_id).where(
                LeagueCompetition.league_id == league.id
            )
        ).all()
        if not competition_ids:
            return FixtureSyncResult(counters=FixtureSyncCounters())
        provider_ids = self._session.scalars(
            select(Competition.provider_id).where(Competition.id.in_(competition_ids))
        ).all()
        if not provider_ids:
            return FixtureSyncResult(counters=FixtureSyncCounters())
        if client is None:
            try:
                client = build_client_from_settings(get_api_settings())
            except ProviderConfigError as exc:
                raise ValidationAuthError(
                    "Chiave API-Football assente sul server. "
                    "Imposta API_FOOTBALL_KEY nell'ambiente backend.",
                    code="provider_key_missing",
                ) from exc
        return sync_mvp_fixtures_with_client(
            self._session,
            client,
            league_ids=list(provider_ids),
            include_details=False,
        )

    def backfill_match_details(
        self,
        league: League,
        *,
        client: ApiFootballClient | None = None,
        limit: int = 25,
    ) -> int:
        """Recupera formazioni ed eventi delle partite già concluse.

        Lo scheduler periodico li scarica solo per le partite che cadono in
        una finestra di polling: una partita sincronizzata *dopo* la fine (o
        conclusa mentre lo scheduler era fermo) resta senza formazioni né
        eventi per sempre, perché nessuno torna più a chiederli. È il motivo
        per cui una partita "Finita 90'" può mostrare "Formazione non
        disponibile". Qui si colma il buco per la stagione della lega.

        Incrementale di proposito: servono tre chiamate provider per partita
        e il rate limit di API-Football farebbe durare minuti un backfill
        completo. Ogni esecuzione recupera le più recenti ancora scoperte, e
        il job periodico chiude lo storico nei giri successivi.

        Ritorna il numero di partite per cui sono stati richiesti i dettagli.
        """
        season_ids = self._league_season_ids(league)
        if not season_ids:
            return 0
        missing = self._session.execute(
            select(Fixture.provider_id)
            .where(
                Fixture.sport_season_id.in_(season_ids),
                Fixture.status_short.in_(FINISHED_FIXTURE_STATUSES),
                ~exists().where(OfficialLineup.fixture_id == Fixture.id),
            )
            .order_by(Fixture.kickoff_at.desc())
            .limit(limit)
        ).scalars().all()
        if not missing:
            return 0
        if client is None:
            try:
                client = build_client_from_settings(get_api_settings())
            except ProviderConfigError as exc:
                raise ValidationAuthError(
                    "Chiave API-Football assente sul server. "
                    "Imposta API_FOOTBALL_KEY nell'ambiente backend.",
                    code="provider_key_missing",
                ) from exc

        provider_ids = self._league_provider_ids(league)
        batches = [
            FixtureDetailBatch(
                fixture_provider_id=provider_id,
                events_envelope=client.get("/fixtures/events", {"fixture": provider_id}),
                lineups_envelope=client.get("/fixtures/lineups", {"fixture": provider_id}),
                players_envelope=client.get("/fixtures/players", {"fixture": provider_id}),
            )
            for provider_id in missing
        ]
        sync_fixtures(
            self._session,
            fixtures_envelopes=[],
            detail_batches=batches,
            league_ids=list(provider_ids),
        )
        logger.info(
            "fantasy_calendar_details_backfilled",
            extra={"league_id": str(league.id), "fixtures": len(batches)},
        )
        return len(batches)

    def _league_season_ids(self, league: League) -> list[UUID]:
        competition_ids = self._session.scalars(
            select(LeagueCompetition.competition_id).where(
                LeagueCompetition.league_id == league.id
            )
        ).all()
        if not competition_ids:
            return []
        return list(
            self._session.scalars(
                select(SportSeason.id).where(
                    SportSeason.competition_id.in_(competition_ids),
                    SportSeason.year == league.season_year,
                )
            ).all()
        )

    def _league_provider_ids(self, league: League) -> list[int]:
        return list(
            self._session.scalars(
                select(Competition.provider_id)
                .join(LeagueCompetition, LeagueCompetition.competition_id == Competition.id)
                .where(LeagueCompetition.league_id == league.id)
            ).all()
        )

    def _count_fixtures_needing_date(self, league: League) -> int:
        competition_ids = self._session.scalars(
            select(LeagueCompetition.competition_id).where(
                LeagueCompetition.league_id == league.id
            )
        ).all()
        if not competition_ids:
            return 0
        season_ids = self._session.scalars(
            select(SportSeason.id).where(
                SportSeason.competition_id.in_(competition_ids),
                SportSeason.year == league.season_year,
            )
        ).all()
        if not season_ids:
            return 0
        return int(
            self._session.scalar(
                select(func.count(Fixture.id)).where(
                    Fixture.sport_season_id.in_(season_ids),
                    Fixture.kickoff_at.is_(None),
                )
            )
            or 0
        )

    def _active_assigned_fixture_ids(self, league_id: UUID) -> set[UUID]:
        rows = self._session.scalars(
            select(FantasyRoundFixture.fixture_id)
            .join(FantasyRound, FantasyRound.id == FantasyRoundFixture.round_id)
            .where(
                FantasyRound.league_id == league_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
        return set(rows)

    def _existing_fixture_ids(self, round_id: UUID) -> set[UUID]:
        return set(
            self._session.scalars(
                select(FantasyRoundFixture.fixture_id).where(
                    FantasyRoundFixture.round_id == round_id,
                    FantasyRoundFixture.excluded_at.is_(None),
                )
            ).all()
        )

    def _link_new_fixtures(
        self,
        round_id: UUID,
        league_id: UUID,
        selected: list[EligibleFixtureRef],
        already_linked: set[UUID],
    ) -> int:
        """Collega al turno le fixture non ancora agganciate.

        Usato anche per i turni "Non disputato" (sotto soglia fantasy): le
        partite reali già note devono comunque comparire nel calendario con i
        loro risultati, a prescindere dallo stato fantasy del turno.
        """
        added = 0
        for row in selected:
            if row.fixture_id in already_linked:
                continue
            self._session.add(
                FantasyRoundFixture(
                    round_id=round_id,
                    league_id=league_id,
                    fixture_id=row.fixture_id,  # type: ignore[arg-type]
                    included_reason=FantasyRoundFixtureReason.WINDOW,
                    observed_kickoff_at=row.kickoff_at,
                )
            )
            added += 1
        if added:
            self._session.flush()
        return added

    def _league_owner_id(self, league_id: UUID) -> UUID | None:
        return self._session.scalar(
            select(LeagueMembership.user_id).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.role == LeagueMemberRole.OWNER,
            )
        )

    def _next_round_number(self, league_id: UUID) -> int:
        """Valore provvisorio e sicuro per l'inserimento di un nuovo turno.

        Non è il numero definitivo: `_renumber_league_rounds` lo corregge
        subito dopo in base all'ordine cronologico reale delle finestre.
        """
        current = self._session.scalar(
            select(func.max(FantasyRound.number)).where(FantasyRound.league_id == league_id)
        )
        return int(current or 0) + 1

    def _renumber_league_rounds(self, league_id: UUID) -> int:
        """Riallinea `FantasyRound.number` all'ordine cronologico delle finestre.

        `_materialize_window` può creare/aggiornare turni fuori ordine (una
        finestra successiva può raggiungere la soglia minima di partite prima
        di una precedente, o un admin può generare manualmente un ancoraggio
        fuori sequenza): senza questo passaggio il numero rifletterebbe
        l'ordine di inserimento invece di quello reale. Auto-correttivo — va
        chiamato dopo ogni creazione/aggiornamento di turno nella stessa
        transazione, così una lega con numerazione già sbagliata si riallinea
        alla prossima sincronizzazione, senza bisogno di una migrazione dati
        separata. Ritorna quanti turni hanno effettivamente cambiato numero.
        """
        rounds = self._session.scalars(
            select(FantasyRound)
            .where(FantasyRound.league_id == league_id)
            .order_by(
                FantasyRound.window_start_at.asc(),
                FantasyRound.window_end_at.asc(),
                FantasyRound.kind.asc(),
            )
            .with_for_update()
        ).all()
        original_numbers = [fantasy_round.number for fantasy_round in rounds]
        # Prima passata a valori temporanei molto alti (mai negativi: c'è un
        # vincolo CHECK number >= 1) per non violare il vincolo unico
        # (league_id, number) mentre si riordina.
        temp_offset = 1_000_000
        for index, fantasy_round in enumerate(rounds):
            fantasy_round.number = temp_offset + index
        self._session.flush()
        changed = 0
        for index, fantasy_round in enumerate(rounds):
            target = index + 1
            fantasy_round.number = target
            if original_numbers[index] != target:
                changed += 1
        self._session.flush()
        if changed:
            # Le giornate dei fantallenatori portano lo stesso numero del
            # Turno Europeo: se i turni si rinumerano, il calendario H2H va
            # riportato in asse nella stessa transazione, altrimenti resta
            # ancorato a numeri che non esistono più.
            # Import locale: `leagues.calendar_service` legge i modelli dei
            # turni, importarlo qui in cima creerebbe un ciclo.
            from leagues.calendar_service import LeagueCalendarService

            league = self._session.get(League, league_id)
            if league is not None:
                LeagueCalendarService(self._session).realign_round_numbers(league)
        return changed

    def _prune_invalid_rounds(self, league: League) -> int:
        """Rimuove i turni che con la regola attuale non sarebbero mai nati.

        Auto-riparazione dei dati generati prima della regola di copertura
        (turni "fantasma" senza partite, o finestre che non permettono a tutti
        di schierare la formazione). **Non tocca mai un turno con dati di
        gioco**: se ha formazioni inviate/effettive o è omologato viene
        lasciato intatto, anche se oggi non supererebbe la regola.
        """
        candidates = list(
            self._session.scalars(
                select(FantasyRound)
                .where(
                    FantasyRound.league_id == league.id,
                    FantasyRound.homologation_status
                    == FantasyRoundHomologationStatus.PROVISIONAL,
                    ~exists().where(LineupSubmission.round_id == FantasyRound.id),
                    ~exists().where(EffectiveLineup.round_id == FantasyRound.id),
                )
                .with_for_update()
            ).all()
        )
        removable: list[UUID] = []
        for fantasy_round in candidates:
            has_fixtures = self._session.scalar(
                select(func.count(FantasyRoundFixture.id)).where(
                    FantasyRoundFixture.round_id == fantasy_round.id,
                    FantasyRoundFixture.excluded_at.is_(None),
                )
            )
            if not has_fixtures:
                removable.append(fantasy_round.id)
                continue
            window = TimeWindow(
                start_at=fantasy_round.window_start_at,
                end_at=fantasy_round.window_end_at,
                kind=fantasy_round.kind,
                timezone=str(DEFAULT_LEAGUE_TZ),
            )
            if not self._window_meets_coverage(league, window):
                removable.append(fantasy_round.id)
        if not removable:
            return 0
        self._session.execute(delete(FantasyRound).where(FantasyRound.id.in_(removable)))
        self._session.flush()
        return len(removable)

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League).where(League.id == league_id).with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

    def _load_rules(self, league_id: UUID) -> LeagueRules | None:
        return self._session.scalars(
            select(LeagueRules).where(LeagueRules.league_id == league_id)
        ).first()

    def _load_round(
        self,
        league_id: UUID,
        round_id: UUID,
        *,
        for_update: bool,
    ) -> FantasyRound:
        stmt = select(FantasyRound).where(
            FantasyRound.id == round_id,
            FantasyRound.league_id == league_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        fantasy_round = self._session.scalars(stmt).first()
        if fantasy_round is None:
            raise ValidationAuthError("Turno non trovato.", code="turn_not_found")
        return fantasy_round

    def _load_round_fixtures(self, round_id: UUID) -> list[FantasyRoundFixture]:
        return list(
            self._session.scalars(
                select(FantasyRoundFixture)
                .where(FantasyRoundFixture.round_id == round_id)
                .options(
                    selectinload(FantasyRoundFixture.fixture).selectinload(Fixture.home_club),
                    selectinload(FantasyRoundFixture.fixture).selectinload(Fixture.away_club),
                    selectinload(FantasyRoundFixture.fixture)
                    .selectinload(Fixture.sport_season)
                    .selectinload(SportSeason.competition),
                )
                .order_by(FantasyRoundFixture.created_at.asc())
            ).all()
        )

    def _fixture_preview_row(
        self,
        fixture_id: object,
        *,
        kickoff: datetime,
        status: str,
    ) -> FantasyTurnFixtureResponse:
        fixture = self._session.scalars(
            select(Fixture)
            .where(Fixture.id == fixture_id)  # type: ignore[arg-type]
            .options(
                selectinload(Fixture.home_club),
                selectinload(Fixture.away_club),
                selectinload(Fixture.sport_season).selectinload(SportSeason.competition),
            )
        ).first()
        if fixture is None:
            return FantasyTurnFixtureResponse(
                id=str(fixture_id),
                fixtureId=str(fixture_id),
                includedReason=FantasyRoundFixtureReason.WINDOW.value,
                excludedAt=None,
                kickoffAt=kickoff,
                observedKickoffAt=kickoff,
                lockLatchedAt=None,
                statusShort=status,
                homeClubName="?",
                awayClubName="?",
                competitionName=None,
                providerId=0,
            )
        competition = None
        if fixture.sport_season and fixture.sport_season.competition:
            competition = fixture.sport_season.competition.name
        return FantasyTurnFixtureResponse(
            id=str(fixture.id),
            fixtureId=str(fixture.id),
            includedReason=FantasyRoundFixtureReason.WINDOW.value,
            excludedAt=None,
            kickoffAt=fixture.kickoff_at,
            observedKickoffAt=fixture.kickoff_at,
            lockLatchedAt=None,
            statusShort=fixture.status_short,
            homeClubName=fixture.home_club.name if fixture.home_club else "?",
            awayClubName=fixture.away_club.name if fixture.away_club else "?",
            competitionName=competition,
            providerId=fixture.provider_id,
        )

    def _to_summary(
        self, fantasy_round: FantasyRound, *, now: datetime
    ) -> FantasyTurnSummaryResponse:
        active_count = self._session.scalar(
            select(func.count(FantasyRoundFixture.id)).where(
                FantasyRoundFixture.round_id == fantasy_round.id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        )
        fixture_states = self._session.execute(
            select(Fixture.status_short, Fixture.kickoff_at)
            .join(
                FantasyRoundFixture,
                FantasyRoundFixture.fixture_id == Fixture.id,
            )
            .where(
                FantasyRoundFixture.round_id == fantasy_round.id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
        effective = derive_effective_status(
            fantasy_round.status,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        return FantasyTurnSummaryResponse(
            id=str(fantasy_round.id),
            leagueId=str(fantasy_round.league_id),
            number=fantasy_round.number,
            kind=fantasy_round.kind.value,
            windowStartAt=fantasy_round.window_start_at,
            windowEndAt=fantasy_round.window_end_at,
            opensAt=fantasy_round.opens_at,
            closesAt=fantasy_round.closes_at,
            cutoffAt=fantasy_round.cutoff_at,
            status=fantasy_round.status.value,
            effectiveStatus=effective.value,
            skipReason=fantasy_round.skip_reason,
            fixtureCount=int(active_count or 0),
            generatedAt=fantasy_round.generated_at,
            modificationAllowed=is_modification_allowed(
                stored=fantasy_round.status,
                now=now,
                cutoff_at=fantasy_round.cutoff_at,
            ),
            matchStatus=aggregate_turn_status(list(fixture_states)),
        )

    def _to_detail(
        self, fantasy_round: FantasyRound, *, now: datetime
    ) -> FantasyTurnDetailResponse:
        summary = self._to_summary(fantasy_round, now=now)
        links = self._load_round_fixtures(fantasy_round.id)
        fixtures = [self._to_fixture_response(link) for link in links if link.excluded_at is None]
        return FantasyTurnDetailResponse(
            id=summary.id,
            leagueId=summary.league_id,
            number=summary.number,
            kind=summary.kind,
            windowStartAt=summary.window_start_at,
            windowEndAt=summary.window_end_at,
            opensAt=summary.opens_at,
            closesAt=summary.closes_at,
            cutoffAt=summary.cutoff_at,
            status=summary.status,
            effectiveStatus=summary.effective_status,
            skipReason=summary.skip_reason,
            fixtureCount=summary.fixture_count,
            generatedAt=summary.generated_at,
            modificationAllowed=summary.modification_allowed,
            matchStatus=summary.match_status,
            homologationStatus=fantasy_round.homologation_status.value,
            fixtures=fixtures,
        )

    @staticmethod
    def _to_fixture_response(link: FantasyRoundFixture) -> FantasyTurnFixtureResponse:
        fixture = link.fixture
        home = fixture.home_club.name if fixture and fixture.home_club else "?"
        away = fixture.away_club.name if fixture and fixture.away_club else "?"
        home_logo = fixture.home_club.logo_url if fixture and fixture.home_club else None
        away_logo = fixture.away_club.logo_url if fixture and fixture.away_club else None
        competition = None
        if fixture and fixture.sport_season and fixture.sport_season.competition:
            competition = fixture.sport_season.competition.name
        # Freschezza del feed (EP13-P04): derivata dall'ultimo aggiornamento
        # normalizzato confrontato con lo stato della partita.
        feed_state = fixture_feed_state(
            FixtureFreshness(
                status_short=fixture.status_short if fixture else "NS",
                updated_at=fixture.updated_at if fixture else None,
            ),
            now=datetime.now(UTC),
        )
        return FantasyTurnFixtureResponse(
            id=str(link.id),
            fixtureId=str(link.fixture_id),
            includedReason=link.included_reason.value,
            excludedAt=link.excluded_at,
            kickoffAt=fixture.kickoff_at if fixture else None,
            observedKickoffAt=link.observed_kickoff_at,
            lockLatchedAt=link.lock_latched_at,
            statusShort=fixture.status_short if fixture else "NS",
            statusElapsed=fixture.status_elapsed if fixture else None,
            homeGoals=fixture.home_goals if fixture else None,
            awayGoals=fixture.away_goals if fixture else None,
            homeClubName=home,
            awayClubName=away,
            homeClubLogoUrl=home_logo,
            awayClubLogoUrl=away_logo,
            competitionName=competition,
            providerId=fixture.provider_id if fixture else 0,
            updatedAt=fixture.updated_at if fixture else None,
            feedState=feed_state.value,
            feedStateLabel=PROVIDER_FEED_LABELS[feed_state],
        )

    def _add_audit(
        self,
        *,
        league_id: UUID,
        actor_id: UUID | None,
        action: LeagueAuditAction,
        details: dict,
    ) -> None:
        resolved_actor_id = actor_id or self._league_owner_id(league_id)
        if resolved_actor_id is None:
            raise ValidationAuthError(
                "Impossibile registrare l'evento: la lega non ha un owner.",
                code="league_owner_missing",
            )
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=resolved_actor_id,
                action=action,
                correlation_id=get_correlation_id(),
                details=details,
            )
        )

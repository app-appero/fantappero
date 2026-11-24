"""Automatic provider-to-standings orchestration for fantasy matchdays.

This module selects which rounds are ready to (re)compute, then delegates
the actual per-round work to `round_calculation_service.calculate_league_round`
— the same function the manual admin commands (global, per-league, and the
historical repair) call, so the automatic job never has behavior of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import FantasyRoundHomologationStatus, FantasyTurnStatus
from fantasy_lineups.turn_start import settle_started_turns
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.round_calculation_service import calculate_league_round
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.fixtures.models import Fixture
from sports_data.scheduler.windows import LATE_DURATION, LIVE_MAX_DURATION

logger = get_logger(__name__)

STARTED_FIXTURE_STATUSES = frozenset(
    {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "FT", "AET", "PEN"}
)

# Il fornitore aggiorna una partita solo fino a 72 ore dopo la fine (finestra
# "correzioni tardive"): oltre, ricalcolare un turno dà sempre lo stesso risultato.
# Senza questo limite il job ricalcolava a ogni giro tutti i turni mai omologati
# (su dev 61 turni e 2091 partite, circa 340 secondi ogni 5 minuti) e teneva
# occupato il worker: i job brevi (scambi scaduti, promemoria) scadevano in coda
# (QA notte 18-19/11). Vale solo per il job automatico: i comandi manuali
# dell'operatore (ricalcolo, recupero dei turni bloccati) guardano tutti i turni.
LIVE_PIPELINE_HORIZON = LIVE_MAX_DURATION + LATE_DURATION


@dataclass
class LivePipelineResult:
    rounds_considered: int = 0
    rounds_processed: int = 0
    rounds_finalized: int = 0
    fixtures_scored: int = 0
    #: Formazioni sistemate dalla regola di inizio turno in questo giro.
    turn_start_teams_changed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "roundsConsidered": self.rounds_considered,
            "roundsProcessed": self.rounds_processed,
            "roundsFinalized": self.rounds_finalized,
            "fixturesScored": self.fixtures_scored,
            "turnStartTeamsChanged": self.turn_start_teams_changed,
            "errors": list(self.errors),
        }

    def error_lines(self) -> list[str]:
        """Gli errori come testo, per il risultato del task Celery.

        Il log di Celery sull'esito del task mostra solo i primi livelli del risultato: con i
        dizionari si leggeva soltanto ``errors: [{...}]`` (pilota, 24/11).
        """
        return [_error_text(item) for item in self.errors]


def _error_text(error: dict[str, str]) -> str:
    return (
        f"round_id={error.get('roundId')} league_id={error.get('leagueId')} "
        f"code={error.get('code')}"
    )


def select_live_rounds(
    session: Session,
    *,
    horizon: timedelta | None = None,
    now: datetime | None = None,
) -> list[tuple[UUID, UUID]]:
    """Turni non omologati con almeno una partita iniziata, come coppie (turno, lega).

    Con `horizon` solo i turni con una partita iniziata dopo `now - horizon`.
    """
    query = (
        select(FantasyRound.id, FantasyRound.league_id)
        .join(FantasyRoundFixture, FantasyRoundFixture.round_id == FantasyRound.id)
        .join(Fixture, Fixture.id == FantasyRoundFixture.fixture_id)
        .where(
            FantasyRound.homologation_status == FantasyRoundHomologationStatus.PROVISIONAL,
            FantasyRound.status != FantasyTurnStatus.SKIPPED,
            FantasyRoundFixture.excluded_at.is_(None),
            Fixture.status_short.in_(STARTED_FIXTURE_STATUSES),
        )
    )
    if horizon is not None:
        query = query.where(Fixture.kickoff_at >= (now or datetime.now(UTC)) - horizon)
    rows = session.execute(query.distinct().order_by(FantasyRound.id.asc())).all()
    return [(row[0], row[1]) for row in rows]


def process_live_fantasy_rounds(
    session: Session,
    *,
    horizon: timedelta | None = None,
    now: datetime | None = None,
) -> LivePipelineResult:
    """Refresh every started, non-homologated round (only recent ones with `horizon`).

    A savepoint isolates one league from another: malformed data in a single
    round is reported and does not prevent other live leagues from updating.
    """
    # Prima di tutto la regola di inizio turno sulle formazioni dei turni appena arrivati al
    # primo blocco (e non ancora calcolati): così vale dal primo blocco anche se nessuno apre la
    # formazione, e prima di qualunque calcolo (fantasy_lineups.turn_start).
    turn_start = settle_started_turns(session, now=now)
    round_rows = select_live_rounds(session, horizon=horizon, now=now)
    result = LivePipelineResult(
        rounds_considered=len(round_rows),
        turn_start_teams_changed=sum(item.teams_changed for item in turn_start),
    )

    for round_id, league_id in round_rows:
        # Chiude la transazione della lega precedente: senza questo i blocchi sui turni
        # restano tenuti fino alla fine di tutto il giro (minuti con molte leghe) e fermano
        # chi li vuole toccare (es. eliminazione lega, azioni dell'admin).
        session.commit()
        try:
            with session.begin_nested():
                calculation = calculate_league_round(
                    session,
                    round_id=round_id,
                    league_id=league_id,
                    actor_id=None,
                    automatic=True,
                )
                result.fixtures_scored += calculation.fixtures_scored
                result.rounds_processed += 1
                if calculation.homologated:
                    result.rounds_finalized += 1
        except ValidationAuthError as exc:
            # Turno, lega e codice anche nel testo: il formatter dei log di Celery scarta gli
            # `extra` e prima si leggeva solo il nome dell'evento (pilota, 24/11).
            error = {"roundId": str(round_id), "leagueId": str(league_id), "code": exc.code}
            result.errors.append(error)
            logger.warning(
                f"fantasy_live_pipeline_round_skipped {_error_text(error)}",
                extra={"round_id": str(round_id), "league_id": str(league_id), "result": exc.code},
            )
        except Exception as exc:  # noqa: BLE001 - isolate a single live league
            error = {
                "roundId": str(round_id),
                "leagueId": str(league_id),
                "code": type(exc).__name__,
            }
            result.errors.append(error)
            logger.exception(
                f"fantasy_live_pipeline_round_failed {_error_text(error)}",
                extra={
                    "round_id": str(round_id),
                    "league_id": str(league_id),
                    "error_type": type(exc).__name__,
                },
            )

    session.commit()

    get_metrics().incr(
        "fantasy_live_pipeline_runs_total",
        labels={"result": "partial" if result.errors else "success"},
    )
    logger.info(
        f"fantasy_live_pipeline_completed rounds_considered={result.rounds_considered} "
        f"rounds_processed={result.rounds_processed} rounds_finalized={result.rounds_finalized} "
        f"errors={len(result.errors)}",
        extra=result.as_dict(),
    )
    return result


__all__ = [
    "LIVE_PIPELINE_HORIZON",
    "LivePipelineResult",
    "process_live_fantasy_rounds",
    "select_live_rounds",
]

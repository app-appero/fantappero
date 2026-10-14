"""Recupero forzato dei risultati rimasti indietro.

Una partita il cui calcio d'inizio è passato ma che è ancora «non iniziata»
blocca l'omologazione del turno, e quindi anche l'apertura del successivo e
il countdown. Il polling periodico può saltarla (tetto per giro, un solo
campionato). Questo comando rifà il calendario di tutti i campionati, chiede
formazioni e statistiche delle partite già finite e poi lancia lo stesso
calcolo del giro live.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import LeagueState
from fantasy_turns.live_pipeline import process_live_fantasy_rounds
from fantasy_turns.service import FantasyTurnService
from leagues.models.league import League
from sports_data.fixtures.sync import sync_mvp_fixtures_with_client
from sports_data.provider.client import ApiFootballClient

# Tre chiamate provider a partita: abbastanza per una giornata europea
# appena chiusa, senza svuotare la quota su tutto lo storico.
DETAILS_PER_LEAGUE = 40


def recover_stale_match_results(session: Session, client: ApiFootballClient) -> dict[str, object]:
    sync_result = sync_mvp_fixtures_with_client(session, client, include_details=False)
    service = FantasyTurnService(session)
    leagues = list(session.scalars(select(League).where(League.state == LeagueState.ACTIVE)).all())
    details_fetched = 0
    for league in leagues:
        details_fetched += service.backfill_match_details(
            league,
            client=client,
            limit=DETAILS_PER_LEAGUE,
        )
    pipeline = process_live_fantasy_rounds(session)
    payload = pipeline.as_dict()
    payload["fixturesCreated"] = sync_result.counters.fixtures_created
    payload["fixturesUpdated"] = sync_result.counters.fixtures_updated
    payload["detailsFetched"] = details_fetched
    return payload

"""Media stagionale e Valore contano solo i campionati; le coppe restano nella carriera (1.3).

Decisione di Rosario (22/11): delle stagioni passate dal fornitore entrano nella media
stagionale («25/26», rossa) e nel Valore solo le righe di campionato (i 5 di
``MVP_LEAGUE_IDS`` o competizioni di tipo ``league``). Coppe escluse; tipo sconosciuto fuori
dai 5 escluso; una stagione con sole coppe è una stagione senza dati. La carriera della scheda
calciatore mostra tutte le righe come prima.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from market.valuation import MISSING_SEASON_INDEX, base_reference_value
from market.valuation_models import AthleteMarketValue
from market.valuation_service import build_career, refresh_market_values, season_samples
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete
from sports_data.season_stats.models import AthleteSeasonStat, ProviderCompetitionType

SEASON = 2026
SERIE_A = 135
SERIE_B = 136
CHAMPIONS_LEAGUE = 2
COPPA_ITALIA = 137
UNKNOWN_COMPETITION = 999  # non è nell'elenco dei tipi

LEAGUE_ONLY = 921_001  # 2025: Serie A
LEAGUE_AND_CUPS = 921_002  # 2025: la stessa Serie A, più Champions League e Coppa Italia
SERIE_B_PLAYER = 921_003  # 2025: Serie B (campionato fuori dai 5, tipo noto)
UNKNOWN_PLAYER = 921_004  # 2025: competizione di tipo sconosciuto
ONLY_CUPS = 921_005  # 2025: solo coppe; 2024: Serie A
NO_HISTORY = 921_006

NAMES = {
    SERIE_A: "Serie A",
    SERIE_B: "Serie B",
    CHAMPIONS_LEAGUE: "UEFA Champions League",
    COPPA_ITALIA: "Coppa Italia",
    UNKNOWN_COMPETITION: "Coppa Sconosciuta",
}


def _row(
    athlete: Athlete,
    *,
    season: int,
    competition: int,
    rating: float,
    apps: int,
) -> AthleteSeasonStat:
    return AthleteSeasonStat(
        athlete_provider_id=athlete.provider_id,
        athlete_id=athlete.id,
        season_year=season,
        source="provider",
        club_provider_id=921_500,
        club_name="Club Storico",
        competition_provider_id=competition,
        competition_name=NAMES[competition],
        appearances=apps,
        minutes=apps * 80,
        rating=rating,
    )


def _types(session: Session) -> None:
    now = datetime.now(UTC)
    session.add_all(
        [
            ProviderCompetitionType(
                provider_id=provider_id, type=kind, name=NAMES[provider_id], fetched_at=now
            )
            for provider_id, kind in (
                (SERIE_B, "league"),
                (CHAMPIONS_LEAGUE, "cup"),
                (COPPA_ITALIA, "cup"),
            )
        ]
    )
    session.flush()


@pytest.fixture
def athletes(session: Session) -> dict[int, Athlete]:
    session.execute(delete(AthleteMarketValue))
    session.execute(delete(AthleteSeasonStat))
    session.execute(delete(ProviderCompetitionType))
    session.execute(delete(RoleAssignment).where(RoleAssignment.season_year == SEASON))
    result: dict[int, Athlete] = {}
    for provider_id in (
        LEAGUE_ONLY,
        LEAGUE_AND_CUPS,
        SERIE_B_PLAYER,
        UNKNOWN_PLAYER,
        ONLY_CUPS,
        NO_HISTORY,
    ):
        athlete = Athlete(provider_id=provider_id, canonical_name=f"Calciatore {provider_id}")
        session.add(athlete)
        session.flush()
        session.add(
            RoleAssignment(
                athlete_id=athlete.id,
                season_year=SEASON,
                role=FantasyRole.A,
                mapping_version="v1.0.0",
            )
        )
        result[provider_id] = athlete
    session.add_all(
        [
            _row(result[LEAGUE_ONLY], season=2025, competition=SERIE_A, rating=6.5, apps=20),
            _row(result[LEAGUE_AND_CUPS], season=2025, competition=SERIE_A, rating=6.5, apps=20),
            _row(
                result[LEAGUE_AND_CUPS],
                season=2025,
                competition=CHAMPIONS_LEAGUE,
                rating=9.0,
                apps=10,
            ),
            _row(
                result[LEAGUE_AND_CUPS], season=2025, competition=COPPA_ITALIA, rating=8.0, apps=3
            ),
            _row(result[SERIE_B_PLAYER], season=2025, competition=SERIE_B, rating=7.0, apps=30),
            _row(
                result[UNKNOWN_PLAYER],
                season=2025,
                competition=UNKNOWN_COMPETITION,
                rating=7.2,
                apps=30,
            ),
            _row(result[ONLY_CUPS], season=2025, competition=COPPA_ITALIA, rating=7.5, apps=4),
            _row(result[ONLY_CUPS], season=2025, competition=CHAMPIONS_LEAGUE, rating=7.0, apps=6),
            _row(result[ONLY_CUPS], season=2024, competition=SERIE_A, rating=6.8, apps=25),
        ]
    )
    session.flush()
    return result


def _values(session: Session, athletes: dict[int, Athlete]) -> dict[int, AthleteMarketValue]:
    rows = session.scalars(
        select(AthleteMarketValue).where(AthleteMarketValue.season_year == SEASON)
    ).all()
    by_athlete = {row.athlete_id: row for row in rows}
    return {provider_id: by_athlete[athlete.id] for provider_id, athlete in athletes.items()}


def _average(value: AthleteMarketValue) -> tuple[float | None, int | None]:
    return value.season_average, value.season_average_year


def _without_excluded(components: dict[str, Any]) -> dict[str, Any]:
    """``components_json`` senza gli elenchi delle righe escluse (gli unici che le coppe
    cambiano)."""
    seasons = {
        slot: {key: value for key, value in season.items() if key != "excluded"}
        for slot, season in components["seasons"].items()
    }
    return {**components, "seasons": seasons}


def test_cups_are_excluded_from_average_and_value(
    session: Session, athletes: dict[int, Athlete]
) -> None:
    _types(session)
    refresh_market_values(session, season_year=SEASON, force=True)
    values = _values(session, athletes)

    # Le coppe (9,0 in Champions, 8,0 in Coppa Italia) non alzano media né Valore: chi ha la
    # stessa Serie A vale uguale.
    with_cups, league_only = values[LEAGUE_AND_CUPS], values[LEAGUE_ONLY]
    assert _average(with_cups) == (pytest.approx(6.5), 2025)
    assert with_cups.season_average_is_current is False
    assert with_cups.value_index == pytest.approx(league_only.value_index)
    assert with_cups.reference_value == pytest.approx(league_only.reference_value)
    # Stessi numeri in ogni passaggio; cambia solo l'elenco delle righe escluse (1.4).
    assert _without_excluded(with_cups.components_json) == _without_excluded(
        league_only.components_json
    )
    previous = with_cups.components_json["seasons"]["previous"]
    assert previous["source"] == "provider"
    assert [(row["competition"], row["appearances"]) for row in previous["rows"]] == [
        ("Serie A", 20)
    ]
    assert [(row["competition"], row["kind"]) for row in previous["excluded"]] == [
        ("UEFA Champions League", "cup"),
        ("Coppa Italia", "cup"),
    ]

    samples = season_samples(session, current_season_year=SEASON)
    assert samples[(LEAGUE_AND_CUPS, 2025)].appearances == 20  # solo le presenze di campionato
    assert samples[(LEAGUE_AND_CUPS, 2025)].rating == pytest.approx(6.5)


def test_championship_outside_the_five_counts(
    session: Session, athletes: dict[int, Athlete]
) -> None:
    _types(session)
    refresh_market_values(session, season_year=SEASON, force=True)
    serie_b = _values(session, athletes)[SERIE_B_PLAYER]

    assert _average(serie_b) == (pytest.approx(7.0), 2025)
    assert serie_b.components_json["hasHistory"] is True
    assert serie_b.components_json["percentiles"]["previous"] is not None
    assert serie_b.reference_value > base_reference_value("A")


def test_unknown_type_outside_the_five_is_excluded(
    session: Session, athletes: dict[int, Athlete]
) -> None:
    _types(session)
    refresh_market_values(session, season_year=SEASON, force=True)
    values = _values(session, athletes)

    unknown = values[UNKNOWN_PLAYER]
    assert _average(unknown) == (None, None)
    assert unknown.components_json["hasHistory"] is False
    assert unknown.value_index == pytest.approx(MISSING_SEASON_INDEX)
    assert unknown.reference_value == pytest.approx(values[NO_HISTORY].reference_value)
    assert unknown.reference_value == pytest.approx(base_reference_value("A"))
    # Il dettaglio dice perché: la riga c'è ma la competizione è di tipo sconosciuto.
    previous = unknown.components_json["seasons"]["previous"]
    assert previous["hasData"] is False
    assert previous["indexUsed"] == pytest.approx(MISSING_SEASON_INDEX)
    assert previous["rows"] == []
    assert [
        (row["competition"], row["kind"], row["appearances"]) for row in previous["excluded"]
    ] == [("Coppa Sconosciuta", "unknown", 30)]


def test_only_cups_season_counts_as_no_data(session: Session, athletes: dict[int, Athlete]) -> None:
    _types(session)
    refresh_market_values(session, season_year=SEASON, force=True)
    only_cups = _values(session, athletes)[ONLY_CUPS]

    # 2025/26 solo coppe: nessuna media «25/26» e stagione scorsa senza dati; la 2024/25 di
    # Serie A conta.
    assert _average(only_cups) == (None, None)
    percentiles = only_cups.components_json["percentiles"]
    assert percentiles["previous"] is None
    assert percentiles["twoSeasonsAgo"] is not None
    assert (ONLY_CUPS, 2025) not in season_samples(session, current_season_year=SEASON)
    seasons = only_cups.components_json["seasons"]
    assert seasons["previous"]["seasonLabel"] == "25/26"
    assert seasons["previous"]["source"] == "provider"
    assert [row["kind"] for row in seasons["previous"]["excluded"]] == ["cup", "cup"]
    assert seasons["twoSeasonsAgo"]["seasonLabel"] == "24/25"
    assert seasons["twoSeasonsAgo"]["rows"][0]["competition"] == "Serie A"
    assert seasons["twoSeasonsAgo"]["poolSize"] == 1  # l'unico attaccante con dati nella 2024/25
    assert seasons["twoSeasonsAgo"]["rank"] == 1


def test_without_competition_types_only_the_five_count(
    session: Session, athletes: dict[int, Athlete]
) -> None:
    # Elenco dei tipi non ancora scaricato: contano solo i 5 campionati.
    refresh_market_values(session, season_year=SEASON, force=True)
    values = _values(session, athletes)

    assert _average(values[LEAGUE_ONLY]) == (pytest.approx(6.5), 2025)
    assert _average(values[LEAGUE_AND_CUPS]) == (pytest.approx(6.5), 2025)
    assert _average(values[SERIE_B_PLAYER]) == (None, None)
    assert _average(values[UNKNOWN_PLAYER]) == (None, None)


def test_career_still_shows_cup_rows(session: Session, athletes: dict[int, Athlete]) -> None:
    _types(session)
    refresh_market_values(session, season_year=SEASON, force=True)

    career = build_career(session, athlete_provider_id=LEAGUE_AND_CUPS, current_season_year=SEASON)
    assert sorted((row.season_label, row.competition_name, row.appearances) for row in career) == [
        ("25/26", "Coppa Italia", 3),
        ("25/26", "Serie A", 20),
        ("25/26", "UEFA Champions League", 10),
    ]
    only_cups = build_career(session, athlete_provider_id=ONLY_CUPS, current_season_year=SEASON)
    assert [(row.season_label, row.competition_name) for row in only_cups] == [
        ("25/26", "UEFA Champions League"),
        ("25/26", "Coppa Italia"),
        ("24/25", "Serie A"),
    ]


def test_new_competition_types_trigger_a_recompute(
    session: Session, athletes: dict[int, Athlete]
) -> None:
    first = refresh_market_values(session, season_year=SEASON)
    assert first.skipped is False
    assert refresh_market_values(session, season_year=SEASON).skipped is True
    assert _average(_values(session, athletes)[SERIE_B_PLAYER]) == (None, None)

    _types(session)  # l'import ha scaricato i tipi: il ricalcolo periodico non salta
    again = refresh_market_values(session, season_year=SEASON)
    assert again.skipped is False
    assert _average(_values(session, athletes)[SERIE_B_PLAYER]) == (pytest.approx(7.0), 2025)

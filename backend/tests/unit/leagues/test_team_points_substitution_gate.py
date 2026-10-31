"""Il punteggio di squadra deve contare il sostituto di un titolare S.V.
solo a turno concluso (tutte le fixture finite): finché il turno è ancora
in corso resta a referto il punteggio del titolare originale (0/S.V.)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from fantasy_lineups.models import EffectiveLineup
from fantasy_ratings.models import PlayerMatchRating
from leagues.scoring_service import _team_points


def test_live_round_uses_the_original_starter_not_the_substitute() -> None:
    league_id = uuid4()
    submission_id = uuid4()
    starter_out_id = uuid4()
    substitute_in_id = uuid4()
    fixture_id = uuid4()

    lineup = EffectiveLineup(
        league_id=league_id,
        submission_id=submission_id,
        effective_starter_ids=[str(substitute_in_id)],
    )

    session = MagicMock()
    original_starters = MagicMock()
    original_starters.all.return_value = [starter_out_id]
    ratings = MagicMock()
    # Solo il subentrante ha un voto: il titolare originale (S.V.) non compare.
    ratings.all.return_value = [
        PlayerMatchRating(athlete_id=substitute_in_id, fantasy_score=7.5),
    ]
    session.scalars.side_effect = [original_starters, ratings]

    points = _team_points(
        session,
        lineup,
        [fixture_id],
        "v1",
        use_substitutes=False,
    )

    assert points == 0.0


def test_concluded_round_uses_the_substitute_score() -> None:
    league_id = uuid4()
    substitute_in_id = uuid4()
    fixture_id = uuid4()

    lineup = EffectiveLineup(
        league_id=league_id,
        submission_id=uuid4(),
        effective_starter_ids=[str(substitute_in_id)],
    )

    session = MagicMock()
    ratings = MagicMock()
    ratings.all.return_value = [
        PlayerMatchRating(athlete_id=substitute_in_id, fantasy_score=7.5),
    ]
    session.scalars.side_effect = [ratings]

    points = _team_points(
        session,
        lineup,
        [fixture_id],
        "v1",
        use_substitutes=True,
    )

    assert points == 7.5

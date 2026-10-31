"""Scontro diretto: il titolare con S.V. resta visibile in campo col SUO
punteggio (mai quello del subentrante, che non lo "sostituisce" mai
visivamente), e il subentrante resta visibile in panchina (non "promosso"
al posto del titolare, non sparisce). La sostituzione nel conteggio di
squadra è decisa altrove (scoring_service), solo a turno concluso."""

from __future__ import annotations

from uuid import uuid4

from database.enums import FantasyModule, FantasyRole, LineupSlotKind
from fantasy_lineups.models import EffectiveLineup, LineupPlayer, LineupSubmission
from fantasy_ratings.round_scores import RoundAthleteScore
from fantasy_teams.models import FantasyTeam
from leagues.h2h_matchday_service import _side_from_effective


def _player(athlete_id, *, slot_kind, role, sort_order):
    player = LineupPlayer(
        athlete_id=athlete_id,
        slot_kind=slot_kind,
        role=role,
        sort_order=sort_order,
    )
    player.athlete = None
    return player


def test_starter_with_no_vote_keeps_his_own_identity_and_his_own_score() -> None:
    starter_out_id = uuid4()  # Freeman: S.V., sostituito nel conteggio finale
    other_starter_id = uuid4()
    bench_ids = [uuid4() for _ in range(10)]  # i 10 panchinari reali, incluso il subentrante
    substitute_in_id = bench_ids[0]  # Hakimi: subentra solo nel conteggio finale

    submission = LineupSubmission(module=FantasyModule.M433)
    submission.players = [
        _player(starter_out_id, slot_kind=LineupSlotKind.STARTER, role=FantasyRole.D, sort_order=1),
        _player(other_starter_id, slot_kind=LineupSlotKind.STARTER, role=FantasyRole.D, sort_order=2),
        *[
            _player(bench_id, slot_kind=LineupSlotKind.BENCH, role=FantasyRole.D, sort_order=10 + i)
            for i, bench_id in enumerate(bench_ids)
        ],
    ]

    effective = EffectiveLineup(
        module=FantasyModule.M433,
        substitutions_json=[
            {
                "outAthleteId": str(starter_out_id),
                "inAthleteId": str(substitute_in_id),
                "role": "D",
                "order": 1,
            }
        ],
    )

    scores_by_athlete = {
        starter_out_id: RoundAthleteScore(fantasy_score=0.0, fixture_status_label="S.V."),
        substitute_in_id: RoundAthleteScore(fantasy_score=7.5),
        other_starter_id: RoundAthleteScore(fantasy_score=6.0),
    }

    result = _side_from_effective(
        effective=effective,
        submission=submission,
        team=FantasyTeam(id=uuid4(), name="Squadra"),
        display_name="Allenatore",
        nickname=None,
        scores_by_athlete=scores_by_athlete,
        probable_by_athlete={},
        persisted_total=None,
        persisted_goals=None,
    )

    assert len(result.starters) == 2
    starter_out = next(row for row in result.starters if row.athlete_id == str(starter_out_id))
    # Identità e punteggio in campo restano quelli del titolare originale: S.V./0,
    # mai il punteggio (né i bonus) del subentrante.
    assert starter_out.athlete_id == str(starter_out_id)
    assert starter_out.fantasy_score == 0.0

    # Tutti i 10 panchinari originali restano visibili, compreso il subentrante,
    # anch'esso col proprio punteggio individuale.
    assert len(result.bench) == 10
    assert {row.athlete_id for row in result.bench} == {str(b) for b in bench_ids}
    substitute_row = next(row for row in result.bench if row.athlete_id == str(substitute_in_id))
    assert substitute_row.fantasy_score == 7.5

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
        _player(
            other_starter_id, slot_kind=LineupSlotKind.STARTER, role=FantasyRole.D, sort_order=2
        ),
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


def _substitution_fixture():
    starter_out_id = uuid4()
    other_starter_id = uuid4()
    substitute_in_id = uuid4()
    unused_bench_id = uuid4()

    submission = LineupSubmission(module=FantasyModule.M433)
    submission.players = [
        _player(starter_out_id, slot_kind=LineupSlotKind.STARTER, role=FantasyRole.D, sort_order=1),
        _player(
            other_starter_id, slot_kind=LineupSlotKind.STARTER, role=FantasyRole.D, sort_order=2
        ),
        _player(substitute_in_id, slot_kind=LineupSlotKind.BENCH, role=FantasyRole.D, sort_order=10),
        _player(unused_bench_id, slot_kind=LineupSlotKind.BENCH, role=FantasyRole.D, sort_order=11),
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
    scores = {
        starter_out_id: RoundAthleteScore(fixture_status_label="Terminata", score_final=True),
        substitute_in_id: RoundAthleteScore(fantasy_score=7.5),
        other_starter_id: RoundAthleteScore(fantasy_score=6.0),
        unused_bench_id: RoundAthleteScore(fantasy_score=9.0),
    }
    return submission, effective, scores, starter_out_id, substitute_in_id, unused_bench_id


def test_concluded_round_marks_who_entered_for_whom_and_totals_match() -> None:
    submission, effective, scores, out_id, in_id, unused_id = _substitution_fixture()

    result = _side_from_effective(
        effective=effective,
        submission=submission,
        team=FantasyTeam(id=uuid4(), name="Squadra"),
        display_name="Allenatore",
        nickname=None,
        scores_by_athlete=scores,
        probable_by_athlete={},
        persisted_total=None,
        persisted_goals=None,
        substitutions_applied=True,
    )

    starter_out = next(row for row in result.starters if row.athlete_id == str(out_id))
    assert starter_out.is_effective_starter is False
    assert starter_out.replaced_by_athlete_id == str(in_id)
    assert starter_out.replaced_by_name == f"Calciatore {str(in_id)[:8]}"
    assert starter_out.fantasy_score is None

    entered = next(row for row in result.bench if row.athlete_id == str(in_id))
    assert entered.is_effective_starter is True
    assert entered.entered_for_athlete_id == str(out_id)
    assert entered.entered_for_name == f"Calciatore {str(out_id)[:8]}"

    unused = next(row for row in result.bench if row.athlete_id == str(unused_id))
    assert unused.is_effective_starter is False
    assert unused.entered_for_athlete_id is None

    # Totale = titolari rimasti + panchinari entrati (6 + 7,5), mai il 9 di chi non è entrato.
    assert result.total_score == 13.5
    visible = sum(
        row.fantasy_score or 0.0
        for row in (*result.starters, *result.bench)
        if row.is_effective_starter
    )
    assert visible == result.total_score


def test_round_in_progress_shows_no_automatic_substitution() -> None:
    submission, effective, scores, _, _, _ = _substitution_fixture()

    result = _side_from_effective(
        effective=effective,
        submission=submission,
        team=FantasyTeam(id=uuid4(), name="Squadra"),
        display_name="Allenatore",
        nickname=None,
        scores_by_athlete=scores,
        probable_by_athlete={},
        persisted_total=None,
        persisted_goals=None,
    )

    assert all(row.is_effective_starter for row in result.starters)
    assert all(row.replaced_by_athlete_id is None for row in result.starters)
    assert all(not row.is_effective_starter for row in result.bench)
    assert all(row.entered_for_athlete_id is None for row in result.bench)
    assert result.total_score == 6.0
    payload = result.model_dump(by_alias=True)
    assert payload["starters"][0]["replacedByName"] is None
    assert payload["bench"][0]["enteredForName"] is None

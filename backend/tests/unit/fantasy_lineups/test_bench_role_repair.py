"""Quota per ruolo dei primi 10 della panchina dopo una riscrittura di sistema (Rosario, 20/11).

«Fabio Trotta ha una formazione con un portiere in panchina al posto dell'attaccante»: uscito un
attaccante dai primi 10, la panchina si ricompattava e saliva il primo della tribuna (spesso un
portiere, con la tribuna in ordine P→D→C→A). ``restore_bench_active_roles`` fa salire invece il
primo della tribuna con il ruolo che manca, senza toccare chi ha la partita già iniziata.
"""

from __future__ import annotations

from database.enums import FantasyRole
from fantasy_lineups.rules import (
    BENCH_ACTIVE_SIZE,
    LineupPlayerRef,
    bench_active_role_shortfall,
    evaluate_lineup,
    restore_bench_active_roles,
)


def _refs(ids: list[str]) -> list[LineupPlayerRef]:
    return [LineupPlayerRef(athlete_id=item, role=FantasyRole(item[0])) for item in ids]


def _ids(refs) -> list[object]:
    return [ref.athlete_id for ref in refs]


# 4-4-2: P1 D1-D4 C1-C4 A1-A2 titolari; in panchina 1P·3D·3C·3A e la tribuna P→D→C→A.
STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "C4", "A1", "A2"]
SAVED_BENCH = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "A5", "P3", "D8", "C8", "A6"]


def _compacted_without(departed: str) -> list[str]:
    """La panchina come la lasciava la pulizia: chi resta nell'ordine, posizioni 0..n-1."""
    return [item for item in SAVED_BENCH if item != departed]


def test_compaction_alone_breaks_the_quota_with_a_goalkeeper_in_tenth_place() -> None:
    bench = _compacted_without("A4")
    assert bench[BENCH_ACTIVE_SIZE - 1] == "P3"
    assert bench_active_role_shortfall(_refs(bench)) == {FantasyRole.A: 1}
    evaluation = evaluate_lineup(
        module="4-4-2",
        starters=_refs(STARTERS),
        bench=_refs(bench),
        roster_athlete_ids=[*STARTERS, *bench],
    )
    assert [issue.code for issue in evaluation.issues] == ["bench_roles_invalid"]
    assert "mancano: 1 attaccante" in evaluation.issues[0].message


def test_the_first_forward_of_the_tribuna_takes_the_tenth_place() -> None:
    repair = restore_bench_active_roles(_refs(_compacted_without("A4")))
    assert _ids(repair.bench) == [
        "P2",
        "D5",
        "D6",
        "D7",
        "C5",
        "C6",
        "C7",
        "A3",
        "A5",
        "A6",
        "P3",
        "D8",
        "C8",
    ]
    assert repair.moves == (("A6", "P3"),)
    assert repair.missing == {}
    evaluation = evaluate_lineup(
        module="4-4-2",
        starters=_refs(STARTERS),
        bench=list(repair.bench),
        roster_athlete_ids=[*STARTERS, *_ids(repair.bench)],
    )
    assert evaluation.valid, evaluation.issues


def test_role_order_is_kept_and_nobody_else_moves() -> None:
    # Due attaccanti mancano: scendono i due in più (prima l'ultimo), gli attaccanti salgono
    # nell'ordine scelto e chi scende resta davanti nella tribuna nel suo ordine.
    bench = ["D5", "P2", "D6", "D7", "C5", "C6", "C7", "A3", "D9", "P3", "A4", "A6"]
    repair = restore_bench_active_roles(_refs(bench))
    assert _ids(repair.bench) == [
        "D5",
        "P2",
        "D6",
        "D7",
        "C5",
        "C6",
        "C7",
        "A3",
        "A4",
        "A6",
        "D9",
        "P3",
    ]
    assert repair.moves == (("A4", "P3"), ("A6", "D9"))


def test_a_valid_bench_or_one_without_the_role_is_left_alone() -> None:
    valid = _refs(SAVED_BENCH)
    assert restore_bench_active_roles(valid).bench == tuple(valid)
    assert not restore_bench_active_roles(valid).changed
    # Nessun altro attaccante in tutta la panchina: la quota chiede solo quelli che ci sono.
    short = _refs([item for item in SAVED_BENCH if item not in {"A4", "A6"}])
    assert bench_active_role_shortfall(short) == {}
    assert restore_bench_active_roles(short).bench == tuple(short)


def test_started_matches_are_not_moved_nor_overtaken() -> None:
    bench = _refs(_compacted_without("A4"))
    # P3 (10°) ha la partita iniziata: per far salire A6 bisognerebbe scavalcarlo, e P2 (l'altro
    # portiere in più) sta prima di lui. La panchina resta com'è e la quota resta scoperta.
    stuck = restore_bench_active_roles(bench, locked_athlete_ids={"P3"})
    assert stuck.bench == tuple(bench)
    assert stuck.missing == {FantasyRole.A: 1}
    # Lo stesso con C8, in tribuna tra P3 e A6.
    assert not restore_bench_active_roles(bench, locked_athlete_ids={"C8"}).changed
    # P2 bloccato non si sposta: scende P3, che è dopo di lui.
    repair = restore_bench_active_roles(bench, locked_athlete_ids={"P2"})
    assert _ids(repair.bench) == [
        "P2",
        "D5",
        "D6",
        "D7",
        "C5",
        "C6",
        "C7",
        "A3",
        "A5",
        "A6",
        "P3",
        "D8",
        "C8",
    ]
    # L'attaccante della tribuna è già in campo: non sale.
    assert not restore_bench_active_roles(bench, locked_athlete_ids={"A6"}).changed


def test_players_without_a_vote_do_not_raise_the_quota() -> None:
    # Fabio (20/11): l'unico terzo attaccante non ha partita nel turno. Contato, la quota
    # chiedeva 3 attaccanti nei primi 10, e web e app lo tengono in coda alla tribuna.
    bench = _refs(_compacted_without("A4"))
    kwargs = {
        "module": "4-4-2",
        "starters": _refs(STARTERS),
        "bench": bench,
        "roster_athlete_ids": [*STARTERS, *_ids(bench)],
    }
    assert not evaluate_lineup(**kwargs).valid
    assert evaluate_lineup(**kwargs, unfieldable_athlete_ids={"A6"}).valid
    # Nei primi 10 chi non prende il voto conta comunque: la regola non diventa più severa.
    fixed = restore_bench_active_roles(bench).bench
    assert evaluate_lineup(**{**kwargs, "bench": list(fixed)}, unfieldable_athlete_ids={"A6"}).valid
    # Con un altro attaccante schierabile in tribuna la quota resta 3.
    assert not evaluate_lineup(**kwargs, unfieldable_athlete_ids={"P3"}).valid


def test_repair_counts_like_the_validation_when_told_who_has_no_vote() -> None:
    bench = _refs(_compacted_without("A4"))
    # Come web e app già installati (tutti contati): sale A6 anche se non prende il voto.
    assert restore_bench_active_roles(bench).moves == (("A6", "P3"),)
    # Come la validazione: A6 senza voto non alza la quota, la panchina resta com'è.
    repair = restore_bench_active_roles(bench, unfieldable_athlete_ids={"A6"})
    assert not repair.changed
    assert repair.missing == {}
    assert bench_active_role_shortfall(bench, unfieldable_athlete_ids={"A6"}) == {}


def test_excess_or_unresolved_players_in_the_tribuna_neither_count_nor_move_up() -> None:
    bench = _refs(_compacted_without("A4"))
    # A6 in esubero di ruolo: in tribuna non conta, la quota chiede 2 attaccanti, va bene così.
    assert bench_active_role_shortfall(bench, unavailable_athlete_ids={"A6"}) == {}
    assert not restore_bench_active_roles(bench, unavailable_athlete_ids={"A6"}).changed

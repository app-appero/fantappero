"""Unit tests for CSV roster import parsing and matching helpers (EP05-04)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from auth.exceptions import ValidationAuthError
from fantasy_teams.csv_import import (
    PreviewRow,
    PreviewRowIssue,
    apply_resolutions,
    normalize_athlete_name,
    normalize_header,
    parse_roster_csv,
    select_name_matches,
    sha256_hex,
    surname_lookup_keys,
)


def test_normalize_header_aliases() -> None:
    assert normalize_header("Squadra") == "squadra"
    assert normalize_header("provider id") == "provider_id"
    assert normalize_header("Credits") == "crediti"


def test_parse_valid_csv() -> None:
    data = (
        b"squadra,provider_id,nome,crediti\n"
        b"Romy,42,L. Martinez,10\n"
        b"Romy,43,N. Barella,5\n"
    )
    rows = parse_roster_csv(data)
    assert len(rows) == 2
    assert rows[0].squadra == "Romy"
    assert rows[0].provider_id == 42
    assert rows[0].crediti == 10
    assert rows[1].nome == "N. Barella"


def test_parse_rejects_empty_and_bad_header() -> None:
    with pytest.raises(ValidationAuthError) as empty:
        parse_roster_csv(b"")
    assert empty.value.code == "csv_empty"

    with pytest.raises(ValidationAuthError) as header:
        parse_roster_csv(b"a,b,c\n1,2,3\n")
    assert header.value.code == "csv_invalid_header"


def test_parse_marks_invalid_numeric_fields() -> None:
    data = b"squadra,provider_id,nome,crediti\nRomy,abc,Foo,x\n"
    rows = parse_roster_csv(data)
    assert rows[0].provider_id is None
    assert rows[0].crediti is None
    assert rows[0].raw["_provider_id_invalid"] == "abc"
    assert rows[0].raw["_crediti_invalid"] == "x"


def test_name_match_accepts_listone_label_or_surname_ignoring_case() -> None:
    class Player:
        def __init__(self, player_id: str, canonical: str, last: str | None) -> None:
            self.id = player_id
            self.canonical_name = canonical
            self.last_name = last

    lautaro = Player("a1", "L. Martinez", "Martinez")
    barella = Player("a2", "N. Barella", "Barella")
    other = Player("a3", "A. Martinez", "Martinez")
    by_exact = {
        normalize_athlete_name(lautaro.canonical_name): [lautaro],
        normalize_athlete_name(barella.canonical_name): [barella],
        normalize_athlete_name(other.canonical_name): [other],
    }
    by_surname: dict[str, list[Player]] = {}
    for player in (lautaro, barella, other):
        for key in surname_lookup_keys(player.canonical_name, player.last_name):
            by_surname.setdefault(key, []).append(player)

    exact, exact_mode = select_name_matches(
        "l. MARTINEZ",
        by_exact=by_exact,
        by_surname=by_surname,
    )
    assert exact_mode == "exact"
    assert exact == [lautaro]

    surname, surname_mode = select_name_matches(
        "barella",
        by_exact=by_exact,
        by_surname=by_surname,
    )
    assert surname_mode == "surname"
    assert surname == [barella]

    ambiguous, ambiguous_mode = select_name_matches(
        "MARTINEZ",
        by_exact=by_exact,
        by_surname=by_surname,
    )
    assert ambiguous_mode == "surname"
    assert {player.id for player in ambiguous} == {"a1", "a3"}

    missing, missing_mode = select_name_matches(
        "sconosciuto",
        by_exact=by_exact,
        by_surname=by_surname,
    )
    assert missing_mode == "none"
    assert missing == []


def test_surname_keys_cover_initial_form_and_full_name() -> None:
    assert surname_lookup_keys("L. Martinez", "Martinez") == {"martinez"}
    assert surname_lookup_keys("K. De Bruyne", "De Bruyne") == {"de bruyne"}
    assert surname_lookup_keys("Lautaro Martinez", None) == {"martinez"}


def test_sha256_stable() -> None:
    assert sha256_hex(b"abc") == sha256_hex(b"abc")
    assert sha256_hex(b"abc") != sha256_hex(b"abd")


def test_apply_resolutions_selects_candidate() -> None:
    from uuid import UUID as Uuid

    from fantasy_teams.csv_import import AthleteCandidate

    athlete_a = str(uuid4())
    athlete_b = str(uuid4())
    row = PreviewRow(
        row_number=2,
        squadra="Romy",
        provider_id=None,
        nome="Rossi",
        crediti=10,
        status="ambiguous",
        fantasy_team_id=str(uuid4()),
        fantasy_team_name="Romy",
        issues=[
            PreviewRowIssue(
                code="ambiguous_athlete_name",
                message="Nome ambiguo",
                severity="error",
            )
        ],
        candidates=[
            AthleteCandidate(athlete_id=athlete_a, provider_id=1, canonical_name="A Rossi"),
            AthleteCandidate(athlete_id=athlete_b, provider_id=2, canonical_name="B Rossi"),
        ],
    )
    updated = apply_resolutions([row], {2: Uuid(athlete_b)})
    assert updated[0].status == "ok"
    assert updated[0].athlete_id == athlete_b
    assert updated[0].provider_id == 2
    assert not any(issue.code == "ambiguous_athlete_name" for issue in updated[0].issues)

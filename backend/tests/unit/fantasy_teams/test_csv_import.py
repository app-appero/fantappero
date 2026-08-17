"""Unit tests for CSV roster import parsing and matching helpers (EP05-04)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from auth.exceptions import ValidationAuthError
from fantasy_teams.csv_import import (
    PreviewRow,
    PreviewRowIssue,
    apply_resolutions,
    normalize_header,
    parse_roster_csv,
    sha256_hex,
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

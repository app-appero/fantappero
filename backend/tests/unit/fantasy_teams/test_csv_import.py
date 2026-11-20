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
    data = b"squadra,provider_id,nome,crediti\nRomy,42,L. Martinez,10\nRomy,43,N. Barella,5\n"
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


def test_parse_roster_csv_accepts_semicolon_and_tab_separators() -> None:
    """Decisione 15 (18/11): CSV di Excel italiano con il punto e virgola."""
    from fantasy_teams.csv_import import detect_csv_delimiter, parse_roster_csv

    semicolon = b"squadra;provider_id;nome;crediti\nFC Test;123;Mario Rossi;15\n"
    rows = parse_roster_csv(semicolon)
    assert len(rows) == 1
    assert rows[0].squadra == "FC Test"
    assert rows[0].provider_id == 123
    assert rows[0].nome == "Mario Rossi"
    assert rows[0].crediti == 15

    tab = b"squadra\tprovider_id\tnome\tcrediti\nFC Test\t\tRossi, Mario\t7\n"
    assert parse_roster_csv(tab)[0].nome == "Rossi, Mario"

    # Virgola come sempre; un nome con il punto e virgola non confonde il riconoscimento.
    comma = 'squadra,provider_id,nome,crediti\nFC Test,,"Rossi; Mario",3\n'
    assert detect_csv_delimiter(comma) == ","
    assert parse_roster_csv(comma.encode())[0].nome == "Rossi; Mario"
    # Con BOM e intestazione in maiuscolo (come esporta Excel).
    bom = "﻿Squadra;Provider_ID;Nome;Crediti\nFC Test;;Rossi;1\n".encode()
    assert parse_roster_csv(bom)[0].crediti == 1


def test_normalize_athlete_name_ignores_accents_case_and_spaces() -> None:
    from fantasy_teams.csv_import import normalize_athlete_name

    assert normalize_athlete_name("  J.  McGinn ") == "j. mcginn"
    assert normalize_athlete_name("E. İlkhan") == normalize_athlete_name("e. ilkhan")
    assert normalize_athlete_name("A. Dembélé") == "a. dembele"


def test_normalize_athlete_name_maps_dotless_turkish_i() -> None:
    """QA 19-20/11: "A. Bayindir" non trovava "A. Bayındır" (ı turca senza punto)."""
    assert normalize_athlete_name("A. Bayındır") == normalize_athlete_name("A. Bayindir")
    assert normalize_athlete_name("A. BAYINDIR") == "a. bayindir"
    # Le altre lettere che NFKD non scompone, come nella ricerca del listone.
    assert normalize_athlete_name("M. Ødegaard") == "m. odegaard"
    assert normalize_athlete_name("Ł. Skorupski") == "l. skorupski"


def _ambiguous_row(row_number: int = 3) -> PreviewRow:
    from fantasy_teams.csv_import import AthleteCandidate

    return PreviewRow(
        row_number=row_number,
        squadra="Romy",
        provider_id=None,
        nome="toni fernandez",
        crediti=4,
        status="ambiguous",
        fantasy_team_id=str(uuid4()),
        fantasy_team_name="Romy",
        issues=[
            PreviewRowIssue(
                code="ambiguous_athlete_name",
                message="Nome ambiguo: seleziona il calciatore corretto.",
                severity="warning",
            )
        ],
        candidates=[
            AthleteCandidate(
                athlete_id=str(uuid4()), provider_id=1, canonical_name="Toni Fernández"
            ),
            AthleteCandidate(
                athlete_id=str(uuid4()), provider_id=2, canonical_name="Toni Fernández"
            ),
        ],
    )


def test_ambiguous_rows_are_not_counted_as_errors() -> None:
    """QA 19-20/11: le righe ambigue finivano in `errorCount`."""
    from fantasy_teams.csv_preview import (
        count_preview_issues,
        count_unresolved_ambiguities,
        has_unresolved_ambiguities,
    )

    ok = PreviewRow(
        row_number=2,
        squadra="Romy",
        provider_id=None,
        nome="Barella",
        crediti=10,
        status="ok",
        athlete_id=str(uuid4()),
    )
    assert count_preview_issues([ok, _ambiguous_row()]) == (0, 1)
    assert count_unresolved_ambiguities([ok, _ambiguous_row()]) == 1
    assert has_unresolved_ambiguities([ok, _ambiguous_row()]) is True
    assert has_unresolved_ambiguities([ok]) is False

    broken = PreviewRow(
        row_number=4,
        squadra="Romy",
        provider_id=None,
        nome="Nessuno",
        crediti=1,
        status="error",
        issues=[PreviewRowIssue(code="athlete_not_found", message="x", severity="error")],
    )
    assert count_preview_issues([ok, _ambiguous_row(), broken]) == (1, 1)


def test_candidate_details_survive_the_stored_preview() -> None:
    from fantasy_teams.csv_import import preview_row_from_dict, preview_row_to_dict

    row = _ambiguous_row()
    row.candidates[0].role = "C"
    row.candidates[0].club_name = "Barcelona"
    row.candidates[0].competition_name = "La Liga"
    restored = preview_row_from_dict(preview_row_to_dict(row))
    first, second = restored.candidates
    assert (first.role, first.club_name, first.competition_name) == ("C", "Barcelona", "La Liga")
    assert (second.role, second.club_name, second.competition_name) == (None, None, None)


def test_excel_keeps_ambiguous_rows_to_choose_and_skips_unknown_names() -> None:
    """Decisione 19-20/11: nell'Excel il nome di più calciatori non si ignora più,
    si sceglie il candidato giusto; il nome che non esiste resta ignorato."""
    from fantasy_teams.csv_preview import skip_unmatched_excel_rows

    ambiguous = _ambiguous_row()
    missing = PreviewRow(
        row_number=4,
        squadra="Romy",
        provider_id=None,
        nome="Nessuno",
        crediti=1,
        status="error",
        fantasy_team_id=str(uuid4()),
        issues=[PreviewRowIssue(code="athlete_not_found", message="x", severity="error")],
    )
    skip_unmatched_excel_rows([ambiguous, missing])
    assert ambiguous.status == "ambiguous"
    assert len(ambiguous.candidates) == 2
    assert missing.status == "skipped"
    assert [issue.code for issue in missing.issues] == ["athlete_not_found"]

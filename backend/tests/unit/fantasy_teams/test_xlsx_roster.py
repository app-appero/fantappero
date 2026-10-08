"""Unit tests for Excel roster template and round-trip into the CSV parser."""

from __future__ import annotations

from fantasy_teams.csv_import import parse_roster_csv
from fantasy_teams.xlsx_roster import (
    is_xlsx,
    rows_to_xlsx_bytes,
    template_xlsx_bytes,
    xlsx_to_csv_bytes,
)


def test_template_is_xlsx_and_parses() -> None:
    data = template_xlsx_bytes()
    assert is_xlsx(data)
    rows = parse_roster_csv(xlsx_to_csv_bytes(data))
    assert len(rows) == 1
    assert rows[0].squadra == "Squadra Esempio"
    assert rows[0].provider_id == 12345
    assert rows[0].nome == "Nome Calciatore"
    assert rows[0].crediti == 10


def test_export_rows_round_trip() -> None:
    data = rows_to_xlsx_bytes(
        [
            ("Romy", 42, "L. Martinez", 10),
            ("Romy", 43, "N. Barella", 5),
        ]
    )
    rows = parse_roster_csv(xlsx_to_csv_bytes(data))
    assert [(row.squadra, row.provider_id, row.nome, row.crediti) for row in rows] == [
        ("Romy", 42, "L. Martinez", 10),
        ("Romy", 43, "N. Barella", 5),
    ]


def test_blank_excel_rows_are_skipped() -> None:
    data = rows_to_xlsx_bytes([("Romy", 42, "L. Martinez", 10), ("", None, "", None)])
    rows = parse_roster_csv(xlsx_to_csv_bytes(data))
    assert len(rows) == 1
    assert rows[0].provider_id == 42

"""Unit tests for the two-column Excel roster file."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from openpyxl import Workbook, load_workbook

from auth.exceptions import ValidationAuthError
from fantasy_teams.csv_import import PreviewRow, PreviewRowIssue
from fantasy_teams.csv_preview import count_preview_issues, skip_unmatched_excel_rows
from fantasy_teams.xlsx_roster import (
    XLSX_HEADERS,
    is_xlsx,
    parse_roster_xlsx,
    rows_to_xlsx_bytes,
    template_xlsx_bytes,
)


def _sheet_rows(data: bytes) -> list[tuple[object, ...]]:
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        assert sheet is not None
        return [tuple(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def test_template_has_only_player_and_credits() -> None:
    data = template_xlsx_bytes()
    assert is_xlsx(data)
    rows = _sheet_rows(data)
    assert rows == [("Calciatore", "Crediti"), ("Nome Calciatore", 10)]
    parsed = parse_roster_xlsx(data, team_name="Rosa demo")
    assert len(parsed) == 1
    assert parsed[0].squadra == "Rosa demo"
    assert parsed[0].provider_id is None
    assert parsed[0].nome == "Nome Calciatore"
    assert parsed[0].crediti == 10


def test_export_round_trip_ignores_team_name_in_the_file() -> None:
    data = rows_to_xlsx_bytes([("L. Martinez", 50), ("N. Barella", 35)])
    assert _sheet_rows(data)[0] == XLSX_HEADERS
    parsed = parse_roster_xlsx(data, team_name="Allenatore IA 01")
    assert [(row.nome, row.crediti, row.provider_id, row.squadra) for row in parsed] == [
        ("L. Martinez", 50, None, "Allenatore IA 01"),
        ("N. Barella", 35, None, "Allenatore IA 01"),
    ]


def test_blank_excel_rows_are_skipped() -> None:
    data = rows_to_xlsx_bytes([("L. Martinez", 10), ("", None)])
    parsed = parse_roster_xlsx(data, team_name="Rosa demo")
    assert len(parsed) == 1
    assert parsed[0].nome == "L. Martinez"


def test_header_without_player_column_is_rejected() -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["Crediti"])
    sheet.append([10])
    buffer = io.BytesIO()
    workbook.save(buffer)
    with pytest.raises(ValidationAuthError) as caught:
        parse_roster_xlsx(buffer.getvalue(), team_name="Rosa demo")
    assert caught.value.code == "xlsx_invalid_header"


def test_unknown_player_row_becomes_a_warning_skip() -> None:
    row = PreviewRow(
        row_number=2,
        squadra="Rosa demo",
        provider_id=None,
        nome="Sconosciuto",
        crediti=8,
        status="error",
        fantasy_team_id=str(uuid4()),
        issues=[
            PreviewRowIssue(
                code="athlete_not_found",
                message="Nessun calciatore trovato per il nome «Sconosciuto».",
                severity="error",
            )
        ],
    )
    matched = PreviewRow(
        row_number=3,
        squadra="Rosa demo",
        provider_id=None,
        nome="L. Martinez",
        crediti=50,
        status="error",
        fantasy_team_id=row.fantasy_team_id,
        athlete_id=str(uuid4()),
        issues=[
            PreviewRowIssue(
                code="athlete_already_on_team",
                message="Il calciatore è già nella rosa di questa squadra.",
                severity="error",
            )
        ],
    )
    skip_unmatched_excel_rows([row, matched])
    assert row.status == "skipped"
    assert row.athlete_id is None
    assert row.slot_index is None
    assert row.issues[0].severity == "warning"
    assert matched.status == "error"
    errors, warnings = count_preview_issues([row, matched])
    assert errors == 1
    assert warnings == 1

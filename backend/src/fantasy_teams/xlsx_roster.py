"""Excel roster template, export and import: player name and credits only."""

from __future__ import annotations

import io
from collections.abc import Iterable

from openpyxl import Workbook, load_workbook

from auth.exceptions import ValidationAuthError
from fantasy_teams.csv_import import (
    CSV_MAX_BYTES,
    CSV_MAX_ROWS,
    ParsedCsvRow,
    normalize_header,
)

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSX_TEMPLATE_FILENAME = "fantappero-import-rosa.xlsx"
XLSX_EXPORT_FILENAME = "fantappero-rose.xlsx"
XLSX_HEADERS = ("Calciatore", "Crediti")

_EXAMPLE_ROW = ("Nome Calciatore", 10)


def is_xlsx(data: bytes) -> bool:
    return data.startswith(b"PK\x03\x04")


def template_xlsx_bytes() -> bytes:
    return rows_to_xlsx_bytes([_EXAMPLE_ROW])


def rows_to_xlsx_bytes(rows: Iterable[tuple[object, ...]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rosa"
    sheet.append(list(XLSX_HEADERS))
    for row in rows:
        sheet.append(list(row))
    sheet.freeze_panes = "A2"
    sheet.column_dimensions["A"].width = 36
    sheet.column_dimensions["B"].width = 12
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def parse_roster_xlsx(data: bytes, *, team_name: str) -> list[ParsedCsvRow]:
    """Read Calciatore + Crediti. The fantasy team stays out of the file."""
    if not data:
        raise ValidationAuthError("Il file Excel è vuoto.", code="csv_empty")
    if len(data) > CSV_MAX_BYTES:
        raise ValidationAuthError(
            "Il file Excel supera la dimensione massima consentita.",
            code="csv_too_large",
        )
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationAuthError(
            "Il file Excel non è leggibile. Usa il modello ufficiale .xlsx.",
            code="xlsx_invalid",
        ) from exc

    try:
        sheet = workbook.active
        if sheet is None:
            raise ValidationAuthError(
                "Il file Excel non contiene un foglio.",
                code="xlsx_invalid",
            )
        return _rows_from_sheet(sheet, team_name=team_name)
    finally:
        workbook.close()


def _rows_from_sheet(sheet: object, *, team_name: str) -> list[ParsedCsvRow]:
    name_index: int | None = None
    credit_index: int | None = None
    parsed: list[ParsedCsvRow] = []
    data_rows = 0
    sheet_rows = sheet.iter_rows(values_only=True)  # type: ignore[attr-defined]
    for row_number, raw in enumerate(sheet_rows, start=1):
        cells = tuple(raw)
        if all(_is_blank(cell) for cell in cells):
            continue
        if name_index is None or credit_index is None:
            mapped = [normalize_header(_cell_text(cell)) for cell in cells]
            if "nome" not in mapped or "crediti" not in mapped:
                raise ValidationAuthError(
                    "Il file Excel deve avere le colonne Calciatore e Crediti.",
                    code="xlsx_invalid_header",
                )
            name_index = mapped.index("nome")
            credit_index = mapped.index("crediti")
            continue

        data_rows += 1
        if data_rows > CSV_MAX_ROWS:
            raise ValidationAuthError(
                f"Il file Excel supera il massimo di {CSV_MAX_ROWS} righe dati.",
                code="csv_too_many_rows",
            )
        nome = _cell_text(cells[name_index]) if name_index < len(cells) else ""
        credit_cell = cells[credit_index] if credit_index < len(cells) else None
        crediti, invalid = _parse_credits(credit_cell)
        if not nome and crediti is None and not invalid:
            continue
        raw_map = {"nome": nome, "crediti": _cell_text(credit_cell)}
        if invalid:
            raw_map["_crediti_invalid"] = raw_map["crediti"]
        parsed.append(
            ParsedCsvRow(
                row_number=row_number,
                squadra=team_name,
                provider_id=None,
                nome=nome,
                crediti=crediti,
                raw=raw_map,
            )
        )

    if name_index is None:
        raise ValidationAuthError("Il file Excel è vuoto.", code="csv_empty")
    if not parsed:
        raise ValidationAuthError(
            "Il file Excel non contiene righe dati da importare.",
            code="csv_no_data_rows",
        )
    return parsed


def _parse_credits(value: object) -> tuple[int | None, bool]:
    if _is_blank(value):
        return None, False
    if isinstance(value, bool):
        return None, True
    if isinstance(value, int):
        return value, False
    if isinstance(value, float):
        if value.is_integer():
            return int(value), False
        return None, True
    text = _cell_text(value)
    try:
        return int(text), False
    except ValueError:
        return None, True


def _is_blank(value: object) -> bool:
    return value is None or str(value).strip() == ""


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value).strip()

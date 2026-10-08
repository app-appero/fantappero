"""Excel roster template, export and import (same columns as the CSV template)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from openpyxl import Workbook, load_workbook

from auth.exceptions import ValidationAuthError
from fantasy_teams.csv_import import CSV_TEMPLATE_HEADERS

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSX_TEMPLATE_FILENAME = "fantappero-import-rosa.xlsx"
XLSX_EXPORT_FILENAME = "fantappero-rose.xlsx"

_EXAMPLE_ROW = ("Squadra Esempio", 12345, "Nome Calciatore", 10)


def is_xlsx(data: bytes) -> bool:
    return data.startswith(b"PK\x03\x04")


def template_xlsx_bytes() -> bytes:
    return rows_to_xlsx_bytes([_EXAMPLE_ROW])


def rows_to_xlsx_bytes(rows: Iterable[tuple[object, ...]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rose"
    sheet.append(list(CSV_TEMPLATE_HEADERS))
    for row in rows:
        sheet.append(list(row))
    sheet.freeze_panes = "A2"
    for column, width in zip(("A", "B", "C", "D"), (28, 16, 32, 12), strict=True):
        sheet.column_dimensions[column].width = width
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def xlsx_to_csv_bytes(data: bytes) -> bytes:
    """Turn the first worksheet into the CSV the existing parser already accepts."""
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
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        for row in sheet.iter_rows(values_only=True):
            if all(_is_blank(cell) for cell in row):
                continue
            writer.writerow([_cell_text(cell) for cell in row])
    finally:
        workbook.close()

    text = buffer.getvalue()
    if not text.strip():
        raise ValidationAuthError("Il file Excel è vuoto.", code="csv_empty")
    return text.encode("utf-8")


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

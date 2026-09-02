"""CSV parsing and athlete/team matching for roster import (EP05-04 / FR-ROS-03)."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from uuid import UUID

from auth.exceptions import ValidationAuthError

CSV_TEMPLATE_HEADERS = ("squadra", "provider_id", "nome", "crediti")
CSV_TEMPLATE_BODY = (
    "squadra,provider_id,nome,crediti\n"
    "Squadra Esempio,12345,Nome Calciatore,10\n"
)
CSV_MAX_BYTES = 512 * 1024
CSV_MAX_ROWS = 500

_HEADER_ALIASES = {
    "squadra": "squadra",
    "team": "squadra",
    "fantasy_team": "squadra",
    "provider_id": "provider_id",
    "providerid": "provider_id",
    "id_provider": "provider_id",
    "nome": "nome",
    "name": "nome",
    "calciatore": "nome",
    "crediti": "crediti",
    "credits": "crediti",
    "prezzo": "crediti",
    "purchase_credits": "crediti",
}


@dataclass(frozen=True)
class ParsedCsvRow:
    row_number: int
    squadra: str
    provider_id: int | None
    nome: str
    crediti: int | None
    raw: dict[str, str]


@dataclass
class AthleteCandidate:
    athlete_id: str
    provider_id: int
    canonical_name: str


@dataclass
class PreviewRowIssue:
    code: str
    message: str
    severity: str  # error | warning


@dataclass
class PreviewRow:
    row_number: int
    squadra: str
    provider_id: int | None
    nome: str
    crediti: int | None
    status: str  # ok | error | ambiguous
    fantasy_team_id: str | None = None
    fantasy_team_name: str | None = None
    athlete_id: str | None = None
    athlete_name: str | None = None
    slot_index: int | None = None
    issues: list[PreviewRowIssue] = field(default_factory=list)
    candidates: list[AthleteCandidate] = field(default_factory=list)


def csv_template_bytes() -> bytes:
    return CSV_TEMPLATE_BODY.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_header(value: str) -> str:
    cleaned = value.strip().lower().replace(" ", "_")
    cleaned = re.sub(r"[^\w]", "", cleaned)
    return _HEADER_ALIASES.get(cleaned, cleaned)


def parse_roster_csv(data: bytes) -> list[ParsedCsvRow]:
    if not data:
        raise ValidationAuthError("Il file CSV è vuoto.", code="csv_empty")
    if len(data) > CSV_MAX_BYTES:
        raise ValidationAuthError(
            "Il file CSV supera la dimensione massima consentita.",
            code="csv_too_large",
        )

    text = _decode_csv(data)
    reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)
    if reader.fieldnames is None:
        raise ValidationAuthError(
            "Intestazione CSV mancante. Scarica il modello ufficiale.",
            code="csv_missing_header",
        )

    mapped_headers = [normalize_header(name or "") for name in reader.fieldnames]
    required = set(CSV_TEMPLATE_HEADERS)
    if not required.issubset(set(mapped_headers)):
        raise ValidationAuthError(
            "Intestazione CSV non valida. Colonne richieste: squadra,provider_id,nome,crediti.",
            code="csv_invalid_header",
        )

    header_map = {
        canonical: original
        for canonical, original in zip(mapped_headers, reader.fieldnames, strict=True)
        if canonical in required
    }

    rows: list[ParsedCsvRow] = []
    for index, raw in enumerate(reader, start=2):
        if index - 1 > CSV_MAX_ROWS:
            raise ValidationAuthError(
                f"Il CSV supera il massimo di {CSV_MAX_ROWS} righe dati.",
                code="csv_too_many_rows",
            )
        if all(not str(value or "").strip() for value in raw.values()):
            continue

        squadra = str(raw.get(header_map["squadra"], "") or "").strip()
        provider_raw = str(raw.get(header_map["provider_id"], "") or "").strip()
        nome = str(raw.get(header_map["nome"], "") or "").strip()
        crediti_raw = str(raw.get(header_map["crediti"], "") or "").strip()

        provider_id: int | None = None
        if provider_raw:
            try:
                provider_id = int(provider_raw)
            except ValueError:
                raw["_provider_id_invalid"] = provider_raw

        crediti: int | None = None
        if crediti_raw:
            try:
                crediti = int(crediti_raw)
            except ValueError:
                raw["_crediti_invalid"] = crediti_raw

        rows.append(
            ParsedCsvRow(
                row_number=index,
                squadra=squadra,
                provider_id=provider_id,
                nome=nome,
                crediti=crediti,
                raw={k: str(v or "") for k, v in raw.items()},
            )
        )

    if not rows:
        raise ValidationAuthError(
            "Il CSV non contiene righe dati da importare.",
            code="csv_no_data_rows",
        )
    return rows


def _decode_csv(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationAuthError(
        "Codifica del file non riconosciuta. Usa UTF-8.",
        code="csv_invalid_encoding",
    )


def normalize_team_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().casefold())


def normalize_athlete_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().casefold())


def preview_row_to_dict(row: PreviewRow) -> dict[str, object]:
    return {
        "rowNumber": row.row_number,
        "squadra": row.squadra,
        "providerId": row.provider_id,
        "nome": row.nome,
        "crediti": row.crediti,
        "status": row.status,
        "fantasyTeamId": row.fantasy_team_id,
        "fantasyTeamName": row.fantasy_team_name,
        "athleteId": row.athlete_id,
        "athleteName": row.athlete_name,
        "slotIndex": row.slot_index,
        "issues": [
            {"code": issue.code, "message": issue.message, "severity": issue.severity}
            for issue in row.issues
        ],
        "candidates": [
            {
                "athleteId": candidate.athlete_id,
                "providerId": candidate.provider_id,
                "canonicalName": candidate.canonical_name,
            }
            for candidate in row.candidates
        ],
    }


def preview_row_from_dict(payload: dict[str, object]) -> PreviewRow:
    issues_raw = payload.get("issues") or []
    candidates_raw = payload.get("candidates") or []
    assert isinstance(issues_raw, list)
    assert isinstance(candidates_raw, list)
    return PreviewRow(
        row_number=int(payload["rowNumber"]),  # type: ignore[arg-type]
        squadra=str(payload.get("squadra") or ""),
        provider_id=payload.get("providerId") if payload.get("providerId") is not None else None,  # type: ignore[arg-type]
        nome=str(payload.get("nome") or ""),
        crediti=payload.get("crediti") if payload.get("crediti") is not None else None,  # type: ignore[arg-type]
        status=str(payload.get("status") or "error"),
        fantasy_team_id=(
            str(payload["fantasyTeamId"]) if payload.get("fantasyTeamId") else None
        ),
        fantasy_team_name=(
            str(payload["fantasyTeamName"]) if payload.get("fantasyTeamName") else None
        ),
        athlete_id=str(payload["athleteId"]) if payload.get("athleteId") else None,
        athlete_name=str(payload["athleteName"]) if payload.get("athleteName") else None,
        slot_index=payload.get("slotIndex") if payload.get("slotIndex") is not None else None,  # type: ignore[arg-type]
        issues=[
            PreviewRowIssue(
                code=str(item.get("code") or "unknown"),
                message=str(item.get("message") or ""),
                severity=str(item.get("severity") or "error"),
            )
            for item in issues_raw
            if isinstance(item, dict)
        ],
        candidates=[
            AthleteCandidate(
                athlete_id=str(item["athleteId"]),
                provider_id=int(item["providerId"]),
                canonical_name=str(item["canonicalName"]),
            )
            for item in candidates_raw
            if isinstance(item, dict)
        ],
    )


def apply_resolutions(
    rows: list[PreviewRow],
    resolutions: dict[int, UUID],
) -> list[PreviewRow]:
    """Apply admin resolutions for ambiguous rows; clear ambiguity when valid."""
    updated: list[PreviewRow] = []
    for row in rows:
        resolved_id = resolutions.get(row.row_number)
        if resolved_id is None or row.status != "ambiguous":
            updated.append(row)
            continue
        match = next(
            (candidate for candidate in row.candidates if candidate.athlete_id == str(resolved_id)),
            None,
        )
        if match is None:
            row.issues.append(
                PreviewRowIssue(
                    code="invalid_resolution",
                    message="La selezione del calciatore non è tra i candidati della riga.",
                    severity="error",
                )
            )
            row.status = "error"
            updated.append(row)
            continue
        row.athlete_id = match.athlete_id
        row.athlete_name = match.canonical_name
        row.provider_id = match.provider_id
        row.candidates = []
        row.issues = [issue for issue in row.issues if issue.code != "ambiguous_athlete_name"]
        row.status = "ok" if not any(issue.severity == "error" for issue in row.issues) else "error"
        updated.append(row)
    return updated

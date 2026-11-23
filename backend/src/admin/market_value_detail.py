"""Pannello operatore: «Dettaglio del Valore» di un calciatore (release 1.4).

Spiega un Valore passo per passo leggendo la riga di ``athlete_market_values`` scritta
dall'ultimo ricalcolo (``components_json``, versione ``1.4.0`` di
``market.valuation_service.VALUATION_VERSION``): non rifà il calcolo e non chiama il fornitore,
così quello che si vede è esattamente il numero mostrato nelle leghe. Una riga scritta prima
della 1.4 ha solo percentili e pesi (``status = "outdated"``: basta «Ricalcola valori»); un
calciatore senza riga vale il valore base del ruolo (``status = "not_computed"``).

Guida per l'operatore: ``docs/operations/valore_di_mercato_e_storico.md`` § 8.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from admin.season_history_schemas import (
    AdminMarketValueDetailResponse,
    AdminMarketValueLeagueCredits,
    AdminMarketValueSeasonDetail,
    AdminMarketValueSeasonRow,
)
from auth.exceptions import ValidationAuthError
from fantasy_teams.ledger import resolve_initial_credits
from leagues.models.league import League
from market.valuation import (
    CURRENT_FULL_WEIGHT_APPEARANCES,
    CURVE_EXPONENT,
    FLOOR_REFERENCE_CREDITS,
    MISSING_SEASON_INDEX,
    REFERENCE_BUDGET,
    SEASON_SLOTS,
    SHRINK_APPEARANCES,
    TOP_REFERENCE_CREDITS,
    base_reference_value,
    credits_for_budget,
    season_weights,
)
from market.valuation_models import AthleteMarketValue
from market.valuation_service import SLOT_SEASON_OFFSETS
from sports_data.catalog.models import Club
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete
from sports_data.season_stats.seasons import season_label

ATHLETE_NOT_FOUND_CODE = "market_value_athlete_not_found"
LEAGUE_NOT_FOUND_CODE = "market_value_league_not_found"
NOT_FOUND_CODES = frozenset({ATHLETE_NOT_FOUND_CODE, LEAGUE_NOT_FOUND_CODE})

_ROW_KINDS = frozenset({"league", "cup", "unknown", "no_rating"})


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _rows(raw: Any) -> list[AdminMarketValueSeasonRow]:
    rows: list[AdminMarketValueSeasonRow] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        rows.append(
            AdminMarketValueSeasonRow(
                competition=str(item.get("competition") or "Competizione sconosciuta"),
                club=item.get("club") if isinstance(item.get("club"), str) else None,
                appearances=_int(item.get("appearances")) or 0,
                average=_float(item.get("average")),
                kind=kind if kind in _ROW_KINDS else "unknown",
            )
        )
    return rows


def _season(
    slot: str,
    *,
    season_year: int,
    stored: dict[str, Any] | None,
    weight: float,
    percentile: float | None,
) -> AdminMarketValueSeasonDetail:
    """Una stagione dal JSON 1.4 (``stored``) o, per le righe più vecchie, dai soli percentile
    e peso."""
    year = season_year - SLOT_SEASON_OFFSETS[slot]
    data = stored or {}
    rows = _rows(data.get("rows"))
    if stored is not None:
        percentile = _float(data.get("percentile"))
        weight = _float(data.get("weight")) or 0.0
    has_data = percentile is not None
    index_used = (
        percentile
        if percentile is not None
        else (0.0 if slot == "current" else MISSING_SEASON_INDEX)
    )
    if stored is not None and _float(data.get("indexUsed")) is not None:
        index_used = float(data["indexUsed"])
    contribution = weight * index_used
    if stored is not None and _float(data.get("contribution")) is not None:
        contribution = float(data["contribution"])
    source = data.get("source")
    competitions = list(dict.fromkeys(row.competition for row in rows))
    return AdminMarketValueSeasonDetail(
        slot=slot,  # type: ignore[arg-type]
        seasonYear=year,
        seasonLabel=season_label(year),
        isCurrent=slot == "current",
        source=source if source in ("provider", "fantappero") else None,
        competitions=competitions,
        rows=rows,
        excluded=_rows(data.get("excluded")),
        hasData=has_data,
        appearances=_int(data.get("appearances")) or 0,
        average=_float(data.get("average")),
        roleAverage=_float(data.get("roleAverage")),
        shrunkAverage=_float(data.get("shrunkAverage")),
        percentile=percentile,
        rank=_int(data.get("rank")),
        poolSize=_int(data.get("poolSize")),
        weight=round(weight, 4),
        indexUsed=round(index_used, 4),
        contribution=round(contribution, 4),
    )


def market_value_detail(
    session: Session,
    *,
    athlete_id: UUID,
    season_year: int,
    league_id: UUID | None = None,
) -> AdminMarketValueDetailResponse:
    """Il Valore di un calciatore del listone di ``season_year``, passo per passo."""
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == athlete_id,
            RoleAssignment.season_year == season_year,
        )
    )
    athlete = session.get(Athlete, athlete_id) if assignment is not None else None
    if assignment is None or athlete is None:
        raise ValidationAuthError(
            "Calciatore non trovato nel listone di questa stagione.",
            code=ATHLETE_NOT_FOUND_CODE,
        )
    league: League | None = None
    if league_id is not None:
        league = session.get(League, league_id)
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code=LEAGUE_NOT_FOUND_CODE)
    club = session.get(Club, assignment.club_id) if assignment.club_id is not None else None
    row = session.scalar(
        select(AthleteMarketValue).where(
            AthleteMarketValue.athlete_id == athlete_id,
            AthleteMarketValue.season_year == season_year,
        )
    )
    # Il ruolo del calcolo (se il ruolo ufficiale è cambiato dopo l'ultimo ricalcolo, il
    # numero mostrato nelle leghe è ancora quello del ruolo di allora).
    role = row.role.value if row is not None else assignment.role.value

    components: dict[str, Any] = (
        row.components_json if row is not None and isinstance(row.components_json, dict) else {}
    )
    stored_seasons = components.get("seasons")
    if row is None:
        status = "not_computed"
        value_index = MISSING_SEASON_INDEX
        reference_value = base_reference_value(role)
    else:
        status = "computed" if isinstance(stored_seasons, dict) else "outdated"
        value_index = float(row.value_index)
        reference_value = float(row.reference_value)

    fallback_weights = season_weights(row.current_votes if row is not None else 0).as_dict()
    stored_weights = components.get("weights")
    weights = stored_weights if isinstance(stored_weights, dict) else fallback_weights
    stored_percentiles = components.get("percentiles")
    percentiles = stored_percentiles if isinstance(stored_percentiles, dict) else {}
    seasons = [
        _season(
            slot,
            season_year=season_year,
            stored=(
                stored_seasons.get(slot)
                if isinstance(stored_seasons, dict) and isinstance(stored_seasons.get(slot), dict)
                else None
            ),
            weight=_float(weights.get(slot)) or 0.0,
            percentile=_float(percentiles.get(slot)),
        )
        for slot in SEASON_SLOTS
    ]

    league_credits: AdminMarketValueLeagueCredits | None = None
    if league is not None:
        budget = resolve_initial_credits(session, league.id)
        league_credits = AdminMarketValueLeagueCredits(
            leagueId=str(league.id),
            leagueName=league.name,
            budget=budget,
            credits=credits_for_budget(reference_value, budget),
        )

    return AdminMarketValueDetailResponse(
        athleteId=str(athlete.id),
        canonicalName=athlete.canonical_name,
        clubName=club.name if club is not None else None,
        role=role,  # type: ignore[arg-type]
        seasonYear=season_year,
        seasonLabel=season_label(season_year),
        status=status,  # type: ignore[arg-type]
        version=str(components["version"]) if components.get("version") else None,
        computedAt=row.updated_at if row is not None else None,
        valueIndex=round(value_index, 6),
        referenceValue=round(reference_value, 4),
        referenceCredits=credits_for_budget(reference_value, REFERENCE_BUDGET),
        referenceBudget=REFERENCE_BUDGET,
        roleTop=TOP_REFERENCE_CREDITS[role],
        floor=FLOOR_REFERENCE_CREDITS,
        curveExponent=CURVE_EXPONENT,
        missingSeasonIndex=MISSING_SEASON_INDEX,
        shrinkAppearances=SHRINK_APPEARANCES,
        currentFullWeightAppearances=CURRENT_FULL_WEIGHT_APPEARANCES,
        baseReferenceValue=round(base_reference_value(role), 4),
        seasons=seasons,
        league=league_credits,
    )

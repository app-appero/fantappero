"""Motore puro del voto statistico: base 6, clamp 3–10, componenti spiegabili."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fantasy_ratings.config import ComponentSpec, FormulaConfig, RoleCode
from fantasy_ratings.eligibility import evaluate_eligibility
from fantasy_ratings.input import PlayerMatchInput


@dataclass(frozen=True)
class ComponentContribution:
    id: str
    path: str
    raw_value: float
    coeff: float
    uncapped: float
    contribution: float
    max_abs: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "raw_value": self.raw_value,
            "coeff": self.coeff,
            "uncapped": self.uncapped,
            "contribution": self.contribution,
            "max_abs": self.max_abs,
        }


@dataclass(frozen=True)
class RatingResult:
    formula_version: str
    fixture_id: int
    player_id: int
    player_name: str
    role: RoleCode | None
    minutes: int | None
    eligible: bool
    eligibility_reason: str
    base: float
    components: tuple[ComponentContribution, ...]
    raw_before_clamp: float
    raw: float
    display: float | None
    provider_rating: float | None
    goals_total: int
    assists_total: int
    stats_hash: str | None = None

    @property
    def components_sum(self) -> float:
        return sum(item.contribution for item in self.components)

    def reconstruct_with(self, config: FormulaConfig) -> float:
        """Ricostruisce il raw da base + componenti, poi applica il clamp."""
        return reconstruct_raw(
            base=config.base,
            contributions=tuple(item.contribution for item in self.components),
            clamp_min=config.clamp_min,
            clamp_max=config.clamp_max,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "formula_version": self.formula_version,
            "fixture_id": self.fixture_id,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role": self.role,
            "minutes": self.minutes,
            "eligible": self.eligible,
            "eligibility_reason": self.eligibility_reason,
            "base": self.base,
            "components": [item.as_dict() for item in self.components],
            "components_sum": self.components_sum,
            "raw_before_clamp": self.raw_before_clamp,
            "raw": self.raw,
            "display": self.display,
            "provider_rating": self.provider_rating,
            "goals_total": self.goals_total,
            "assists_total": self.assists_total,
        }


def reconstruct_raw(
    *,
    base: float,
    contributions: tuple[float, ...],
    clamp_min: float,
    clamp_max: float,
) -> float:
    return _clamp(base + sum(contributions), clamp_min, clamp_max)


def reconstruct_raw_from_stored(
    formula: dict[str, Any],
    components: list[dict[str, Any]],
) -> float:
    """Ricostruisce il voto dai JSON persistiti (formula + componenti)."""
    return reconstruct_raw(
        base=float(formula["base"]),
        contributions=tuple(float(item["contribution"]) for item in components),
        clamp_min=float(formula["clamp_min"]),
        clamp_max=float(formula["clamp_max"]),
    )


def compute_rating(player: PlayerMatchInput, config: FormulaConfig) -> RatingResult:
    role = _map_role(player.position, config)
    eligible, reason = _eligibility(player, config, role)

    if role is None:
        return RatingResult(
            formula_version=config.version,
            fixture_id=player.fixture_id,
            player_id=player.player_id,
            player_name=player.player_name,
            role=None,
            minutes=player.minutes,
            eligible=False,
            eligibility_reason="unknown_position",
            base=config.base,
            components=(),
            raw_before_clamp=config.base,
            raw=config.base,
            display=None,
            provider_rating=player.provider_rating,
            goals_total=player.goals_total,
            assists_total=player.assists_total,
            stats_hash=player.stats_hash,
        )

    components = tuple(
        _eval_component(spec, player.statistics, config) for spec in config.components_for(role)
    )
    raw_before = config.base + sum(item.contribution for item in components)
    raw = _clamp(raw_before, config.clamp_min, config.clamp_max)
    display = round_to_step(raw, config.display_step) if eligible else None

    return RatingResult(
        formula_version=config.version,
        fixture_id=player.fixture_id,
        player_id=player.player_id,
        player_name=player.player_name,
        role=role,
        minutes=player.minutes,
        eligible=eligible,
        eligibility_reason=reason,
        base=config.base,
        components=components,
        raw_before_clamp=raw_before,
        raw=raw,
        display=display,
        provider_rating=player.provider_rating,
        goals_total=player.goals_total,
        assists_total=player.assists_total,
        stats_hash=player.stats_hash,
    )


def round_to_step(value: float, step: float) -> float:
    """Arrotonda allo scatto più vicino (half-up per voti in 3–10)."""
    if step <= 0:
        raise ValueError("display_step must be > 0")
    scaled = value / step
    rounded = int(scaled + 0.5)
    return round(rounded * step, 10)


def _eligibility(
    player: PlayerMatchInput, config: FormulaConfig, role: RoleCode | None
) -> tuple[bool, str]:
    decision = evaluate_eligibility(
        minutes=player.minutes,
        substitute=player.substitute,
        role=role,
        has_relevant_event=player.relevant_events.any_relevant(config.relevant_event_flags),
        entered_in_stoppage=player.entered_in_stoppage,
        minutes_threshold=config.minutes_threshold,
        goalkeeper_starter_always_eligible=config.goalkeeper_starter_always_eligible,
    )
    return decision.eligible, decision.reason


def _map_role(position: str | None, config: FormulaConfig) -> RoleCode | None:
    if not position:
        return None
    return config.position_map.get(position)


def _eval_component(
    spec: ComponentSpec, statistics: dict[str, Any], config: FormulaConfig
) -> ComponentContribution:
    if spec.path in config.excluded_stat_paths:
        raise ValueError(f"component {spec.id} uses excluded path {spec.path}")

    raw_value = _feature_value(spec, statistics)
    uncapped = spec.coeff * raw_value
    contribution = _clamp(uncapped, -spec.max_abs, spec.max_abs)
    return ComponentContribution(
        id=spec.id,
        path=spec.path,
        raw_value=raw_value,
        coeff=spec.coeff,
        uncapped=uncapped,
        contribution=contribution,
        max_abs=spec.max_abs,
    )


def _feature_value(spec: ComponentSpec, statistics: dict[str, Any]) -> float:
    if spec.transform == "raw":
        return _numeric(_dig(statistics, spec.path))
    if spec.transform == "rate":
        num = _numeric(_dig(statistics, spec.path))
        den = _numeric(_dig(statistics, spec.denom_path or ""))
        return (num / den) if den > 0 else 0.0
    if spec.transform == "accuracy":
        return _pass_accuracy(statistics, spec.path, spec.denom_path or "passes.total")
    raise ValueError(f"unknown transform {spec.transform}")


def _pass_accuracy(statistics: dict[str, Any], path: str, denom_path: str) -> float:
    """Normalizza ``passes.accuracy`` (conteggio o percentuale) in 0–1."""
    raw = _dig(statistics, path)
    total = _numeric(_dig(statistics, denom_path))
    if raw is None:
        return 0.0
    if isinstance(raw, str) and raw.endswith("%"):
        try:
            return float(raw[:-1]) / 100.0
        except ValueError:
            return 0.0
    value = _numeric(raw)
    if total > 0 and value <= total:
        return value / total
    if value > 1.0:
        return value / 100.0
    return value


def _dig(stats: dict[str, Any], path: str) -> Any:
    if not path:
        return None
    cur: Any = stats
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _numeric(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip().rstrip("%")
        try:
            return float(text)
        except ValueError:
            return 0.0
    return 0.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))

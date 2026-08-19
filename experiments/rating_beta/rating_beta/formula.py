"""Experimental Rating Beta formula (explainable, versioned)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import ComponentSpec, FormulaConfig, RoleCode
from .input import PlayerMatchInput


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

    @property
    def components_sum(self) -> float:
        return sum(c.contribution for c in self.components)

    def reconstruct_with(self, config: FormulaConfig) -> float:
        """Rebuild raw from base + components, then clamp (audit / tests)."""
        total = config.base + sum(c.contribution for c in self.components)
        return _clamp(total, config.clamp_min, config.clamp_max)

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
            "components": [c.as_dict() for c in self.components],
            "components_sum": self.components_sum,
            "raw_before_clamp": self.raw_before_clamp,
            "raw": self.raw,
            "display": self.display,
            "provider_rating": self.provider_rating,
            "goals_total": self.goals_total,
            "assists_total": self.assists_total,
        }


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
        )

    components = tuple(
        _eval_component(spec, player.statistics, config)
        for spec in config.components_for(role)
    )
    raw_before = config.base + sum(c.contribution for c in components)
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
    )


def round_to_step(value: float, step: float) -> float:
    """Round to nearest step (half-up away from zero for .25/.75 edges via banker's-free)."""
    if step <= 0:
        raise ValueError("display_step must be > 0")
    scaled = value / step
    # half-up: floor(x + 0.5) for positive values (votes are in 3–10)
    rounded = int(scaled + 0.5)
    return round(rounded * step, 10)


def _eligibility(
    player: PlayerMatchInput, config: FormulaConfig, role: RoleCode | None
) -> tuple[bool, str]:
    minutes = player.minutes
    if minutes is None or minutes <= 0:
        if player.relevant_events.any_relevant(config.relevant_event_flags):
            return True, "relevant_event_zero_minutes"
        return False, "no_minutes"

    if minutes >= config.minutes_threshold:
        return True, "minutes_threshold"

    if (
        config.goalkeeper_starter_always_eligible
        and role == "P"
        and not player.substitute
    ):
        return True, "goalkeeper_starter"

    if player.relevant_events.any_relevant(config.relevant_event_flags):
        return True, "relevant_event_under_threshold"

    return False, "under_threshold_no_relevant_event"


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
    """Normalize API-Football passes.accuracy (count or percent string) to 0–1."""
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
    if isinstance(value, (int, float)):
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

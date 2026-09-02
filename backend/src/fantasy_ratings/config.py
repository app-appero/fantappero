"""Configurazione versionata della formula Rating (EP07-01 / spike EP00-05)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from fantasy_ratings.eligibility import (
    STANDARD_MINUTES_THRESHOLD,
    coerce_minutes_threshold,
)

Transform = Literal["raw", "rate", "accuracy"]
RoleCode = Literal["P", "D", "C", "A"]

DEFAULT_FORMULA_VERSION = "beta-v0.1"
DEFAULT_FORMULA_CARD = "EP07-01"

# Coefficienti e soglie dello spike EP00-05 (config/beta-v0.1.yaml).
# Gol/assist restano fuori dal voto statistico (bonus FR-SCO-02 / EP07-03).
BETA_V0_1: dict[str, Any] = {
    "version": DEFAULT_FORMULA_VERSION,
    "card": DEFAULT_FORMULA_CARD,
    "base": 6.0,
    "clamp_min": 3.0,
    "clamp_max": 10.0,
    "display_step": 0.5,
    "minutes_threshold": STANDARD_MINUTES_THRESHOLD,
    "goalkeeper_starter_always_eligible": True,
    "relevant_event_flags": [
        "goal",
        "assist",
        "penalty_missed",
        "own_goal",
        "red_card",
    ],
    "excluded_stat_paths": ["goals.total", "goals.assists"],
    "position_map": {"G": "P", "D": "D", "M": "C", "F": "A"},
    "roles": {
        "P": {
            "components": [
                {
                    "id": "saves",
                    "path": "goals.saves",
                    "coeff": 0.18,
                    "max_abs": 1.8,
                    "transform": "raw",
                },
                {
                    "id": "pass_volume",
                    "path": "passes.total",
                    "coeff": 0.008,
                    "max_abs": 0.6,
                    "transform": "raw",
                },
                {
                    "id": "fouls_committed",
                    "path": "fouls.committed",
                    "coeff": -0.12,
                    "max_abs": 0.6,
                    "transform": "raw",
                },
            ]
        },
        "D": {
            "components": [
                {
                    "id": "tackles",
                    "path": "tackles.total",
                    "coeff": 0.12,
                    "max_abs": 1.2,
                    "transform": "raw",
                },
                {
                    "id": "interceptions",
                    "path": "tackles.interceptions",
                    "coeff": 0.10,
                    "max_abs": 1.0,
                    "transform": "raw",
                },
                {
                    "id": "blocks",
                    "path": "tackles.blocks",
                    "coeff": 0.10,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
                {
                    "id": "duels_won",
                    "path": "duels.won",
                    "coeff": 0.06,
                    "max_abs": 1.0,
                    "transform": "raw",
                },
                {
                    "id": "pass_accuracy",
                    "path": "passes.accuracy",
                    "denom_path": "passes.total",
                    "coeff": 0.8,
                    "max_abs": 0.8,
                    "transform": "accuracy",
                },
                {
                    "id": "fouls_committed",
                    "path": "fouls.committed",
                    "coeff": -0.10,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
            ]
        },
        "C": {
            "components": [
                {
                    "id": "key_passes",
                    "path": "passes.key",
                    "coeff": 0.18,
                    "max_abs": 1.2,
                    "transform": "raw",
                },
                {
                    "id": "pass_accuracy",
                    "path": "passes.accuracy",
                    "denom_path": "passes.total",
                    "coeff": 0.9,
                    "max_abs": 0.9,
                    "transform": "accuracy",
                },
                {
                    "id": "tackles",
                    "path": "tackles.total",
                    "coeff": 0.08,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
                {
                    "id": "dribbles_success",
                    "path": "dribbles.success",
                    "coeff": 0.12,
                    "max_abs": 1.0,
                    "transform": "raw",
                },
                {
                    "id": "shots_on",
                    "path": "shots.on",
                    "coeff": 0.15,
                    "max_abs": 0.9,
                    "transform": "raw",
                },
                {
                    "id": "fouls_committed",
                    "path": "fouls.committed",
                    "coeff": -0.10,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
            ]
        },
        "A": {
            "components": [
                {
                    "id": "shots_on",
                    "path": "shots.on",
                    "coeff": 0.25,
                    "max_abs": 1.5,
                    "transform": "raw",
                },
                {
                    "id": "shots_total",
                    "path": "shots.total",
                    "coeff": 0.08,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
                {
                    "id": "key_passes",
                    "path": "passes.key",
                    "coeff": 0.15,
                    "max_abs": 1.0,
                    "transform": "raw",
                },
                {
                    "id": "dribbles_success",
                    "path": "dribbles.success",
                    "coeff": 0.14,
                    "max_abs": 1.2,
                    "transform": "raw",
                },
                {
                    "id": "duels_won",
                    "path": "duels.won",
                    "coeff": 0.05,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
                {
                    "id": "fouls_committed",
                    "path": "fouls.committed",
                    "coeff": -0.10,
                    "max_abs": 0.8,
                    "transform": "raw",
                },
            ]
        },
    },
}


@dataclass(frozen=True)
class ComponentSpec:
    id: str
    path: str
    coeff: float
    max_abs: float
    transform: Transform = "raw"
    denom_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "path": self.path,
            "coeff": self.coeff,
            "max_abs": self.max_abs,
            "transform": self.transform,
        }
        if self.denom_path is not None:
            payload["denom_path"] = self.denom_path
        return payload


@dataclass(frozen=True)
class FormulaConfig:
    version: str
    card: str
    base: float
    clamp_min: float
    clamp_max: float
    display_step: float
    minutes_threshold: int
    goalkeeper_starter_always_eligible: bool
    relevant_event_flags: tuple[str, ...]
    excluded_stat_paths: tuple[str, ...]
    position_map: dict[str, RoleCode]
    roles: dict[RoleCode, tuple[ComponentSpec, ...]]

    def components_for(self, role: RoleCode) -> tuple[ComponentSpec, ...]:
        return self.roles[role]

    def with_minutes_threshold(self, minutes_threshold: int) -> FormulaConfig:
        return replace(self, minutes_threshold=coerce_minutes_threshold(minutes_threshold))

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "card": self.card,
            "base": self.base,
            "clamp_min": self.clamp_min,
            "clamp_max": self.clamp_max,
            "display_step": self.display_step,
            "minutes_threshold": self.minutes_threshold,
            "goalkeeper_starter_always_eligible": self.goalkeeper_starter_always_eligible,
            "relevant_event_flags": list(self.relevant_event_flags),
            "excluded_stat_paths": list(self.excluded_stat_paths),
            "position_map": dict(self.position_map),
            "roles": {
                role: {"components": [spec.as_dict() for spec in specs]}
                for role, specs in self.roles.items()
            },
        }


def default_formula_config() -> FormulaConfig:
    return load_formula_config(BETA_V0_1)


def load_formula_config(raw: dict[str, Any] | None = None) -> FormulaConfig:
    payload = raw if raw is not None else BETA_V0_1
    return _from_dict(payload, source="formula_config")


def _from_dict(raw: dict[str, Any], *, source: str) -> FormulaConfig:
    required = (
        "version",
        "base",
        "clamp_min",
        "clamp_max",
        "display_step",
        "minutes_threshold",
        "roles",
        "position_map",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"config {source} missing keys: {missing}")

    roles: dict[RoleCode, tuple[ComponentSpec, ...]] = {}
    for role, payload in raw["roles"].items():
        if role not in ("P", "D", "C", "A"):
            raise ValueError(f"unknown role {role!r} in {source}")
        comps = payload.get("components") if isinstance(payload, dict) else payload
        if not isinstance(comps, list):
            raise ValueError(f"roles.{role}.components must be a list in {source}")
        roles[role] = tuple(_component(item, role=role, source=source) for item in comps)

    for role in ("P", "D", "C", "A"):
        if role not in roles:
            raise ValueError(f"config {source} missing role formula for {role}")

    position_map = {str(key): value for key, value in raw["position_map"].items()}
    for key, value in position_map.items():
        if value not in ("P", "D", "C", "A"):
            raise ValueError(f"invalid position map {key}->{value} in {source}")

    return FormulaConfig(
        version=str(raw["version"]),
        card=str(raw.get("card", DEFAULT_FORMULA_CARD)),
        base=float(raw["base"]),
        clamp_min=float(raw["clamp_min"]),
        clamp_max=float(raw["clamp_max"]),
        display_step=float(raw["display_step"]),
        minutes_threshold=coerce_minutes_threshold(int(raw["minutes_threshold"])),
        goalkeeper_starter_always_eligible=bool(
            raw.get("goalkeeper_starter_always_eligible", True)
        ),
        relevant_event_flags=tuple(raw.get("relevant_event_flags") or ()),
        excluded_stat_paths=tuple(raw.get("excluded_stat_paths") or ()),
        position_map=position_map,  # type: ignore[arg-type]
        roles=roles,
    )


def _component(raw: dict[str, Any], *, role: str, source: str) -> ComponentSpec:
    for key in ("id", "path", "coeff", "max_abs"):
        if key not in raw:
            raise ValueError(f"component missing {key} in roles.{role} ({source})")
    transform = str(raw.get("transform", "raw"))
    if transform not in ("raw", "rate", "accuracy"):
        raise ValueError(f"invalid transform {transform!r} in roles.{role}.{raw['id']}")
    return ComponentSpec(
        id=str(raw["id"]),
        path=str(raw["path"]),
        coeff=float(raw["coeff"]),
        max_abs=float(raw["max_abs"]),
        transform=transform,  # type: ignore[arg-type]
        denom_path=str(raw["denom_path"]) if raw.get("denom_path") else None,
    )

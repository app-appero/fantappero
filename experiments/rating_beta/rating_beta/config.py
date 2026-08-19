"""Versioned formula configuration for Rating Beta."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .yaml_lite import load_yaml

Transform = Literal["raw", "rate", "accuracy"]
RoleCode = Literal["P", "D", "C", "A"]

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = EXPERIMENT_ROOT / "config" / "beta-v0.1.yaml"
DEFAULT_REPORT_PATH = EXPERIMENT_ROOT / "reports" / "rating_beta_v0.1.md"


@dataclass(frozen=True)
class ComponentSpec:
    id: str
    path: str
    coeff: float
    max_abs: float
    transform: Transform = "raw"
    denom_path: str | None = None


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


def load_formula_config(path: Path | str | None = None) -> FormulaConfig:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw = load_yaml(cfg_path)
    return _from_dict(raw, source=str(cfg_path))


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
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"config {source} missing keys: {missing}")

    roles: dict[RoleCode, tuple[ComponentSpec, ...]] = {}
    for role, payload in raw["roles"].items():
        if role not in ("P", "D", "C", "A"):
            raise ValueError(f"unknown role {role!r} in {source}")
        comps = payload.get("components") if isinstance(payload, dict) else payload
        if not isinstance(comps, list):
            raise ValueError(f"roles.{role}.components must be a list in {source}")
        roles[role] = tuple(_component(c, role=role, source=source) for c in comps)

    for role in ("P", "D", "C", "A"):
        if role not in roles:
            raise ValueError(f"config {source} missing role formula for {role}")

    position_map = {str(k): v for k, v in raw["position_map"].items()}
    for k, v in position_map.items():
        if v not in ("P", "D", "C", "A"):
            raise ValueError(f"invalid position map {k}->{v} in {source}")

    return FormulaConfig(
        version=str(raw["version"]),
        card=str(raw.get("card", "EP00-05")),
        base=float(raw["base"]),
        clamp_min=float(raw["clamp_min"]),
        clamp_max=float(raw["clamp_max"]),
        display_step=float(raw["display_step"]),
        minutes_threshold=int(raw["minutes_threshold"]),
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

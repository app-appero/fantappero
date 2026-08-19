"""Role-level statistical report for Rating Beta experiments."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import FormulaConfig, RoleCode
from .formula import RatingResult


@dataclass(frozen=True)
class RoleStats:
    role: RoleCode
    n: int
    mean: float | None
    median: float | None
    stdev: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    minimum: float | None
    maximum: float | None
    n_ineligible: int = 0
    mean_provider: float | None = None
    mean_abs_delta_vs_provider: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "n": self.n,
            "mean": self.mean,
            "median": self.median,
            "stdev": self.stdev,
            "p10": self.p10,
            "p25": self.p25,
            "p75": self.p75,
            "p90": self.p90,
            "min": self.minimum,
            "max": self.maximum,
            "n_ineligible": self.n_ineligible,
            "mean_provider": self.mean_provider,
            "mean_abs_delta_vs_provider": self.mean_abs_delta_vs_provider,
        }


def build_role_stats(results: Iterable[RatingResult]) -> dict[RoleCode, RoleStats]:
    by_role: dict[RoleCode, list[RatingResult]] = {"P": [], "D": [], "C": [], "A": []}
    ineligible: dict[RoleCode, int] = {"P": 0, "D": 0, "C": 0, "A": 0}

    for r in results:
        if r.role is None:
            continue
        if not r.eligible or r.display is None:
            ineligible[r.role] += 1
            continue
        by_role[r.role].append(r)

    out: dict[RoleCode, RoleStats] = {}
    for role, items in by_role.items():
        values = [r.raw for r in items]
        provider_pairs = [
            (r.raw, r.provider_rating)
            for r in items
            if r.provider_rating is not None
        ]
        out[role] = RoleStats(
            role=role,
            n=len(values),
            mean=_mean(values),
            median=_median(values),
            stdev=_stdev(values),
            p10=_percentile(values, 10),
            p25=_percentile(values, 25),
            p75=_percentile(values, 75),
            p90=_percentile(values, 90),
            minimum=min(values) if values else None,
            maximum=max(values) if values else None,
            n_ineligible=ineligible[role],
            mean_provider=_mean([p for _, p in provider_pairs]) if provider_pairs else None,
            mean_abs_delta_vs_provider=(
                _mean([abs(raw - prov) for raw, prov in provider_pairs])
                if provider_pairs
                else None
            ),
        )
    return out


def render_markdown_report(
    *,
    config: FormulaConfig,
    role_stats: dict[RoleCode, RoleStats],
    results: list[RatingResult],
    corpus_note: str,
    sample_decompositions: list[RatingResult] | None = None,
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    eligible = [r for r in results if r.eligible and r.display is not None]
    lines: list[str] = [
        f"# Rating Beta report — {config.version}",
        "",
        "| Metadato | Valore |",
        "| --- | --- |",
        f"| Card | {config.card} |",
        f"| Formula | `{config.version}` |",
        f"| Generato | {generated} |",
        f"| Corpus | {corpus_note} |",
        f"| Base | {config.base} |",
        f"| Clamp | {config.clamp_min}–{config.clamp_max} |",
        f"| Display step | {config.display_step} |",
        f"| Soglia minuti | {config.minutes_threshold} |",
        f"| Voti eleggibili | {len(eligible)} / {len(results)} |",
        "",
        "## Controlli di design",
        "",
        "- Gol e assist **non** entrano nel voto statistico (solo flag di eleggibilità sotto soglia).",
        "- `games.rating` provider è riportato solo come **diagnostica** (media scarto assoluto per ruolo).",
        "- Il prototipo **non** scrive risultati ufficiali nel database applicativo.",
        "- Ogni voto eleggibile è ricostruibile come `clamp(base + Σ componenti)`.",
        "",
        "## Statistiche per ruolo (valore grezzo `raw`)",
        "",
        (
            "| Ruolo | n | media | mediana | σ | p10 | p25 | p75 | p90 | min | max "
            "| non eleggibili | mean abs Δ vs provider |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for role in ("P", "D", "C", "A"):
        s = role_stats[role]
        lines.append(
            "| {role} | {n} | {mean} | {median} | {stdev} | {p10} | {p25} | {p75} | {p90} | {minimum} | {maximum} | {n_ineligible} | {delta} |".format(
                role=s.role,
                n=s.n,
                mean=_fmt(s.mean),
                median=_fmt(s.median),
                stdev=_fmt(s.stdev),
                p10=_fmt(s.p10),
                p25=_fmt(s.p25),
                p75=_fmt(s.p75),
                p90=_fmt(s.p90),
                minimum=_fmt(s.minimum),
                maximum=_fmt(s.maximum),
                n_ineligible=s.n_ineligible,
                delta=_fmt(s.mean_abs_delta_vs_provider),
            )
        )

    samples = sample_decompositions or _pick_samples(eligible)
    lines.extend(["", "## Scomposizioni di esempio", ""])
    for r in samples:
        lines.append(
            f"### {r.player_name} (fixture {r.fixture_id}, ruolo {r.role})"
        )
        lines.append("")
        lines.append(
            f"- eleggibilità: `{r.eligibility_reason}` · minuti={r.minutes} · "
            f"raw={_fmt(r.raw)} · display={_fmt(r.display)} · "
            f"provider={_fmt(r.provider_rating)}"
        )
        lines.append(f"- ricostruzione: `{config.base} + Σ = {_fmt(r.reconstruct_with(config))}`")
        lines.append("")
        lines.append("| componente | path | valore | coeff | contributo |")
        lines.append("| --- | --- | ---: | ---: | ---: |")
        for c in r.components:
            lines.append(
                f"| {c.id} | `{c.path}` | {_fmt(c.raw_value)} | {c.coeff} | {_fmt(c.contribution)} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Note di calibrazione",
            "",
            "Coefficienti `beta-v0.1` sono **sperimentali** (Master §8.1 / FR-SCO-01): "
            "servono a verificare coverage e spiegabilità offline, non a chiudere la formula definitiva.",
            "",
        ]
    )
    return "\n".join(lines)


def _pick_samples(eligible: list[RatingResult], n: int = 4) -> list[RatingResult]:
    picked: list[RatingResult] = []
    seen_roles: set[str] = set()
    for r in sorted(eligible, key=lambda x: (x.role or "", x.player_id)):
        if r.role and r.role not in seen_roles:
            picked.append(r)
            seen_roles.add(r.role)
        if len(picked) >= n:
            break
    return picked


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.fmean(values)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return float(statistics.stdev(values))


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    weight = rank - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"

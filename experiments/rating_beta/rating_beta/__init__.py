"""FantApperò Rating Beta — experimental offline formula (EP00-05).

Does not write official scores to the application database.
"""

from __future__ import annotations

from .config import FormulaConfig, load_formula_config
from .formula import RatingResult, compute_rating
from .report import RoleStats, build_role_stats, render_markdown_report

__all__ = [
    "FormulaConfig",
    "RatingResult",
    "RoleStats",
    "build_role_stats",
    "compute_rating",
    "load_formula_config",
    "render_markdown_report",
]

__version__ = "0.1.0"

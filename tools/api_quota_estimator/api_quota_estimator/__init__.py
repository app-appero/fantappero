"""API-Football quota estimator (EP00-04).

Central SPD sync sizing: request volume does not scale with fantasy users.
"""

from .calculator import QuotaCalculator, ScenarioResult, SimulationReport
from .config import EstimatorConfig, load_config

__all__ = [
    "EstimatorConfig",
    "QuotaCalculator",
    "ScenarioResult",
    "SimulationReport",
    "load_config",
]

__version__ = "1.0.0"

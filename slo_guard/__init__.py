"""slo-guard: SRE alerting engine with burn-rate alerting and SLO tracking."""
from .pipeline import Pipeline, run

__all__ = ["Pipeline", "run"]
__version__ = "1.0.0"

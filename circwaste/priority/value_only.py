"""Value-only prize policy (alpha = 0); see recovery_aware.PrizePolicy."""
from .recovery_aware import PrizePolicy


def value_only(beta: float, overflow_cost_inr: float) -> PrizePolicy:
    return PrizePolicy("value_only", 0.0, beta, overflow_cost_inr)

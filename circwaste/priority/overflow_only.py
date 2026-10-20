"""Overflow-only prize policy (beta = 0); see recovery_aware.PrizePolicy."""
from .recovery_aware import PrizePolicy


def overflow_only(alpha: float, overflow_cost_inr: float) -> PrizePolicy:
    return PrizePolicy("overflow_only", alpha, 0.0, overflow_cost_inr)

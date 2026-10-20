"""Policies selected by name from configs/policies.yaml."""
from __future__ import annotations

from circwaste.config import val

from .base import DayForecast
from .overflow_only import overflow_only
from .recovery_aware import PrizePolicy
from .threshold import ThresholdPolicy
from .value_only import value_only

POLICY_NAMES = ["threshold", "overflow_only", "recovery_aware", "value_only"]


def make_policy(name: str, pcfg: dict, acfg: dict, alpha: float | None = None, beta: float | None = None):
    """Build a policy from configs/policies.yaml (`pcfg`) and assumptions (`acfg`); alpha/beta override the config (what-if, ablation)."""
    p = pcfg["policies"][name]
    oc = float(val(acfg, "costs.overflow_cost_inr"))
    a = float(p.get("alpha", 0.0) if alpha is None else alpha)
    b = float(p.get("beta", 0.0) if beta is None else beta)
    if name == "threshold":
        return ThresholdPolicy(p["threshold_fill"], pcfg.get("threshold_prize_inr", 100000.0))
    if name == "overflow_only":
        return overflow_only(a, oc)
    if name == "value_only":
        return value_only(b, oc)
    if name == "recovery_aware":
        return PrizePolicy("recovery_aware", a, b, oc)
    raise KeyError(name)


__all__ = ["DayForecast", "POLICY_NAMES", "PrizePolicy", "ThresholdPolicy", "make_policy"]

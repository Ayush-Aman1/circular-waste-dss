"""Prize = alpha * P(overflow) * overflow_cost + beta * recovery value (both INR/day).

recovery_aware: alpha, beta > 0 (this project's contribution). overflow_only: beta = 0 (style of the 2024 integrated selection-and-routing
paper, arXiv 2409.13386: prizes from the probability of overflowing before the next plan). value_only: alpha = 0.
"""
from __future__ import annotations

from .base import DayForecast


class PrizePolicy:
    def __init__(self, name: str, alpha: float, beta: float, overflow_cost_inr: float):
        self.name, self.alpha, self.beta, self.oc = name, float(alpha), float(beta), float(overflow_cost_inr)

    def prizes(self, state, forecast: DayForecast) -> dict[str, float]:
        pr = self.alpha * forecast.overflow_risk * self.oc + self.beta * forecast.recovery_value_inr
        return dict(zip(forecast.point_ids, map(float, pr)))

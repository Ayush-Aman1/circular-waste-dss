"""Tier A: collect a point if its predicted fill fraction is >= the threshold (guide: 80 %). Selected points get one large uniform prize,
the others none, so the router solves a CVRP over the selected set (and, only if the fleet cannot take them all, drops the cheapest to skip)."""
from __future__ import annotations

from .base import DayForecast


class ThresholdPolicy:
    name = "threshold"

    def __init__(self, threshold_fill: float, prize_inr: float):
        self.threshold, self.prize = float(threshold_fill), float(prize_inr)

    def prizes(self, state, forecast: DayForecast) -> dict[str, float]:
        sel = forecast.pred_fill_frac >= self.threshold
        return {p: (self.prize if s else 0.0) for p, s in zip(forecast.point_ids, sel)}

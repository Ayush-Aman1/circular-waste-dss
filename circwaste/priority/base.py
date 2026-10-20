"""Policy contract: prizes(state, forecast) -> {point_id: prize in INR for visiting the point today}. All prizes are INR/day so they sit on the
same scale as route costs (docs/DECISIONS.md D9). Policies see only forecasts and the observed fill, never the future generation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DayForecast:
    point_ids: list[str]
    fill_kg: np.ndarray            # observed fill at the start of the day
    capacity_kg: np.ndarray
    gen_pred_kg: np.ndarray        # forecast mass generated today (point forecast)
    overflow_risk: np.ndarray      # recalibrated P(fill + generation today > capacity | not collected)
    recovery_value_inr: np.ndarray # value of the bin's current content at forecast composition (segregation x efficiency x price)

    @property
    def pred_fill_frac(self) -> np.ndarray:
        """Predicted fill fraction at the end of the day if the bin is not emptied."""
        return (self.fill_kg + self.gen_pred_kg) / self.capacity_kg

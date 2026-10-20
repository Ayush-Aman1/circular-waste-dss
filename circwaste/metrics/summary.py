"""Aggregate per-day loop records into the summary metrics (guide P6). All sums are over the policy-controlled evaluation days of one run."""
from __future__ import annotations

import pandas as pd

from circwaste.models import MATERIALS

STREAMS = {"recycling": ["paper", "plastic", "glass", "metal", "textile", "rubber_leather"], "composting_biomethanation": ["organic"]}


def summarise(days: pd.DataFrame, overflow_cost_inr: float) -> dict:
    """`days`: one row per evaluated day (columns written by circwaste.scenario.loop)."""
    s = days.sum(numeric_only=True)
    coll = float(s.collected_kg)
    rec_total = float(sum(s[f"rec_{m}_kg"] for m in MATERIALS))
    operating = float(s.routing_cost_inr + s.fixed_daily_cost_inr)
    penalty = float(s.overflow_events * overflow_cost_inr)
    out = {
        "synthetic": True,
        "days": int(len(days)),
        "overflow_events": float(s.overflow_events),
        "overflow_kg": float(s.overflow_kg),
        "km": float(s.km),
        "vehicle_hours": float(s.vehicle_hours),
        "operating_cost_inr": operating,
        "overflow_penalty_inr": penalty,
        "recovered_value_inr": float(s.recovered_value_inr),
        "net_cost_inr": operating + penalty - float(s.recovered_value_inr),
        "generated_kg": float(s.generated_kg),
        "collected_kg": coll,
        "recovered_kg": rec_total,
        "landfill_kg": float(s.landfill_kg),
        "recovery_rate": rec_total / coll if coll else 0.0,
        "landfill_diversion_rate": 1.0 - float(s.landfill_kg) / coll if coll else 0.0,
        "facility_over_capacity_days": float(s.over_capacity),
        "stops": float(s.stops),
        "trips": float(s.trips),
    }
    for name, mats in STREAMS.items():
        out[f"recovered_kg_{name}"] = float(sum(s[f"rec_{m}_kg"] for m in mats))
    for m in MATERIALS:
        out[f"recovered_kg_{m}"] = float(s[f"rec_{m}_kg"])
    return out

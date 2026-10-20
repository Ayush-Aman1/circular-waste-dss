"""Scenario levers (guide P7 + BUILD prompt): everything a what-if run may change. The loop's code is never touched; levers only edit a copy
of the assumptions, the fleet, the flow capacities and the policy settings, then rerun the same seeds."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field

from circwaste.models import MATERIALS


@dataclass
class Levers:
    policy: str = "recovery_aware"
    generation_pct: float = 0.0              # change of the waste generated per person (%)
    segregation_rate: float | None = None    # share of recyclable material arriving separated (0-1); None = assumptions value
    fleet_size: int | None = None            # number of compactors; None = assumptions value
    vehicles_unavailable: int = 0            # compactors out of service today
    trips_per_vehicle: int | None = None     # collection frequency: collect-and-unload trips per vehicle per day
    capacity_pct: dict[str, float] = field(default_factory=dict)   # facility daily capacity change per kind (%), keys wet_plant/biomethanation/dwcc
    price_pct: float = 0.0                   # material price change (%)
    festival_multiplier: float | None = None # festival-day surge multiplier
    alpha: float | None = None               # prize weights; None = configs/policies.yaml
    beta: float | None = None
    overflow_cost_pct: float = 0.0           # change of the penalty per overflow event (%; sensitivity analysis)
    forecast_noise: float = 1.0              # multiplier on the forecast error (sensitivity analysis)

    def key(self, extra: dict | None = None) -> str:
        """Stable hash of the levers (+ run settings) used to cache scenario results."""
        d = {**asdict(self), **(extra or {})}
        d["capacity_pct"] = {k: v for k, v in sorted(d["capacity_pct"].items()) if v}
        return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:12]

    def is_base(self) -> bool:
        return self == Levers(policy=self.policy)


def apply_levers(cfg: dict, lv: Levers) -> dict:
    """Return a copy of the assumptions with the levers applied (zero-change levers return an identical copy)."""
    c = copy.deepcopy(cfg)
    if lv.generation_pct:
        c["generation"]["per_capita_kg_day"]["value"] *= 1.0 + lv.generation_pct / 100.0
    if lv.segregation_rate is not None:
        c["segregation"]["rate"]["value"] = float(lv.segregation_rate)
    if lv.price_pct:
        pr = c["recovery"]["price_per_kg"]["value"]
        for m in MATERIALS:
            pr[m] *= 1.0 + lv.price_pct / 100.0
    if lv.festival_multiplier is not None:
        c["generation"]["festival_multiplier"]["value"] = float(lv.festival_multiplier)
    if lv.overflow_cost_pct:
        c["costs"]["overflow_cost_inr"]["value"] *= 1.0 + lv.overflow_cost_pct / 100.0
    veh = c["costs"]["vehicle"]["value"]
    if lv.fleet_size is not None:
        veh["count"] = int(lv.fleet_size)
    if lv.trips_per_vehicle is not None:
        c["fleet"]["trips_per_vehicle_per_day"]["value"] = int(lv.trips_per_vehicle)
    return c

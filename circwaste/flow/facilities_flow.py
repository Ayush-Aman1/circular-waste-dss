"""Material flow after collection. Collected mass by material is split into

  * segregated share  (mass x segregation) -> sent to the nearest facility of the material's stream with daily capacity left
    (assumptions flow.streams: organic -> wet plants / biomethanation, dry recyclables -> DWCC, inert -> landfill)
  * the rest (mass x (1 - segregation)) -> landfill

At a facility the delivered mass is recovered at the material's efficiency; the rejects go to landfill. Delivered mass beyond the daily
capacity of every facility of the stream is diverted to landfill and the day counts as a facility over-capacity day. Within shared facilities
(all dry streams share the DWCCs) materials are served in descending order of price x efficiency, a fixed documented priority.
Mass balance: collected = recovered + landfill, always (tested).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from circwaste.config import val
from circwaste.models import MATERIALS


@dataclass
class FlowResult:
    recovered_kg: dict[str, float]            # per material
    recovered_value_inr: float
    landfill_kg: float
    delivered_kg: dict[str, float]            # per facility id (segregated mass received that day)
    spilled_kg: float                         # segregated mass that found no capacity (included in landfill_kg)
    over_capacity: bool
    by_stream: dict[str, float] = field(default_factory=dict)   # recovered kg: recycling (dry) / composting_biomethanation (organic)


class FlowModel:
    def __init__(self, facilities: pd.DataFrame, cfg: dict, segregation: float | None = None, capacity_pct: dict[str, float] | None = None):
        self.cfg = cfg
        self.seg = float(val(cfg, "segregation.rate") if segregation is None else segregation)
        self.eff = {m: float(v) for m, v in val(cfg, "recovery.efficiency").items()}
        self.price = {m: float(v) for m, v in val(cfg, "recovery.price_per_kg").items()}
        self.streams: dict[str, list[str]] = val(cfg, "flow.streams")
        f = facilities.sort_values("dist_km").reset_index(drop=True)
        mult = {k: 1.0 + float(v) / 100.0 for k, v in (capacity_pct or {}).items()}
        self.fac = [(r.id, r.kind, float(r.capacity_kg_day) * mult.get(r.kind, 1.0)) for r in f.itertuples()]
        self.stock: dict[str, float] = {fid: 0.0 for fid, _, _ in self.fac}   # cumulative kg delivered

    def day(self, collected_kg: np.ndarray) -> FlowResult:
        """`collected_kg`: mass per material (MATERIALS order) collected today."""
        remaining = {fid: cap for fid, _, cap in self.fac}
        delivered = {fid: 0.0 for fid, _, _ in self.fac}
        order = sorted(range(len(MATERIALS)), key=lambda k: -(self.price[MATERIALS[k]] * self.eff[MATERIALS[k]]))
        rec = {m: 0.0 for m in MATERIALS}
        spilled = 0.0
        landfill = 0.0
        over = False
        by_stream = {"recycling": 0.0, "composting_biomethanation": 0.0}
        for k in order:
            m = MATERIALS[k]
            mass = float(collected_kg[k])
            kinds = self.streams[m]
            if kinds == ["landfill"] or self.eff[m] == 0.0:
                landfill += mass
                continue
            seg_in = mass * self.seg
            landfill += mass - seg_in
            left = seg_in
            for fid, kind, _ in self.fac:
                if left <= 0:
                    break
                if kind not in kinds:
                    continue
                take = min(left, remaining[fid])
                remaining[fid] -= take
                delivered[fid] += take
                left -= take
                rec[m] += take * self.eff[m]
                landfill += take * (1.0 - self.eff[m])
                by_stream["composting_biomethanation" if m == "organic" else "recycling"] += take * self.eff[m]
            if left > 1e-9:
                spilled += left
                landfill += left
                over = True
        for fid, d in delivered.items():
            self.stock[fid] += d
        value = float(sum(rec[m] * self.price[m] for m in MATERIALS))
        return FlowResult(rec, value, landfill, delivered, spilled, over, by_stream)

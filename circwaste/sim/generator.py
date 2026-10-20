"""Virtual-bin generator. Deterministic by seed. ALL output is SYNTHETIC (column synthetic=True).

Per point/day: generated_kg = point_mean_kg x weekday_mult x festival_mult x noise, where noise is lognormal AR(1) with the sigma/rho fitted on
Edinburgh (artifacts/sim/fill_noise.json) and is renormalised across the points of a ward each day, so each ward's daily total equals
ward_daily_kg x weekday x festival EXACTLY (mass balance by construction). Composition: per-point Dirichlet draw around the BBMP shares (static
per point and sim seed) with daily Dirichlet jitter. Bins follow a baseline fixed 2-day emptying schedule while history is generated; overflow
mass above capacity is recorded in overflow_kg (never silently dropped): generated = collected + overflow + change in fill.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from circwaste.config import load_assumptions, val
from circwaste.models import MATERIALS


@dataclass
class World:
    points: pd.DataFrame       # point_id, ward, node, lat, lon, weight_area_m2, capacity_kg
    ward_daily_kg: dict[str, float]
    cfg: dict
    noise: dict


def load_noise(path: str = "artifacts/sim/fill_noise.json") -> dict:
    return json.loads(Path(path).read_text())


def build_world(points: pd.DataFrame, cfg: dict | None = None, noise: dict | None = None) -> World:
    cfg = cfg or load_assumptions()
    noise = noise or load_noise()
    pts = points.copy()
    per_cap = float(val(cfg, "generation.per_capita_kg_day"))
    ppm2 = float(val(cfg, "generation.persons_per_building_m2"))
    # ward population ~ total building area x persons per m2; ward kg/day = population x per-capita rate
    ward_area = pts.groupby("ward").weight_area_m2.sum()
    ward_kg = {w: float(a * ppm2 * per_cap) for w, a in ward_area.items()}
    mean_kg = pts.apply(lambda r: ward_kg[r.ward] * r.weight_area_m2 / ward_area[r.ward], axis=1)
    pts["mean_kg_day"] = mean_kg
    pts["capacity_kg"] = mean_kg * float(val(cfg, "bins.capacity_days_of_mean_generation"))
    return World(pts, ward_kg, cfg, noise)


def _weekday(day: int, start_weekday: int = 0) -> int:
    return (day + start_weekday) % 7


def generate_history(world: World, sim_seed: int, days: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng([1234, sim_seed])
    cfg, noise, pts = world.cfg, world.noise, world.points.reset_index(drop=True)
    n = len(pts)
    shares = np.array([val(cfg, "composition.shares")[m] for m in MATERIALS])
    conc = float(val(cfg, "composition.point_variation_concentration"))
    pt_shares = np.stack([rng.dirichlet(np.maximum(shares * conc, 1e-3)) if shares.sum() > 0 else shares for _ in range(n)])
    wd_mult = np.array(noise["weekday_multipliers_mon_to_sun"])
    sigma, rho = float(noise["lognormal_sigma"]), float(noise["ar1_log_rate"])
    fest_days = set(val(cfg, "generation.festival_days"))
    fest_mult = float(val(cfg, "generation.festival_multiplier"))
    price = np.array([val(cfg, "recovery.price_per_kg")[m] for m in MATERIALS])
    eff = np.array([val(cfg, "recovery.efficiency")[m] for m in MATERIALS])
    seg = float(val(cfg, "segregation.rate"))
    cap = pts.capacity_kg.to_numpy()
    wards = pts.ward.to_numpy()
    mean_kg = np.zeros(n)
    for w, tot in world.ward_daily_kg.items():
        m = wards == w
        mean_kg[m] = tot * pts.weight_area_m2[m] / pts.weight_area_m2[m].sum()
    phase = rng.integers(0, 2, size=n)           # baseline 2-day emptying cycle
    z = rng.standard_normal(n)
    fill = np.full(n, float(val(cfg, "bins.initial_fill_fraction"))) * cap
    recs = []
    for d in range(days):
        z = rho * z + np.sqrt(1 - rho ** 2) * rng.standard_normal(n)
        nz = np.exp(sigma * z - sigma ** 2 / 2)
        gen = mean_kg * nz
        for w in world.ward_daily_kg:                # exact ward-day mass balance
            m = wards == w
            target = mean_kg[m].sum() * wd_mult[_weekday(d)] * (fest_mult if d in fest_days else 1.0)
            gen[m] *= target / gen[m].sum()
        day_shares = np.stack([rng.dirichlet(np.maximum(pt_shares[i] * 400.0, 1e-3)) for i in range(n)])
        mat_kg = gen[:, None] * day_shares
        fill = fill + gen
        overflow = np.maximum(fill - cap, 0.0)
        fill = np.minimum(fill, cap)
        collected = np.where((d + phase) % 2 == 0, fill, 0.0)
        fill_end = fill - collected
        value = (mat_kg * seg * eff * price).sum(1)
        df = pd.DataFrame({"sim_seed": sim_seed, "day": d, "weekday": _weekday(d), "festival": int(d in fest_days), "point_id": pts.point_id, "ward": wards,
                           "generated_kg": gen, "fill_before_collection_kg": fill, "collected_kg": collected, "overflow_kg": overflow, "fill_end_kg": fill_end,
                           "capacity_kg": cap, "recovery_value_inr": value})
        for k, m in enumerate(MATERIALS):
            df[f"kg_{m}"] = mat_kg[:, k]
        recs.append(df)
        fill = fill_end
    out = pd.concat(recs, ignore_index=True)
    out["synthetic"] = True
    return out

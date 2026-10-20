"""Pydantic schemas of the API. Everything derived from bin-level data carries `synthetic: true`."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NOTICE = "Synthetic simulation data: bin-level data is simulated from public statistics (BBMP/CPCB/World Bank figures, Edinburgh sensor shape). Map data (c) OpenStreetMap contributors (ODbL)."


class LeversIn(BaseModel):
    policy: Literal["threshold", "overflow_only", "recovery_aware", "value_only"] = "recovery_aware"
    generation_pct: float = Field(0.0, ge=-50, le=100, description="change of waste generated per person (%)")
    segregation_rate: float | None = Field(None, ge=0, le=1, description="share of recyclables arriving separated; null = assumptions value")
    fleet_size: int | None = Field(None, ge=1, le=20)
    vehicles_unavailable: int = Field(0, ge=0, le=20)
    trips_per_vehicle: int | None = Field(None, ge=1, le=8, description="collection frequency: collect-and-unload trips per vehicle per day")
    capacity_pct: dict[Literal["wet_plant", "biomethanation", "dwcc"], float] = Field(default_factory=dict, description="facility daily capacity change per kind (%)")
    price_pct: float = Field(0.0, ge=-90, le=300)
    festival_multiplier: float | None = Field(None, ge=1, le=5)
    alpha: float | None = Field(None, ge=0, le=10, description="overflow-risk prize weight")
    beta: float | None = Field(None, ge=0, le=10, description="recovery-value prize weight")


class ScenarioRequest(BaseModel):
    levers: LeversIn = Field(default_factory=LeversIn)
    seeds: list[int] | None = Field(None, description="simulation seeds (default: configs/loop.yaml whatif seeds)")
    eval_days: int | None = Field(None, ge=1, le=60)


class JobStatus(BaseModel):
    id: str
    status: Literal["queued", "running", "done", "failed"]
    progress: float = 0.0
    cached: bool = False
    error: str | None = None
    result: dict | None = None
    synthetic: bool = True

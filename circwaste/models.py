"""Shared contracts (pydantic) for points, facilities, vehicles and day state."""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

MATERIALS = ["organic", "paper", "plastic", "glass", "metal", "textile", "rubber_leather", "inert_other"]


class Point(BaseModel):
    id: str
    lat: float
    lon: float
    node: int | None = None
    capacity_kg: float
    ward: str


class Facility(BaseModel):
    id: str
    kind: Literal["dwcc", "wet_plant", "biomethanation", "landfill"]
    accepts: list[str]
    capacity_kg_day: float | None = None
    lat: float | None = None
    lon: float | None = None
    node: int | None = None
    name: str = ""
    source: str = ""


class Vehicle(BaseModel):
    id: str
    capacity_kg: float
    cost_per_km: float
    available: bool = True


class DayState(BaseModel):
    day: int
    fill_kg: dict[str, dict[str, float]] = Field(default_factory=dict)  # point -> material -> kg
    facility_stock_kg: dict[str, float] = Field(default_factory=dict)


class Router(Protocol):
    def solve(self, points, prizes, demands, vehicles, matrix, time_limit): ...


class Policy(Protocol):
    def prizes(self, state: DayState, forecast) -> dict[str, float]: ...

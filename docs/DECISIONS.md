# DECISIONS (choices the guide left open)

**D1 Study area.** Guide allows 1–3 wards, unspecified. OSM/Nominatim returned polygons for HSR Layout (6.7 km²) and Madiwala (0.7 km²), which are
~100 m apart (adjacent); several other Bengaluru localities (Koramangala, BTM, Jayanagar, …) have no polygon in Nominatim. They are "wards" in this
project's sense (OSM suburb polygons), not BBMP's official ward boundaries (not available as open polygons in the downloaded OpenCity set). Configured in `configs/study.yaml`.

**D2 Real fill dynamics.** The Melbourne Argyle Square smart-bin dataset is no longer published on the City of Melbourne portal (404; BLOCKERS.md), so the
fill-increment shape is fitted on Edinburgh only (334 bins, 10,000 collection events, Jun–Aug 2016). Edinburgh gives fill-before-collection per event, so daily rates are
derived from inter-collection intervals (right-censored at 100 %, fill-triggered; both caveats stored in `artifacts/sim/fill_noise.json`). Only the *shape* (lognormal sigma,
AR(1), weekday pattern) is transferred; volumes are rescaled to Indian generation.

**D3 Ward mass.** Ward daily kg = building footprint area × persons-per-m² (TODO-SOURCE) × India per-capita generation (World Bank What a Waste 2.0, computed from the downloaded file).
Point means split the ward total by building-area catchment. Noise is renormalised across a ward's points each day so ward totals are exact (mass balance by construction);
noise therefore redistributes mass between points rather than changing ward totals.

**D4 Bin capacity.** Real bin sizes are unknown, so capacity = 2.5 × the point's mean daily generation (`bins.capacity_days_of_mean_generation`, TODO-SOURCE). Baseline history uses a fixed
2-day emptying cycle so overflow occurs and is recorded.

**D5 Seeds.** 6 synthetic seeds × 180 days (guide default 5): seeds 0–2 train, 3 validation (isotonic recalibration only), 4–5 test. Rolling origins at days 120/135/150/165 (15-day steps).
Policy comparisons in the BUILD phase use their own ≥ 10 paired seeds.

**D6 Overflow event for the TRAIN backtest.** One-day horizon: fill carried in + tomorrow's generation > capacity (no visit). The 2-day-visit horizon belongs to the BUILD-phase loop.

**D7 Facility legs.** Facilities lie outside the study graph; legs use haversine × detour factor ÷ speed (TODO-SOURCE) instead of a city-wide road graph.

**D8 Composition mapping.** BBMP composition categories were grouped into the 8 model materials (see source string in assumptions.yaml) and renormalised from a sum of 1.01.

**D9 Prize units.** All prizes are INR per day so they share a scale with route costs: prize = alpha x P(overflow) x overflow_cost_inr + beta x recovery_value_inr
(configs/policies.yaml weights). The recovery value of a bin is the value of its *current* content at the forecast composition (14-day mean shares) x segregation x
efficiency x price; the overflow term uses the recalibrated LightGBM P(fill + today's generation > capacity | not visited). The threshold policy gives selected points one large
uniform prize (`threshold_prize_inr`) and the others none.

**D10 Trips.** Each compactor makes `fleet.trips_per_vehicle_per_day` collect-and-unload trips; the router sees every trip as a separate vehicle (trip slot) with the full truck capacity. A trip's fixed cost
is the depot -> unloading-facility round trip (haversine x detour, D7) at the vehicle cost per km, the unloading facility being the nearest wet plant / biomethanation plant (organic dominates the load); `fixed_daily` is charged per physical vehicle used.
Shift-length limits are not modelled; vehicle-hours are reported (travel + facility legs + stop service time). Haulage of dry fractions to DWCCs is not costed separately.

**D11 Timing.** Bins are read and emptied in the morning of day d from fill at the end of d-1; day d's generation then arrives. This matches the TRAIN overflow event (prev_fill_end + generated > capacity). The warm-up
(30 days, baseline 2-day schedule) is shared by every policy and scenario of a seed; forecasts for day d use history up to d-1 only.

**D12 Loop forecaster.** The loop uses the trained LightGBM models + isotonic recalibrator. Chronos-2 is evaluated in the TRAIN report; it needs torch, which cannot share a process with LightGBM on macOS.

**D13 Solver determinism.** PyVRP runs a fixed iteration budget per day (deterministic per seed). OR-Tools (threshold policy) is stopped by a wall-clock limit, so its solutions can differ slightly between runs/machines.

**D14 Facility capacities.** Capacities listed in the OpenCity plants CSV are multiplied by `facilities.study_area_share` (the plants serve all of Bengaluru; TODO-SOURCE); facilities with no listed capacity use per-kind placeholder
defaults (TODO-SOURCE); the nearest `facilities.max_per_kind` per kind are used. Dry materials are served in descending price x efficiency order when they share DWCC capacity.

**D15 Seeds.** Test seeds 100-109 (headline comparison), validation seeds 200-204 (alpha/beta ablation), what-if seeds 100-102; all disjoint from the forecaster training seeds 0-5.

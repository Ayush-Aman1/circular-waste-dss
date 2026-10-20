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

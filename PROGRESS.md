# PROGRESS — Circular Waste DSS

[TRAIN]
- [x] P0 scaffold, contracts (pydantic), config validation (missing `source:` fails), policies.yaml
- [x] P1 geography: wards (OSM), drivable graph, buildings, OSM waste points, OpenCity facilities (+capacities where the CSV lists them)
- [x] Data acquisition: OpenCity, World Bank WaW 2.0, Edinburgh (Melbourne unavailable → BLOCKERS.md)
- [x] P2 simulator: placement, Edinburgh calibration, generator, tests
- [x] P3 forecasting: baselines, LightGBM point+quantiles, Chronos-2 zero-shot, overflow probability + isotonic recalibration, composition/recovery value, Edinburgh external check
- [x] Full pipeline run DONE → artifacts/MANIFEST.json, TRAINING_REPORT.md

[BUILD] (next prompt)
- [x] P1 distance matrices on the graph (circwaste/geo/world.py)
- [x] P4 routers (OR-Tools, PyVRP) + tests
- [x] P5 policies, daily loop, material flow + tests (mass balance closes every day)
- [x] P6 experiments: 5 policies x 10 paired test seeds, alpha-beta ablation on validation seeds, sensitivity (price, forecast error, overflow cost, fleet), Wilcoxon tests -> experiments/results/
- [x] P7 what-if engine (levers, cache by lever hash, precomputed grid in experiments/whatif_cache)
- [x] P8 FastAPI backend + TestClient tests
- [x] P9 dashboard (web/): map, routes, policy comparison, trade-off chart, what-if panel, synthetic notice, OSM attribution
- [x] Makefile (setup/test/demo/experiments/report), README, DEMO.md, CREDITS.md, claims-guard tests

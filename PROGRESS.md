# PROGRESS — Circular Waste DSS

[TRAIN]
- [x] P0 scaffold, contracts (pydantic), config validation (missing `source:` fails), policies.yaml
- [x] P1 geography: wards (OSM), drivable graph, buildings, OSM waste points, OpenCity facilities (+capacities where the CSV lists them)
- [x] Data acquisition: OpenCity, World Bank WaW 2.0, Edinburgh (Melbourne unavailable → BLOCKERS.md)
- [x] P2 simulator: placement, Edinburgh calibration, generator, tests
- [x] P3 forecasting: baselines, LightGBM point+quantiles, Chronos-2 zero-shot, overflow probability + isotonic recalibration, composition/recovery value, Edinburgh external check
- [ ] Full pipeline run → artifacts/MANIFEST.json, TRAINING_REPORT.md

[BUILD] (next prompt)
- [ ] P1 distance matrices on the graph · P4 routers (OR-Tools, PyVRP) · P5 policies, daily loop, material flow · P6 experiments · P7 what-if · P8 API · P9 dashboard

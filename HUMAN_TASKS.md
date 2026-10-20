# HUMAN TASKS (auto-generated from configs/assumptions.yaml)

These calibration values have no verified source yet. The simulator runs with the placeholder value shown, but every result that depends on
them is only as good as the placeholder. Replace the value, set `source:` to a citation, then re-run `bash pipelines/train_all.sh` (delete `runs/train_all/stages/history.done`, `forecast.done`, `collect.done`).

| entry | placeholder value | note |
|---|---|---|
| `generation.persons_per_building_m2` | `0.03` | TODO-SOURCE: population proxy (people per m2 of OSM building footprint); replace with Census/ward population |
| `generation.festival_multiplier` | `1.3` | TODO-SOURCE: festival-day uplift |
| `generation.festival_days` | `[1, 40, 100, 150, 200, 260, 300, 320]` | TODO-SOURCE: placeholder simulation-day indices of festival days |
| `segregation.rate` | `0.5` | TODO-SOURCE: share of recyclable material arriving separated at source |
| `recovery.efficiency` | `{'organic': 0.8, 'paper': 0.7, 'plastic': 0.6, 'glass': 0.7, 'metal': 0.8, 'textile': 0.4, 'rubber_leather': 0.3, 'inert_other': 0.0}` | TODO-SOURCE: per-material recovery efficiency |
| `recovery.price_per_kg` | `{'organic': 1.5, 'paper': 8.0, 'plastic': 15.0, 'glass': 2.0, 'metal': 25.0, 'textile': 3.0, 'rubber_leather': 2.0, 'inert_other': 0.0}` | TODO-SOURCE: INR/kg material price |
| `bins.capacity_days_of_mean_generation` | `2.5` | TODO-SOURCE: bin capacity expressed as days of the point's mean daily generation (real bin sizes unknown) |
| `costs.overflow_cost_inr` | `500.0` | TODO-SOURCE: penalty per overflow event |
| `costs.vehicle` | `{'capacity_kg': 3000.0, 'cost_per_km': 25.0, 'fixed_daily': 500.0, 'count': 3}` | TODO-SOURCE: compactor fleet |
| `logistics.facility_detour_factor` | `1.4` | TODO-SOURCE: road/haversine detour for legs outside the study graph |
| `logistics.facility_speed_kph` | `25.0` | TODO-SOURCE: average speed for facility legs |
| `facilities.default_capacity_kg_day` | `{'wet_plant': 3000.0, 'biomethanation': 800.0, 'dwcc': 1500.0, 'landfill': None}` | TODO-SOURCE: kg/day available to the study area at facilities with no capacity in the OpenCity plants CSV (landfill: unbounded); placeholder |
| `facilities.study_area_share` | `0.01` | TODO-SOURCE: share of a plant's listed capacity (OpenCity plants CSV) available to the study area, as the plants serve all of Bengaluru |

Also optional: fill facility capacities for plants/DWCCs not listed in the OpenCity plants CSV (`data/geo/facilities.csv`, column capacity_kg_day).

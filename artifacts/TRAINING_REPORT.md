# Circular Waste DSS - training report

**All bin-level data in this report is SYNTHETIC simulation data** (calibrated on BBMP/CPCB/World Bank figures and Edinburgh real sensor shape). Only the Edinburgh external check uses real sensor data.

Generated 2026-10-20 from metrics files only (git 799e5cb).

## Synthetic history

seeds=6, days=180, collection points=120; ward kg/day: {"hsr_layout": 19248.7, "madiwala": 2946.1}

| seed | rows | mean generated kg/point-day | share of point-days with overflow (baseline 2-day schedule) |
|---|---|---|---|
| 0 | 21600 | 186.04 | 0.117 |
| 1 | 21600 | 186.04 | 0.115 |
| 2 | 21600 | 186.04 | 0.117 |
| 3 | 21600 | 186.04 | 0.117 |
| 4 | 21600 | 186.04 | 0.118 |
| 5 | 21600 | 186.04 | 0.114 |

## Fill-noise calibration (REAL Edinburgh sensor data)

bins=302, intervals=9531, lognormal sigma=0.471, AR(1)=0.1567, weekday multipliers (Mon..Sun)=[1.0072, 0.9697, 0.9822, 0.9348, 0.9792, 1.0396, 1.0873], censored share=0.191

Caveats: collections are fill-triggered (selection bias toward fuller bins); right-censored at 100 %; Edinburgh street litter bins in summer 2016 transferred to Indian community bins by rescaling only; Melbourne Argyle Square dataset no longer published (BLOCKERS.md)

## Forecasting (out-of-time rolling origins on held-out synthetic seeds)

seeds={'train': [0, 1, 2], 'val': [3], 'test': [4, 5]}, origins=[120, 135, 150, 165], target: generated_kg per point-day (one day ahead)

| model | n | MAE | RMSE | MASE |
|---|---|---|---|---|
| naive | 14400 | 89.462 | 162.187 | 1.007 |
| snaive | 14400 | 96.882 | 176.842 | 1.091 |
| ma7 | 14400 | 74.069 | 133.031 | 0.834 |
| lgbm_mean | 14400 | 68.601 | 124.110 | 0.772 |
| lgbm_q0.5 | 14400 | 66.442 | 125.452 | 0.748 |
| chronos2_q0.5 | 14400 | 68.377 | 127.473 | 0.770 |

| quantile model | pinball | coverage of q0.5 | q0.8 | q0.95 |
|---|---|---|---|---|
| lgbm | 20.587 | 0.505 | 0.797 | 0.936 |
| chronos2_zero_shot | 21.149 | 0.507 | 0.799 | 0.944 |

### Overflow risk - event: prev_fill_end_kg + generated_kg > capacity_kg (no visit before the end of the day); test event rate 0.113

| model | Brier raw | Brier recalibrated (isotonic, val-fit) | Brier climatology |
|---|---|---|---|
| lgbm | 0.0598 | 0.0599 | 0.1006 |
| chronos2 | 0.0615 | 0.0613 | 0.1006 |
| naive_indicator | 0.1003 | nan | nan |

### Recovery value: MAE 94.00 INR vs mean true 260.05 INR (n=14400). uses TODO-SOURCE prices/efficiencies from configs/assumptions.yaml; values are placeholders until sourced

### External check on REAL Edinburgh data

Edinburgh litter-bin sensors (aggregated street-level daily volume, OGL v3); streets=38; train days [14, 45], test days [46, 67], n=836

| model | MAE | RMSE | MASE |
|---|---|---|---|
| naive | 586.47 | 1209.61 | 0.930 |
| snaive | 513.38 | 1170.43 | 0.814 |
| ma7 | 404.47 | 857.57 | 0.641 |
| lgbm_mean | 427.31 | 891.03 | 0.677 |
| chronos2_median | 400.78 | 930.57 | 0.635 |

lgbm_quantiles: pinball 120.34, coverage q0.5/q0.8/q0.95 = 0.50/0.78/0.91

chronos2_quantiles: pinball 112.08, coverage q0.5/q0.8/q0.95 = 0.39/0.77/0.94

## Data sources (data/SOURCES.csv)

| name | licence | retrieved |
|---|---|---|
| OpenCity BBMP SWM: BBMP Waste Processing Plants | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| OpenCity BBMP SWM: BBMP: Bangalore Chemical Composition of Municipal Solid Waste | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| OpenCity BBMP SWM: BBMP Segregated Waste Collections April-May 2020 | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| OpenCity BBMP SWM: BBMP Waste Processing Units Map | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| OpenCity BBMP SWM: BBMP Dry Waste Collection Centres Map | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| OpenCity BBMP SWM: BBMP Landfill Locations Map | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| OpenCity BBMP SWM: Bengaluru Bio Methanisation Plants Locations | check per file (OpenCity: maps marked Public Domain) | 2026-10-20 |
| World Bank What a Waste 2.0 (country) | CC BY 4.0 | 2026-10-20 |
| Edinburgh litter-bin sensor data (via aileenmcd/bin_project) | OGL v3.0 | 2026-10-20 |
| Edinburgh street-level daily collected volume (aileenmcd/bin_project cleaned_data) | OGL v3.0 | 2026-10-20 |

Open human tasks (TODO-SOURCE calibration values): see HUMAN_TASKS.md


# Experiment summary

**All results here are from SYNTHETIC simulation data** (virtual bins calibrated on public statistics; no Indian bin-level sensor data exists publicly). Every number below is read from the files in this directory.

Run: 2026-10-21, git 7a60b47; eval days per run: 30; test seeds: [100, 101, 102, 103, 104, 105, 106, 107, 108, 109].

## Policy comparison (test seeds, mean +- std over seeds; `main_table.csv`)

| policy | overflow events | km | operating cost INR | recovered value INR | net cost INR | landfill diversion | facility over-capacity days |
|---|---|---|---|---|---|---|---|
| overflow_only | 69.9 +- 9.2 | 2,930.1 +- 14.1 | 116,651 +- 639 | 871,907 +- 18,668 | -720,306 +- 22,067 | 0.323 +- 0.004 | 27.8 |
| recovery_aware | 56.7 +- 6.0 | 3,129.8 +- 11.8 | 122,695 +- 391 | 880,620 +- 19,317 | -729,575 +- 21,231 | 0.323 +- 0.005 | 29.0 |
| recovery_aware_valsel | 56.8 +- 6.4 | 3,114.9 +- 11.4 | 122,323 +- 391 | 880,695 +- 19,348 | -729,972 +- 21,336 | 0.323 +- 0.004 | 29.0 |
| threshold | 117.0 +- 7.1 | 3,014.6 +- 23.1 | 119,615 +- 673 | 865,375 +- 18,885 | -687,260 +- 19,992 | 0.323 +- 0.004 | 28.2 |
| threshold_pyvrp | 121.6 +- 7.4 | 2,846.8 +- 16.0 | 114,871 +- 555 | 862,920 +- 18,874 | -687,248 +- 20,756 | 0.323 +- 0.004 | 27.7 |
| value_only | 60.4 +- 5.4 | 3,109.0 +- 13.2 | 122,175 +- 433 | 880,467 +- 19,333 | -728,092 +- 20,896 | 0.323 +- 0.004 | 29.0 |

n seeds per policy: 10. Recovered value and landfill diversion depend on TODO-SOURCE prices, efficiencies and facility capacities (HUMAN_TASKS.md).

## Paired comparison over seeds (`main_paired_tests.csv`; Wilcoxon signed-rank)

| a vs b | metric | mean a | mean b | mean diff (a-b) | a lower in share of seeds | p |
|---|---|---|---|---|---|---|
| recovery_aware vs overflow_only | net_cost_inr | -729,575.5 | -720,305.9 | -9,269.6 | 1.00 | 0.0020 |
| recovery_aware vs overflow_only | operating_cost_inr | 122,694.7 | 116,651.3 | 6,043.4 | 0.00 | 0.0020 |
| recovery_aware vs overflow_only | overflow_events | 56.7 | 69.9 | -13.2 | 1.00 | 0.0020 |
| recovery_aware vs overflow_only | km | 3,129.8 | 2,930.1 | 199.7 | 0.00 | 0.0020 |
| recovery_aware vs overflow_only | recovered_value_inr | 880,620.2 | 871,907.2 | 8,713.0 | 0.00 | 0.0020 |
| recovery_aware vs threshold | net_cost_inr | -729,575.5 | -687,260.2 | -42,315.2 | 1.00 | 0.0020 |
| recovery_aware vs threshold | operating_cost_inr | 122,694.7 | 119,614.6 | 3,080.1 | 0.00 | 0.0020 |
| recovery_aware vs threshold | overflow_events | 56.7 | 117.0 | -60.3 | 1.00 | 0.0020 |
| recovery_aware vs threshold | km | 3,129.8 | 3,014.6 | 115.2 | 0.00 | 0.0020 |
| recovery_aware vs threshold | recovered_value_inr | 880,620.2 | 865,374.8 | 15,245.4 | 0.00 | 0.0020 |
| recovery_aware vs threshold_pyvrp | net_cost_inr | -729,575.5 | -687,248.3 | -42,327.1 | 1.00 | 0.0020 |
| recovery_aware vs threshold_pyvrp | operating_cost_inr | 122,694.7 | 114,871.2 | 7,823.5 | 0.00 | 0.0020 |
| recovery_aware vs threshold_pyvrp | overflow_events | 56.7 | 121.6 | -64.9 | 1.00 | 0.0020 |
| recovery_aware vs threshold_pyvrp | km | 3,129.8 | 2,846.8 | 282.9 | 0.00 | 0.0020 |
| recovery_aware vs threshold_pyvrp | recovered_value_inr | 880,620.2 | 862,919.6 | 17,700.6 | 0.00 | 0.0020 |
| overflow_only vs threshold_pyvrp | net_cost_inr | -720,305.9 | -687,248.3 | -33,057.5 | 1.00 | 0.0020 |
| overflow_only vs threshold_pyvrp | operating_cost_inr | 116,651.3 | 114,871.2 | 1,780.1 | 0.00 | 0.0020 |
| overflow_only vs threshold_pyvrp | overflow_events | 69.9 | 121.6 | -51.7 | 1.00 | 0.0020 |
| overflow_only vs threshold_pyvrp | km | 2,930.1 | 2,846.8 | 83.2 | 0.00 | 0.0020 |
| overflow_only vs threshold_pyvrp | recovered_value_inr | 871,907.2 | 862,919.6 | 8,987.6 | 0.00 | 0.0020 |
| value_only vs overflow_only | net_cost_inr | -728,092.2 | -720,305.9 | -7,786.4 | 1.00 | 0.0020 |
| value_only vs overflow_only | operating_cost_inr | 122,175.1 | 116,651.3 | 5,523.8 | 0.00 | 0.0020 |
| value_only vs overflow_only | overflow_events | 60.4 | 69.9 | -9.5 | 0.90 | 0.0039 |
| value_only vs overflow_only | km | 3,109.0 | 2,930.1 | 179.0 | 0.00 | 0.0020 |
| value_only vs overflow_only | recovered_value_inr | 880,467.3 | 871,907.2 | 8,560.1 | 0.00 | 0.0020 |
| recovery_aware_valsel vs overflow_only | net_cost_inr | -729,971.8 | -720,305.9 | -9,666.0 | 1.00 | 0.0020 |
| recovery_aware_valsel vs overflow_only | operating_cost_inr | 122,322.7 | 116,651.3 | 5,671.4 | 0.00 | 0.0020 |
| recovery_aware_valsel vs overflow_only | overflow_events | 56.8 | 69.9 | -13.1 | 1.00 | 0.0020 |
| recovery_aware_valsel vs overflow_only | km | 3,114.9 | 2,930.1 | 184.9 | 0.00 | 0.0020 |
| recovery_aware_valsel vs overflow_only | recovered_value_inr | 880,694.6 | 871,907.2 | 8,787.4 | 0.00 | 0.0020 |

## Alpha-beta ablation (validation seeds only; `ablation_table.csv`, `tradeoff_pareto.png`)

Pareto-optimal (alpha, beta) w.r.t. operating cost, overflow and recovered value: a=0/b=0.5, a=0.5/b=0, a=0.5/b=0.5, a=0.5/b=1, a=1/b=0, a=1/b=0.5, a=1/b=1, a=2/b=0, a=2/b=0.5, a=2/b=1.
Lowest validation net cost among alpha, beta > 0: alpha=1, beta=0.5. The headline `recovery_aware` row uses the configs/policies.yaml weights, fixed before the test seeds were run.

## Sensitivity: recovery_aware minus overflow_only (`sensitivity_paired.csv`)

| scenario | net cost diff INR | overflow events diff | recovered value diff INR | p (net cost) |
|---|---|---|---|---|
| base | -9,270 | -13.2 | 8,713 | 0.0020 |
| price_-30% | -6,981 | -13.2 | 6,120 | 0.0020 |
| price_+30% | -11,835 | -13.2 | 11,337 | 0.0020 |
| forecast_error_x2 | -86,557 | -123.2 | 34,622 | 0.0020 |
| overflow_cost_x0.5 | -23,665 | -44.0 | 23,530 | 0.0020 |
| overflow_cost_x2 | -3,541 | -3.5 | 3,386 | 0.0098 |
| fleet_2_trips_per_day | -15,286 | 24.8 | 32,730 | 0.0020 |
| fleet_4_trips_per_day | -9,567 | -12.9 | 9,025 | 0.0020 |

## Router cross-check (`router_crosscheck.csv`)

20 random instances of 25 points: mean relative objective gap PyVRP vs OR-Tools -0.564% (negative = PyVRP better), max |gap| 5.405%; mean runtime OR-Tools 2.88 s, PyVRP 0.06 s.

## Claim

The contribution is a collection prize combining predicted overflow risk with predicted composition-based recovery value, evaluated against (a) the overflow-only prize policy of the 2024 integrated selection-and-routing paper (arXiv 2409.13386) and (b) a threshold + CVRP baseline, inside a scenario simulator that also tracks recycling, composting and landfill flows under facility capacity limits. No novelty is claimed for prediction, for routing, or for value-aware routing in general.

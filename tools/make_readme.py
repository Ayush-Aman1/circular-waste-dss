"""Fill the results table of README.md from experiments/results/*.csv (numbers come only from files written by code).
    python -m tools.make_readme"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def table() -> str:
    res = Path("experiments/results")
    f = res / "main_table.csv"
    if not f.exists():
        return "_No results yet: run `make experiments`._"
    t = pd.read_csv(f).set_index("policy")
    meta = json.loads((res / "meta.json").read_text())
    p = pd.read_csv(res / "main_paired_tests.csv")
    L = [f"Test seeds {meta['test_seeds'][0]}-{meta['test_seeds'][-1]} ({len(meta['test_seeds'])} paired seeds), {meta['eval_days']} policy-controlled days after {meta['warmup_days']} warm-up days; "
         f"mean ± std over seeds; git `{meta['git_commit']}`, {meta['date']}. **Synthetic simulation data.**", "",
         "| policy | overflow events | km | operating cost (INR) | recovered value (INR) | net cost (INR) | landfill diversion |", "|---|---|---|---|---|---|---|"]
    for name, r in t.iterrows():
        L.append(f"| {name} | {r.overflow_events_mean:.1f} ± {r.overflow_events_std:.1f} | {r.km_mean:.0f} ± {r.km_std:.0f} | {r.operating_cost_inr_mean:,.0f} ± {r.operating_cost_inr_std:,.0f} | "
                 f"{r.recovered_value_inr_mean:,.0f} ± {r.recovered_value_inr_std:,.0f} | {r.net_cost_inr_mean:,.0f} ± {r.net_cost_inr_std:,.0f} | {r.landfill_diversion_rate_mean:.3f} |")
    L += ["", "Paired Wilcoxon signed-rank, `recovery_aware` vs `overflow_only` (`experiments/results/main_paired_tests.csv`):", "", "| metric | mean difference | p |", "|---|---|---|"]
    for r in p[(p.a == "recovery_aware") & (p.b == "overflow_only") & p.metric.isin(["net_cost_inr", "operating_cost_inr", "overflow_events", "recovered_value_inr", "km"])].itertuples():
        L.append(f"| {r.metric} | {r.mean_diff_a_minus_b:,.1f} | {r.wilcoxon_p:.4f} |")
    sf = res / "sensitivity_paired.csv"
    if sf.exists():
        sp = pd.read_csv(sf)
        L += ["", "Sensitivity, `recovery_aware` minus `overflow_only`, mean over the same paired seeds (`experiments/results/sensitivity_paired.csv`; negative = recovery_aware lower):", "",
              "| scenario | net cost (INR) | overflow events | recovered value (INR) | p (net cost) |", "|---|---|---|---|---|"]
        for sc in sp.scenario.unique():
            g = sp[sp.scenario == sc].set_index("metric")
            L.append(f"| {sc} | {g.loc['net_cost_inr', 'mean_diff_a_minus_b']:,.0f} | {g.loc['overflow_events', 'mean_diff_a_minus_b']:,.1f} | "
                     f"{g.loc['recovered_value_inr', 'mean_diff_a_minus_b']:,.0f} | {g.loc['net_cost_inr', 'wilcoxon_p']:.4f} |")
    L += ["", "Prices, efficiencies, fleet and facility capacities are `TODO-SOURCE` placeholders (see [HUMAN_TASKS.md](HUMAN_TASKS.md)); read the differences between policies, not the absolute rupee values. "
          "Full tables, ablation, sensitivity and plots: [experiments/results/summary.md](experiments/results/summary.md)."]
    return "\n".join(L)


def main() -> None:
    f = Path("README.md")
    s = f.read_text()
    a, b = s.index(START) + len(START), s.index(END)
    f.write_text(s[:a] + "\n" + table() + "\n" + s[b:])
    print("README.md results table updated")


if __name__ == "__main__":
    main()

"""P6 experiments. Every output row is SYNTHETIC simulation data (column `synthetic`, JSON field `synthetic`).

    python -m experiments.run_experiments [--stage all|main|ablation|sensitivity|report] [--workers 6] [--smoke]

main         policies {threshold (OR-Tools), threshold_pyvrp, overflow_only, recovery_aware, value_only} x 10 test seeds (paired); mean +- std, paired Wilcoxon tests
ablation     alpha x beta grid on the VALIDATION seeds only (never the test seeds); trade-off and Pareto plots
sensitivity  material price +-30 %, forecast error x2, overflow cost x0.5 / x2, fleet 2 or 4 trips/vehicle/day (binding vs loose fleet): overflow_only vs recovery_aware on the test seeds
report       summary.md that only quotes the CSV/JSON files above
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from circwaste.scenario.levers import Levers
from circwaste.scenario.parallel import lever_dict, run_jobs

OUT = Path("experiments/results")
KEY_METRICS = ["net_cost_inr", "operating_cost_inr", "overflow_events", "overflow_kg", "km", "vehicle_hours", "recovered_value_inr", "recovered_kg",
               "landfill_kg", "landfill_diversion_rate", "facility_over_capacity_days", "recovered_kg_recycling", "recovered_kg_composting_biomethanation"]
MAIN_POLICIES = [("threshold", "threshold", None), ("threshold_pyvrp", "threshold", "pyvrp"), ("overflow_only", "overflow_only", None),
                 ("recovery_aware", "recovery_aware", None), ("value_only", "value_only", None)]


def progress(tag: str):
    def cb(i: int, n: int, r: dict) -> None:
        print(f"[{tag}] {i}/{n} {r['job'].get('label') or r['job']['policy']} seed={r['job']['seed']} {r['runtime_s']:.0f}s", flush=True)
    return cb


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def collect(results: list[dict], extra: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs = pd.DataFrame([{**r["summary"], **(extra or {}), **{k: v for k, v in r["job"].get("tags", {}).items()}} for r in results])
    days = pd.DataFrame([{**d, **r["job"].get("tags", {})} for r in results for d in r["days"]])
    return runs, days


def mean_std(runs: pd.DataFrame, by: list[str], metrics: list[str]) -> pd.DataFrame:
    g = runs.groupby(by)[metrics]
    out = g.mean().add_suffix("_mean").join(g.std(ddof=1).add_suffix("_std")).join(g.size().rename("n_seeds")).reset_index()
    out["synthetic"] = True
    return out


def paired(runs: pd.DataFrame, a: str, b: str, metrics: list[str], by_col: str = "policy", extra: dict | None = None) -> list[dict]:
    """Paired comparison of policy a vs b over seeds: mean difference (a - b), win share, Wilcoxon signed-rank p."""
    from scipy.stats import wilcoxon

    pa, pb = runs[runs[by_col] == a].set_index("seed"), runs[runs[by_col] == b].set_index("seed")
    seeds = sorted(set(pa.index) & set(pb.index))
    rows = []
    for m in metrics:
        x, y = pa.loc[seeds, m].to_numpy(float), pb.loc[seeds, m].to_numpy(float)
        d = x - y
        try:
            p = float(wilcoxon(x, y).pvalue) if np.any(d != 0) else 1.0
        except ValueError:
            p = float("nan")
        rows.append({**(extra or {}), "a": a, "b": b, "metric": m, "n_seeds": len(seeds), "mean_a": float(x.mean()), "mean_b": float(y.mean()), "mean_diff_a_minus_b": float(d.mean()),
                     "std_diff": float(d.std(ddof=1)) if len(d) > 1 else 0.0, "a_lower_share": float((d < 0).mean()), "wilcoxon_p": p, "synthetic": True})
    return rows


def pareto_mask(df: pd.DataFrame, minimise: list[str], maximise: list[str]) -> np.ndarray:
    """True for non-dominated rows (lower is better for `minimise`, higher for `maximise`)."""
    X = np.column_stack([df[c].to_numpy(float) for c in minimise] + [-df[c].to_numpy(float) for c in maximise])
    keep = np.ones(len(X), bool)
    for i in range(len(X)):
        dom = np.all(X <= X[i], axis=1) & np.any(X < X[i], axis=1)
        keep[i] = not dom.any()
    return keep


# ---------------------------------------------------------------------------------------------------------------- stages
def stage_main(lc: dict, workers: int, seeds: list[int]) -> None:
    jobs = [{"policy": base, "label": lab, "backend": be, "seed": s, "levers": lever_dict(Levers(policy=base)), "tags": {"scenario": "base"}}
            for lab, base, be in MAIN_POLICIES for s in seeds]
    jobs += [j for j in extra_main_jobs(seeds)]
    res = run_jobs(jobs, workers, progress("main"))
    runs, days = collect(res)
    runs.to_csv(OUT / "main_runs.csv", index=False)
    days.to_csv(OUT / "main_days.csv.gz", index=False)
    tab = mean_std(runs, ["policy"], KEY_METRICS)
    tab.to_csv(OUT / "main_table.csv", index=False)
    rows = []
    for a, b in [("recovery_aware", "overflow_only"), ("recovery_aware", "threshold"), ("recovery_aware", "threshold_pyvrp"), ("overflow_only", "threshold_pyvrp"),
                 ("value_only", "overflow_only")]:
        rows += paired(runs, a, b, KEY_METRICS)
    for extra in {j["label"] for j in jobs} - {m[0] for m in MAIN_POLICIES}:
        rows += paired(runs, extra, "overflow_only", KEY_METRICS)
    pd.DataFrame(rows).to_csv(OUT / "main_paired_tests.csv", index=False)


def extra_main_jobs(seeds: list[int]) -> list[dict]:
    """recovery_aware with the alpha/beta chosen on the validation seeds (written by the ablation stage), if it differs from the config default."""
    f = OUT / "ablation_selected.json"
    if not f.exists():
        return []
    sel = json.loads(f.read_text())
    if (sel["alpha"], sel["beta"]) == (1.0, 1.0):
        return []
    return [{"policy": "recovery_aware", "label": "recovery_aware_valsel", "backend": None, "seed": s, "tags": {"scenario": "base"},
             "levers": lever_dict(Levers(policy="recovery_aware", alpha=sel["alpha"], beta=sel["beta"]))} for s in seeds]


def stage_ablation(lc: dict, workers: int, seeds: list[int]) -> None:
    alphas, betas = [0.0, 0.5, 1.0, 2.0], [0.0, 0.5, 1.0, 2.0]
    grid = [(a, b) for a in alphas for b in betas if a + b > 0]
    jobs = [{"policy": "recovery_aware", "label": f"a{a}_b{b}", "seed": s, "levers": lever_dict(Levers(policy="recovery_aware", alpha=a, beta=b)),
             "tags": {"alpha": a, "beta": b}} for a, b in grid for s in seeds]
    res = run_jobs(jobs, workers, progress("ablation"))
    runs, _ = collect(res)
    runs.to_csv(OUT / "ablation_runs.csv", index=False)
    tab = mean_std(runs, ["alpha", "beta"], KEY_METRICS)
    tab["pareto_cost_value_overflow"] = pareto_mask(tab, ["operating_cost_inr_mean", "overflow_events_mean"], ["recovered_value_inr_mean"])
    tab.to_csv(OUT / "ablation_table.csv", index=False)
    both = tab[(tab.alpha > 0) & (tab.beta > 0)].sort_values("net_cost_inr_mean")
    best = both.iloc[0]
    (OUT / "ablation_selected.json").write_text(json.dumps({
        "synthetic": True, "alpha": float(best.alpha), "beta": float(best.beta), "criterion": "lowest mean net_cost_inr over the validation seeds among alpha>0, beta>0",
        "validation_seeds": seeds, "net_cost_inr_mean": float(best.net_cost_inr_mean)}, indent=1))
    plot_ablation(tab)


def plot_ablation(tab: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    sc = ax[0].scatter(tab.operating_cost_inr_mean, tab.recovered_value_inr_mean, c=tab.overflow_events_mean, s=60, cmap="viridis_r")
    for r in tab.itertuples():
        ax[0].annotate(f"a{r.alpha:g}/b{r.beta:g}", (r.operating_cost_inr_mean, r.recovered_value_inr_mean), fontsize=6, xytext=(3, 3), textcoords="offset points")
    fig.colorbar(sc, ax=ax[0], label="overflow events (mean)")
    ax[0].set_xlabel("operating cost, INR"); ax[0].set_ylabel("recovered value, INR"); ax[0].set_title("Cost vs recovered value vs overflow (validation seeds)", fontsize=9)
    p = tab[tab.pareto_cost_value_overflow].sort_values("operating_cost_inr_mean")
    ax[1].scatter(tab.overflow_events_mean, tab.recovered_value_inr_mean, c="lightgrey", s=40, label="all (alpha, beta)")
    ax[1].scatter(p.overflow_events_mean, p.recovered_value_inr_mean, c="C3", s=60, label="Pareto-optimal (cost, overflow, value)")
    ax[1].set_xlabel("overflow events (mean)"); ax[1].set_ylabel("recovered value, INR"); ax[1].legend(fontsize=7)
    ax[1].set_title("Pareto front", fontsize=9)
    fig.text(0.5, 0.005, "Synthetic simulation data", ha="center", fontsize=7, color="grey")
    fig.tight_layout(); fig.savefig(OUT / "tradeoff_pareto.png", dpi=130); plt.close(fig)


def stage_sensitivity(lc: dict, workers: int, seeds: list[int]) -> None:
    scen = {"base": Levers(), "price_-30%": Levers(price_pct=-30), "price_+30%": Levers(price_pct=30), "forecast_error_x2": Levers(forecast_noise=2.0),
            "overflow_cost_x0.5": Levers(overflow_cost_pct=-50), "overflow_cost_x2": Levers(overflow_cost_pct=100),
            "fleet_2_trips_per_day": Levers(trips_per_vehicle=2), "fleet_4_trips_per_day": Levers(trips_per_vehicle=4)}
    jobs = []
    for name, lv in scen.items():
        for pol in ("overflow_only", "recovery_aware"):
            for s in seeds:
                d = lever_dict(lv)
                d["policy"] = pol
                jobs.append({"policy": pol, "seed": s, "levers": d, "tags": {"scenario": name}})
    res = run_jobs(jobs, workers, progress("sensitivity"))
    runs, _ = collect(res)
    runs.to_csv(OUT / "sensitivity_runs.csv", index=False)
    rows = []
    for name in scen:
        rows += paired(runs[runs.scenario == name], "recovery_aware", "overflow_only", KEY_METRICS, extra={"scenario": name})
    pd.DataFrame(rows).to_csv(OUT / "sensitivity_paired.csv", index=False)
    mean_std(runs, ["scenario", "policy"], KEY_METRICS).to_csv(OUT / "sensitivity_table.csv", index=False)


def plots_main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = pd.read_csv(OUT / "main_table.csv").set_index("policy")
    order = [p for p in ["threshold", "threshold_pyvrp", "overflow_only", "recovery_aware", "value_only"] if p in t.index] + [p for p in t.index if p.endswith("valsel")]
    fig, ax = plt.subplots(1, 4, figsize=(14, 3.6))
    for a, m, ttl in zip(ax, ["overflow_events", "operating_cost_inr", "recovered_value_inr", "landfill_diversion_rate"],
                         ["Overflow events", "Operating cost (INR)", "Recovered value (INR)", "Landfill diversion rate"]):
        a.bar(range(len(order)), t.loc[order, f"{m}_mean"], yerr=t.loc[order, f"{m}_std"], capsize=3, color=[f"C{i}" for i in range(len(order))])
        a.set_xticks(range(len(order))); a.set_xticklabels(order, rotation=40, ha="right", fontsize=7); a.set_title(ttl, fontsize=9)
    fig.text(0.5, 0.005, "Synthetic simulation data; bars = mean +- std over test seeds", ha="center", fontsize=7, color="grey")
    fig.tight_layout(); fig.savefig(OUT / "policy_comparison.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    rec = t.loc[order, ["recovered_kg_recycling_mean", "recovered_kg_composting_biomethanation_mean"]]
    rec.plot.bar(stacked=True, ax=ax, color=["C2", "C1"])
    ax.set_ylabel("recovered kg (sum over eval days)"); ax.set_title("Recovered mass by stream (synthetic)", fontsize=9); ax.tick_params(axis="x", rotation=40, labelsize=7)
    fig.tight_layout(); fig.savefig(OUT / "recovered_by_stream.png", dpi=130); plt.close(fig)


def fmt(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}"


def stage_report(lc: dict) -> None:
    """summary.md: numbers are read from the CSV/JSON files only."""
    L = ["# Experiment summary", "", "**All results here are from SYNTHETIC simulation data** (virtual bins calibrated on public statistics; no Indian bin-level sensor data exists publicly). "
         "Every number below is read from the files in this directory.", ""]
    meta = json.loads((OUT / "meta.json").read_text()) if (OUT / "meta.json").exists() else {}
    L += [f"Run: {meta.get('date', '?')}, git {meta.get('git_commit', '?')}; eval days per run: {lc['eval_days']}; test seeds: {lc['seeds']['test']}.", ""]
    if (OUT / "main_table.csv").exists():
        t = pd.read_csv(OUT / "main_table.csv").set_index("policy")
        L += ["## Policy comparison (test seeds, mean +- std over seeds; `main_table.csv`)", "",
              "| policy | overflow events | km | operating cost INR | recovered value INR | net cost INR | landfill diversion | facility over-capacity days |", "|---|---|---|---|---|---|---|---|"]
        for p, r in t.iterrows():
            L.append(f"| {p} | {fmt(r.overflow_events_mean)} +- {fmt(r.overflow_events_std)} | {fmt(r.km_mean)} +- {fmt(r.km_std)} | {fmt(r.operating_cost_inr_mean, 0)} +- {fmt(r.operating_cost_inr_std, 0)} | "
                     f"{fmt(r.recovered_value_inr_mean, 0)} +- {fmt(r.recovered_value_inr_std, 0)} | {fmt(r.net_cost_inr_mean, 0)} +- {fmt(r.net_cost_inr_std, 0)} | "
                     f"{r.landfill_diversion_rate_mean:.3f} +- {r.landfill_diversion_rate_std:.3f} | {fmt(r.facility_over_capacity_days_mean)} |")
        L += ["", f"n seeds per policy: {int(t.n_seeds.iloc[0])}. Recovered value and landfill diversion depend on TODO-SOURCE prices, efficiencies and facility capacities (HUMAN_TASKS.md).", ""]
    if (OUT / "main_paired_tests.csv").exists():
        pt = pd.read_csv(OUT / "main_paired_tests.csv")
        L += ["## Paired comparison over seeds (`main_paired_tests.csv`; Wilcoxon signed-rank)", "",
              "| a vs b | metric | mean a | mean b | mean diff (a-b) | a lower in share of seeds | p |", "|---|---|---|---|---|---|---|"]
        for r in pt[pt.metric.isin(["net_cost_inr", "overflow_events", "recovered_value_inr", "operating_cost_inr", "km"])].itertuples():
            L.append(f"| {r.a} vs {r.b} | {r.metric} | {fmt(r.mean_a, 1)} | {fmt(r.mean_b, 1)} | {fmt(r.mean_diff_a_minus_b, 1)} | {r.a_lower_share:.2f} | {r.wilcoxon_p:.4f} |")
        L.append("")
    if (OUT / "ablation_table.csv").exists():
        a = pd.read_csv(OUT / "ablation_table.csv")
        sel = json.loads((OUT / "ablation_selected.json").read_text())
        L += ["## Alpha-beta ablation (validation seeds only; `ablation_table.csv`, `tradeoff_pareto.png`)", "",
              f"Pareto-optimal (alpha, beta) w.r.t. operating cost, overflow and recovered value: {', '.join(f'a={r.alpha:g}/b={r.beta:g}' for r in a[a.pareto_cost_value_overflow].itertuples())}.",
              f"Lowest validation net cost among alpha, beta > 0: alpha={sel['alpha']:g}, beta={sel['beta']:g}. The headline `recovery_aware` row uses the configs/policies.yaml weights, fixed before the test seeds were run.", ""]
    if (OUT / "sensitivity_paired.csv").exists():
        s = pd.read_csv(OUT / "sensitivity_paired.csv")
        L += ["## Sensitivity: recovery_aware minus overflow_only (`sensitivity_paired.csv`)", "", "| scenario | net cost diff INR | overflow events diff | recovered value diff INR | p (net cost) |", "|---|---|---|---|---|"]
        for sc in s.scenario.unique():
            g = s[s.scenario == sc].set_index("metric")
            L.append(f"| {sc} | {fmt(g.loc['net_cost_inr', 'mean_diff_a_minus_b'], 0)} | {fmt(g.loc['overflow_events', 'mean_diff_a_minus_b'])} | "
                     f"{fmt(g.loc['recovered_value_inr', 'mean_diff_a_minus_b'], 0)} | {g.loc['net_cost_inr', 'wilcoxon_p']:.4f} |")
        L.append("")
    if (OUT / "router_crosscheck.json").exists():
        c = json.loads((OUT / "router_crosscheck.json").read_text())
        L += ["## Router cross-check (`router_crosscheck.csv`)", "", f"{c['instances']} random instances of {c['points_per_instance']} points: mean relative objective gap PyVRP vs OR-Tools "
              f"{c['mean_rel_gap_pyvrp_vs_ortools']:+.3%} (negative = PyVRP better), max |gap| {c['max_abs_rel_gap']:.3%}; mean runtime OR-Tools {c['mean_ortools_s']:.2f} s, PyVRP {c['mean_pyvrp_s']:.2f} s.", ""]
    L += ["## Claim", "", "The contribution is a collection prize combining predicted overflow risk with predicted composition-based recovery value, evaluated against (a) the overflow-only prize policy of the 2024 "
          "integrated selection-and-routing paper (arXiv 2409.13386) and (b) a threshold + CVRP baseline, inside a scenario simulator that also tracks recycling, composting and landfill flows under "
          "facility capacity limits. No novelty is claimed for prediction, for routing, or for value-aware routing in general.", ""]
    (OUT / "summary.md").write_text("\n".join(L))
    print("wrote", OUT / "summary.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "main", "ablation", "sensitivity", "report"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--smoke", action="store_true", help="2 seeds, 4 eval days, tiny grid; writes to experiments/results_smoke")
    a = ap.parse_args()
    global OUT
    lc = yaml.safe_load(open("configs/loop.yaml"))
    test, val_ = lc["seeds"]["test"], lc["seeds"]["validation"]
    if a.smoke:
        OUT = Path("experiments/results_smoke")
        lc["eval_days"] = 4
        test, val_ = test[:2], val_[:2]
    OUT.mkdir(parents=True, exist_ok=True)
    if a.smoke:
        (OUT / "loop_smoke.yaml").write_text(yaml.safe_dump(lc))
        os.environ["CIRCWASTE_LOOP_CONFIG"] = str(OUT / "loop_smoke.yaml")     # worker processes inherit this
    stages = ["ablation", "main", "sensitivity", "report"] if a.stage == "all" else [a.stage]    # ablation first: main may add the validation-selected row
    (OUT / "meta.json").write_text(json.dumps({"synthetic": True, "date": str(date.today()), "git_commit": git_commit(), "stages": stages, "test_seeds": test,
                                                "validation_seeds": val_, "eval_days": lc["eval_days"], "warmup_days": lc["warmup_days"], "argv": sys.argv}, indent=1))
    for s in stages:
        if s == "main":
            stage_main(lc, a.workers, test); plots_main()
        elif s == "ablation":
            stage_ablation(lc, a.workers, val_)
        elif s == "sensitivity":
            stage_sensitivity(lc, a.workers, test)
        else:
            stage_report(lc)
    print("experiments done:", stages)


if __name__ == "__main__":
    main()

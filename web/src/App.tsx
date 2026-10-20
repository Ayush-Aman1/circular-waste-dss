import { useEffect, useState } from "react";
import { BASE_LEVERS, Base, Levers, Scenario, getBase, getExperiments, runScenario } from "./api";
import { FlowChart, KpiCards, LeverPanel, MapView, POLICY_LABEL, TradeoffChart, fmt } from "./components";

type Tab = "plan" | "compare" | "results";

export default function App() {
  const [base, setBase] = useState<Base>();
  const [tab, setTab] = useState<Tab>("plan");
  const [levers, setLevers] = useState<Levers>(BASE_LEVERS);
  const [cur, setCur] = useState<Scenario>();
  const [A, setA] = useState<Scenario>();
  const [B, setB] = useState<Scenario>();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState<string>();
  const [exp, setExp] = useState<any>();

  useEffect(() => { getBase().then(setBase).catch((e) => setErr(String(e))); getExperiments().then(setExp).catch(() => undefined); }, []);
  const run = async (lv: Levers = levers) => {
    setBusy(true); setErr(undefined); setProgress(0);
    try { const s = await runScenario(lv, (p) => setProgress(p)); setCur(s); return s; }
    catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };
  useEffect(() => { if (base && !cur) void run(BASE_LEVERS); }, [base]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Side-by-side: run the same levers under two policies (overflow-only vs recovery-aware). */
  const comparePolicies = async () => {
    const a = await run({ ...levers, policy: "overflow_only" }); if (a) setA(a);
    const b = await run({ ...levers, policy: "recovery_aware" }); if (b) setB(b);
    setTab("compare");
  };

  return (
    <>
      <div className="notice">Synthetic simulation data — bin-level data is simulated from public statistics; it is not sensor data from Bengaluru bins.</div>
      <header>
        <h1>Circular Waste DSS · Bengaluru (HSR Layout &amp; Madiwala)</h1>
        <nav>
          <button className={tab === "plan" ? "on" : ""} onClick={() => setTab("plan")}>Map &amp; plan</button>
          <button className={tab === "compare" ? "on" : ""} onClick={() => setTab("compare")}>Compare scenarios</button>
          <button className={tab === "results" ? "on" : ""} onClick={() => setTab("results")}>Policy results</button>
        </nav>
      </header>
      <main>
        {err && <div className="card bad" style={{ marginBottom: 8 }}>{err}</div>}
        {!base ? <div className="card">Loading… (is the API running on :8000?)</div> : (
          <>
            {tab !== "results" && (
              <div className="grid2">
                <div>
                  <LeverPanel base={base} levers={levers} setLevers={setLevers} onRun={() => void run()} busy={busy} progress={progress} last={cur && { cached: cur.cached }} />
                  <div className="card" style={{ marginTop: 12 }}>
                    <h3>Compare</h3>
                    <button className="ghost" disabled={!cur} onClick={() => setA(cur)}>Pin current as A</button>
                    <button className="ghost" disabled={!cur} onClick={() => setB(cur)}>Pin current as B</button>
                    <button className="run" disabled={busy} onClick={() => void comparePolicies()}>Overflow-only vs recovery-aware (these levers)</button>
                  </div>
                </div>
                <div>
                  {tab === "plan" && (<>
                    <h3 style={{ margin: "0 0 6px" }}>{cur ? POLICY_LABEL[cur.levers.policy] : "Scenario"}</h3>
                    <KpiCards s={cur} />
                    <MapView base={base} scenario={cur} />
                  </>)}
                  {tab === "compare" && (<>
                    <div className="grid2b">
                      <div><h3>A · {A ? POLICY_LABEL[A.levers.policy] : "pin a scenario"}</h3><KpiCards s={A} /></div>
                      <div><h3>B · {B ? POLICY_LABEL[B.levers.policy] : "pin a scenario"}</h3><KpiCards s={B} against={A} /></div>
                    </div>
                    <div className="grid2b"><FlowChart s={A} title="A" /><FlowChart s={B} title="B" /></div>
                    {A && B && <Diff A={A} B={B} />}
                  </>)}
                </div>
              </div>
            )}
            {tab === "results" && <Results exp={exp} />}
          </>
        )}
      </main>
      <footer>
        {base?.attribution ?? "© OpenStreetMap contributors"} · Contribution: a collection prize combining predicted overflow risk with predicted composition-based recovery value, evaluated against the overflow-only prize
        policy of the 2024 integrated selection-and-routing paper (arXiv 2409.13386) and a threshold + CVRP baseline, inside a scenario simulator that also tracks recycling, composting and landfill flows under facility capacity limits.
      </footer>
    </>
  );
}

function Diff({ A, B }: { A: Scenario; B: Scenario }) {
  const rows: [string, (m: Record<string, number>) => number, number][] = [
    ["Net cost INR", (m) => m.net_cost_inr, 0], ["Operating cost INR", (m) => m.operating_cost_inr, 0], ["Overflow events", (m) => m.overflow_events, 1],
    ["Recovered value INR", (m) => m.recovered_value_inr, 0], ["Recovered kg", (m) => m.recovered_kg, 0], ["Landfill kg", (m) => m.landfill_kg, 0], ["Distance km", (m) => m.km, 0],
    ["Facility over-capacity days", (m) => m.facility_over_capacity_days, 1],
  ];
  return (
    <div className="card"><h3>A vs B (mean ± std over {A.seeds.length} seeds, {A.eval_days} days each; synthetic)</h3>
      <table><thead><tr><th>metric</th><th>A</th><th>B</th><th>B − A</th></tr></thead><tbody>
        {rows.map(([n, f, d]) => <tr key={n}><td>{n}</td><td>{fmt(f(A.summary.mean), d)} ± {fmt(f(A.summary.std), d)}</td><td>{fmt(f(B.summary.mean), d)} ± {fmt(f(B.summary.std), d)}</td><td>{fmt(f(B.summary.mean) - f(A.summary.mean), d)}</td></tr>)}
      </tbody></table></div>
  );
}

function Results({ exp }: { exp: any }) {
  if (!exp?.main) return <div className="card">No experiment results yet — run <code>make experiments</code>.</div>;
  return (
    <div>
      <div className="card"><h3>Policy comparison on {exp.meta?.test_seeds?.length ?? "?"} paired test seeds (mean ± std; synthetic)</h3>
        <table><thead><tr><th>policy</th><th>overflow events</th><th>km</th><th>operating cost</th><th>recovered value</th><th>net cost</th><th>landfill diversion</th></tr></thead><tbody>
          {exp.main.map((r: any) => <tr key={r.policy}><td>{r.policy}</td><td>{fmt(r.overflow_events_mean, 1)} ± {fmt(r.overflow_events_std, 1)}</td><td>{fmt(r.km_mean)} ± {fmt(r.km_std)}</td>
            <td>{fmt(r.operating_cost_inr_mean)} ± {fmt(r.operating_cost_inr_std)}</td><td>{fmt(r.recovered_value_inr_mean)} ± {fmt(r.recovered_value_inr_std)}</td>
            <td>{fmt(r.net_cost_inr_mean)} ± {fmt(r.net_cost_inr_std)}</td><td>{(r.landfill_diversion_rate_mean).toFixed(3)}</td></tr>)}
        </tbody></table>
        <div className="legend">Prices, efficiencies, fleet and facility capacities are TODO-SOURCE placeholders (see HUMAN_TASKS.md): read differences between policies, not absolute rupees.</div>
      </div>
      <div className="grid2b" style={{ marginTop: 12 }}>
        {exp.ablation && <TradeoffChart rows={exp.ablation} />}
        <div className="card"><h3>Paired tests, recovery_aware vs overflow_only (Wilcoxon)</h3>
          <table><thead><tr><th>metric</th><th>mean diff</th><th>p</th></tr></thead><tbody>
            {exp.paired?.filter((r: any) => r.a === "recovery_aware" && r.b === "overflow_only" && ["net_cost_inr", "operating_cost_inr", "overflow_events", "recovered_value_inr", "km"].includes(r.metric))
              .map((r: any) => <tr key={r.metric}><td>{r.metric}</td><td>{fmt(r.mean_diff_a_minus_b, 1)}</td><td>{r.wilcoxon_p.toFixed(4)}</td></tr>)}
          </tbody></table>
        </div>
      </div>
      <div className="grid2b" style={{ marginTop: 12 }}>
        {exp.plots?.includes("policy_comparison.png") && <div className="card"><img style={{ width: "100%" }} src="/api/experiments/plots/policy_comparison.png" alt="policy comparison" /></div>}
        {exp.plots?.includes("tradeoff_pareto.png") && <div className="card"><img style={{ width: "100%" }} src="/api/experiments/plots/tradeoff_pareto.png" alt="trade-off and Pareto front" /></div>}
      </div>
    </div>
  );
}

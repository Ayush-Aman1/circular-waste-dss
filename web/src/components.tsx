import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { BASE_LEVERS, Base, Day, Kpis, Levers, Scenario, getDay } from "./api";

export const fmt = (x: number | undefined, d = 0) => (x === undefined || Number.isNaN(x) ? "–" : x.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));

export const POLICY_LABEL: Record<string, string> = {
  threshold: "Threshold + CVRP (Tier A)", overflow_only: "Overflow-only prize (2024 paper style)", recovery_aware: "Recovery-aware prize (this project)", value_only: "Value-only prize",
};

// ------------------------------------------------------------------------------------------------ lever panel
function Slider(p: { label: string; value: number; min: number; max: number; step: number; unit?: string; onChange: (v: number) => void; fmtv?: (v: number) => string }) {
  return (
    <>
      <label className="s">{p.label}: <b>{p.fmtv ? p.fmtv(p.value) : p.value}{p.unit ?? ""}</b></label>
      <input type="range" min={p.min} max={p.max} step={p.step} value={p.value} onChange={(e) => p.onChange(Number(e.target.value))} />
    </>
  );
}

export function LeverPanel(p: { base: Base; levers: Levers; setLevers: (l: Levers) => void; onRun: () => void; busy: boolean; progress: number; last?: { cached: boolean } }) {
  const { base, levers: l, setLevers } = p;
  const d = base.defaults, f = base.fleet;
  const set = (patch: Partial<Levers>) => setLevers({ ...l, ...patch });
  const cap = Object.values(l.capacity_pct)[0] ?? 0;
  return (
    <div className="card">
      <h3>What-if levers</h3>
      <label className="s">Policy</label>
      <select value={l.policy} onChange={(e) => set({ policy: e.target.value as Levers["policy"] })}>
        {Object.entries(POLICY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <Slider label="Waste generation per person" value={l.generation_pct} min={-20} max={20} step={10} unit="%" onChange={(v) => set({ generation_pct: v })} fmtv={(v) => (v > 0 ? `+${v}` : `${v}`)} />
      <Slider label="Segregation at source" value={l.segregation_rate ?? d.segregation_rate} min={0.3} max={0.9} step={0.2}
        onChange={(v) => set({ segregation_rate: v === d.segregation_rate ? null : v })} fmtv={(v) => `${Math.round(v * 100)}%`} />
      <Slider label="Vehicles out of service" value={l.vehicles_unavailable} min={0} max={2} step={1} onChange={(v) => set({ vehicles_unavailable: v })} fmtv={(v) => `${v} of ${f.count}`} />
      <Slider label="Collection frequency (trips / vehicle / day)" value={l.trips_per_vehicle ?? f.trips_per_vehicle_per_day} min={2} max={4} step={1}
        onChange={(v) => set({ trips_per_vehicle: v === f.trips_per_vehicle_per_day ? null : v })} />
      <Slider label="Facility capacity (plants + DWCC)" value={cap} min={-50} max={200} step={50} unit="%"
        onChange={(v) => set({ capacity_pct: v === 0 ? {} : { wet_plant: v, biomethanation: v, dwcc: v } })} fmtv={(v) => (v > 0 ? `+${v}` : `${v}`)} />
      <Slider label="Material prices" value={l.price_pct} min={-30} max={30} step={30} unit="%" onChange={(v) => set({ price_pct: v })} fmtv={(v) => (v > 0 ? `+${v}` : `${v}`)} />
      <Slider label="Festival surge (multiplier)" value={l.festival_multiplier ?? d.festival_multiplier} min={d.festival_multiplier} max={2} step={0.7}
        onChange={(v) => set({ festival_multiplier: v === d.festival_multiplier ? null : v })} fmtv={(v) => `×${v.toFixed(1)}`} />
      <button className="run" disabled={p.busy} onClick={p.onRun}>{p.busy ? `Running… ${Math.round(p.progress * 100)}%` : "Run scenario"}</button>
      {p.busy && <div className="bar"><i style={{ width: `${p.progress * 100}%` }} /></div>}
      {p.last && <div className="legend"><span className={`badge ${p.last.cached ? "ok" : ""}`}>{p.last.cached ? "precomputed" : "computed just now"}</span></div>}
      <div className="legend">Stops are the precomputed grid; other values run a background job (about a minute).</div>
      <button className="ghost" style={{ marginTop: 8 }} onClick={() => setLevers({ ...BASE_LEVERS, policy: l.policy })}>Reset levers</button>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ KPI cards
const KPI_DEFS: { k: string; label: string; lowerIsBetter: boolean; f: (m: Kpis) => number; d: number }[] = [
  { k: "net", label: "Net cost, INR", lowerIsBetter: true, f: (m) => m.net_cost_inr, d: 0 },
  { k: "op", label: "Operating cost, INR", lowerIsBetter: true, f: (m) => m.operating_cost_inr, d: 0 },
  { k: "of", label: "Overflow events", lowerIsBetter: true, f: (m) => m.overflow_events, d: 1 },
  { k: "rv", label: "Recovered value, INR", lowerIsBetter: false, f: (m) => m.recovered_value_inr, d: 0 },
  { k: "lf", label: "Landfill share of collected", lowerIsBetter: true, f: (m) => 100 * (m.landfill_kg / Math.max(m.collected_kg, 1e-9)), d: 1 },
  { k: "km", label: "Distance, km", lowerIsBetter: true, f: (m) => m.km, d: 0 },
];

export function KpiCards({ s, against }: { s?: Scenario; against?: Scenario }) {
  if (!s) return <div className="legend">Run a scenario to see KPIs.</div>;
  return (
    <div className="kpis">
      {KPI_DEFS.map((k) => {
        const v = k.f(s.summary.mean), r = against ? k.f(against.summary.mean) : undefined;
        const dv = r === undefined ? undefined : v - r;
        const good = dv === undefined ? undefined : k.lowerIsBetter ? dv < 0 : dv > 0;
        return (
          <div className="kpi" key={k.k}>
            <div className="l">{k.label}</div>
            <div className="v">{fmt(v, k.d)}{k.k === "lf" ? "%" : ""}</div>
            {dv !== undefined && Math.abs(dv) > 1e-9 && <div className={`d ${good ? "good" : "bad"}`}>{dv > 0 ? "+" : ""}{fmt(dv, k.d)} vs {"A"}</div>}
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ flow chart
export function FlowChart({ s, title }: { s?: Scenario; title: string }) {
  const data = useMemo(() => {
    if (!s) return [];
    const x = s.series;
    return x.day.map((day, i) => ({
      day,
      composting: x.rec_organic_kg[i],
      recycling: ["paper", "plastic", "glass", "metal", "textile", "rubber_leather"].reduce((a, m) => a + x[`rec_${m}_kg`][i], 0),
      landfill: x.landfill_kg[i],
      overflow: x.overflow_kg[i],
    }));
  }, [s]);
  return (
    <div className="card">
      <h3>{title}: daily material flow (kg, mean over seeds)</h3>
      <div style={{ height: 230 }}>
        <ResponsiveContainer>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="day" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend />
            <Area isAnimationActive={false} type="monotone" dataKey="composting" stackId="1" name="composting / biomethanation" stroke="#d97706" fill="#f59e0b" />
            <Area isAnimationActive={false} type="monotone" dataKey="recycling" stackId="1" name="recycling" stroke="#15803d" fill="#22c55e" />
            <Area isAnimationActive={false} type="monotone" dataKey="landfill" stackId="1" name="landfill" stroke="#475467" fill="#98a2b3" />
            <Area isAnimationActive={false} type="monotone" dataKey="overflow" stackId="1" name="overflowed (uncollected)" stroke="#b42318" fill="#f97066" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ trade-off scatter
export function TradeoffChart({ rows }: { rows: any[] }) {
  const data = rows.map((r) => ({ x: r.operating_cost_inr_mean, y: r.recovered_value_inr_mean, z: r.overflow_events_mean, name: `α=${r.alpha}, β=${r.beta}`, pareto: r.pareto_cost_value_overflow }));
  return (
    <div className="card">
      <h3>Cost vs recovered value vs overflow (α, β ablation, validation seeds)</h3>
      <div style={{ height: 300 }}>
        <ResponsiveContainer>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis type="number" dataKey="x" name="operating cost" unit=" INR" fontSize={11} domain={["auto", "auto"]} />
            <YAxis type="number" dataKey="y" name="recovered value" unit=" INR" fontSize={11} domain={["auto", "auto"]} />
            <ZAxis type="number" dataKey="z" range={[40, 260]} name="overflow events" />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} />
            <Legend />
            <Scatter isAnimationActive={false} name="dominated" data={data.filter((d) => !d.pareto)} fill="#98a2b3" />
            <Scatter isAnimationActive={false} name="Pareto-optimal" data={data.filter((d) => d.pareto)} fill="#0f766e" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="legend">Bubble size = overflow events. Synthetic simulation data.</div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ map
import L from "leaflet";
import { CircleMarker, GeoJSON as GeoJSONLayer, MapContainer, Polyline, Popup, TileLayer, Tooltip as MapTip, useMap } from "react-leaflet";

const KIND_COLOR: Record<string, string> = { dwcc: "#2563eb", wet_plant: "#d97706", biomethanation: "#7c3aed", landfill: "#475467" };
const TRIP_COLORS = ["#e11d48", "#2563eb", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#ca8a04", "#be185d", "#4f46e5", "#0d9488"];

function riskColor(r: number) { // green -> amber -> red
  const t = Math.max(0, Math.min(1, r));
  return `hsl(${120 - 120 * t}, 75%, 42%)`;
}
function valueColor(v: number, max: number) { // light -> deep teal
  const t = Math.max(0, Math.min(1, v / Math.max(max, 1)));
  return `hsl(172, 70%, ${88 - 55 * t}%)`;
}

function Fit({ b }: { b: Base }) {
  const map = useMap();
  useEffect(() => { map.fitBounds(L.geoJSON(b.wards as any).getBounds().pad(0.05)); }, [b, map]);
  return null;
}

export function MapView({ base, scenario }: { base: Base; scenario?: Scenario }) {
  const [day, setDay] = useState(0);
  const [data, setData] = useState<Day | undefined>();
  const [colorBy, setColorBy] = useState<"risk" | "value">("risk");
  const [err, setErr] = useState<string | undefined>();
  useEffect(() => { setDay(0); }, [scenario?.key]);
  useEffect(() => {
    if (!scenario) { setData(undefined); return; }
    getDay(scenario.key, day).then((d) => { setData(d); setErr(undefined); }).catch((e) => setErr(String(e)));
  }, [scenario?.key, day]);
  const maxV = useMemo(() => Math.max(1, ...(data?.bins.map((b) => b.recovery_value_inr) ?? [1])), [data]);
  const maxFill = useMemo(() => Math.max(1, ...(data?.bins.map((b) => b.capacity_kg) ?? [1])), [data]);
  return (
    <div>
      <div className="mapbox">
        <MapContainer center={[base.depot.lat, base.depot.lon]} zoom={14} style={{ height: "100%" }} scrollWheelZoom>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Fit b={base} />
          <GeoJSONLayer data={base.wards as any} style={{ color: "#0f766e", weight: 2, fillOpacity: 0.04, dashArray: "4" }} />
          {data?.routes.features.map((f, i) => (
            <Polyline key={`${data.day}-${i}`} positions={(f.geometry as any).coordinates.map((c: number[]) => [c[1], c[0]])}
              pathOptions={{ color: TRIP_COLORS[i % TRIP_COLORS.length], weight: 4, opacity: 0.85 }}>
              <MapTip sticky>{f.properties!.vehicle}: {f.properties!.stops} stops, {(f.properties!.distance_km as number).toFixed(1)} km, {(f.properties!.load_kg as number).toFixed(0)} kg</MapTip>
            </Polyline>
          ))}
          {(data?.bins ?? base.points.map((p) => ({ ...p, overflow_risk: 0, recovery_value_inr: 0, capacity_kg: 1, fill_kg: 0, visited: false, dropped_with_prize: false, overflowed: false, prize_inr: 0, fill_end_kg: 0, ward: "" } as any))).map((b: any) => {
            const col = colorBy === "risk" ? riskColor(b.overflow_risk) : valueColor(b.recovery_value_inr, maxV);
            const hollow = !b.visited;                       // not collected today: hollow ring
            return (
              <CircleMarker key={b.id} center={[b.lat, b.lon]} radius={4 + 9 * Math.sqrt(Math.min(1, b.capacity_kg / maxFill) * Math.min(1, (b.fill_kg || 0) / Math.max(b.capacity_kg, 1)))}
                pathOptions={{ color: b.overflowed ? "#b42318" : "#1d2430", weight: b.overflowed ? 3 : 1, fillColor: col, fillOpacity: hollow ? 0.15 : 0.9, dashArray: b.dropped_with_prize ? "2 3" : undefined }}>
                <Popup>
                  <b>{b.id}</b> (synthetic)<br />fill {fmt(b.fill_kg)} / {fmt(b.capacity_kg)} kg<br />overflow risk {(b.overflow_risk * 100).toFixed(0)}%<br />
                  recovery value {fmt(b.recovery_value_inr)} INR<br />prize {fmt(b.prize_inr)} INR<br />{b.visited ? "collected today" : b.dropped_with_prize ? "skipped despite prize" : "not collected"}{b.overflowed ? " · overflowed" : ""}
                </Popup>
              </CircleMarker>
            );
          })}
          {base.facilities.map((f) => (
            <CircleMarker key={f.id} center={[f.lat, f.lon]} radius={7} pathOptions={{ color: "#fff", weight: 2, fillColor: KIND_COLOR[f.kind], fillOpacity: 1 }}>
              <MapTip>{f.kind}: {f.name} · {f.capacity_kg_day === null ? "unbounded" : `${fmt(f.capacity_kg_day)} kg/day (study-area share)`} · {f.dist_km.toFixed(1)} km from depot</MapTip>
            </CircleMarker>
          ))}
          <CircleMarker center={[base.depot.lat, base.depot.lon]} radius={9} pathOptions={{ color: "#000", weight: 3, fillColor: "#fde047", fillOpacity: 1 }}><MapTip>depot</MapTip></CircleMarker>
        </MapContainer>
      </div>
      <div className="legend">
        <span>Colour by:
          <select style={{ width: "auto", marginLeft: 6 }} value={colorBy} onChange={(e) => setColorBy(e.target.value as any)}>
            <option value="risk">overflow risk</option><option value="value">recovery value</option>
          </select></span>
        <span><span className="dot" style={{ background: "hsl(120,75%,42%)" }} />low</span><span><span className="dot" style={{ background: "hsl(0,75%,42%)" }} />high risk</span>
        <span>filled = collected · hollow = not collected · dashed = skipped though it had a prize · red ring = overflowed · size = fill level</span>
      </div>
      <div className="legend">
        {Object.entries(KIND_COLOR).map(([k, c]) => <span key={k}><span className="dot" style={{ background: c }} />{k}</span>)}
        <span><span className="dot" style={{ background: "#fde047", border: "1px solid #000" }} />depot</span>
      </div>
      {scenario && (
        <div style={{ marginTop: 8 }}>
          <label className="s">Simulated day <b>{day + 1} / {data?.n_days ?? scenario.eval_days}</b> (seed {data?.seed ?? scenario.seeds[0]}; routes are per vehicle trip)</label>
          <input type="range" min={0} max={(data?.n_days ?? scenario.eval_days) - 1} step={1} value={day} onChange={(e) => setDay(Number(e.target.value))} />
          {err && <div className="bad">{err}</div>}
          {data && <div className="legend">Collected {data.routes.features.reduce((a, f) => a + (f.properties!.stops as number), 0)} bins on {data.routes.features.length} trips · landfill {fmt(data.flows.landfill_kg)} kg · {data.flows.over_capacity ? "a facility was at capacity today" : "facilities within capacity"}</div>}
        </div>
      )}
    </div>
  );
}

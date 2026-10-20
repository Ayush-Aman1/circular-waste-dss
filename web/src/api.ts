// Thin client for the FastAPI backend (proxied at /api by Vite).
export type Levers = {
  policy: "threshold" | "overflow_only" | "recovery_aware" | "value_only";
  generation_pct: number;
  segregation_rate: number | null;
  vehicles_unavailable: number;
  trips_per_vehicle: number | null;
  capacity_pct: Record<string, number>;
  price_pct: number;
  festival_multiplier: number | null;
  alpha: number | null;
  beta: number | null;
};

export const BASE_LEVERS: Levers = {
  policy: "recovery_aware", generation_pct: 0, segregation_rate: null, vehicles_unavailable: 0, trips_per_vehicle: null,
  capacity_pct: {}, price_pct: 0, festival_multiplier: null, alpha: null, beta: null,
};

export type Kpis = Record<string, number>;
export type Scenario = {
  key: string; cached: boolean; levers: Levers; eval_days: number; seeds: number[];
  summary: { mean: Kpis; std: Kpis };
  series: Record<string, number[]>;
};
export type Job = { id: string; status: "queued" | "running" | "done" | "failed"; progress: number; cached: boolean; error?: string; result?: Scenario };

export type BinState = {
  id: string; lat: number; lon: number; ward: string; fill_kg: number; fill_end_kg: number; capacity_kg: number; overflow_risk: number;
  recovery_value_inr: number; prize_inr: number; visited: boolean; dropped_with_prize: boolean; overflowed: boolean;
};
export type Day = {
  day: number; n_days: number; seed: number; routes: GeoJSON.FeatureCollection; bins: BinState[];
  flows: { recovered_kg: Record<string, number>; landfill_kg: number; spilled_kg: number; over_capacity: boolean };
};
export type Base = {
  wards: GeoJSON.FeatureCollection; depot: { lat: number; lon: number };
  points: { id: string; lat: number; lon: number }[];
  facilities: { id: string; kind: string; name: string; lat: number; lon: number; capacity_kg_day: number | null; dist_km: number }[];
  fleet: { count: number; trips_per_vehicle_per_day: number; capacity_kg: number };
  defaults: { segregation_rate: number; festival_multiplier: number; overflow_cost_inr: number };
  attribution: string; notice: string;
};

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch("/api" + url, init);
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const getBase = () => j<Base>("/base");
export const getDay = (key: string, day: number) => j<Day>(`/day/${key}/${day}`);
export const getExperiments = () => j<any>("/experiments");
export const getCached = () => j<{ scenarios: { key: string; levers: Levers; kpis: Kpis }[] }>("/cached");
export const postScenario = (levers: Levers) => j<Job>("/scenario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ levers }) });
export const getJob = (id: string) => j<Job>(`/scenario/${id}`);

/** Start a scenario and resolve when done; `onProgress` gets 0..1 and whether the answer is precomputed. */
export async function runScenario(levers: Levers, onProgress: (p: number, cached: boolean) => void): Promise<Scenario> {
  let job = await postScenario(levers);
  onProgress(job.progress, job.cached);
  while (job.status === "queued" || job.status === "running") {
    await new Promise((r) => setTimeout(r, 1000));
    job = await getJob(job.id);
    onProgress(job.progress, job.cached);
  }
  if (job.status === "failed" || !job.result) throw new Error(job.error ?? "scenario failed");
  return { ...job.result, cached: job.cached };
}

# Circular Waste DSS Fallback Baseline: Build Guide

Oct 18, 2026 · @Ayush Aman

## Purpose and strategy

The fallback is predict, then prize-collecting routing, then a material-flow simulation, then a what-if dashboard, built from mature solvers and forecasting libraries. Dozens of student repos already do predict-then-CVRP; none found model recovery value or downstream flows, so that is where your own work concentrates.

| Tier | What it is | Covers | Risk |
|----|----|----|----|
| A | Fill forecast, a fixed threshold (e.g. collect if predicted fill tomorrow is 80% or more), OR-Tools CVRP on road distances | The baseline every comparison is made against | Near zero |
| B | Recovery-aware prize-collecting VRP: every bin is optional with a prize combining overflow risk and recovery value; run day by day inside a virtual-bin simulator with facility capacities | Your core contribution and its evaluation | Low |
| C | What-if decision-support dashboard: scenario sliders, policy comparison over several seeds, cost vs recovery vs overflow trade-off view | The DSS contribution | Low to medium |

The trick that keeps Tier B small: OR-Tools (skip penalties on optional nodes) and PyVRP (prize=..., required=False) both solve prize-collecting VRPs natively. Recovery-aware priority is therefore just a prize formula, not a new solver.

### Novelty check

Your framing is right not to claim prediction or routing; it also needs to avoid claiming value-aware routing in general, because parts of it exist.

| Prior work | What it already does | What it leaves open |
|----|----|----|
| [BIN-CT](https://arxiv.org/pdf/1807.01603) (Ferrer & Alba) | Predicts container fill levels and routes on the predictions | Fill only; no composition or value |
| [Integrated selection and routing policy](https://arxiv.org/pdf/2409.13386) (2024) | Prizes from the probability a cluster overflows before the next plan, solved as a prize-collecting VRP inside a simulation | Your closest baseline: overflow-risk prizes, no recovery term |
| [Smart waste collection routing problem](https://www.sciencedirect.com/science/article/abs/pii/S0957417418301404) (Ramos et al., Valorsul) | Selects which recyclable bins to visit by fill level and location | Single-stream recyclables, no forecasting of composition |
| [Dynamic multi-compartment VRP](https://www.researchgate.net/publication/368558512_Dynamic_Multi-Compartment_Vehicle_Routing_Problem_for_Smart_Waste_Collection) | Maximises recyclables collected, prioritising the fullest containers, with historical fill estimates | Fullness, not material value or downstream capacity |
| Student repos (see Pick list) | Forecast, priority score, OR-Tools CVRP, dashboard | Everything circular |

Defensible claim: a collection prize that combines predicted overflow risk with predicted composition-based recovery value, evaluated against the overflow-only prize of the 2024 paper, inside a scenario simulator that also tracks recycling, composting and landfill flows under facility capacity limits.

**Pretrained models checked.** No trained bin-fill or routing model is worth reusing: fill models are tied to the bins they learned from, the student repos train on synthetic data, and routing is solved rather than learned. The one model you can use directly is Chronos-2, a zero-shot forecasting model (Apache-2.0, runs on CPU) that outputs quantiles with no training; it is added to P3 as a forecaster alongside LightGBM.

## Architecture

The system is a day-by-day simulation loop with two swappable parts: the prize policy and the router backend. Every baseline and ablation is a policy name in a config file.

<img src="media/image1.png" style="width:6in;height:4.85714in" alt="fallback architecture, daily simulation loop" />

fallback architecture, daily simulation loop

The what-if engine never touches the loop's code; it only edits assumptions, fleet and policy settings, then reruns the loop on the same seeds. That is what makes scenario comparisons fair.

### Folder layout

circwaste/\
AGENTS.md CREDITS.md\
circwaste/\
geo/ wards.py, facilities.py, matrix.py\
sim/ placement.py, calibrate.py, generator.py\
forecast/ features.py, models.py\
priority/ threshold.py, overflow_only.py, recovery_aware.py, value_only.py\
route/ ortools_router.py, pyvrp_router.py\
flow/ facilities_flow.py\
scenario/ loop.py, whatif.py\
metrics/\
api/ main.py\
configs/ assumptions.yaml, policies.yaml, scenarios/\*.yaml\
data/raw/ data/cache/ runs/ experiments/\
web/ Vite + React + TS + react-leaflet + recharts\
tests/ docs/ third_party/

## Data sources

Use Bengaluru as the case city: OpenCity already publishes BBMP's waste composition, processing-plant and dry-waste-centre locations, which gives the recovery side real facilities to route to. Bin-level fill dynamics come from foreign sensor datasets and drive a calibrated virtual-bin simulator.

| Layer | Source | What you take | Licence |
|----|----|----|----|
| City facilities and composition | [OpenCity: BBMP Solid Waste Management Data](https://data.opencity.in/dataset/bbmp-solid-waste-management-data) | Waste processing plants, chemical composition of MSW, segregated collections April-May 2020, dry waste collection centre, landfill and biomethanisation plant locations | Maps marked Public Domain; check each file |
| City scale | [BBMP SWM overview](https://site.bbmp.gov.in/documents/Overview.pdf) | City generation of about 3,000 to 3,500 tonnes a day, 185 dry waste collection centres | Cite as source |
| National statistics | CPCB annual SWM reports, data.gov.in | State and city generation, segregation and processing shares | Government open data; cite |
| Composition benchmarks | World Bank What a Waste 2.0 | Composition by category for India and comparable cities | CC BY 4.0 |
| Real bin fill dynamics | [Edinburgh litter-bin sensors](https://github.com/aileenmcd/bin_project) | 323 sensor bins, June-August 2016 | Open Government Licence v3 |
| Real bin fill dynamics | [Melbourne Argyle Square smart bins](https://discover.data.vic.gov.au/dataset/smart-bins-argyle-square/resource/07837d22-e224-40a1-a212-b8dcbcb45e98) | Fill-level readings with timestamps and bin size | Open (check terms) |
| Roads and buildings | OpenStreetMap via OSMnx | Drivable road graph, travel times, building footprints, any mapped waste or recycling points | ODbL |

### The virtual-bin simulator

No Indian bin-level sensor data is public, so the simulator creates it, and the paper says so plainly.

1.  **Placement.** Put collection points on the road graph of one to three wards: mapped waste points where OSM has them, otherwise spaced along streets and weighted by building density.

2.  **Generation.** Each point's daily mass = ward population share × per-capita generation, scaled so the ward total matches the BBMP and CPCB figures, with weekday and festival multipliers.

3.  **Composition.** Draw each point's material shares around the BBMP composition, with per-point variation so some points are recyclable-rich.

4.  **Fill noise.** Fit the shape of daily fill increments and their variance on the Edinburgh and Melbourne series, then rescale to Indian volumes.

5.  **Recovery value.** Recoverable mass = material mass × segregation rate × recovery efficiency; value = recoverable mass × price per kg.

Every parameter lives in configs/assumptions.yaml with a source or the word assumed. The what-if sliders edit exactly these numbers.

## Download checklist

Nothing here needs a GPU; the whole system runs on a Mac laptop. The only heavy step is building a road travel-time matrix, which is cached once per ward set.

### Software

- [ ] Miniconda with a Python 3.11 environment named circwaste

- [ ] pip install ortools pyvrp osmnx networkx geopandas shapely pandas numpy scikit-learn lightgbm pydantic pyyaml joblib matplotlib pytest

- [ ] pip install fastapi uvicorn (backend)

- [ ] Node.js 20 LTS, then a Vite React + TypeScript app with leaflet, react-leaflet and recharts

- [ ] Optional: Docker Desktop, only if OSMnx travel-time matrices get too slow and you switch to a local OSRM server

### Pretrained model

- [ ] pip install "chronos-forecasting\>=2.0", then pre-cache the Chronos-2 weights once so the demo works offline

### Data files (into data/raw/, never edited by hand)

- [ ] OpenCity BBMP SWM files: composition, processing plants, dry waste collection centres, landfills, biomethanisation plants, segregated collections April-May 2020

- [ ] BBMP SWM overview PDF (city totals)

- [ ] Latest CPCB annual SWM report PDF and the matching data.gov.in tables

- [ ] World Bank What a Waste 2.0 city and country CSVs

- [ ] Edinburgh litter-bin sensor CSVs (from the Edinburgh open data portal linked in the bin_project README)

- [ ] Melbourne Argyle Square smart-bin CSV

- [ ] OSM roads and buildings: pulled automatically by OSMnx in P1, cached as GraphML

### Repos and papers (into third_party/ and docs/refs/)

- [ ] Gnanakamalesh-M/smart-waste-iot-routing: the most careful reference repo (simulated bins, sensor noise, OSMnx roads, OR-Tools, honest evaluation notes)

- [ ] coolbandariya/smart_waste_project: priority scoring plus OR-Tools CVRP plus map dashboard, i.e. your Tier A shape

- [ ] PyVRP's optional-clients tutorial and OR-Tools' "penalties and dropping visits" VRP example

- [ ] Papers: the 2024 integrated selection and routing policy (arXiv 2409.13386), BIN-CT (arXiv 1807.01603), Ramos et al. smart waste collection routing, and the waste collection routing survey

Freeze versions with pip freeze \> requirements.lock and commit package-lock.json after installing.

## Pick list

Solvers and libraries are dependencies; the student repos and papers supply baselines and ideas. The prize formula, simulator, material-flow model and scenario engine are written fresh, since that is your contribution.

| Source | Take | Ignore | Feeds module |
|----|----|----|----|
| OR-Tools routing | Capacity dimension, AddDisjunction skip penalties (your prizes), guided local search with a time limit, per-vehicle availability | CP-SAT, pickup-and-delivery | Router (primary) |
| PyVRP | Model.add_client(..., prize=..., required=False), multiple trips, MaxRuntime stop | Its benchmark tooling | Router (cross-check solver) |
| OSMnx | Drive network for chosen wards, edge speeds and travel times, nearest_nodes, building footprints and mapped waste points | Walking and cycling networks | Geo, virtual bins |
| LightGBM / scikit-learn | Per-point next-day increment forecasting with lag and calendar features; quantile models for overflow probability | Deep sequence models (optional comparison only) | Forecaster |
| smart-waste-iot-routing | Sensor noise and fault model, cost model (fuel, CO2, labour, fixed), its "synthetic data, say so" evaluation discipline | IoT firmware, ThingSpeak, Streamlit | Simulator, metrics |
| smart_waste_project | Membership-curve priority score as the Tier A baseline | Streamlit UI | Baselines |
| arXiv 2409.13386 | Overflow-probability prize, prize-collecting VRP inside a rolling simulation | Their time windows and driver breaks (add later if wanted) | Baseline B0 |
| OpenCity BBMP data | Facility locations as route destinations: dry waste to DWCCs, wet waste to processing and biomethanisation plants, rejects to landfill; composition table | Budget and work-order files | Geo, material flow |
| react-leaflet, recharts | Route and bin map layers; scenario comparison charts | Map tile styling beyond OSM default | Dashboard |
| Chronos-2 | Zero-shot quantile forecasts per collection point from its recent history; no training | Fine-tuning (not needed for a baseline) | Forecaster |

The recovery-aware prize, written into configs/policies.yaml so every term can be switched off for ablation:

\text{prize}\_i = \alpha \\, P(\text{overflow}\_i \mid \text{skip}) \cdot C\_{\text{overflow}} + \beta \sum_m \hat{w}\_{i,m} \\, s \\, \eta_m \\, p_m \\, \kappa_m

Here ŵ is the forecast mass of material m at point i, s the segregation rate, η the recovery efficiency, p the price per kg, and κ the remaining capacity share of the facility that accepts m. Setting β to 0 gives the 2024 paper's overflow-only policy; setting α to 0 gives a value-only policy.

## Build order and gates

The Tier A baseline runs end to end by week 6, recovery-aware results exist by week 8, and the what-if dashboard is demo-ready by week 11. Your idea note gave no schedule, so these weeks are a proposal.

<img src="media/image2.png" style="width:6in;height:3.8125in" alt="proposed 12-week build schedule, 3 gates" />

proposed 12-week build schedule, 3 gates

Gate criteria: Tier A end to end means one simulated week runs from forecast to routes on the real road graph with the threshold policy. Tier B results means all four policies have compared metrics over 10 seeds. Full demo means every demo-flow box in the checklist is ticked. If week 8 slips, a threshold-vs-overflow-only comparison with the dashboard is still a complete, honest project.

## Running the coding agent

Save the master prompt as AGENTS.md (or CLAUDE.md for Claude Code) in the repo root, put your project description at docs/idea.md, then paste one module prompt per session.

1.  Create the repo, add AGENTS.md and docs/idea.md, download the data files into data/raw/.

2.  Paste the next module prompt and let it run to its report.

3.  Check three things: tests pass, the demo command works, git diff stays inside the module's folders. Commit.

4.  If it fails twice on the same thing, paste the matching row from Troubleshooting.

One step needs a human: someone fills the sources for each number in configs/assumptions.yaml (P1 stops and asks).

### Master context prompt (AGENTS.md)

You are building the FALLBACK BASELINE of "AI-Based Circular Waste Management\
Decision Support System" (docs/idea.md). Goal: a working, honest system even\
if the team's custom work is unfinished. Reuse solvers and libraries; credit\
them.\
\
ARCHITECTURE (do not change without asking):\
\- Python 3.11 package \`circwaste/\`: geo/, sim/, forecast/, priority/,\
route/, flow/, scenario/, metrics/, api/. Dashboard in web/ (Vite + React\
\+ TS + react-leaflet + recharts).\
\- One simulated day = forecast -\> prize per point -\> route -\> collect -\>\
material flow to facilities -\> update bins and facility stocks.\
\- Router interface: solve(points, prizes, demands, vehicles, matrix,\
time_limit) -\> routes, dropped. Backends: ortools (default), pyvrp.\
\- Policy interface: prizes(state, forecast) -\> dict. Policies: threshold\
(Tier A), overflow_only (2024 paper style), recovery_aware (ours),\
value_only. Selected by name in configs/policies.yaml.\
\- Every number that is not data lives in configs/assumptions.yaml with a\
\`source:\` field (citation or the word "assumed").\
\- Scenarios are YAML overrides of assumptions + fleet; the same seed set\
is used for every policy.\
\
NON-NEGOTIABLE RESEARCH RULES:\
1\. Never invent results. Numbers in reports come from files the code wrote.\
2\. Bin-level data is simulated; every output and the UI say so.\
3\. Policies are compared on identical seeds and scenarios; report mean and\
spread over at least 10 seeds.\
4\. Forecasts are evaluated out of time (train on earlier days, test on\
later), never with random splits.\
5\. Do not hand-tune the recovery-aware policy on the test seeds.\
\
ENGINEERING RULES:\
6\. Work only in the folders the task names. Never refactor others.\
7\. Read the INSTALLED version's docs or source for ortools, pyvrp and\
osmnx before using their APIs.\
8\. Seed everything; runs write to runs/\<name\>/\<timestamp\>/ with config,\
metrics.json and per-day CSVs.\
9\. Integer-scale costs and demands for OR-Tools (it needs integers).\
10\. Each module ships pytest tests and a one-line demo command.\
11\. Code adapted from third_party/ gets a comment with URL and licence, plus\
a line in CREDITS.md.\
12\. End each task with a report: files changed, tests and results, demo\
command, known issues. Then stop.

## Module prompts

Paste these one per session, in order. Each assumes AGENTS.md is in place and earlier modules are committed.

### P0. Scaffold and contracts

Task P0: repo skeleton and shared contracts.\
\- Package circwaste/ with geo/, sim/, forecast/, priority/, route/, flow/,\
scenario/, metrics/, api/; plus configs/, data/raw/, data/cache/, runs/,\
experiments/, tests/, web/, third_party/ (gitignored), docs/.\
\- Pydantic models: Point (id, lat, lon, node, capacity_kg, ward),\
Facility (id, kind: dwcc\|wet_plant\|biomethanation\|landfill, accepts,\
capacity_kg_day), Vehicle (id, capacity_kg, cost_per_km, available),\
DayState (fill_kg per material per point, facility stocks, day).\
\- Router and Policy interfaces exactly as AGENTS.md says.\
\- configs/assumptions.yaml skeleton: per-capita generation, composition\
shares, segregation rate, recovery efficiency and price per material,\
facility capacities, overflow cost, vehicle costs, each with source: TODO.\
\- configs/policies.yaml with alpha, beta, threshold values.\
Tests: config validation fails on a missing source field.

### P1. Geography and facilities

Task P1: circwaste/geo/.\
\- wards.py: load 1-3 chosen wards (config) as polygons; get the OSMnx drive\
network with speeds and travel times; cache GraphML in data/cache/.\
\- facilities.py: parse the OpenCity BBMP files in data/raw/ (DWCC, waste\
processing plants, biomethanisation plants, landfills) into Facility rows;\
keep those within a configurable radius of the wards; snap to graph nodes.\
\- matrix.py: travel-time and distance matrices between depot, points and\
facilities via shortest paths; cache to parquet keyed by a hash of\
inputs.\
\- STOP and print a checklist asking the team to fill every source: field in\
configs/assumptions.yaml from the BBMP overview, CPCB report, What a\
Waste and OpenCity composition file.\
Demo: a static HTML map (folium) of ward roads, facilities and depot.

### P2. Virtual-bin simulator

Task P2: circwaste/sim/.\
\- placement.py: collection points from mapped OSM waste points, else spaced\
along streets weighted by nearby building area; N configurable.\
\- calibrate.py: from the Edinburgh and Melbourne CSVs in data/raw/, fit the\
distribution of daily fill increments relative to each bin's mean\
(dispersion, weekday pattern, autocorrelation). Save fitted params and\
plots to docs/calibration/.\
\- generator.py: daily mass per point = ward total from assumptions x point\
weight x weekday/festival multiplier x calibrated noise; split into\
materials by composition drawn per point around the BBMP shares.\
\- Overflow = fill above capacity; overflowed mass is recorded, not lost.\
\- 180 simulated days per seed; deterministic per seed.\
Tests: ward totals over 30 days match assumptions within 3%; same seed gives\
identical output.

### P3. Forecaster

Task P3: circwaste/forecast/.\
\- Features per point-day: lags 1-7 of increments, rolling means, weekday,\
festival flag, point static features. Train on days 1-120, test 121-180.\
\- Models: naive (yesterday), seasonal naive (same weekday), LightGBM point\
forecast, LightGBM quantiles (0.5, 0.8, 0.95), and Chronos-2 zero-shot\
quantiles (chronos-forecasting\>=2.0, no training; read the installed\
package README for the current API and model id).\
\- overflow_prob(point, horizon): from quantiles, P(fill + increments \>\
capacity) if skipped for the horizon.\
\- Composition forecast: rolling mean shares per point (simple and honest).\
\- Report MAE, RMSE, quantile coverage, Brier score for overflow per model.\
Also report the same metrics on the real Edinburgh data as an external\
check of the method.

### P4. Router

Task P4: circwaste/route/.\
\- ortools_router.py: CVRP with capacity dimension; every point optional via\
AddDisjunction with penalty = integer-scaled prize; vehicles with\
available=false excluded; guided local search; time limit from config.\
Trucks unload at the correct facility type at route end (multiple trips\
allowed if the installed OR-Tools version supports it simply; otherwise\
one trip per vehicle per day, documented).\
\- pyvrp_router.py: same instance with prize and required=False.\
\- Cross-check script: both solvers on 20 random instances, report objective\
gap and runtime.\
Tests: a point with a huge prize is always visited; a zero-prize far point\
is dropped; capacity is never exceeded.

### P5. Policies, daily loop and material flow

Task P5: circwaste/priority/, circwaste/flow/, circwaste/scenario/loop.py.\
\- Policies: threshold (collect if forecast fill \>= x%, prize = big),\
overflow_only (beta=0), recovery_aware (formula in docs/idea.md and\
configs/policies.yaml), value_only (alpha=0).\
\- flow/: collected mass by material -\> facility by type; recovered = mass x\
segregation x efficiency, limited by facility daily capacity; excess and\
rejects go to landfill. Track recycling, composting/biomethanation,\
landfill tonnes and revenue.\
\- loop.py: run N days for a policy, scenario and seed; write per-day CSVs.\
Tests: mass balance closes every day (generated = in bins + collected +\
overflow); facility capacity never exceeded.

### P6. Experiments

Task P6: experiments/.\
\- Compare all four policies over 10+ seeds, test days only: total cost, km,\
overflow events and kg, recovered kg and value, landfill kg, recovery rate.\
\- Ablation of alpha and beta on a grid; plot the cost vs recovered value vs\
overflow trade-off and the Pareto front.\
\- Sensitivity: price per kg +/-30%, forecast noise doubled.\
\- Statistical comparison of recovery_aware vs overflow_only with paired\
seeds (Wilcoxon signed-rank).\
Write CSVs and plots to experiments/results/ plus a summary.md that only\
quotes those files.

### P7. What-if scenario engine

Task P7: circwaste/scenario/whatif.py.\
\- Levers: generation change (%), segregation rate, vehicles unavailable,\
facility capacity change per type, material price change, policy choice,\
alpha/beta.\
\- run_scenario(levers, seeds) -\> summary metrics + per-day series + one\
representative day's routes. Cache results by lever hash.\
\- Precompute a grid of common scenarios so the demo responds instantly;\
run uncached scenarios in a background worker with progress.\
Tests: zero-change levers reproduce the base run exactly.

### P8. Backend

Task P8: circwaste/api/ with FastAPI.\
\- GET /base (wards, points, facilities, depot), GET /policies,\
POST /scenario (levers) -\> job id, GET /scenario/{id} -\> status/result,\
GET /day/{scenario}/{day} -\> routes as GeoJSON polylines along roads,\
bin states, flows.\
\- Tests with TestClient.

### P9. Dashboard

Task P9: web/ with Vite + React + TS + react-leaflet + recharts.\
\- Map: points coloured by overflow risk, sized by recovery value; routes per\
vehicle; facilities by type; dropped points shown hollow.\
\- Scenario panel: sliders for each lever, policy selector, run button.\
\- Comparison view: two scenarios side by side, KPI cards (cost, overflow,\
recovered value, landfill share) and stacked flow chart per day.\
\- A permanent note: bin-level data is simulated from public statistics.

## Demo and testing checklist

The fallback is ready when every box is ticked on a laptop with Wi-Fi off. Run the list at the Tier B gate and again before submission.

Research integrity

- [ ] Every value in assumptions.yaml has a citation or is marked assumed

- [ ] Simulator ward totals match the cited figures within 3%

- [ ] Forecasts evaluated out of time, against naive and seasonal-naive baselines

- [ ] All policies run on identical seeds and scenarios; 10+ seeds

- [ ] Every number in the report traces to a file in runs/ or experiments/results/

- [ ] The paper and UI both state that bin-level data is simulated

Models and results

- [ ] Router tests pass on both OR-Tools and PyVRP; cross-check gap reported

- [ ] Mass balance closes every simulated day

- [ ] Policy comparison table: threshold, overflow-only, recovery-aware, value-only

- [ ] Alpha-beta trade-off plot and paired statistical test vs overflow-only

- [ ] Sensitivity results for prices and forecast error

Demo flow

- [ ] uvicorn circwaste.api.main:app and npm run dev start with cached graph and matrices, no internet

- [ ] Base day: map shows risk-coloured points, routes and facilities

- [ ] Slider: generation +20% shows more overflow or cost in under 5 seconds (precomputed)

- [ ] Slider: segregation 50% to 70% shows recovered value and landfill change

- [ ] Remove one vehicle: dropped points and overflow change visibly

- [ ] Raise facility capacity: landfill share falls

- [ ] Side-by-side comparison of overflow-only vs recovery-aware

- [ ] A screen recording of the demo exists as backup

## Credits and licences

The code stack is all permissive; the obligations are on the data side. Every map needs "© OpenStreetMap contributors", and World Bank and Edinburgh data need attribution in the report.

| Source | Used for | Licence | Note |
|----|----|----|----|
| OR-Tools | Primary router | Apache-2.0 |  |
| [PyVRP](https://pyvrp.org/notebooks/optional_clients.html) | Cross-check router | MIT |  |
| OSMnx | Road graph | MIT |  |
| OpenStreetMap data | Roads, buildings, waste points | ODbL | Attribution on every map |
| LightGBM, scikit-learn | Forecasting | MIT, BSD-3-Clause |  |
| FastAPI, recharts | Backend, charts | MIT |  |
| Leaflet, react-leaflet | Map | BSD-2-Clause; check react-leaflet's current licence |  |
| [OpenCity BBMP SWM data](https://data.opencity.in/dataset/bbmp-solid-waste-management-data) | Facilities, composition | Maps marked Public Domain; others check |  |
| World Bank What a Waste 2.0 | Composition benchmarks | CC BY 4.0 | Attribute |
| Edinburgh litter-bin sensor data | Fill-dynamics calibration | Open Government Licence v3 | Attribute |
| Melbourne smart-bin data | Fill-dynamics calibration | Open (check terms) |  |
| [smart-waste-iot-routing](https://github.com/Gnanakamalesh-M/smart-waste-iot-routing), [smart_waste_project](https://github.com/coolbandariya/smart_waste_project) | Ideas, Tier A baseline shape | Check each repo | Reference only unless licensed |
| [arXiv 2409.13386](https://arxiv.org/pdf/2409.13386), [BIN-CT](https://arxiv.org/pdf/1807.01603), Ramos et al. | Baselines, framing | Papers | Cite |
| Chronos-2 (amazon-science/chronos-forecasting) | Zero-shot forecaster | Apache-2.0 | Cite the Chronos-2 paper |

Credit format for CREDITS.md and code headers: Adapted from \<URL\> (\<licence\>), \<what was taken\>.

## Troubleshooting

The usual failures are prize scaling in the solver, slow matrices, and a simulator that quietly makes the proposed policy win. Paste the "tell the agent" text as-is.

| Symptom | Likely cause | Tell the agent |
|----|----|----|
| Solver visits every point or none | Prizes on a different scale from travel costs | "Print prize and arc-cost ranges; express both in rupees per day and integer-scale them by the same factor." |
| OR-Tools returns no solution | Infeasible capacity or too short a time limit | "Make every point optional, log the status code, raise the time limit, and check total demand against fleet capacity." |
| Matrix building takes very long | Shortest paths computed one pair at a time | "Use single-source Dijkstra per origin over the graph, cache to parquet; if still slow, switch to a local OSRM table service." |
| Recovery-aware wins by a huge margin | Simulator or prize tuned on test seeds, or overflow cost too low | "Freeze alpha and beta on training seeds, rerun on held-out seeds, and report sensitivity to the overflow cost." |
| Forecaster barely beats naive | Simulated noise dominates | "Report it honestly; show the seasonal-naive gap and the Brier score for overflow, which matters more than MAE here." |
| Mass balance fails | Overflowed or rejected mass not tracked | "Add a per-day ledger test and find the step where mass appears or disappears." |
| What-if sliders feel slow | Scenarios computed on request | "Serve precomputed grid results; run new ones in a background job and show progress." |
| OSMnx download fails or times out | Overpass rate limits | "Use a smaller polygon, enable OSMnx caching, retry with backoff, then commit the GraphML to data/cache/." |
| Agent hardcodes numbers in code | Skipped assumptions.yaml | "Move every constant into assumptions.yaml with a source field; add a test that greps for magic numbers in policy and flow code." |
| Agent edits unrelated modules | Context drift | "Revert changes outside \<folders\>. Re-read AGENTS.md rule 6 and redo within scope." |

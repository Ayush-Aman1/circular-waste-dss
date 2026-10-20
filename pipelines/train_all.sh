#!/usr/bin/env bash
# Circular Waste DSS training pipeline (local CPU/MPS). Idempotent via runs/train_all/stages/<stage>.done.
# SMOKE=1: one ward, 1 seed, 30 days, tiny backtest; writes to data_smoke/ and artifacts_smoke/.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
source .venv/bin/activate
export PYTHONPATH="$ROOT"
SMOKE="${SMOKE:-0}"
if [ "$SMOKE" = "1" ]; then STG=runs/train_smoke/stages; SM="--smoke"; ART=artifacts_smoke; else STG=runs/train_all/stages; SM=""; ART=artifacts; fi
mkdir -p "$STG" "$ART/sim"
fail() { echo "FAILED stage: $1"; bash tools/notify.sh "Waste DSS: training FAILED" "$1 — see runs/train_all/log.txt"; exit 1; }
stage() { local n="$1"; shift; if [ -f "$STG/$n.done" ]; then echo "[skip] $n"; return 0; fi; echo "[$(date '+%T')] >>> $n"; "$@" || fail "$n"; touch "$STG/$n.done"; }

stage acquire        python -m circwaste.data.acquire all
stage assumptions    bash -c "python -m circwaste.data.build_assumptions && python -m circwaste.data.human_tasks"
stage geo            python -m circwaste.geo.build $SM
stage calibrate      python -m circwaste.sim.calibrate --out "$ART/sim"
stage history        python -m circwaste.sim.run_history $SM
if [ "$SMOKE" = "1" ]; then
  stage forecast     python -m circwaste.forecast.train --smoke
  stage collect      python -m circwaste.artifacts.collect --smoke
else
  stage forecast     python -m circwaste.forecast.train
  stage collect      python -m circwaste.artifacts.collect
fi
echo "ALL STAGES DONE"
[ "$SMOKE" = "1" ] || bash tools/notify.sh "Waste DSS: training DONE" "Next: prompts/02_BUILD.md"

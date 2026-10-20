# Circular Waste DSS. Everything runs locally; trained models and the precomputed what-if grid are committed, so no training is needed.
PY := .venv/bin/python
UVICORN := .venv/bin/uvicorn
export OMP_NUM_THREADS ?= 1
export OPENBLAS_NUM_THREADS ?= 1

.PHONY: setup test demo demo-check api web experiments precompute report train clean-smoke

setup:                       ## create .venv, install Python + web dependencies
	@command -v uv >/dev/null 2>&1 && uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r requirements.txt \
	  || (python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt)
	cd web && npm install --no-audit --no-fund

test:                        ## Python tests + TypeScript typecheck
	$(PY) -m pytest -q
	cd web && npx tsc --noEmit

api:                         ## backend on :8000 (OpenAPI docs at /docs)
	$(UVICORN) circwaste.api.main:app --host 127.0.0.1 --port 8000

web:                         ## dashboard on :5173 (proxies /api to :8000)
	cd web && npm run dev

demo:                        ## backend + dashboard; open http://localhost:5173 (Ctrl-C stops both)
	@trap 'kill 0' INT TERM EXIT; \
	$(UVICORN) circwaste.api.main:app --host 127.0.0.1 --port 8000 & \
	for i in $$(seq 1 60); do curl -sf http://127.0.0.1:8000/health >/dev/null && break || sleep 1; done; \
	echo "API healthy -> http://127.0.0.1:8000/docs"; \
	cd web && npm run dev

demo-check:                  ## start the API, check /health and /base, stop (used by the fresh-clone check)
	@$(UVICORN) circwaste.api.main:app --host 127.0.0.1 --port 8765 >/tmp/circwaste_api.log 2>&1 & echo $$! > /tmp/circwaste_api.pid; \
	for i in $$(seq 1 60); do curl -sf http://127.0.0.1:8765/health >/dev/null && break || sleep 1; done; \
	curl -sf http://127.0.0.1:8765/health && echo && curl -sf http://127.0.0.1:8765/base | head -c 120 && echo; \
	kill `cat /tmp/circwaste_api.pid`; echo "demo health check passed"

experiments:                 ## policy comparison, alpha/beta ablation, sensitivity (background; ~40 min on 8 cores)
	bash tools/bg.sh experiments "OMP_NUM_THREADS=1 python -m experiments.run_experiments --stage all --workers 7"

precompute:                  ## precompute the what-if grid (background)
	bash tools/bg.sh precompute "OMP_NUM_THREADS=1 python -m circwaste.scenario.precompute --workers 3"

report:                      ## README results table + experiments/results/summary.md from experiments/results/*.csv
	$(PY) -m experiments.run_experiments --stage report
	$(PY) -m tools.make_readme

train:                       ## re-run the TRAIN phase from scratch (needs requirements-train.txt and internet)
	bash pipelines/train_all.sh

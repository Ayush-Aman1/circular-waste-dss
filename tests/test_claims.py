"""Claims guard: README and generated reports state the contribution as in CLAUDE.md, cite the prior work, and say the bin data is synthetic."""
from pathlib import Path

CLAIM = "a collection prize combining predicted overflow risk with predicted composition-based recovery value"
PRIOR = ["1807.01603", "2409.13386", "Ramos", "Dynamic Multi-Compartment"]
FORBIDDEN = ["novel forecasting", "novel routing", "first to model value-aware routing", "we invent prize-collecting"]


def docs():
    return {p: Path(p).read_text() for p in ["README.md", "DEMO.md", "CREDITS.md"] if Path(p).exists()}


def test_readme_states_claim_and_cites_prior_work():
    t = Path("README.md").read_text()
    assert CLAIM in t
    for p in PRIOR:
        assert p in t, p
    assert "Synthetic" in t or "synthetic" in t
    assert "OpenStreetMap" in t


def test_no_overclaiming():
    for name, t in docs().items():
        low = t.lower()
        for f in FORBIDDEN:
            assert f not in low, (name, f)


def test_generated_summary_carries_claim_and_synthetic_flag():
    f = Path("experiments/results/summary.md")
    if f.exists():
        t = f.read_text()
        assert "SYNTHETIC" in t and "No novelty is claimed" in t


def test_result_files_flagged_synthetic():
    import json
    import pandas as pd
    res = Path("experiments/results")
    for c in res.glob("*.csv"):
        assert "synthetic" in pd.read_csv(c, nrows=1).columns, c
    for j in res.glob("*.json"):
        assert json.loads(j.read_text()).get("synthetic") is True, j

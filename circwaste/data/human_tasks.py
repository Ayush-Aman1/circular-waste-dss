"""Regenerate HUMAN_TASKS.md from the TODO-SOURCE entries of configs/assumptions.yaml."""
from __future__ import annotations

from pathlib import Path

from circwaste.config import load_assumptions, todo_sources, val


def main() -> None:
    cfg = load_assumptions()
    paths = todo_sources(cfg)
    lines = ["# HUMAN TASKS (auto-generated from configs/assumptions.yaml)", "",
             "These calibration values have no verified source yet. The simulator runs with the placeholder value shown, but every result that depends on",
             "them is only as good as the placeholder. Replace the value, set `source:` to a citation, then re-run `bash pipelines/train_all.sh` (delete `runs/train_all/stages/history.done`, `forecast.done`, `collect.done`).", "",
             "| entry | placeholder value | note |", "|---|---|---|"]
    for p in paths:
        node = cfg
        for k in p.split("."):
            node = node[k]
        lines.append(f"| `{p}` | `{node.get('value')}` | {str(node['source'])[:140]} |")
    lines += ["", "Also optional: fill facility capacities for plants/DWCCs not listed in the OpenCity plants CSV (`data/geo/facilities.csv`, column capacity_kg_day)."]
    Path("HUMAN_TASKS.md").write_text("\n".join(lines) + "\n")
    print(f"HUMAN_TASKS.md: {len(paths)} entries")


if __name__ == "__main__":
    main()

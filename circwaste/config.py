"""Load configs/*.yaml; every numeric leaf group must carry a `source` field (citation, 'assumed' or 'TODO-SOURCE')."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


def _check(node: Any, path: str) -> None:
    if isinstance(node, dict):
        has_value = "value" in node or "values" in node
        if has_value and "source" not in node:
            raise ConfigError(f"{path}: missing `source` field")
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _check(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _check(v, f"{path}[{i}]")


def load_assumptions(path: str | Path = "configs/assumptions.yaml") -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    _check(cfg, "assumptions")
    return cfg


def todo_sources(cfg: dict, prefix: str = "") -> list[str]:
    """Dotted paths of every entry whose source is TODO-SOURCE."""
    out: list[str] = []
    if isinstance(cfg, dict):
        if str(cfg.get("source", "")).startswith("TODO-SOURCE"):
            out.append(prefix.rstrip("."))
        for k, v in cfg.items():
            out += todo_sources(v, f"{prefix}{k}.")
    return out


def val(cfg: dict, dotted: str) -> Any:
    node = cfg
    for k in dotted.split("."):
        node = node[k]
    return node["value"] if isinstance(node, dict) and "value" in node else node

import pytest
import yaml

from circwaste.config import ConfigError, load_assumptions, todo_sources


def test_missing_source_fails(tmp_path):
    p = tmp_path / "a.yaml"
    p.write_text(yaml.safe_dump({"x": {"value": 1}}))
    with pytest.raises(ConfigError):
        load_assumptions(p)


def test_shipped_assumptions_valid():
    cfg = load_assumptions()
    assert isinstance(todo_sources(cfg), list)

"""Checkpoint load: invalid JSON and shape warnings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.state_manager import StateManager, empty_session


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{ not json", encoding="utf-8")
    sm = StateManager(p)
    with pytest.raises(RuntimeError, match="not valid JSON"):
        sm.load()


def test_load_valid_session_no_raise(tmp_path: Path) -> None:
    p = tmp_path / "ok.json"
    s = empty_session()
    p.write_text(json.dumps(s), encoding="utf-8")
    sm = StateManager(p)
    out = sm.load()
    assert out["project"]["status"] == "executing"


def test_load_non_dict_root_raises(tmp_path: Path) -> None:
    p = tmp_path / "arr.json"
    p.write_text("[1,2]", encoding="utf-8")
    sm = StateManager(p)
    with pytest.raises(RuntimeError, match="must be a JSON object"):
        sm.load()

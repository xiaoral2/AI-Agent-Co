from __future__ import annotations

from xr_ai_co.session_validate import validate_session_shape


def test_valid_minimal_session() -> None:
    s = {
        "project": {"status": "executing"},
        "tasks": [],
        "workers": [],
    }
    assert validate_session_shape(s) == []


def test_detects_missing_keys() -> None:
    assert validate_session_shape({}) != []
    assert any("project" in m for m in validate_session_shape({}))

"""Resume CLI env helpers."""

from __future__ import annotations

import os

import pytest

from xr_ai_co import cli


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("", False),
        ("0", False),
        ("false", False),
    ],
)
def test_env_resume_refresh_config(monkeypatch: pytest.MonkeyPatch, value: str, expected: bool) -> None:
    monkeypatch.delenv("XR_AI_CO_RESUME_REFRESH_CONFIG", raising=False)
    if value:
        monkeypatch.setenv("XR_AI_CO_RESUME_REFRESH_CONFIG", value)
    assert cli._env_resume_refresh_config() is expected

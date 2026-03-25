"""§5.3 LLM-backed Tester Tool — generate tests and run pytest.

Falls back to template-based stub (just runs pytest on existing files).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from orchestrator.types import ToolResult
from tools.filesystem import write_file
from tools.run_pytest import run_pytest
from xr_ai_co.context import assemble_messages
from xr_ai_co.llm import LLMProvider, LLMProviderError

log = logging.getLogger(__name__)


def _extract_test_files(text: str) -> list[tuple[str, str]]:
    """Reuse coder extraction for test file blocks."""
    import re

    pattern = r"```[\w]*:([^\n]+)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return [(m[0].strip(), m[1]) for m in matches]
    return []


def test_with_llm(
    task: dict[str, Any],
    session: dict[str, Any],
    workspace: Path,
    llm: LLMProvider,
    mission: str = "",
    *,
    pytest_timeout_sec: float | None = 120.0,
) -> ToolResult:
    """Call LLM to generate test files, then run pytest."""
    sys, messages = assemble_messages(
        role="tester",
        task=task,
        session=session,
        mission=mission,
    )

    try:
        resp = llm.chat(system=sys, messages=messages, max_tokens=4096, temperature=0.2)
    except LLMProviderError as e:
        log.error("tester LLM call failed: %s", e)
        return ToolResult(
            success=False,
            error=f"llm_error: {e}",
            payload={"task_id": task["id"], "fallback": "run_existing"},
        )

    files = _extract_test_files(resp.text)
    for rel_path, content in files:
        try:
            write_file(workspace, rel_path, content)
        except (OSError, ValueError) as e:
            log.error("failed to write test file %s: %s", rel_path, e)

    return _run_verification(task, workspace, timeout_sec=pytest_timeout_sec)


def test_with_existing(
    task: dict[str, Any],
    workspace: Path,
    *,
    pytest_timeout_sec: float | None = 120.0,
) -> ToolResult:
    """Just run pytest on existing test files — no LLM."""
    return _run_verification(task, workspace, timeout_sec=pytest_timeout_sec)


def _run_verification(
    task: dict[str, Any],
    workspace: Path,
    *,
    timeout_sec: float | None = 120.0,
) -> ToolResult:
    ver = task.get("verification") or {}
    paths = ver.get("paths") or []
    extra = ver.get("extra_args") or []
    if not paths:
        return ToolResult(
            success=False,
            error="test task missing verification.paths",
            payload={"task_id": task["id"]},
        )
    code, out, err = run_pytest(workspace, paths, extra_args=extra, timeout_sec=timeout_sec)
    blob = {"returncode": code, "stdout": out, "stderr": err}
    ok = code == 0
    return ToolResult(
        success=ok,
        error=None if ok else "pytest_failed",
        logs=json.dumps(blob, ensure_ascii=False)[:8000],
        payload={"task_id": task["id"], "role": "tester", "pytest": blob},
    )

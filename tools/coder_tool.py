"""§5.2 LLM-backed Coder Tool — generate code files from task spec.

Profile A (§5.2): in-process LLM + §6.1 file tools.
Falls back to template-based stub when LLM is unavailable.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from orchestrator.types import ToolResult
from tools.filesystem import write_file
from xr_ai_co.builtin_templates import (
    GENERIC_MAIN,
    GENERIC_TEST,
    RATE_LIMIT_MODULE,
    RATE_LIMIT_TEST,
)
from xr_ai_co.context import assemble_messages, read_workspace_files
from xr_ai_co.llm import LLMProvider, LLMProviderError

log = logging.getLogger(__name__)


def _extract_file_blocks(text: str) -> list[tuple[str, str]]:
    """Extract ```lang:path\\n<code>\\n``` blocks from LLM output.

    Returns list of (relative_path, content).
    """
    pattern = r"```[\w]*:([^\n]+)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return [(m[0].strip(), m[1]) for m in matches]

    pattern2 = r"# file:\s*(\S+)\s*\n```[\w]*\n(.*?)```"
    matches2 = re.findall(pattern2, text, re.DOTALL)
    if matches2:
        return [(m[0].strip(), m[1]) for m in matches2]

    return []


def code_with_llm(
    task: dict[str, Any],
    session: dict[str, Any],
    workspace: Path,
    llm: LLMProvider,
    mission: str = "",
) -> ToolResult:
    """Call LLM to generate code, extract files, write to workspace."""
    hints = task.get("path_hints") or []
    existing = read_workspace_files(workspace, hints) if hints else ""

    sys, messages = assemble_messages(
        role="coder",
        task=task,
        session=session,
        mission=mission,
        workspace=workspace,
    )
    if existing:
        messages[0]["content"] += f"\n\n## Existing files\n{existing}"

    try:
        resp = llm.chat(system=sys, messages=messages, max_tokens=4096, temperature=0.2)
    except LLMProviderError as e:
        log.error("coder LLM call failed: %s", e)
        return ToolResult(
            success=False,
            error=f"llm_error: {e}",
            payload={"task_id": task["id"], "fallback": "template"},
        )

    files = _extract_file_blocks(resp.text)
    if not files:
        log.warning("coder LLM did not produce any file blocks")
        return ToolResult(
            success=False,
            error="no_file_blocks_in_output",
            logs=resp.text[:2000],
            payload={"task_id": task["id"], "fallback": "template"},
        )

    artifacts: list[str] = []
    for rel_path, content in files:
        try:
            write_file(workspace, rel_path, content)
            artifacts.append(rel_path)
        except (OSError, ValueError) as e:
            log.error("failed to write %s: %s", rel_path, e)

    if not artifacts:
        return ToolResult(
            success=False,
            error="all_file_writes_failed",
            payload={"task_id": task["id"]},
        )

    return ToolResult(
        success=True,
        payload={
            "task_id": task["id"],
            "role": "coder",
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
        },
        artifacts=artifacts,
    )


def code_with_template(
    task: dict[str, Any],
    workspace: Path,
    profile: str,
) -> ToolResult:
    """Deterministic template coder — no LLM needed."""
    try:
        if profile == "rate_limiter":
            write_file(workspace, "ratelimit.py", RATE_LIMIT_MODULE)
            write_file(workspace, "tests/test_ratelimit.py", RATE_LIMIT_TEST)
            artifacts = ["ratelimit.py", "tests/test_ratelimit.py"]
        else:
            write_file(workspace, "app.py", GENERIC_MAIN)
            write_file(workspace, "tests/test_app.py", GENERIC_TEST)
            artifacts = ["app.py", "tests/test_app.py"]
        return ToolResult(
            success=True,
            payload={"task_id": task["id"], "role": "coder"},
            artifacts=artifacts,
        )
    except OSError as e:
        return ToolResult(success=False, error=str(e), payload={"task_id": task["id"]})

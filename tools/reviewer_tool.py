"""§5.4 LLM-backed Reviewer Tool — structured review_report (5 dims) + feedback.

Dimensions: correctness, test_coverage, requirement_alignment, code_quality, security.
Verdict: 'approve' or 'request_changes'.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from orchestrator.types import ToolResult
from xr_ai_co.context import assemble_messages, read_workspace_files
from xr_ai_co.llm import LLMProvider, LLMProviderError

log = logging.getLogger(__name__)

DIMENSIONS = ("correctness", "test_coverage", "requirement_alignment", "code_quality", "security")


def _extract_review_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of review JSON from LLM output."""
    for pattern in (r"```json\s*\n(.*?)```", r"```\s*\n(.*?)```"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1).strip())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def review_with_llm(
    task: dict[str, Any],
    session: dict[str, Any],
    workspace: Path,
    llm: LLMProvider,
    mission: str = "",
) -> ToolResult:
    """Call LLM to produce structured review_report per §5.4."""
    hints = task.get("path_hints") or []
    existing = read_workspace_files(workspace, hints, cap=12000) if hints else ""

    sys, messages = assemble_messages(
        role="reviewer",
        task=task,
        session=session,
        mission=mission,
        workspace=workspace,
    )
    if existing:
        messages[0]["content"] += f"\n\n## Code under review\n{existing}"

    try:
        resp = llm.chat(system=sys, messages=messages, max_tokens=4096, temperature=0.2)
    except LLMProviderError as e:
        log.error("reviewer LLM call failed: %s", e)
        return ToolResult(
            success=False,
            error=f"llm_error: {e}",
            payload={"task_id": task["id"], "role": "reviewer"},
        )

    report = _extract_review_json(resp.text)
    if report is None:
        report = {
            "verdict": "request_changes",
            "dimensions": {d: "unknown" for d in DIMENSIONS},
            "feedback": resp.text[:3000],
            "knowledge_entries": [],
        }
        log.warning("reviewer LLM did not return valid JSON, wrapping raw text as feedback")

    verdict = report.get("verdict", "request_changes")
    return ToolResult(
        success=(verdict == "approve"),
        error=None if verdict == "approve" else "review_request_changes",
        payload={
            "task_id": task["id"],
            "role": "reviewer",
            "review_report": report,
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
        },
    )


def review_stub(
    task: dict[str, Any],
    session: dict[str, Any],
) -> ToolResult:
    """Stub reviewer — auto-approve (no LLM). Used in template mode."""
    g = session.get("global") or {}
    lp = g.get("last_pytest") or {}
    rc = lp.get("returncode")

    if rc is not None and rc != 0:
        return ToolResult(
            success=False,
            error="review_request_changes",
            payload={
                "task_id": task["id"],
                "role": "reviewer",
                "review_report": {
                    "verdict": "request_changes",
                    "dimensions": {
                        "correctness": "fail",
                        "test_coverage": "unknown",
                        "requirement_alignment": "unknown",
                        "code_quality": "unknown",
                        "security": "unknown",
                    },
                    "feedback": f"pytest failed (exit code {rc}). Fix the code and re-run tests.",
                    "knowledge_entries": [],
                },
            },
        )

    return ToolResult(
        success=True,
        payload={
            "task_id": task["id"],
            "role": "reviewer",
            "review_report": {
                "verdict": "approve",
                "dimensions": {d: "pass" for d in DIMENSIONS},
                "feedback": "All checks passed.",
                "knowledge_entries": [],
            },
        },
    )

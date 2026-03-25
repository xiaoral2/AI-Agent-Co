"""§4.3 LLM-backed Planner Tool — produce JSON task array from mission.

Falls back to template-based stub planner when LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from orchestrator.types import ToolResult
from xr_ai_co.config import AppConfig
from xr_ai_co.context import assemble_messages
from xr_ai_co.llm import LLMProvider, LLMProviderError
from xr_ai_co.plan_validate import validate_plan_tasks
from xr_ai_co.planner import build_tasks as stub_build_tasks
from xr_ai_co.task_token_estimates import annotate_task_token_estimates

log = logging.getLogger(__name__)


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    """Best-effort extraction of a JSON array from LLM output."""
    for pattern in (r"```json\s*\n(.*?)```", r"```\s*\n(.*?)```", r"(\[.*\])"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1).strip())
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                continue
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def plan_with_llm(
    mission: str,
    session: dict[str, Any],
    llm: LLMProvider,
    plan_revision_id: str = "rev-001",
) -> ToolResult:
    """Call LLM to produce tasks, validate against schema, return ToolResult."""
    dummy_task: dict[str, Any] = {"id": "planning", "type": "design", "description": mission}
    sys, messages = assemble_messages(
        role="planner",
        task=dummy_task,
        session=session,
        mission=mission,
    )
    messages[0]["content"] += (
        f"\n\n**Instruction:** produce a JSON array of tasks for plan_revision_id={plan_revision_id!r}. "
        "Every test-type task must include a 'verification' object with 'paths' and "
        "`\"kind\": \"pytest\"` exactly (literal string pytest only; not execution, unittest, or shell). "
        "You may include `type: design` tasks that produce docs/interface.md; place them before "
        "dependent `code` tasks using `depends_on`. "
        "For every task, fields `input`, `output`, `description`, and `test_plan` must be JSON "
        "strings (plain text), never nested objects. For design tasks, describe paths and content "
        "in those strings; do not use `{{\"file\": \"...\", \"content\": \"...\"}}` as a field value. "
        "Return ONLY the JSON array in a ```json fenced block."
    )

    try:
        resp = llm.chat(system=sys, messages=messages, max_tokens=4096, temperature=0.3)
    except LLMProviderError as e:
        log.error("planner LLM call failed: %s", e)
        return ToolResult(
            success=False,
            error=f"llm_error: {e}",
            payload={"fallback": "template"},
        )

    tasks = _extract_json_array(resp.text)
    if tasks is None:
        log.warning("planner LLM did not return valid JSON array, falling back to template")
        return ToolResult(
            success=False,
            error="llm_output_parse_error",
            logs=resp.text[:2000],
            payload={"fallback": "template"},
        )

    for t in tasks:
        t.setdefault("plan_revision_id", plan_revision_id)
        t.setdefault("status", "todo")
        t.setdefault("retry_count", 0)
        t.setdefault("owner", None)

    try:
        validate_plan_tasks(tasks)
    except ValueError as e:
        log.warning("planner LLM output failed schema validation: %s", e)
        return ToolResult(
            success=False,
            error=f"schema_validation_failed: {e}",
            logs=resp.text[:2000],
            payload={"fallback": "template"},
        )

    return ToolResult(
        success=True,
        payload={
            "tasks": tasks,
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
        },
    )


def plan_tasks(
    mission: str,
    session: dict[str, Any],
    config: AppConfig,
    llm: LLMProvider | None = None,
    plan_revision_id: str = "rev-001",
) -> tuple[list[dict[str, Any]], str]:
    """High-level entry: try LLM planner, fall back to stub.

    Returns (tasks, profile) matching the stub planner signature.
    """
    if llm is not None and config.llm.api_key:
        result = plan_with_llm(mission, session, llm, plan_revision_id)
        if result.success:
            tasks = result.payload["tasks"]
            annotate_task_token_estimates(tasks)
            return tasks, "llm"

    tasks, profile = stub_build_tasks(
        mission,
        plan_revision_id=plan_revision_id,
        include_design=config.planner.include_design_task,
    )
    annotate_task_token_estimates(tasks)
    return tasks, profile

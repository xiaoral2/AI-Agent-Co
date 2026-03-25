"""§2.5.6 — optional PM requirements-clarification pass before Planner."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from xr_ai_co.config import AppConfig
from xr_ai_co.llm import LLMProvider, LLMProviderError

log = logging.getLogger(__name__)


def _extract_questions_json(text: str) -> list[str] | None:
    for pattern in (r"```json\s*\n(.*?)```", r"```\s*\n(.*?)```", r"(\{.*\})"):
        m = re.search(pattern, text, re.DOTALL)
        if not m:
            continue
        try:
            obj = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("questions"), list):
            qs = [str(q).strip() for q in obj["questions"] if str(q).strip()]
            return qs[:5]
    return None


def run_pm_clarification_loop(
    mission: str,
    config: AppConfig,
    llm: LLMProvider | None,
) -> str:
    """Interactive Q&A; persist answers by appending to mission text for Planner."""
    stub_task: dict[str, Any] = {
        "id": "pm-pass",
        "type": "design",
        "description": "Requirements clarification",
    }
    session: dict[str, Any] = {
        "global": {"requirements_summary": mission},
        "project": {"status": "planning"},
        "tasks": [],
        "workers": [],
        "budget_counters": {},
        "policies": {},
    }

    questions: list[str] = []
    if llm is not None and config.llm.api_key:
        from xr_ai_co.context import assemble_messages

        sys_p, messages = assemble_messages(
            role="pm",
            task=stub_task,
            session=session,
            mission=mission,
        )
        messages[0]["content"] += (
            "\n\n**Instruction:** Output ONLY a JSON object in a ```json block with key "
            '"questions" (array of 1–4 short clarification questions about scope, '
            "constraints, success criteria, or risks). No other text."
        )
        try:
            resp = llm.chat(system=sys_p, messages=messages, max_tokens=1024, temperature=0.3)
            questions = _extract_questions_json(resp.text) or []
        except LLMProviderError as e:
            log.warning("PM clarification LLM failed: %s", e)

    if not questions:
        print("\n— PM clarification (§2.5.6) —\nAdd constraints or success criteria (empty line to skip):")
        extra = input().strip()
        if not extra:
            return mission
        return f"{mission.strip()}\n\n**CEO clarification:**\n{extra}"

    print("\n— PM clarification (§2.5.6) —")
    answers: list[str] = []
    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q}")
        try:
            a = input("Your answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            a = ""
        answers.append(a)

    lines: list[str] = []
    for i, q in enumerate(questions):
        a = answers[i] if i < len(answers) else ""
        lines.append(f"Q: {q}\nA: {a if a else '(no answer)'}")
    block = "\n".join(lines)
    return f"{mission.strip()}\n\n**Clarification Q&A:**\n{block}"

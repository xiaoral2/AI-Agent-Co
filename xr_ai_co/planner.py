"""Materialize JSON tasks from a natural-language mission (stub planner — §4.3)."""

from __future__ import annotations

import re
from typing import Literal

MissionProfile = Literal["rate_limiter", "generic"]


def detect_profile(mission: str) -> MissionProfile:
    m = mission.lower()
    if re.search(r"rate[\s_-]*limit|ratelimit|令牌桶|限流", m):
        return "rate_limiter"
    return "generic"


def _design_task(mission: str, plan_revision_id: str, task_id: str = "T0") -> dict:
    return {
        "id": task_id,
        "type": "design",
        "description": "Produce interface spec (docs/interface.md) before implementation",
        "status": "todo",
        "depends_on": [],
        "owner": None,
        "retry_count": 0,
        "plan_revision_id": plan_revision_id,
        "priority": "normal",
        "input": mission.strip()[:2000],
        "output": "docs/interface.md with API boundaries, data model, and invariants",
        "constraints": ["Markdown only under docs/", "no production implementation"],
        "acceptance_criteria": ["docs/interface.md exists and is non-empty"],
        "test_plan": "N/A — design task; validated by document presence",
        "path_hints": ["docs/interface.md"],
        "design_notes": "§5.5 architect handoff before code",
    }


def build_tasks(
    mission: str,
    plan_revision_id: str = "rev-001",
    *,
    include_design: bool = False,
) -> tuple[list[dict], MissionProfile]:
    profile = detect_profile(mission)
    code_id, test_id = "T1", "T2"
    code_dep: list[str] = ["T0"] if include_design else []
    if profile == "rate_limiter":
        code_task = {
            "id": code_id,
            "type": "code",
            "description": "Implement TokenBucket rate limiter in ratelimit.py",
            "status": "todo",
            "depends_on": code_dep,
            "owner": None,
            "retry_count": 0,
            "plan_revision_id": plan_revision_id,
            "priority": "normal",
            "input": mission.strip(),
            "output": "ratelimit.py at workspace root with class TokenBucket(rate, capacity), consume(n), refill(elapsed)",
            "constraints": ["Python 3.11+", "no third-party deps for core logic"],
            "acceptance_criteria": ["Unit tests in tests/test_ratelimit.py pass"],
            "test_plan": "pytest tests/test_ratelimit.py",
            "path_hints": ["ratelimit.py", "tests/test_ratelimit.py"],
        }
        test_task = {
            "id": test_id,
            "type": "test",
            "description": "Verify rate limiter with pytest",
            "status": "todo",
            "depends_on": [code_id],
            "owner": None,
            "retry_count": 0,
            "plan_revision_id": plan_revision_id,
            "priority": "normal",
            "input": "T1 deliverable on disk",
            "output": "pytest green for tests/test_ratelimit.py",
            "constraints": ["run only under workspace root"],
            "acceptance_criteria": ["tests/test_ratelimit.py passes"],
            "test_plan": "pytest tests/test_ratelimit.py",
            "verification": {
                "kind": "pytest",
                "paths": ["tests/test_ratelimit.py"],
                "extra_args": ["-q"],
            },
        }
        if include_design:
            tasks = [_design_task(mission, plan_revision_id, "T0"), code_task, test_task]
        else:
            tasks = [code_task, test_task]
    else:
        code_task = {
            "id": code_id,
            "type": "code",
            "description": f"Implement software for: {mission.strip()[:200]}",
            "status": "todo",
            "depends_on": code_dep,
            "owner": None,
            "retry_count": 0,
            "plan_revision_id": plan_revision_id,
            "priority": "normal",
            "input": mission.strip(),
            "output": "app/main.py with a working entrypoint",
            "constraints": ["Python 3.11+"],
            "acceptance_criteria": ["tests/test_app.py passes"],
            "test_plan": "pytest tests/test_app.py",
            "path_hints": ["app/main.py", "tests/test_app.py"],
        }
        test_task = {
            "id": test_id,
            "type": "test",
            "description": "Run pytest for generic mission",
            "status": "todo",
            "depends_on": [code_id],
            "owner": None,
            "retry_count": 0,
            "plan_revision_id": plan_revision_id,
            "priority": "normal",
            "input": "T1 output",
            "output": "pytest green",
            "constraints": ["pytest runs with cwd = workspace root"],
            "acceptance_criteria": ["tests/test_app.py passes"],
            "test_plan": "pytest tests/test_app.py",
            "verification": {
                "kind": "pytest",
                "paths": ["tests/test_app.py"],
                "extra_args": ["-q"],
            },
        }
        if include_design:
            tasks = [_design_task(mission, plan_revision_id, "T0"), code_task, test_task]
        else:
            tasks = [code_task, test_task]
    return tasks, profile


def requirements_summary(mission: str, profile: MissionProfile) -> str:
    return f"Mission: {mission.strip()}\nProfile: {profile}\nPlanner: stub (no LLM)."

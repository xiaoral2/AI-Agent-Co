"""Assemble checkpoint-shaped session dict (§3.1, §6.6) + §4.3.1 replan."""

from __future__ import annotations

import time
from typing import Any

from orchestrator.state_manager import empty_session

from xr_ai_co.planner import MissionProfile


def build_session(
    mission: str,
    tasks: list[dict[str, Any]],
    profile: MissionProfile,
    *,
    auto_approve: bool,
) -> dict[str, Any]:
    s = empty_session()
    rev = tasks[0]["plan_revision_id"] if tasks else "rev-001"
    s["project"]["plan_revision_id"] = rev
    s["project"]["approved_plan_revision_id"] = rev if auto_approve else None
    s["project"]["status"] = "executing" if auto_approve else "planning"
    s["tasks"] = tasks
    # Full mission text (incl. PM §2.5.6 clarifications) for §6.5.1 — not the stub one-liner.
    s["global"] = {
        "requirements_summary": mission.strip(),
        "last_pytest": None,
        "last_reviewer_feedback": None,
        "planner_profile": profile,
    }
    s["policies"]["retry_policy"] = {"max_retries_per_task": 5}
    s["policies"]["parallelism_policy"] = {"max_concurrent_code_tasks": 2}
    if auto_approve:
        s["project"]["session_started_epoch"] = time.time()
    return s


def ceo_approve(session: dict[str, Any]) -> None:
    rev = session["project"].get("plan_revision_id")
    if not session["tasks"]:
        raise ValueError("no tasks to approve")
    if rev is None:
        rev = session["tasks"][0]["plan_revision_id"]
    session["project"]["approved_plan_revision_id"] = rev
    session["project"]["status"] = "executing"
    session["project"].setdefault("session_started_epoch", time.time())


def next_revision_id(current: str) -> str:
    """Generate next plan_revision_id from current (e.g. rev-001 → rev-002)."""
    if current.startswith("rev-"):
        try:
            n = int(current.split("-", 1)[1])
            return f"rev-{n + 1:03d}"
        except (ValueError, IndexError):
            pass
    return current + "-next"


def merge_replan_tasks(
    session: dict[str, Any],
    new_tasks: list[dict[str, Any]],
    new_revision: str | None = None,
) -> str:
    """§4.3.1: merge new tasks into session after replan.

    - Stamps new_revision on all new tasks
    - Updates project.plan_revision_id (but NOT approved — CEO must re-approve)
    - Sets project.status to 'planning'
    - Returns the new revision id
    """
    current_rev = session["project"].get("plan_revision_id", "rev-001")
    rev = new_revision or next_revision_id(current_rev)

    for t in new_tasks:
        t["plan_revision_id"] = rev
        t.setdefault("status", "todo")
        t.setdefault("retry_count", 0)
        t.setdefault("owner", None)

    session["tasks"] = new_tasks
    session["project"]["plan_revision_id"] = rev
    session["project"]["approved_plan_revision_id"] = None
    session["project"]["status"] = "planning"

    return rev


def ceo_pause(session: dict[str, Any]) -> None:
    """§6.7 — pause controller loop (checkpoint-friendly)."""
    if session["project"].get("status") == "executing":
        session["project"]["status"] = "paused"


def ceo_continue(session: dict[str, Any], reset_task_ids: list[str] | None = None) -> None:
    """§7.2 'continue' action: resume execution, optionally reset retry counts."""
    session["project"]["status"] = "executing"
    session["project"].setdefault("session_started_epoch", time.time())
    if reset_task_ids:
        for t in session["tasks"]:
            if t["id"] in reset_task_ids:
                t["status"] = "todo"
                t["retry_count"] = 0
                t["owner"] = None
    else:
        for t in session["tasks"]:
            if t.get("status") == "failed":
                t["status"] = "todo"
                t["retry_count"] = 0
                t["owner"] = None

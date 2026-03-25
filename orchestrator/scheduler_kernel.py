"""Executable scheduling tick — §6.4.1 (rules as functions, not only prose).

This module is the reference `schedule(state) -> DecisionOutput` execution layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from .types import DecisionInput, DecisionOutput


def task_by_id(tasks: list[dict[str, Any]], tid: str) -> dict[str, Any]:
    for t in tasks:
        if t["id"] == tid:
            return t
    raise KeyError(tid)


def map_task_type_to_role(task_type: str) -> str:
    # §17.5
    if task_type == "code":
        return "coder"
    if task_type == "test":
        return "tester"
    if task_type == "design":
        return "architect"
    raise ValueError(f"unsupported Task.type: {task_type}")


def violates_budget_next_step(task: dict[str, Any], state: DecisionInput) -> bool:
    """§17.2 + §17.2.1 — honor session token cap + max_retries_total."""
    limits = state.budget_limits or {}
    counters = state.budget_counters or {}

    # Token budget
    max_session = limits.get("max_tokens_per_session")
    if max_session is not None:
        est = int(task.get("estimated_prompt_tokens", 0) or 0) + int(
            task.get("estimated_completion_tokens", 0) or 0
        )
        used = int(counters.get("tokens_used_session", 0) or 0)
        if used + est > int(max_session):
            return True

    # Global retry budget
    budget_policy = (state.policies or {}).get("budget_policy") or {}
    max_retries_total = budget_policy.get("max_retries_total")
    if max_retries_total is not None:
        retries_used = int(counters.get("retries_used_project", 0) or 0)
        if retries_used >= int(max_retries_total):
            return True

    # §17.2 — estimated spend (USD heuristic)
    max_cost = limits.get("max_cost_per_project")
    if max_cost is not None:
        spent = float(counters.get("estimated_cost_usd", 0) or 0)
        if spent >= float(max_cost):
            return True

    return False


_TIERS = ("low", "normal", "high", "urgent")
_TIER_I = {t: i for i, t in enumerate(_TIERS)}


def _hours_until_deadline(deadline: str | None, now: datetime) -> float | None:
    if not deadline:
        return None
    try:
        from datetime import datetime, timezone

        parts = str(deadline).strip().split("-", 2)[:3]
        y, m, d = (int(x) for x in parts)
        end = datetime(y, m, d, 23, 59, 59, tzinfo=timezone.utc)
        nw = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return (end - nw).total_seconds() / 3600.0
    except (ValueError, TypeError, IndexError):
        return None


def sla_effective_priority(
    task: dict[str, Any],
    now: datetime,
    sla_policy: dict[str, Any],
) -> tuple[str, bool]:
    """§2.5.3a — max(stored priority, deadline floor). Returns (tier, sla_boost_applied)."""
    raw = task.get("priority") or "normal"
    if raw not in _TIER_I:
        raw = "normal"
    bi = _TIER_I[raw]
    fi = 0
    if sla_policy:
        hrs = _hours_until_deadline(task.get("deadline"), now)
        if hrs is not None:
            if hrs < 0:
                fi = 3
            else:
                uh = sla_policy.get("deadline_urgent_within_hours")
                hh = sla_policy.get("deadline_high_within_hours")
                if uh is not None and hrs <= float(uh):
                    fi = 3
                elif hh is not None and hrs <= float(hh):
                    fi = 2
    ei = max(bi, fi)
    return _TIERS[ei], ei > bi


def compute_effective_priority_rank(
    task: dict[str, Any],
    now: datetime,
    sla_policy: dict[str, Any],
) -> str:
    """§2.5.3a — effective tier for scheduling sort keys."""
    return sla_effective_priority(task, now, sla_policy)[0]


def deadline_key(deadline: str | None, inf: float) -> tuple[float, str]:
    """Sort key fragment: earlier deadline first; missing deadline sorts after."""
    if not deadline:
        return (inf, "")
    try:
        from datetime import date

        y, m, d = (int(x) for x in deadline.split("-", 2))
        return (date(y, m, d).toordinal(), deadline)
    except (ValueError, TypeError):
        return (inf, deadline or "")


def default_workspace_safe(
    batch: list[dict[str, Any]],
    in_flight: list[dict[str, Any]],
    file_locks: dict[str, str],
) -> bool:
    """§9.4.1 — path-overlap + file-lock workspace safety check.

    Returns False if any task in *batch* writes to a path that is already
    locked or overlaps with an in-flight task's path_hints.
    """
    locked_paths = set(file_locks.keys())
    in_flight_paths: set[str] = set()
    for t in in_flight:
        for p in t.get("path_hints") or []:
            in_flight_paths.add(p)

    for t in batch:
        hints = set(t.get("path_hints") or [])
        if not hints:
            continue
        if hints & locked_paths:
            return False
        if hints & in_flight_paths:
            return False
        in_flight_paths |= hints

    return True


def select_parallel_batch(
    ordered: list[dict[str, Any]],
    state: DecisionInput,
    max_concurrent_code: int,
    workspace_safe: Callable[[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]], bool],
) -> list[dict[str, Any]]:
    """Greedy batch — §6.4.1."""
    batch: list[dict[str, Any]] = []
    code_in_batch = 0
    for t in ordered:
        mutating = t.get("type") in ("code", "design")
        if mutating and code_in_batch >= max_concurrent_code:
            continue
        candidate = batch + [t]
        if not workspace_safe(candidate, state.in_flight_tasks, state.file_locks):
            continue
        batch.append(t)
        if mutating:
            code_in_batch += 1
    return batch


def assign_or_provision_worker(
    task: dict[str, Any],
    state: DecisionInput,
) -> dict[str, Any] | None:
    """§6.4.1 — reuse idle (lexicographic id) or provision under scaling_policy cap."""
    required_role = map_task_type_to_role(task["type"])
    scaling = (state.policies or {}).get("scaling_policy") or {}
    cap = int(scaling.get(required_role, 4))

    idle = [
        w
        for w in state.workers
        if w.get("role") == required_role and w.get("status") == "idle"
    ]
    if idle:
        chosen = min(idle, key=lambda w: w["id"])
        return chosen

    active = [w for w in state.workers if w.get("role") == required_role and w.get("status") != "retired"]
    if len(active) >= cap:
        return None

    wid = f"{required_role}_{len(state.workers) + 1}"
    w = {"id": wid, "role": required_role, "status": "idle", "repo_root": task.get("repo_root", ".")}
    state.workers.append(w)
    return w


def scheduling_dispatch_tick(state: DecisionInput) -> DecisionOutput:
    """§6.4.1 reference implementation (same structure as spec pseudocode)."""
    approved = state.project.get("approved_plan_revision_id")
    ready = [
        t
        for t in state.tasks
        if t.get("status") == "todo"
        and all(task_by_id(state.tasks, d).get("status") == "done" for d in t.get("depends_on", []))
        and t.get("plan_revision_id") == approved
        and state.project.get("status") == "executing"
    ]
    if not ready:
        return DecisionOutput(
            selected_tasks=[],
            worker_assignment=[],
            decision_log_entries=[],
            side_effect=None,
        )

    eligible = [t for t in ready if not violates_budget_next_step(t, state)]
    if not eligible:
        return DecisionOutput(
            selected_tasks=[],
            worker_assignment=[],
            decision_log_entries=[
                {"decision": "escalate", "reason": "budget_exhausted_or_no_eligible_work"}
            ],
            side_effect="escalate",
        )

    sla = (state.policies or {}).get("sla_policy") or {}
    tier_rank = {"urgent": 3, "high": 2, "normal": 1, "low": 0}
    inf = float("inf")
    ordered = sorted(
        eligible,
        key=lambda t: (
            -tier_rank[compute_effective_priority_rank(t, state.now, sla)],
            deadline_key(t.get("deadline"), inf),
            t["id"],
        ),
    )

    batch = select_parallel_batch(
        ordered,
        state,
        max_concurrent_code=state.effective_max_concurrent_code_tasks,
        workspace_safe=default_workspace_safe,
    )

    assignments: list[tuple[str, str | None]] = []
    for task in batch:
        worker = assign_or_provision_worker(task, state)
        assignments.append((task["id"], worker["id"] if worker else None))

    log_entries: list[dict[str, Any]] = [{"decision": "schedule_batch", "tasks": [a[0] for a in assignments]}]
    sla_boosts: list[dict[str, Any]] = []
    for task in batch:
        eff, boosted = sla_effective_priority(task, state.now, sla)
        if boosted:
            sla_boosts.append({"task_id": task["id"], "effective_tier": eff, "reason": "deadline_proximity"})
    if sla_boosts:
        log_entries.append(
            {"decision": "sla_priority_boost", "reason": "deadline_proximity", "context": {"tasks": sla_boosts}},
        )
    return DecisionOutput(
        selected_tasks=batch,
        worker_assignment=assignments,
        decision_log_entries=log_entries,
        side_effect=None,
    )


def _effective_code_cap(session: dict[str, Any]) -> int:
    """§2.2: compute effective max concurrent code tasks with optional host clamp."""
    import os

    eff = (session.get("policies") or {}).get("parallelism_policy") or {}
    configured = max(1, int(eff.get("max_concurrent_code_tasks", 2)))

    clamp = (session.get("policies") or {}).get("clamp_code_tasks_to_host", False)
    if clamp:
        cpu = os.cpu_count() or 1
        host_ceiling = max(1, min(cpu // 2, 4))
        return min(configured, host_ceiling)

    return configured


def decision_input_from_session(session: dict[str, Any], now: datetime | None = None) -> DecisionInput:
    """Build DecisionInput from a StateManager JSON blob."""
    now = now or datetime.now().astimezone()
    in_flight = [t for t in session["tasks"] if t.get("status") == "in_progress"]
    max_code = _effective_code_cap(session)
    return DecisionInput(
        tasks=session["tasks"],
        project=session["project"],
        budget_counters=session.get("budget_counters") or {},
        budget_limits=session.get("budget_limits") or {},
        workers=session["workers"],
        now=now,
        policies=session.get("policies") or {},
        file_locks=session.get("file_locks") or {},
        in_flight_tasks=in_flight,
        effective_max_concurrent_code_tasks=max_code,
    )

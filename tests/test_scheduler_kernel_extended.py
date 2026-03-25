"""Scheduler kernel: budgets, ordering, workers, decision_input."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from orchestrator.scheduler_kernel import (
    assign_or_provision_worker,
    deadline_key,
    decision_input_from_session,
    default_workspace_safe,
    map_task_type_to_role,
    scheduling_dispatch_tick,
    select_parallel_batch,
    task_by_id,
    violates_budget_next_step,
)
from orchestrator.state_manager import empty_session
from orchestrator.types import DecisionInput


def test_task_by_id_ok() -> None:
    tasks = [{"id": "a", "x": 1}]
    assert task_by_id(tasks, "a")["x"] == 1


def test_task_by_id_keyerror() -> None:
    with pytest.raises(KeyError):
        task_by_id([], "x")


def test_map_task_type_to_role() -> None:
    assert map_task_type_to_role("code") == "coder"
    assert map_task_type_to_role("test") == "tester"
    assert map_task_type_to_role("design") == "architect"
    with pytest.raises(ValueError):
        map_task_type_to_role("weird")


def test_violates_budget_session_tokens() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={"tokens_used_session": 100},
        budget_limits={"max_tokens_per_session": 100},
        workers=[],
        now=datetime.now(timezone.utc),
        policies={},
        file_locks={},
        in_flight_tasks=[],
    )
    task = {"estimated_prompt_tokens": 1, "estimated_completion_tokens": 0}
    assert violates_budget_next_step(task, state)


def test_violates_budget_retries() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={"retries_used_project": 5},
        budget_limits={},
        workers=[],
        now=datetime.now(timezone.utc),
        policies={"budget_policy": {"max_retries_total": 5}},
        file_locks={},
        in_flight_tasks=[],
    )
    assert violates_budget_next_step({"estimated_prompt_tokens": 0, "estimated_completion_tokens": 0}, state)


def test_violates_budget_cost() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={"estimated_cost_usd": 10.0},
        budget_limits={"max_cost_per_project": 10.0},
        workers=[],
        now=datetime.now(timezone.utc),
        policies={},
        file_locks={},
        in_flight_tasks=[],
    )
    assert violates_budget_next_step({"estimated_prompt_tokens": 0, "estimated_completion_tokens": 0}, state)


def test_violates_budget_false() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={},
        budget_limits={},
        workers=[],
        now=datetime.now(timezone.utc),
        policies={},
        file_locks={},
        in_flight_tasks=[],
    )
    assert not violates_budget_next_step({"estimated_prompt_tokens": 0, "estimated_completion_tokens": 0}, state)


def test_deadline_key_missing() -> None:
    inf = float("inf")
    assert deadline_key(None, inf)[0] == inf


def test_deadline_key_invalid() -> None:
    inf = float("inf")
    k = deadline_key("not-a-date", inf)
    assert k[0] == inf


def test_workspace_safe_overlap() -> None:
    assert not default_workspace_safe(
        [{"path_hints": ["a"]}],
        [{"path_hints": ["a"]}],
        {},
    )
    assert default_workspace_safe(
        [{"path_hints": ["a"]}],
        [{"path_hints": ["b"]}],
        {},
    )


def test_workspace_safe_file_lock() -> None:
    assert not default_workspace_safe(
        [{"path_hints": ["x"]}],
        [],
        {"x": "other"},
    )


def test_select_parallel_batch_respects_code_cap() -> None:
    ordered = [
        {"id": "c1", "type": "code"},
        {"id": "c2", "type": "code"},
        {"id": "c3", "type": "code"},
    ]
    state = DecisionInput(
        tasks=ordered,
        project={},
        budget_counters={},
        budget_limits={},
        workers=[],
        now=datetime.now(timezone.utc),
        policies={},
        file_locks={},
        in_flight_tasks=[],
    )

    def always_ok(batch, inflight, locks):
        return True

    b = select_parallel_batch(ordered, state, 2, always_ok)
    assert len(b) == 2


def test_assign_reuses_idle_worker() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={},
        budget_limits={},
        workers=[{"id": "coder_2", "role": "coder", "status": "idle", "repo_root": "."}],
        now=datetime.now(timezone.utc),
        policies={"scaling_policy": {"coder": 4}},
        file_locks={},
        in_flight_tasks=[],
    )
    w = assign_or_provision_worker({"type": "code", "repo_root": "."}, state)
    assert w is not None
    assert w["id"] == "coder_2"


def test_assign_provisions_new() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={},
        budget_limits={},
        workers=[],
        now=datetime.now(timezone.utc),
        policies={"scaling_policy": {"coder": 4}},
        file_locks={},
        in_flight_tasks=[],
    )
    w = assign_or_provision_worker({"type": "code"}, state)
    assert w is not None
    assert w["role"] == "coder"


def test_assign_cap_returns_none() -> None:
    state = DecisionInput(
        tasks=[],
        project={},
        budget_counters={},
        budget_limits={},
        workers=[{"id": "c1", "role": "coder", "status": "busy", "repo_root": "."}],
        now=datetime.now(timezone.utc),
        policies={"scaling_policy": {"coder": 1}},
        file_locks={},
        in_flight_tasks=[],
    )
    assert assign_or_provision_worker({"type": "code"}, state) is None


def test_scheduling_dispatch_empty() -> None:
    s = empty_session()
    s["tasks"] = []
    inp = decision_input_from_session(s, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    out = scheduling_dispatch_tick(inp)
    assert out.worker_assignment == []


def test_scheduling_budget_escalate() -> None:
    s = empty_session()
    s["budget_limits"] = {"max_tokens_per_session": 1}
    s["budget_counters"] = {"tokens_used_session": 0}
    s["tasks"] = [
        {
            "id": "T1",
            "type": "code",
            "status": "todo",
            "depends_on": [],
            "plan_revision_id": "rev-001",
            "estimated_prompt_tokens": 999,
            "estimated_completion_tokens": 0,
        },
    ]
    inp = decision_input_from_session(s, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    out = scheduling_dispatch_tick(inp)
    assert out.side_effect == "escalate"


def test_scheduling_sla_boost_log() -> None:
    s = empty_session()
    s.setdefault("policies", {})["sla_policy"] = {"deadline_urgent_within_hours": 99999}
    s["tasks"] = [
        {
            "id": "T1",
            "type": "code",
            "status": "todo",
            "depends_on": [],
            "plan_revision_id": "rev-001",
            "priority": "low",
            "deadline": "2026-01-02",
        },
    ]
    inp = decision_input_from_session(s, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    out = scheduling_dispatch_tick(inp)
    assert any(e.get("decision") == "sla_priority_boost" for e in out.decision_log_entries)


def test_decision_input_clamp_host(monkeypatch: pytest.MonkeyPatch) -> None:
    s = empty_session()
    s.setdefault("policies", {})["parallelism_policy"] = {"max_concurrent_code_tasks": 99}
    s.setdefault("policies", {})["clamp_code_tasks_to_host"] = True
    monkeypatch.setattr("os.cpu_count", lambda: 2)
    inp = decision_input_from_session(s)
    assert inp.effective_max_concurrent_code_tasks == 1


def test_hours_until_deadline_bad_string() -> None:
    from orchestrator.scheduler_kernel import _hours_until_deadline

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _hours_until_deadline("x-y-z", now) is None

"""ReferenceOrchestrator.run() integration-style tests (tmp state file + StubExecutor)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.orchestrator_loop import ReferenceOrchestrator, StubExecutor
from orchestrator.state_manager import StateManager, empty_session
from orchestrator.types import ToolResult


def _minimal_code_task(tid: str = "T1") -> dict:
    return {
        "id": tid,
        "type": "code",
        "description": "x",
        "status": "todo",
        "depends_on": [],
        "owner": None,
        "retry_count": 0,
        "plan_revision_id": "rev-001",
        "priority": "normal",
        "input": "i",
        "output": "o",
        "constraints": "c",
        "acceptance_criteria": "a",
        "test_plan": "t",
        "path_hints": ["."],
    }


def test_run_completes_single_stub_task(tmp_path: Path) -> None:
    s = empty_session()
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor(), workspace=None).run(max_ticks=16)
    out = json.loads(p.read_text(encoding="utf-8"))
    assert out["project"]["status"] == "done"
    assert out["tasks"][0]["status"] == "done"


def test_run_respects_paused(tmp_path: Path) -> None:
    s = empty_session()
    s["project"]["status"] = "paused"
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor()).run(max_ticks=4)
    out = json.loads(p.read_text(encoding="utf-8"))
    assert out["project"]["status"] == "paused"


def test_run_stops_when_not_executing(tmp_path: Path) -> None:
    s = empty_session()
    s["project"]["status"] = "blocked"
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor()).run(max_ticks=4)
    assert json.loads(p.read_text(encoding="utf-8"))["project"]["status"] == "blocked"


def test_run_session_duration_block(tmp_path: Path) -> None:
    import time

    s = empty_session()
    s["budget_limits"] = {"session_max_duration_sec": 1}
    s["project"]["session_started_epoch"] = time.time() - 500
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor()).run(max_ticks=4)
    assert json.loads(p.read_text(encoding="utf-8"))["project"]["status"] == "blocked"


def test_run_global_retry_budget_block(tmp_path: Path) -> None:
    s = empty_session()
    s.setdefault("policies", {})["budget_policy"] = {"max_retries_total": 0}
    s["budget_counters"]["retries_used_project"] = 0
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor()).run(max_ticks=4)
    assert json.loads(p.read_text(encoding="utf-8"))["project"]["status"] == "blocked"


def test_run_per_task_token_block(tmp_path: Path) -> None:
    s = empty_session()
    s["budget_limits"] = {"max_tokens_per_task": 10}
    s["tasks"] = [{**_minimal_code_task(), "tokens_used": 100}]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor()).run(max_ticks=4)
    out = json.loads(p.read_text(encoding="utf-8"))
    assert out["project"]["status"] == "blocked"


def test_run_scheduler_budget_escalate(tmp_path: Path) -> None:
    s = empty_session()
    s["budget_limits"] = {"max_tokens_per_session": 1}
    s["budget_counters"] = {"tokens_used_session": 0, "retries_used_project": 0, "estimated_cost_usd": 0.0}
    s["tasks"] = [
        {
            **_minimal_code_task(),
            "estimated_prompt_tokens": 99999,
            "estimated_completion_tokens": 0,
        },
    ]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor()).run(max_ticks=4)
    assert json.loads(p.read_text(encoding="utf-8"))["project"]["status"] == "blocked"


def test_run_success_path_review_request_changes(tmp_path: Path) -> None:
    class Exec(StubExecutor):
        def review(self, task: dict) -> ToolResult:
            return ToolResult(
                success=True,
                payload={
                    "review_report": {
                        "verdict": "request_changes",
                        "feedback": "redo",
                    },
                },
            )

    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 50}
    s.setdefault("policies", {})["review_policy"] = {"code_success_gate": True}
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=Exec(), workspace=None).run(max_ticks=16)
    out = json.loads(p.read_text(encoding="utf-8"))
    assert out["tasks"][0]["status"] == "todo"
    assert out["global"].get("last_reviewer_feedback") == "redo"


def test_run_with_workspace_calls_git_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_init(ws: Path) -> bool:
        calls.append("init")
        return False

    monkeypatch.setattr("xr_ai_co.workspace_git.git_init", fake_init)
    s = empty_session()
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    ws = tmp_path / "ws"
    ws.mkdir()
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=StubExecutor(), workspace=ws).run(max_ticks=8)
    assert "init" in calls


def test_run_usage_increments_tokens(tmp_path: Path) -> None:
    class U(StubExecutor):
        def execute(self, task: dict) -> ToolResult:
            return ToolResult(
                success=True,
                payload={"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
            )

    s = empty_session()
    s["tasks"] = [_minimal_code_task()]
    p = tmp_path / "s.json"
    sm = StateManager(p)
    sm.persist(s)
    ReferenceOrchestrator(sm, executor=U(), workspace=None).run(max_ticks=8)
    t = json.loads(p.read_text(encoding="utf-8"))["tasks"][0]
    assert t.get("tokens_used") == 15


def test_orchestrator_main_creates_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    from orchestrator import orchestrator_loop as ol

    ol.main()
    assert (tmp_path / "state" / "reference_session.json").is_file()

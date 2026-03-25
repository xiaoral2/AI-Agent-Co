"""Unit tests for orchestrator_loop helpers, FSM, and failure classification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.orchestrator_loop import (
    StubExecutor,
    acquire_code_file_locks,
    all_relevant_tasks_done,
    apply_orchestrator_closure,
    apply_orchestrator_failure_routing,
    classify_failure_type,
    release_code_file_locks,
    _check_global_retry_budget,
    _check_per_task_token_budget,
    _code_success_review_enabled,
    _decision_entry,
    _increment_global_retries,
    _maybe_rollback_after_code_failure,
    _record_usage_if_supported,
    _session_wall_clock_ok,
    _try_git_init,
    _try_git_snapshot,
)
from orchestrator.state_manager import empty_session
from orchestrator.types import ToolResult


def test_classify_success_path_review() -> None:
    r = ToolResult(success=False, error="success_path_review: x", payload={})
    assert classify_failure_type(r, {"type": "code"}) == "test_failure"


def test_classify_infra_llm_timeout() -> None:
    r = ToolResult(success=False, error="llm_error: boom", payload={})
    assert classify_failure_type(r, {"type": "code"}) == "infra_error"
    r2 = ToolResult(success=False, error="connection reset", payload={})
    assert classify_failure_type(r2, {"type": "code"}) == "infra_error"


def test_classify_pytest_and_test_task() -> None:
    assert classify_failure_type(
        ToolResult(success=False, error="pytest_failed", payload={}),
        {"type": "test"},
    ) == "test_failure"


def test_classify_syntax_from_logs() -> None:
    r = ToolResult(
        success=False,
        error="bad",
        logs="Traceback\nSyntaxError: invalid",
        payload={},
    )
    assert classify_failure_type(r, {"type": "code"}) == "syntax_error"


def test_classify_requirement_keywords() -> None:
    r = ToolResult(success=False, error="requirement mismatch", payload={})
    assert classify_failure_type(r, {"type": "code"}) == "requirement_mismatch"


def test_classify_review_report_dims() -> None:
    r = ToolResult(
        success=False,
        payload={
            "review_report": {
                "verdict": "request_changes",
                "dimensions": {"correctness": "fail", "requirement_alignment": "fail"},
            }
        },
    )
    assert classify_failure_type(r, {"type": "code"}) == "requirement_mismatch"


def test_classify_code_default_test_failure() -> None:
    r = ToolResult(success=False, error="x", logs="build failed", payload={})
    assert classify_failure_type(r, {"type": "code"}) == "test_failure"


def test_classify_unknown_defaults_test_failure() -> None:
    r = ToolResult(success=False, error="x", payload={})
    assert classify_failure_type(r, {"type": "design"}) == "test_failure"


def test_stub_executor() -> None:
    ex = StubExecutor()
    assert ex.execute({"id": "x"}).success
    assert ex.review({"id": "x"}).success


def test_record_usage_if_supported() -> None:
    ex = MagicMock()
    ex.record_tool_usage = MagicMock()
    r = ToolResult(success=True, payload={})
    _record_usage_if_supported(ex, r)
    ex.record_tool_usage.assert_called_once_with(r)


def test_record_usage_no_attr() -> None:
    _record_usage_if_supported(object(), ToolResult(success=True, payload={}))


def test_all_relevant_tasks_done_empty() -> None:
    s = empty_session()
    s["tasks"] = []
    assert all_relevant_tasks_done(s)


def test_all_relevant_tasks_done_mixed_revision() -> None:
    s = empty_session()
    s["project"]["approved_plan_revision_id"] = "rev-001"
    s["tasks"] = [
        {"id": "a", "plan_revision_id": "rev-001", "status": "done"},
        {"id": "b", "plan_revision_id": "rev-old", "status": "todo"},
    ]
    assert all_relevant_tasks_done(s)


def test_global_retry_budget() -> None:
    s = empty_session()
    assert _check_global_retry_budget(s)
    s.setdefault("policies", {})["budget_policy"] = {"max_retries_total": 2}
    s["budget_counters"]["retries_used_project"] = 2
    assert not _check_global_retry_budget(s)


def test_per_task_token_budget() -> None:
    s = empty_session()
    s["budget_limits"] = {"max_tokens_per_task": 100}
    t = {"tokens_used": 50}
    assert _check_per_task_token_budget(s, t)
    t["tokens_used"] = 100
    assert not _check_per_task_token_budget(s, t)


def test_increment_global_retries() -> None:
    s = empty_session()
    _increment_global_retries(s)
    assert s["budget_counters"]["retries_used_project"] == 1


def test_session_wall_clock() -> None:
    s = empty_session()
    assert _session_wall_clock_ok(s)
    import time

    s["budget_limits"] = {"session_max_duration_sec": 3600}
    s["project"]["session_started_epoch"] = time.time() - 10
    assert _session_wall_clock_ok(s)
    s["project"]["session_started_epoch"] = time.time() - 99999
    assert not _session_wall_clock_ok(s)


def test_code_success_review_enabled() -> None:
    s = empty_session()
    assert not _code_success_review_enabled(s, {"type": "test"})
    assert _code_success_review_enabled(s, {"type": "code", "needs_review": True})
    s.setdefault("policies", {})["review_policy"] = {"code_success_gate": True}
    assert _code_success_review_enabled(s, {"type": "code"})


def test_file_locks() -> None:
    s = empty_session()
    t1 = {"type": "code", "path_hints": ["src/a.py"]}
    assert acquire_code_file_locks(s, t1, "A")
    t2 = {"type": "code", "path_hints": ["src/a.py"]}
    assert not acquire_code_file_locks(s, t2, "B")
    release_code_file_locks(s, "A")
    assert acquire_code_file_locks(s, t2, "B")


def test_non_code_lock_noop() -> None:
    s = empty_session()
    assert acquire_code_file_locks(s, {"type": "test"}, "T")


def test_decision_entry() -> None:
    e = _decision_entry("x", "y", task_id="t1", k=1)
    assert e["decision"] == "x"
    assert e["context"]["task_id"] == "t1"
    assert e["context"]["k"] == 1


def test_maybe_rollback_calls_git(tmp_path: Path) -> None:
    s = empty_session()
    s.setdefault("policies", {})["git_policy"] = {"rollback_on_code_failure": True}
    s.setdefault("global", {})["last_good_commit_sha"] = "abc"
    t = {"type": "code"}
    with patch("xr_ai_co.workspace_git.rollback") as rb:
        _maybe_rollback_after_code_failure(s, tmp_path, t, "syntax_error")
        rb.assert_called_once_with(tmp_path, "abc")


def test_maybe_rollback_skipped_wrong_failure() -> None:
    s = empty_session()
    s.setdefault("policies", {})["git_policy"] = {"rollback_on_code_failure": True}
    with patch("xr_ai_co.workspace_git.rollback") as rb:
        _maybe_rollback_after_code_failure(s, Path("/tmp"), {"type": "code"}, "infra_error")
        rb.assert_not_called()


def test_try_git_init_swallows(tmp_path: Path) -> None:
    with patch("xr_ai_co.workspace_git.git_init", side_effect=RuntimeError("no git")):
        _try_git_init(tmp_path)


def test_try_git_snapshot_returns_none_on_error(tmp_path: Path) -> None:
    with patch("xr_ai_co.workspace_git.snapshot", side_effect=OSError("x")):
        assert _try_git_snapshot(tmp_path, "t", "m") is None


def test_apply_closure_marks_done(tmp_path: Path) -> None:
    s = empty_session()
    s["tasks"] = [
        {
            "id": "T1",
            "type": "code",
            "status": "in_progress",
            "plan_revision_id": "rev-001",
            "depends_on": [],
        }
    ]
    s["workers"] = [{"id": "coder_1", "role": "coder", "status": "busy"}]
    r = ToolResult(success=True, payload={})
    apply_orchestrator_closure(s, "T1", "coder_1", r, workspace=None)
    assert s["tasks"][0]["status"] == "done"
    assert s["workers"][0]["status"] == "idle"


def test_apply_closure_design_digest(tmp_path: Path) -> None:
    s = empty_session()
    s["tasks"] = [
        {
            "id": "D0",
            "type": "design",
            "status": "in_progress",
            "plan_revision_id": "rev-001",
            "depends_on": [],
            "design_notes": "API sketch",
        },
    ]
    s["workers"] = [{"id": "arch_1", "role": "architect", "status": "busy"}]
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "interface.md").write_text("# iface", encoding="utf-8")
    apply_orchestrator_closure(
        s, "D0", "arch_1", ToolResult(success=True, payload={}), workspace=tmp_path,
    )
    assert "D0" in (s["global"].get("design_digest") or "")
    assert s["global"].get("interface_digest")


def test_failure_route_max_retries_blocked() -> None:
    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 0}
    s["tasks"] = [
        {"id": "T1", "type": "code", "status": "in_progress", "retry_count": 0, "plan_revision_id": "rev-001"},
    ]
    s["workers"] = [{"id": "c1", "role": "coder", "status": "busy"}]
    apply_orchestrator_failure_routing(
        s, "T1", "c1", ToolResult(success=False, error="pytest", payload={}),
        executor=None, skip_reviewer=True,
    )
    assert s["project"]["status"] == "blocked"
    assert s["tasks"][0]["status"] == "failed"


def test_failure_requirement_mismatch_escalate() -> None:
    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 99}
    s["tasks"] = [
        {"id": "T1", "type": "code", "status": "in_progress", "retry_count": 0, "plan_revision_id": "rev-001"},
    ]
    s["workers"] = [{"id": "c1", "role": "coder", "status": "busy"}]
    apply_orchestrator_failure_routing(
        s,
        "T1",
        "c1",
        ToolResult(success=False, error="requirement mismatch", payload={}),
        skip_reviewer=True,
    )
    assert s["project"]["status"] == "blocked"


def test_failure_infra_retry() -> None:
    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 99}
    s["tasks"] = [
        {"id": "T1", "type": "code", "status": "in_progress", "retry_count": 0, "plan_revision_id": "rev-001"},
    ]
    s["workers"] = [{"id": "c1", "role": "coder", "status": "busy"}]
    apply_orchestrator_failure_routing(
        s, "T1", "c1", ToolResult(success=False, error="llm_error: timeout", payload={}),
        skip_reviewer=True,
    )
    assert s["tasks"][0]["status"] == "todo"


def test_failure_test_reroutes_code_dep() -> None:
    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 99}
    s["tasks"] = [
        {"id": "C1", "type": "code", "status": "done", "retry_count": 0, "plan_revision_id": "rev-001"},
        {
            "id": "T2",
            "type": "test",
            "status": "in_progress",
            "retry_count": 0,
            "plan_revision_id": "rev-001",
            "depends_on": ["C1"],
        },
    ]
    s["workers"] = [{"id": "t1", "role": "tester", "status": "busy"}]
    apply_orchestrator_failure_routing(
        s,
        "T2",
        "t1",
        ToolResult(success=False, error="pytest_failed", payload={}),
        skip_reviewer=True,
    )
    assert s["tasks"][0]["status"] == "todo"
    assert s["tasks"][1]["status"] == "todo"


def test_failure_with_mock_reviewer_updates_feedback() -> None:
    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 99}
    s["tasks"] = [
        {"id": "T1", "type": "code", "status": "in_progress", "retry_count": 0, "plan_revision_id": "rev-001"},
    ]
    s["workers"] = [{"id": "c1", "role": "coder", "status": "busy"}]

    class Ex:
        def review(self, task: dict) -> ToolResult:
            return ToolResult(
                success=True,
                payload={
                    "review_report": {
                        "verdict": "request_changes",
                        "feedback": "fix it",
                        "knowledge_entries": [{"tip": "a"}],
                        "failure_type": "syntax_error",
                    }
                },
            )

        def record_tool_usage(self, r: ToolResult) -> None:
            pass

    apply_orchestrator_failure_routing(
        s, "T1", "c1", ToolResult(success=False, error="bad", logs="SyntaxError", payload={}),
        executor=Ex(),
    )
    assert s["global"]["last_reviewer_feedback"] == "fix it"
    kb = s["global"].get("knowledge_base")
    assert isinstance(kb, list) and kb


def test_failure_reviewer_raises_logged() -> None:
    s = empty_session()
    s.setdefault("policies", {})["retry_policy"] = {"max_retries_per_task": 99}
    s["tasks"] = [
        {"id": "T1", "type": "code", "status": "in_progress", "retry_count": 0, "plan_revision_id": "rev-001"},
    ]
    s["workers"] = [{"id": "c1", "role": "coder", "status": "busy"}]

    class Bad:
        def review(self, task: dict) -> ToolResult:
            raise RuntimeError("boom")

    apply_orchestrator_failure_routing(
        s, "T1", "c1", ToolResult(success=False, error="x", payload={}),
        executor=Bad(),
    )
    assert s["tasks"][0]["status"] == "todo"

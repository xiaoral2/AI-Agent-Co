"""Reference control loop — §7.1.1 (hydrate → tick → execute → checkpoint).

Enhanced with:
  - §4.4 failure_type taxonomy (test_failure/syntax_error/requirement_mismatch/infra_error)
  - §4.4 test→coder routing (re-queue upstream code task on test failure)
  - §17.2 budget gate (max_retries_total + per-task token budget)
  - §6.5.1 last_pytest / last_reviewer_feedback propagation
  - §2.5.9 structured DecisionLog entries
  - §9.2+§9.3 workspace git integration (init/snapshot/rollback)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Protocol

from .scheduler_kernel import decision_input_from_session, scheduling_dispatch_tick, task_by_id
from .state_manager import StateManager, empty_session
from .types import ToolResult

log = logging.getLogger(__name__)


# ── §4.4 failure_type classification ─────────────────────────────────────────

def classify_failure_type(result: ToolResult, task: dict[str, Any]) -> str:
    """§4.4: classify a ToolResult failure into a normative failure_type token."""
    error = (result.error or "").lower()
    logs = (result.logs or "").lower()

    if "success_path_review" in error:
        return "test_failure"

    if "llm_error" in error or "timeout" in error or "connection" in error:
        return "infra_error"

    if task.get("type") == "test" or "pytest" in error:
        return "test_failure"

    if "syntax" in error or "import" in error or "parse" in error:
        if "SyntaxError" in (result.logs or "") or "ImportError" in (result.logs or ""):
            return "syntax_error"

    if "requirement" in error or "mismatch" in error:
        return "requirement_mismatch"

    review_report = result.payload.get("review_report") or {}
    if review_report.get("verdict") == "request_changes":
        dims = review_report.get("dimensions") or {}
        if dims.get("correctness") == "fail" and dims.get("requirement_alignment") == "fail":
            return "requirement_mismatch"

    if task.get("type") == "code":
        return "syntax_error" if ("syntax" in logs or "import" in logs) else "test_failure"

    return "test_failure"


# ── Protocols ────────────────────────────────────────────────────────────────

def _record_usage_if_supported(executor: Any, result: ToolResult) -> None:
    fn = getattr(executor, "record_tool_usage", None)
    if callable(fn):
        fn(result)


class TaskExecutor(Protocol):
    def execute(self, task: dict[str, Any]) -> ToolResult: ...
    def review(self, task: dict[str, Any]) -> ToolResult: ...
    def set_session(self, session: dict[str, Any]) -> None: ...


class StubExecutor:
    def execute(self, task: dict[str, Any]) -> ToolResult:
        _ = task
        return ToolResult(success=True, payload={"stub": True})

    def review(self, task: dict[str, Any]) -> ToolResult:
        _ = task
        return ToolResult(success=True, payload={"stub": True, "review_report": {"verdict": "approve"}})

    def set_session(self, session: dict[str, Any]) -> None:
        pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def all_relevant_tasks_done(session: dict[str, Any]) -> bool:
    approved = session["project"].get("approved_plan_revision_id")
    relevant = [t for t in session["tasks"] if t.get("plan_revision_id") == approved]
    if not relevant:
        return True
    return all(t.get("status") == "done" for t in relevant)


def _check_global_retry_budget(session: dict[str, Any]) -> bool:
    """§17.2: check max_retries_total across all tasks."""
    bc = session.get("budget_counters") or {}
    retries_used = int(bc.get("retries_used_project", 0))
    policies = session.get("policies") or {}
    budget_policy = policies.get("budget_policy") or {}
    max_retries_total = int(budget_policy.get("max_retries_total", 50))
    return retries_used < max_retries_total


def _check_per_task_token_budget(session: dict[str, Any], task: dict[str, Any]) -> bool:
    """§17.2: check max_tokens_per_task for this specific task."""
    limits = session.get("budget_limits") or {}
    max_per_task = limits.get("max_tokens_per_task")
    if max_per_task is None:
        return True
    used = int(task.get("tokens_used", 0))
    return used < int(max_per_task)


def _increment_global_retries(session: dict[str, Any]) -> None:
    bc = session.setdefault("budget_counters", {})
    bc["retries_used_project"] = int(bc.get("retries_used_project", 0)) + 1


def _session_wall_clock_ok(session: dict[str, Any]) -> bool:
    lim = session.get("budget_limits") or {}
    max_dur = lim.get("session_max_duration_sec")
    if max_dur is None:
        return True
    started = session.get("project", {}).get("session_started_epoch")
    if started is None:
        return True
    return (time.time() - float(started)) <= float(max_dur)


def _code_success_review_enabled(session: dict[str, Any], task: dict[str, Any]) -> bool:
    """§2.5.4 — optional success-path review before marking code tasks done."""
    if task.get("type") != "code":
        return False
    if task.get("needs_review"):
        return True
    rp = (session.get("policies") or {}).get("review_policy") or {}
    return bool(rp.get("code_success_gate"))


def acquire_code_file_locks(session: dict[str, Any], task: dict[str, Any], task_id: str) -> bool:
    """§9.4 — register path_hints (or whole workspace) for code / design tasks."""
    if task.get("type") not in ("code", "design"):
        return True
    paths = list(task.get("path_hints") or ["."])
    fl = session.setdefault("file_locks", {})
    for p in paths:
        holder = fl.get(p)
        if holder is not None and holder != task_id:
            return False
    for p in paths:
        fl[p] = task_id
    return True


def release_code_file_locks(session: dict[str, Any], task_id: str) -> None:
    fl = session.get("file_locks") or {}
    for k in list(fl.keys()):
        if fl[k] == task_id:
            del fl[k]


def _maybe_rollback_after_code_failure(
    session: dict[str, Any],
    workspace: Path | None,
    task: dict[str, Any],
    failure_type: str,
) -> None:
    if workspace is None or task.get("type") != "code":
        return
    gp = (session.get("policies") or {}).get("git_policy") or {}
    if not gp.get("rollback_on_code_failure"):
        return
    if failure_type not in ("syntax_error", "test_failure"):
        return
    good = (session.get("global") or {}).get("last_good_commit_sha")
    if not good:
        return
    try:
        from xr_ai_co.workspace_git import rollback

        rollback(workspace, good)
        log.info("git rollback to last good commit after code failure")
    except Exception as e:
        log.warning("git rollback skipped: %s", e)


def _decision_entry(
    decision: str,
    reason: str,
    *,
    task_id: str | None = None,
    failure_type: str | None = None,
    retry_count: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """§2.5.9: build a structured DecisionLog entry."""
    entry: dict[str, Any] = {"decision": decision, "reason": reason}
    ctx: dict[str, Any] = {}
    if task_id is not None:
        ctx["task_id"] = task_id
    if failure_type is not None:
        ctx["failure_type"] = failure_type
    if retry_count is not None:
        ctx["retry_count"] = retry_count
    ctx.update(extra)
    if ctx:
        entry["context"] = ctx
    return entry


# ── §9.2+§9.3 Git integration ───────────────────────────────────────────────

def _try_git_init(workspace: Path) -> None:
    """Initialize git in workspace if not already present."""
    try:
        from xr_ai_co.workspace_git import git_init
        git_init(workspace)
    except Exception as e:
        log.debug("git init skipped: %s", e)


def _try_git_snapshot(workspace: Path, task_id: str, message: str) -> str | None:
    """§9.3: snapshot workspace after green pytest / successful task."""
    try:
        from xr_ai_co.workspace_git import snapshot
        return snapshot(workspace, message, task_id=task_id)
    except Exception as e:
        log.debug("git snapshot skipped: %s", e)
        return None


# ── FSM transitions ─────────────────────────────────────────────────────────

def apply_orchestrator_closure(
    session: dict[str, Any],
    task_id: str,
    worker_id: str,
    result: ToolResult,
    workspace: Path | None = None,
) -> None:
    """§4.1.1 + §2.5.7 — success path → done."""
    StateManager.update_task_status(session, task_id, "done", owner=None)
    for w in session["workers"]:
        if w.get("id") == worker_id:
            w["status"] = "idle"

    StateManager.append_decision_log(session, [
        _decision_entry("task_done", "tool_success", task_id=task_id),
    ])

    task = task_by_id(session["tasks"], task_id)
    if task.get("type") == "design" and workspace is not None:
        g = session.setdefault("global", {})
        notes = (task.get("design_notes") or "").strip()
        line = f"[{task_id}] {notes}" if notes else f"[{task_id}] design complete"
        prev = (g.get("design_digest") or "").strip()
        g["design_digest"] = f"{prev}\n{line}".strip() if prev else line
        iface = workspace / "docs" / "interface.md"
        if iface.is_file():
            try:
                g["interface_digest"] = iface.read_text(encoding="utf-8")[:6000]
            except OSError:
                pass

    # §9.3: snapshot after green test
    if workspace is not None:
        if task.get("type") == "test":
            sha = _try_git_snapshot(workspace, task_id, f"done: {task_id} (tests green)")
            if sha:
                task["commit_sha"] = sha
                session.setdefault("global", {})["last_good_commit_sha"] = sha


def apply_orchestrator_failure_routing(
    session: dict[str, Any],
    task_id: str,
    worker_id: str,
    result: ToolResult,
    executor: TaskExecutor | None = None,
    *,
    workspace: Path | None = None,
    skip_reviewer: bool = False,
) -> None:
    """§4.1.1 + §4.4 — failure routing with failure_type taxonomy."""
    t = task_by_id(session["tasks"], task_id)
    failure_type = classify_failure_type(result, t)
    t["retry_count"] = int(t.get("retry_count", 0)) + 1
    t["owner"] = None
    t["last_failure_type"] = failure_type
    _increment_global_retries(session)

    for w in session["workers"]:
        if w.get("id") == worker_id:
            w["status"] = "idle"

    max_r = int(session.get("policies", {}).get("retry_policy", {}).get("max_retries_per_task", 8))

    # §2.5.9: log the failure routing decision
    StateManager.append_decision_log(session, [
        _decision_entry(
            "failure_route", f"failure_{failure_type}",
            task_id=task_id, failure_type=failure_type,
            retry_count=t["retry_count"],
        ),
    ])

    if t["retry_count"] > max_r or not _check_global_retry_budget(session):
        t["status"] = "failed"
        session["project"]["status"] = "blocked"
        StateManager.append_decision_log(session, [
            _decision_entry(
                "escalate", "max_retries_exceeded",
                task_id=task_id, failure_type=failure_type,
                retry_count=t["retry_count"],
            ),
        ])
        log.warning("task %s failed (%s) after %d retries (max %d) — project blocked",
                     task_id, failure_type, t["retry_count"], max_r)
        return

    # §4.4: run reviewer on failure for structured diagnosis
    if executor is not None and not skip_reviewer:
        try:
            review_result = executor.review(t)
            _record_usage_if_supported(executor, review_result)
            report = review_result.payload.get("review_report") or {}
            feedback = report.get("feedback", "")
            session.setdefault("global", {})["last_reviewer_feedback"] = feedback

            knowledge = report.get("knowledge_entries") or []
            if knowledge:
                kb = session.setdefault("global", {}).setdefault("knowledge_base", [])
                if isinstance(kb, list):
                    kb.extend(knowledge[:5])

            reviewer_ft = report.get("failure_type")
            if reviewer_ft and reviewer_ft in ("test_failure", "syntax_error", "requirement_mismatch", "infra_error"):
                failure_type = reviewer_ft
                t["last_failure_type"] = failure_type

            log.info("reviewer verdict for %s: %s (failure_type=%s)",
                     task_id, report.get("verdict", "n/a"), failure_type)
        except Exception as e:
            log.error("reviewer failed for task %s: %s", task_id, e)

    # §4.4: route by failure_type
    if failure_type == "requirement_mismatch":
        t["status"] = "failed"
        session["project"]["status"] = "blocked"
        StateManager.append_decision_log(session, [
            _decision_entry(
                "escalate", "requirement_mismatch_needs_replan",
                task_id=task_id, failure_type=failure_type,
            ),
        ])
        log.warning("task %s: requirement_mismatch — escalating for replan/CEO", task_id)
        return

    if failure_type == "infra_error":
        t["status"] = "todo"
        StateManager.append_decision_log(session, [
            _decision_entry(
                "retry_route", "infra_retry",
                task_id=task_id, failure_type=failure_type,
                retry_count=t["retry_count"],
            ),
        ])
        return

    _maybe_rollback_after_code_failure(session, workspace, t, failure_type)

    # test_failure or syntax_error: retry with test→coder routing
    if t.get("type") == "test":
        for dep_id in t.get("depends_on", []):
            try:
                dep = task_by_id(session["tasks"], dep_id)
                if dep.get("type") == "code" and dep.get("status") == "done":
                    dep["status"] = "todo"
                    dep["retry_count"] = int(dep.get("retry_count", 0)) + 1
                    dep["owner"] = None
                    _increment_global_retries(session)
                    StateManager.append_decision_log(session, [
                        _decision_entry(
                            "retry_route", "test_to_coder_fix",
                            task_id=dep_id, failure_type=failure_type,
                            retry_count=dep["retry_count"],
                        ),
                    ])
                    log.info("test→coder routing: re-queued %s for fix", dep_id)
            except KeyError:
                pass

    t["status"] = "todo"


# ── Main orchestrator ────────────────────────────────────────────────────────

class ReferenceOrchestrator:
    """Observe → schedule → act → persist (controller shape from review slides)."""

    def __init__(
        self,
        state_manager: StateManager,
        executor: TaskExecutor | None = None,
        workspace: Path | None = None,
    ) -> None:
        self.state_manager = state_manager
        self.executor = executor or StubExecutor()
        self.workspace = workspace

    def run(self, max_ticks: int = 512) -> None:
        # §9.2: git init in workspace on first run
        if self.workspace is not None:
            _try_git_init(self.workspace)

        # §2.2: log host metrics at start
        cpu = os.cpu_count()
        log.info("host: cpu_count=%s", cpu)

        for tick in range(max_ticks):
            session = self.state_manager.load()
            proj = session["project"]

            st = proj.get("status")
            if st == "paused":
                return
            if st != "executing":
                return

            if not _session_wall_clock_ok(session):
                proj["status"] = "blocked"
                StateManager.append_decision_log(session, [
                    _decision_entry("escalate", "session_max_duration_sec_exceeded"),
                ])
                self.state_manager.checkpoint(session)
                return

            if all_relevant_tasks_done(session):
                proj["status"] = "done"
                self.state_manager.checkpoint(session)
                return

            # §17.2 budget gate
            if not _check_global_retry_budget(session):
                proj["status"] = "blocked"
                StateManager.append_decision_log(session, [
                    _decision_entry("escalate", "max_retries_total_exceeded"),
                ])
                self.state_manager.checkpoint(session)
                return

            self.executor.set_session(session)

            inp = decision_input_from_session(session)
            out = scheduling_dispatch_tick(inp)
            StateManager.append_decision_log(session, out.decision_log_entries)

            if out.side_effect == "escalate":
                proj["status"] = "blocked"
                self.state_manager.checkpoint(session)
                return

            progressed = False
            for task_id, worker_id in out.worker_assignment:
                if worker_id is None:
                    StateManager.append_decision_log(session, [
                        _decision_entry("worker_cap_wait", "scaling_policy_cap", task_id=task_id),
                    ])
                    continue

                task = task_by_id(session["tasks"], task_id)

                # §17.2: per-task token budget check
                if not _check_per_task_token_budget(session, task):
                    StateManager.append_decision_log(session, [
                        _decision_entry("budget_exceeded", "max_tokens_per_task",
                                        task_id=task_id, tokens_used=task.get("tokens_used", 0)),
                    ])
                    task["status"] = "failed"
                    proj["status"] = "blocked"
                    self.state_manager.checkpoint(session)
                    return

                if not acquire_code_file_locks(session, task, task_id):
                    StateManager.append_decision_log(session, [
                        _decision_entry("file_lock_wait", "path_locked_by_other_task", task_id=task_id),
                    ])
                    continue

                locks_acquired = True
                try:
                    StateManager.update_task_status(session, task_id, "in_progress", owner=worker_id)
                    for w in session["workers"]:
                        if w.get("id") == worker_id:
                            w["status"] = "busy"

                    StateManager.append_decision_log(session, [
                        _decision_entry("execute_task", "dispatch",
                                        task_id=task_id, worker_id=worker_id,
                                        task_type=task.get("type")),
                    ])

                    log.info("tick %d: executing %s (type=%s) on %s",
                             tick, task_id, task.get("type"), worker_id)
                    result = self.executor.execute(task)

                    # §2.5.8: track token usage per task
                    usage = result.payload.get("usage")
                    if usage:
                        task["tokens_used"] = int(task.get("tokens_used", 0)) + \
                            int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))

                    # §6.5.1: propagate pytest results to global context
                    if result.payload.get("pytest") is not None:
                        session.setdefault("global", {})["last_pytest"] = result.payload["pytest"]

                    if result.success and _code_success_review_enabled(session, task):
                        rr = self.executor.review(task)
                        _record_usage_if_supported(self.executor, rr)
                        rep = rr.payload.get("review_report") or {}
                        if rep.get("verdict") != "approve":
                            session.setdefault("global", {})["last_reviewer_feedback"] = rep.get("feedback") or ""
                            synthetic = ToolResult(
                                success=False,
                                error="success_path_review: request_changes",
                                payload={"review_report": rep},
                                logs=rr.logs,
                            )
                            apply_orchestrator_failure_routing(
                                session, task_id, worker_id, synthetic, executor=self.executor,
                                workspace=self.workspace, skip_reviewer=True,
                            )
                        else:
                            apply_orchestrator_closure(
                                session, task_id, worker_id, result, workspace=self.workspace,
                            )
                    elif result.success:
                        apply_orchestrator_closure(
                            session, task_id, worker_id, result, workspace=self.workspace,
                        )
                    else:
                        apply_orchestrator_failure_routing(
                            session, task_id, worker_id, result, executor=self.executor,
                            workspace=self.workspace,
                        )
                    progressed = True
                finally:
                    if locks_acquired:
                        release_code_file_locks(session, task_id)

            self.state_manager.checkpoint(session)

            if not progressed and not out.worker_assignment:
                if out.side_effect is not None:
                    return
                continue


def main() -> None:
    """Reference loop demo with §2.5.1a-shaped tasks + StubExecutor.

    For production use ``xr-ai-co run`` / ``HarnessExecutor`` and validated plans.
    """
    path = Path("state/reference_session.json")
    sm = StateManager(path)
    if not path.exists():
        s = empty_session()
        s["tasks"] = [
            {
                "id": "T1",
                "type": "code",
                "description": "Demo code task (reference harness)",
                "status": "todo",
                "depends_on": [],
                "owner": None,
                "retry_count": 0,
                "plan_revision_id": "rev-001",
                "priority": "normal",
                "input": "demo",
                "output": "placeholder",
                "constraints": "none",
                "acceptance_criteria": "stub executor marks done",
                "test_plan": "see sibling test task",
                "path_hints": ["."],
            },
            {
                "id": "T2",
                "type": "test",
                "description": "Demo test task (reference harness)",
                "status": "todo",
                "depends_on": ["T1"],
                "owner": None,
                "retry_count": 0,
                "plan_revision_id": "rev-001",
                "priority": "normal",
                "input": "T1",
                "output": "stub pass",
                "constraints": "none",
                "acceptance_criteria": "stub executor marks done",
                "test_plan": "pytest tests/ (not run in stub demo)",
                "verification": {"kind": "pytest", "paths": ["tests/"]},
            },
        ]
        sm.persist(s)
    ReferenceOrchestrator(sm).run()


if __name__ == "__main__":  # pragma: no cover
    main()

"""§11 CLI — natural language mission → plan → CEO gate → orchestrator loop.

Supports:
  - LLM-backed and template-only modes via --config / env
  - §7.2 CEO interactive choices after escalation (modify_plan/continue/abort)
  - §6.7 resume from checkpoint (crash recovery)
  - §2.5.8 artifact lineage propagation
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from orchestrator.orchestrator_loop import ReferenceOrchestrator
from orchestrator.state_manager import StateManager

from xr_ai_co.config import AppConfig, load_config
from xr_ai_co.harness_executor import HarnessExecutor
from xr_ai_co.llm import LLMProvider
from xr_ai_co.plan_validate import validate_plan_tasks
from xr_ai_co.knowledge_store import load_kb_into_session, persist_kb_from_session
from xr_ai_co.session_validate import validate_session_shape
from xr_ai_co.session_builder import (
    build_session,
    ceo_approve,
    ceo_continue,
    ceo_pause,
    merge_replan_tasks,
)

log = logging.getLogger(__name__)


def _env_resume_refresh_config() -> bool:
    v = os.environ.get("XR_AI_CO_RESUME_REFRESH_CONFIG", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _build_llm(config: AppConfig) -> LLMProvider | None:
    if config.llm.api_key:
        return LLMProvider(config.llm)
    return None


def executive_report_json(session: dict) -> dict:
    """§7.2 minimum JSON shape for blocked / failed runs."""
    proj = session["project"]
    tasks = session["tasks"]
    failed = [t for t in tasks if t.get("status") in ("failed",)]

    ft = "unknown"
    if failed:
        ft = failed[0].get("last_failure_type", "unknown")
        if ft == "unknown" and any(t.get("type") == "test" for t in failed):
            ft = "test_failure"

    tid = failed[0]["id"] if failed else None
    return {
        "event": "escalate" if proj.get("status") == "blocked" else "status",
        "project_id": proj.get("id"),
        "task_id": tid,
        "project_status": proj.get("status"),
        "failure_type": ft,
        "reason": _failure_reason(ft),
        "attempts": failed[0].get("retry_count") if failed else 0,
        "max_attempts": session.get("policies", {}).get("retry_policy", {}).get("max_retries_per_task"),
        "suggested_actions": ["modify_plan", "continue", "abort"],
        "last_pytest": (session.get("global") or {}).get("last_pytest"),
    }


def _set_design_digest(session: dict, tasks: list[Any]) -> None:
    """Lightweight plan summary for §6.5 global context."""
    lines: list[str] = []
    for t in tasks:
        desc = (t.get("description") or "")[:160]
        lines.append(f"- {t['id']} ({t['type']}): {desc}")
    session.setdefault("global", {})["design_digest"] = "\n".join(lines) if lines else ""


def ceo_status_summary(session: dict[str, Any]) -> dict[str, Any]:
    """§2.2 — CEO-facing checkpoint snapshot (machine-readable core)."""
    proj = session.get("project") or {}
    tasks = session.get("tasks") or []
    approved = proj.get("approved_plan_revision_id")
    rel = [t for t in tasks if t.get("plan_revision_id") == approved] if approved else list(tasks)
    by_s: dict[str, int] = {}
    for t in rel:
        st = str(t.get("status", "?"))
        by_s[st] = by_s.get(st, 0) + 1
    failed_ids = [t["id"] for t in rel if t.get("status") == "failed"]
    in_prog = [t["id"] for t in rel if t.get("status") == "in_progress"]
    lp = (session.get("global") or {}).get("last_pytest") or {}
    return {
        "project_id": proj.get("id"),
        "project_status": proj.get("status"),
        "approved_plan_revision_id": approved,
        "relevant_task_count": len(rel),
        "tasks_by_status": by_s,
        "failed_task_ids": failed_ids,
        "in_progress_task_ids": in_prog,
        "budget_counters": session.get("budget_counters") or {},
        "budget_limits": session.get("budget_limits") or {},
        "workers": [
            {"id": w.get("id"), "role": w.get("role"), "status": w.get("status")}
            for w in session.get("workers") or []
        ],
        "last_pytest_returncode": lp.get("returncode"),
    }


def cmd_status(args: argparse.Namespace) -> int:
    """Print §2.2 status summary for a session file."""
    config = load_config(args.config)
    root = Path.cwd()
    sd = args.state_dir or config.state_dir
    state_path = (root / sd / f"{args.session_id}.json").resolve()
    if not state_path.exists():
        print(f"error: no checkpoint at {state_path}", file=sys.stderr)
        return 2
    session = StateManager(state_path).load()
    issues = validate_session_shape(session)
    summary = ceo_status_summary(session)
    if getattr(args, "json", False):
        print(json.dumps({"validation_issues": issues, "summary": summary}, indent=2, ensure_ascii=False))
        return 0
    if issues:
        print("— Validation warnings —", file=sys.stderr)
        for x in issues:
            print(f"  - {x}", file=sys.stderr)
        print(file=sys.stderr)
    print("— Session status (§2.2) —")
    print(f"  project: {summary['project_id']}  status: {summary['project_status']}")
    print(f"  approved_plan_revision_id: {summary['approved_plan_revision_id']!r}")
    print(f"  relevant tasks: {summary['relevant_task_count']}  by status: {summary['tasks_by_status']}")
    if summary["failed_task_ids"]:
        print(f"  failed: {summary['failed_task_ids']}")
    if summary["in_progress_task_ids"]:
        print(f"  in_progress: {summary['in_progress_task_ids']}")
    print(f"  budget_counters: {summary['budget_counters']}")
    if summary["workers"]:
        print(f"  workers ({len(summary['workers'])}):", ", ".join(f"{w['id']}:{w.get('status')}" for w in summary["workers"][:8]))
    rc = summary.get("last_pytest_returncode")
    if rc is not None:
        print(f"  last_pytest returncode: {rc}")
    return 0


def _failure_reason(ft: str) -> str:
    return {
        "test_failure": "tests_failed",
        "syntax_error": "syntax_or_import_error",
        "requirement_mismatch": "requirement_mismatch_needs_replan",
        "infra_error": "infrastructure_error",
    }.get(ft, "blocked_or_retries")


def _handle_blocked_interactive(
    session: dict,
    sm: StateManager,
    config: AppConfig,
    llm: LLMProvider | None,
    workspace: Path,
    profile: str,
    max_ticks: int,
    state_dir: Path,
) -> int:
    """§7.2: present CEO choices after escalation and act on them."""
    report = executive_report_json(session)
    print("\n— Executive report (§7.2) —")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    print("\nCEO choices:")
    print("  [m] modify_plan — replan with new instructions")
    print("  [c] continue    — reset failed tasks and retry")
    print("  [a] abort       — cancel the mission")
    print()

    try:
        choice = input("Choose [m/c/a]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "a"

    if choice in ("a", "abort"):
        session["project"]["status"] = "cancelled"
        sm.checkpoint(session)
        print("mission cancelled.")
        return 1

    if choice in ("c", "continue"):
        ceo_continue(session)
        sm.checkpoint(session)
        print("resuming execution (failed tasks reset)...")
        executor = HarnessExecutor(workspace, profile, config=config, llm=llm, session=session)
        orch = ReferenceOrchestrator(sm, executor=executor, workspace=workspace)
        orch.run(max_ticks=max_ticks)
        return _check_final(sm, llm, state_dir=state_dir)

    if choice in ("m", "modify", "modify_plan"):
        feedback = input("CEO feedback for replan: ").strip()
        if not feedback:
            print("no feedback provided, aborting.")
            return 1

        from tools.planner_tool import plan_tasks

        mission = (session.get("global") or {}).get("requirements_summary", "")
        new_mission = f"{mission}\n\nCEO feedback: {feedback}"
        new_tasks, new_profile = plan_tasks(
            new_mission, session, config, llm=llm,
        )
        try:
            validate_plan_tasks(new_tasks)
        except ValueError as e:
            print(f"replan validation failed: {e}", file=sys.stderr)
            return 2

        rev = merge_replan_tasks(session, new_tasks)
        _set_design_digest(session, new_tasks)
        print(f"\n— New plan (revision {rev}, awaiting APPROVE) —")
        print(json.dumps(new_tasks, indent=2, ensure_ascii=False))
        ans = input("APPROVE new plan? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            print("replan rejected.")
            return 1
        ceo_approve(session)
        session.setdefault("global", {})["requirements_summary"] = new_mission.strip()
        session.setdefault("global", {})["planner_profile"] = new_profile
        sm.checkpoint(session)
        print("executing new plan...")
        executor = HarnessExecutor(workspace, new_profile, config=config, llm=llm, session=session)
        orch = ReferenceOrchestrator(sm, executor=executor, workspace=workspace)
        orch.run(max_ticks=max_ticks)
        return _check_final(sm, llm, state_dir=state_dir)

    print(f"unknown choice: {choice!r}")
    return 1


def _check_final(
    sm: StateManager,
    llm: LLMProvider | None,
    *,
    state_dir: Path | None = None,
) -> int:
    final = sm.load()
    if state_dir is not None:
        persist_kb_from_session(final, state_dir)
    ps = final["project"].get("status")
    if ps == "done":
        print("OK — project status: done")
        if llm:
            u = llm.cumulative_usage
            print(f"LLM usage — prompt: {u.prompt_tokens}, completion: {u.completion_tokens}, total: {u.total_tokens}")
        return 0
    if ps == "blocked":
        report = executive_report_json(final)
        print("— Executive report (§7.2) —")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    if ps == "cancelled":
        print("mission cancelled.")
        return 1
    print(f"finished with project status: {ps!r}", file=sys.stderr)
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    llm = _build_llm(config)

    mission = args.mission_text if args.mission_text else " ".join(args.mission)
    if not mission.strip():
        print("error: mission text is empty", file=sys.stderr)
        return 2

    root = Path.cwd()
    ws_name = args.workspace or config.workspace
    workspace = (root / ws_name).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    sd = args.state_dir or config.state_dir
    state_path = (root / sd / f"{args.session_id}.json").resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)

    from tools.planner_tool import plan_tasks
    from xr_ai_co.pm_clarification import run_pm_clarification_loop

    auto = args.yes
    wants_pm = (config.pm.clarification_before_plan or getattr(args, "clarify", False)) and not auto
    if wants_pm:
        mission = run_pm_clarification_loop(mission, config, llm)

    session_stub = {"global": {}, "project": {"status": "planning"}, "tasks": [], "workers": []}
    session_stub["global"]["requirements_summary"] = mission
    tasks, profile = plan_tasks(
        mission, session_stub, config, llm=llm, plan_revision_id=args.revision,
    )

    try:
        validate_plan_tasks(tasks)
    except ValueError as e:
        print(f"plan validation failed: {e}", file=sys.stderr)
        return 2

    if args.plan_only:
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
        return 0

    session = build_session(mission, tasks, profile, auto_approve=auto)

    _apply_config_policies(session, config)
    _set_design_digest(session, tasks)
    load_kb_into_session(session, state_path.parent)

    if not auto:
        print("— Plan (awaiting CEO APPROVE) —")
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
        ans = input("APPROVE plan? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            print("aborted (no approval).")
            return 1
        ceo_approve(session)

    mode = "LLM" if llm else "template"
    log.info("starting orchestrator — mode=%s, workspace=%s, state=%s", mode, workspace, state_path)

    sm = StateManager(state_path)
    sm.persist(session)

    executor = HarnessExecutor(workspace, profile, config=config, llm=llm, session=session)
    orch = ReferenceOrchestrator(sm, executor=executor, workspace=workspace)
    orch.run(max_ticks=args.max_ticks)

    final = sm.load()
    ps = final["project"].get("status")
    state_dir = state_path.parent
    blocked_interactive = (
        (not auto)
        or getattr(args, "blocked_interactive", False)
        or (os.environ.get("XR_AI_CO_BLOCKED_INTERACTIVE", "").strip() not in ("", "0", "false", "no"))
    )

    if ps == "done":
        return _check_final(sm, llm, state_dir=state_dir)

    if ps == "blocked" and blocked_interactive:
        return _handle_blocked_interactive(
            final, sm, config, llm, workspace, profile, args.max_ticks, state_dir,
        )

    return _check_final(sm, llm, state_dir=state_dir)


def cmd_resume(args: argparse.Namespace) -> int:
    """§6.7: resume from existing checkpoint."""
    config = load_config(args.config)
    llm = _build_llm(config)

    root = Path.cwd()
    sd = args.state_dir or config.state_dir
    state_path = (root / sd / f"{args.session_id}.json").resolve()

    if not state_path.exists():
        print(f"error: no checkpoint found at {state_path}", file=sys.stderr)
        return 2

    sm = StateManager(state_path)
    session = sm.load()
    ps = session["project"].get("status")
    state_dir = state_path.parent

    if getattr(args, "refresh_config", False) or _env_resume_refresh_config():
        _apply_config_policies(session, config)
        sm.checkpoint(session)

    load_kb_into_session(session, state_dir)
    sm.checkpoint(session)

    ws_name = args.workspace or config.workspace
    workspace = (root / ws_name).resolve()

    profile = "generic"
    g = session.get("global") or {}
    rs = g.get("requirements_summary", "")
    if "rate" in rs.lower() and "limit" in rs.lower():
        profile = "rate_limiter"

    if ps == "blocked" and not args.yes:
        return _handle_blocked_interactive(
            session, sm, config, llm, workspace, profile, args.max_ticks, state_dir,
        )

    if ps == "blocked" and args.yes:
        ceo_continue(session)
        sm.checkpoint(session)

    if ps == "paused":
        session["project"]["status"] = "executing"
        sm.checkpoint(session)
        ps = "executing"

    if ps in ("done", "cancelled"):
        print(f"session already {ps}.")
        return 0 if ps == "done" else 1

    executor = HarnessExecutor(workspace, profile, config=config, llm=llm, session=session)
    orch = ReferenceOrchestrator(sm, executor=executor, workspace=workspace)
    orch.run(max_ticks=args.max_ticks)

    return _check_final(sm, llm, state_dir=state_dir)


def _apply_config_policies(session: dict, config: AppConfig) -> None:
    cp = config.policies
    sp = session.setdefault("policies", {})
    for key in (
        "retry_policy",
        "scaling_policy",
        "parallelism_policy",
        "scheduler_policy",
        "sla_policy",
        "failure_policy",
        "review_policy",
        "git_policy",
    ):
        val = getattr(cp, key, None)
        if val:
            sp.setdefault(key, {}).update(val)
    sp.setdefault("budget_policy", {})["max_retries_total"] = config.budget.max_retries_total

    if config.clamp_code_tasks_to_host:
        sp["clamp_code_tasks_to_host"] = True

    session["budget_limits"] = {
        "max_tokens_per_task": config.budget.max_tokens_per_task,
        "max_tokens_per_session": config.budget.max_tokens_per_session,
        "max_retries_total": config.budget.max_retries_total,
    }
    if config.budget.max_cost_per_project is not None:
        session["budget_limits"]["max_cost_per_project"] = config.budget.max_cost_per_project
    if config.llm.session_max_duration_sec is not None:
        session["budget_limits"]["session_max_duration_sec"] = float(config.llm.session_max_duration_sec)
    session["decision_log_max_entries"] = int(config.decision_log_max_entries)


def cmd_pause(args: argparse.Namespace) -> int:
    """§6.7 — mark session paused so the next orchestrator run exits immediately."""
    config = load_config(args.config)
    root = Path.cwd()
    sd = args.state_dir or config.state_dir
    state_path = (root / sd / f"{args.session_id}.json").resolve()
    if not state_path.exists():
        print(f"error: no checkpoint found at {state_path}", file=sys.stderr)
        return 2
    sm = StateManager(state_path)
    session = sm.load()
    before = session["project"].get("status")
    ceo_pause(session)
    sm.checkpoint(session)
    after = session["project"].get("status")
    if before != "executing":
        print(f"session status unchanged: {after!r} (pause only applies when executing).")
    else:
        print("session status: paused (use `resume` to continue).")
    return 0


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="xr-ai-co", description="XR-AI-Co harness CLI (Mode 1)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # run subcommand
    r = sub.add_parser("run", help="Run mission end-to-end")
    r.add_argument("mission", nargs="*", help='Natural language mission e.g. build a rate limiter')
    r.add_argument("--text", dest="mission_text", default=None, help="Mission as one string")
    r.add_argument("--config", default=None, help="Path to xr_ai_co.yaml config file")
    r.add_argument("--workspace", default=None, help="Workspace root (§9)")
    r.add_argument("--state-dir", default=None, help="Checkpoint directory")
    r.add_argument("--session-id", default="default", help="Session file basename without .json")
    r.add_argument("--revision", default="rev-001", help="plan_revision_id for this run")
    r.add_argument("-y", "--yes", action="store_true", help="Auto-approve plan (non-interactive)")
    r.add_argument(
        "--clarify",
        action="store_true",
        help="§2.5.6 PM clarification Q&A before planning (interactive; ignored with -y)",
    )
    r.add_argument(
        "--blocked-interactive",
        action="store_true",
        help="After blocked, prompt for CEO choices even with -y (or set XR_AI_CO_BLOCKED_INTERACTIVE)",
    )
    r.add_argument("--plan-only", action="store_true", help="Print JSON tasks and exit")
    r.add_argument("--max-ticks", type=int, default=512, help="Orchestrator iteration cap")
    r.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    r.set_defaults(func=cmd_run)

    # resume subcommand (§6.7)
    res = sub.add_parser("resume", help="Resume from existing checkpoint (§6.7)")
    res.add_argument("--config", default=None, help="Path to xr_ai_co.yaml config file")
    res.add_argument("--workspace", default=None, help="Workspace root")
    res.add_argument("--state-dir", default=None, help="Checkpoint directory")
    res.add_argument("--session-id", default="default", help="Session file basename")
    res.add_argument("-y", "--yes", action="store_true", help="Auto-continue on blocked")
    res.add_argument(
        "--refresh-config",
        action="store_true",
        help="Re-apply xr_ai_co.yaml budget/policies (or set XR_AI_CO_RESUME_REFRESH_CONFIG=1)",
    )
    res.add_argument("--max-ticks", type=int, default=512, help="Orchestrator iteration cap")
    res.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    res.set_defaults(func=cmd_resume)

    pa = sub.add_parser("pause", help="Pause session (§6.7) — set project status to paused")
    pa.add_argument("--config", default=None, help="Path to xr_ai_co.yaml config file")
    pa.add_argument("--state-dir", default=None, help="Checkpoint directory")
    pa.add_argument("--session-id", default="default", help="Session file basename")
    pa.set_defaults(func=cmd_pause)

    st = sub.add_parser("status", help="§2.2 Print CEO-oriented checkpoint summary")
    st.add_argument("--config", default=None, help="Path to xr_ai_co.yaml (for state-dir default)")
    st.add_argument("--state-dir", default=None, help="Checkpoint directory")
    st.add_argument("--session-id", default="default", help="Session file basename")
    st.add_argument("--json", action="store_true", help="Emit JSON (includes validation_issues)")
    st.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    if getattr(args, "verbose", False):
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()

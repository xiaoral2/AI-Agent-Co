"""Unified persistence + task status writes used by the orchestrator (§4.1.1, §6.6).

Tools and workers return ToolResult only; they do not call these APIs — the orchestrator does.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def empty_session() -> dict[str, Any]:
    """Minimal JSON-serializable session blob for demos/tests."""
    return {
        "project": {
            "id": "P1",
            "status": "executing",
            "approved_plan_revision_id": "rev-001",
        },
        "tasks": [],
        "workers": [],
        "file_locks": {},
        "budget_counters": {"tokens_used_session": 0, "retries_used_project": 0, "estimated_cost_usd": 0.0},
        "budget_limits": {},
        "policies": {
            "scheduler_policy": {},
            "sla_policy": {},
            "scaling_policy": {"coder": 4, "tester": 4, "architect": 4},
            "parallelism_policy": {},
        },
        "decision_log": [],
        "global": {
            "requirements_summary": "",
            "last_pytest": None,
            "last_reviewer_feedback": None,
        },
    }


class StateManager:
    """load_state / persist_state / update_task_status — single place for authoritative mutations."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            session = empty_session()
            self.persist(session)
            return session
        try:
            with self.path.open(encoding="utf-8") as f:
                raw = f.read()
            session = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error("invalid JSON in checkpoint %s: %s", self.path, e)
            raise RuntimeError(
                f"checkpoint is not valid JSON: {self.path}\n"
                "Repair the file or remove it to start a fresh session."
            ) from e
        if not isinstance(session, dict):
            raise RuntimeError(f"checkpoint root must be a JSON object: {self.path}")
        try:
            from xr_ai_co.session_validate import validate_session_shape

            for msg in validate_session_shape(session):
                log.warning("checkpoint shape: %s (%s)", msg, self.path)
        except Exception as e:
            log.debug("session_validate skipped: %s", e)
        return session

    def persist(self, session: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)

    def checkpoint(self, session: dict[str, Any]) -> None:
        """Alias — §6.6 checkpoint after material transitions."""
        self.persist(session)

    @staticmethod
    def update_task_status(
        session: dict[str, Any],
        task_id: str,
        new_status: str,
        **extra: Any,
    ) -> None:
        for t in session["tasks"]:
            if t["id"] == task_id:
                t["status"] = new_status
                for k, v in extra.items():
                    t[k] = v
                return
        raise KeyError(f"unknown task_id: {task_id}")

    @staticmethod
    def append_decision_log(session: dict[str, Any], entries: list[dict[str, Any]]) -> None:
        dl = session.setdefault("decision_log", [])
        dl.extend(entries)
        mx = session.get("decision_log_max_entries")
        if mx is None:
            mx = 500
        mx = int(mx)
        if mx > 0 and len(dl) > mx:
            del dl[: len(dl) - mx]

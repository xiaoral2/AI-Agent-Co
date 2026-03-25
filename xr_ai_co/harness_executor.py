"""§6.3 TaskExecutor — dispatches to LLM or template tools with §17.2 budget tracking."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from orchestrator.types import ToolResult
from tools.architect_tool import design_stub, design_with_llm
from tools.coder_tool import code_with_llm, code_with_template
from tools.reviewer_tool import review_stub, review_with_llm
from tools.tester_tool import test_with_existing, test_with_llm
from xr_ai_co.config import AppConfig
from xr_ai_co.llm import LLMProvider

log = logging.getLogger(__name__)

# Conservative blended rate when max_cost_per_project is set but YAML omits explicit rate.
_DEFAULT_USD_PER_1K_TOKENS = 0.003


class HarnessExecutor:
    """Unified executor that routes code/test/review tasks to LLM or template tools.

    §17.2: checks budget_counters before each LLM call; updates after.
    """

    def __init__(
        self,
        workspace: Path,
        profile: str,
        *,
        config: AppConfig | None = None,
        llm: LLMProvider | None = None,
        session: dict[str, Any] | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.profile = profile
        self.config = config
        self.llm = llm
        self._session: dict[str, Any] = session or {}

    @property
    def use_llm(self) -> bool:
        return self.llm is not None and bool(self.config and self.config.llm.api_key)

    def set_session(self, session: dict[str, Any]) -> None:
        """Update the live session reference (called by orchestrator each tick)."""
        self._session = session

    def execute(self, task: dict[str, Any]) -> ToolResult:
        kind = task.get("type")
        if kind == "code":
            result = self._coder(task)
        elif kind == "test":
            result = self._tester(task)
        elif kind == "design":
            result = self._architect(task)
        else:
            result = ToolResult(success=False, error=f"unsupported Task.type: {kind!r}")
        self._stamp_lineage(result, task)
        return result

    def _stamp_lineage(self, result: ToolResult, task: dict[str, Any]) -> None:
        """§2.5.8: ensure plan_revision_id + retry_count in payload for traceability."""
        result.payload.setdefault("task_id", task.get("id"))
        result.payload.setdefault("plan_revision_id", task.get("plan_revision_id"))
        result.payload.setdefault("retry_count", task.get("retry_count", 0))

    def review(self, task: dict[str, Any]) -> ToolResult:
        """Run reviewer on the task (called by orchestrator on failure path)."""
        if self.use_llm:
            return review_with_llm(
                task, self._session, self.workspace, self.llm,  # type: ignore[arg-type]
                mission=self._mission(),
            )
        return review_stub(task, self._session)

    def _budget_ok(self, task: dict[str, Any]) -> bool:
        """§17.2: pre-dispatch budget check."""
        if not self.config:
            return True
        bc = self._session.get("budget_counters") or {}
        bl = self.config.budget

        used = int(bc.get("tokens_used_session", 0))
        if used >= bl.max_tokens_per_session:
            log.warning("budget exceeded: tokens_used_session=%d >= max=%d", used, bl.max_tokens_per_session)
            return False

        retries_total = int(bc.get("retries_used_project", 0))
        if retries_total >= bl.max_retries_total:
            log.warning("budget exceeded: retries_used_project=%d >= max=%d", retries_total, bl.max_retries_total)
            return False

        if bl.max_cost_per_project is not None:
            spent = float(bc.get("estimated_cost_usd", 0) or 0)
            if spent >= float(bl.max_cost_per_project):
                log.warning("budget exceeded: estimated_cost_usd=%.4f >= max=%s", spent, bl.max_cost_per_project)
                return False

        return True

    def record_tool_usage(self, result: ToolResult) -> None:
        """Apply payload.usage to session counters (e.g. success-path review, any LLM tool)."""
        self._update_budget(result)

    def _update_budget(self, result: ToolResult) -> None:
        """§17.2: post-call budget counter update."""
        usage = result.payload.get("usage")
        if usage and self._session:
            bc = self._session.setdefault("budget_counters", {})
            pt = int(usage.get("prompt_tokens", 0))
            ct = int(usage.get("completion_tokens", 0))
            bc["tokens_used_session"] = int(bc.get("tokens_used_session", 0)) + pt + ct
            if self.config and self.config.budget.max_cost_per_project is not None:
                rate = self.config.budget.usd_per_1k_total_tokens
                if rate is None:
                    rate = _DEFAULT_USD_PER_1K_TOKENS
                delta = (pt + ct) / 1000.0 * float(rate)
                bc["estimated_cost_usd"] = float(bc.get("estimated_cost_usd", 0) or 0) + delta

    def _mission(self) -> str:
        g = self._session.get("global") or {}
        return g.get("requirements_summary", "")

    def _architect(self, task: dict[str, Any]) -> ToolResult:
        if self.use_llm and self._budget_ok(task):
            result = design_with_llm(
                task, self._session, self.workspace, self.llm,  # type: ignore[arg-type]
                mission=self._mission(),
            )
            self._update_budget(result)
            if result.success:
                return result
            log.info("LLM architect failed, falling back to stub: %s", result.error)
        return design_stub(task, self.workspace)

    def _coder(self, task: dict[str, Any]) -> ToolResult:
        if self.use_llm and self._budget_ok(task):
            result = code_with_llm(
                task, self._session, self.workspace, self.llm,  # type: ignore[arg-type]
                mission=self._mission(),
            )
            self._update_budget(result)
            if result.success:
                return result
            log.info("LLM coder failed, falling back to template: %s", result.error)

        return code_with_template(task, self.workspace, self.profile)

    def _pytest_timeout(self) -> float | None:
        if not self.config:
            return 120.0
        return float(self.config.llm.task_timeout_sec)

    def _tester(self, task: dict[str, Any]) -> ToolResult:
        to = self._pytest_timeout()
        if self.use_llm and self._budget_ok(task):
            result = test_with_llm(
                task, self._session, self.workspace, self.llm,  # type: ignore[arg-type]
                mission=self._mission(),
                pytest_timeout_sec=to,
            )
            self._update_budget(result)
            return result

        return test_with_existing(task, self.workspace, pytest_timeout_sec=to)

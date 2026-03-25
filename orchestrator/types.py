"""Typed shapes for the reference harness (informative — bind to your codebase).

Normative field meanings: design_notes/ai-company-spec.md §3.2, §3.3, §6.4.1, §16.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


SideEffect = Literal[None, "escalate", "blocked"]


@dataclass
class DecisionInput:
    """§6.4.1 — one scheduling tick."""

    tasks: list[dict[str, Any]]
    project: dict[str, Any]
    budget_counters: dict[str, Any]
    budget_limits: dict[str, Any]
    workers: list[dict[str, Any]]
    now: datetime
    policies: dict[str, Any]
    file_locks: dict[str, str]
    in_flight_tasks: list[dict[str, Any]]
    effective_max_concurrent_code_tasks: int = 1


@dataclass
class DecisionOutput:
    """§6.4.1 — scheduler result for one tick."""

    selected_tasks: list[dict[str, Any]]
    worker_assignment: list[tuple[str, str | None]]
    decision_log_entries: list[dict[str, Any]]
    side_effect: SideEffect = None


@dataclass
class ToolResult:
    """§6.3.1 — minimal portable result."""

    success: bool
    error: str | None = None
    logs: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)

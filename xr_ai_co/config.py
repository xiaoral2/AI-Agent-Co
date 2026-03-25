"""§14 Config — YAML loader with env-var fallback and §17 defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    llm_call_timeout_sec: float = 120.0
    max_retries_transient_api: int = 3
    task_timeout_sec: float = 600.0
    session_max_duration_sec: float | None = None


@dataclass
class BudgetConfig:
    max_tokens_per_task: int = 200_000
    max_tokens_per_session: int = 2_000_000
    max_cost_per_project: float | None = None
    max_retries_total: int = 50
    # When max_cost_per_project is set, accumulate USD estimate as tokens × (rate / 1000).
    usd_per_1k_total_tokens: float | None = None


@dataclass
class PmConfig:
    """§2.5.6 — requirements clarification before planning."""

    clarification_before_plan: bool = False


@dataclass
class PlannerConfig:
    """Stub / template planner extras."""

    include_design_task: bool = False


@dataclass
class PolicyConfig:
    retry_policy: dict[str, Any] = field(default_factory=lambda: {"max_retries_per_task": 5})
    scaling_policy: dict[str, Any] = field(
        default_factory=lambda: {"coder": 4, "tester": 4, "reviewer": 2, "architect": 4}
    )
    parallelism_policy: dict[str, Any] = field(default_factory=lambda: {"max_concurrent_code_tasks": 2})
    scheduler_policy: dict[str, Any] = field(default_factory=dict)
    sla_policy: dict[str, Any] = field(default_factory=dict)
    failure_policy: dict[str, Any] = field(default_factory=dict)
    review_policy: dict[str, Any] = field(default_factory=dict)
    git_policy: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    policies: PolicyConfig = field(default_factory=PolicyConfig)
    pm: PmConfig = field(default_factory=PmConfig)
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    workspace: str = "workspace"
    state_dir: str = "state"
    decision_log_max_entries: int = 500
    clamp_code_tasks_to_host: bool = False


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (mutates base)."""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _env_overrides() -> dict[str, Any]:
    """Read environment variables that map to config fields."""
    out: dict[str, Any] = {}
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("XR_AI_CO_API_KEY")
    if key:
        out.setdefault("llm", {})["api_key"] = key
    model = os.environ.get("XR_AI_CO_MODEL")
    if model:
        out.setdefault("llm", {})["model"] = model
    provider = os.environ.get("XR_AI_CO_PROVIDER")
    if provider:
        out.setdefault("llm", {})["provider"] = provider
    return out


def _dict_to_config(raw: dict[str, Any]) -> AppConfig:
    llm_d = raw.get("llm") or {}
    budget_d = raw.get("budget") or {}
    policies_d = raw.get("policies") or {}
    pm_d = raw.get("pm") or {}
    planner_d = raw.get("planner") or {}
    return AppConfig(
        llm=LLMConfig(**{k: v for k, v in llm_d.items() if k in LLMConfig.__dataclass_fields__}),
        budget=BudgetConfig(**{k: v for k, v in budget_d.items() if k in BudgetConfig.__dataclass_fields__}),
        policies=PolicyConfig(**{k: v for k, v in policies_d.items() if k in PolicyConfig.__dataclass_fields__}),
        pm=PmConfig(**{k: v for k, v in pm_d.items() if k in PmConfig.__dataclass_fields__}),
        planner=PlannerConfig(**{k: v for k, v in planner_d.items() if k in PlannerConfig.__dataclass_fields__}),
        workspace=raw.get("workspace", "workspace"),
        state_dir=raw.get("state_dir", "state"),
        decision_log_max_entries=int(raw.get("decision_log_max_entries", 500)),
        clamp_code_tasks_to_host=bool(raw.get("clamp_code_tasks_to_host", False)),
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load config from YAML, merge env overrides, return typed AppConfig."""
    raw: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if p.is_file():
            with p.open(encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
    _deep_merge(raw, _env_overrides())
    return _dict_to_config(raw)

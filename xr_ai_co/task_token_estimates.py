"""§17.2.1 — default per-task token estimates for scheduler pre-checks when Planner omits them."""

from __future__ import annotations

from typing import Any

# Conservative defaults (prompt + completion) so violates_budget_next_step is not a no-op.
_DEFAULTS: dict[str, tuple[int, int]] = {
    "code": (14_000, 10_000),
    "test": (10_000, 8_000),
    "design": (8_000, 6_000),
}


def annotate_task_token_estimates(tasks: list[dict[str, Any]]) -> None:
    """Set estimated_prompt_tokens / estimated_completion_tokens if absent."""
    for t in tasks:
        if t.get("estimated_prompt_tokens") is not None and t.get("estimated_completion_tokens") is not None:
            continue
        kind = t.get("type") or "code"
        pr, comp = _DEFAULTS.get(kind, (6_000, 4_000))
        desc = str(t.get("description") or "")
        bump = min(len(desc) // 100, 20) * 200
        pr = pr + bump
        if t.get("estimated_prompt_tokens") is None:
            t["estimated_prompt_tokens"] = pr
        if t.get("estimated_completion_tokens") is None:
            t["estimated_completion_tokens"] = comp

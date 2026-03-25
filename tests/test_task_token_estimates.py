"""Default token estimates for scheduler."""

from __future__ import annotations

from xr_ai_co.task_token_estimates import annotate_task_token_estimates


def test_annotate_sets_fields_by_type() -> None:
    tasks = [
        {"id": "T0", "type": "design", "description": "x"},
        {"id": "T1", "type": "code", "description": "y"},
    ]
    annotate_task_token_estimates(tasks)
    assert tasks[0]["estimated_prompt_tokens"] >= 8000
    assert tasks[1]["estimated_prompt_tokens"] >= 14000


def test_annotate_respects_existing() -> None:
    tasks = [{"id": "T1", "type": "code", "description": "z", "estimated_prompt_tokens": 1, "estimated_completion_tokens": 2}]
    annotate_task_token_estimates(tasks)
    assert tasks[0]["estimated_prompt_tokens"] == 1
    assert tasks[0]["estimated_completion_tokens"] == 2

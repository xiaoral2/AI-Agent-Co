"""DAG cycle detection (§6.4)."""

from __future__ import annotations

import pytest

from xr_ai_co.plan_validate import detect_dag_cycles, validate_plan_tasks

_MIN = {
    "status": "todo",
    "retry_count": 0,
    "owner": None,
    "plan_revision_id": "r1",
    "priority": "normal",
    "input": "i",
    "output": "o",
    "constraints": "c",
    "acceptance_criteria": "a",
    "test_plan": "t",
}


def test_detect_dag_cycles_finds_loop() -> None:
    tasks = [
        {**_MIN, "id": "A", "type": "code", "description": "a", "depends_on": ["B"]},
        {**_MIN, "id": "B", "type": "code", "description": "b", "depends_on": ["A"]},
    ]
    c = detect_dag_cycles(tasks)
    assert c is not None
    assert "A" in c and "B" in c


def test_validate_plan_tasks_rejects_cycle() -> None:
    tasks = [
        {**_MIN, "id": "A", "type": "code", "description": "a", "depends_on": ["B"]},
        {**_MIN, "id": "B", "type": "code", "description": "b", "depends_on": ["A"]},
    ]
    with pytest.raises(ValueError, match="cyclic"):
        validate_plan_tasks(tasks)

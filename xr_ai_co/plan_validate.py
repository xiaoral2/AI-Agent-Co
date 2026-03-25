"""§2.5.1a — validate plan tasks against schemas/task.v1.json + §6.4 DAG cycle detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def schema_path() -> Path:
    return repo_root() / "schemas" / "task.v1.json"


def load_schema() -> dict[str, Any]:
    with schema_path().open(encoding="utf-8") as f:
        return json.load(f)


def detect_dag_cycles(tasks: list[dict[str, Any]]) -> list[str] | None:
    """§6.4: reject cyclic depends_on. Returns cycle path or None."""
    ids = {t["id"] for t in tasks}
    adj: dict[str, list[str]] = {t["id"]: list(t.get("depends_on") or []) for t in tasks}

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in ids}
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for dep in adj.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                cycle_start = path.index(dep)
                return path[cycle_start:] + [dep]
            if color[dep] == WHITE:
                result = dfs(dep)
                if result is not None:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for tid in ids:
        if color[tid] == WHITE:
            result = dfs(tid)
            if result is not None:
                return result
    return None


def validate_plan_tasks(tasks: list[dict[str, Any]]) -> None:
    """Validate schema + DAG acyclicity."""
    schema = load_schema()
    for i, task in enumerate(tasks):
        try:
            jsonschema.validate(instance=task, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"task[{i}] id={task.get('id')!r}: {e.message}") from e

    cycle = detect_dag_cycles(tasks)
    if cycle is not None:
        raise ValueError(f"cyclic depends_on detected: {' → '.join(cycle)}")

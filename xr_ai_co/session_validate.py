"""Best-effort checkpoint shape checks (fail-soft for forward compatibility)."""

from __future__ import annotations

from typing import Any

REQUIRED_TOP_LEVEL = ("project", "tasks", "workers")


def validate_session_shape(session: dict[str, Any]) -> list[str]:
    """Return human-readable issues; empty list means OK for harness execution."""
    issues: list[str] = []
    if not isinstance(session, dict):
        return ["session root must be a JSON object"]
    for k in REQUIRED_TOP_LEVEL:
        if k not in session:
            issues.append(f"missing top-level key: {k!r}")
    proj = session.get("project")
    if isinstance(proj, dict):
        for k in ("status",):
            if k not in proj:
                issues.append(f"project missing {k!r}")
    else:
        issues.append("project must be an object")
    if "tasks" in session and not isinstance(session["tasks"], list):
        issues.append("tasks must be an array")
    if "workers" in session and not isinstance(session["workers"], list):
        issues.append("workers must be an array")
    return issues

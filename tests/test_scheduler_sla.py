"""§2.5.3a SLA deadline floors."""

from __future__ import annotations

from datetime import datetime, timezone

from orchestrator.scheduler_kernel import compute_effective_priority_rank, sla_effective_priority


def test_deadline_high_within_hours_boosts() -> None:
    now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    task = {"priority": "normal", "deadline": "2026-03-24"}
    sla = {"deadline_high_within_hours": 168}
    eff, boosted = sla_effective_priority(task, now, sla)
    assert boosted
    assert eff == "high"
    assert compute_effective_priority_rank(task, now, sla) == "high"


def test_no_deadline_no_boost() -> None:
    now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    task = {"priority": "low"}
    sla = {"deadline_high_within_hours": 1, "deadline_urgent_within_hours": 1}
    eff, boosted = sla_effective_priority(task, now, sla)
    assert not boosted
    assert eff == "low"


def test_overdue_is_urgent() -> None:
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    task = {"priority": "normal", "deadline": "2026-03-01"}
    eff, boosted = sla_effective_priority(task, now, {"deadline_high_within_hours": 9999})
    assert eff == "urgent"
    assert boosted

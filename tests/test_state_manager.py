"""Decision log tail trim."""

from __future__ import annotations

from orchestrator.state_manager import StateManager, empty_session


def test_append_decision_log_trims_from_front() -> None:
    s = empty_session()
    s["decision_log_max_entries"] = 3
    StateManager.append_decision_log(s, [{"decision": "a"}])
    StateManager.append_decision_log(s, [{"decision": "b"}])
    StateManager.append_decision_log(s, [{"decision": "c"}])
    assert len(s["decision_log"]) == 3
    StateManager.append_decision_log(s, [{"decision": "d"}])
    assert len(s["decision_log"]) == 3
    assert s["decision_log"][0]["decision"] == "b"
    assert s["decision_log"][-1]["decision"] == "d"

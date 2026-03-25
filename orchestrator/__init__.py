"""Reference harness spine (design_notes/ai-company-spec.md §6.4.1, §7.1.1, §14).

Run from repo root::

    python -m orchestrator.orchestrator_loop

`ReferenceOrchestrator` lives in `orchestrator.orchestrator_loop` so importing this
package does not eagerly load the loop (avoids runpy warnings).
"""

from .scheduler_kernel import decision_input_from_session, scheduling_dispatch_tick
from .state_manager import StateManager, empty_session

__all__ = [
    "StateManager",
    "empty_session",
    "decision_input_from_session",
    "scheduling_dispatch_tick",
]

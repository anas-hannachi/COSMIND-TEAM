from __future__ import annotations

from ..actions import Action, Decision


class EarliestDeadlineFirstScheduler:
    """Feasibility-aware earliest-deadline-first reference policy."""

    name = "edf"

    def decide(self, state, tasks, simulation) -> Decision:
        pairs = simulation.feasible_pairs()
        if not pairs:
            return Decision(Action.IDLE, rationale="no deadline-feasible EDF route")
        immediate = [pair for pair in pairs if pair[1] != Action.STORE]
        candidates = immediate or pairs
        record, action = min(
            candidates,
            key=lambda pair: (
                pair[0].task.deadline_s,
                {Action.TRANSMIT: 0, Action.PROCESS: 1, Action.STORE: 2}[pair[1]],
                pair[0].task.id,
            ),
        )
        return Decision(action, record.task.id, "earliest-deadline feasible action")

from __future__ import annotations

import math

from ..actions import Action, Decision
from .edf_scheduler import EarliestDeadlineFirstScheduler


class ContactKnapsackScheduler:
    """Exact 0/1 value packing for the current contact, replanned per action.

    The discrete optimization maximizes nominal mission value subject to the
    remaining contact time. Durations are rounded up to whole seconds so the
    selected batch cannot exceed the modeled contact window. Energy feasibility
    is checked again before each actual transfer by the simulator.
    """

    name = "contact_knapsack"

    def __init__(self) -> None:
        self._edf = EarliestDeadlineFirstScheduler()

    def decide(self, state, tasks, simulation) -> Decision:
        if not state.contact_available:
            decision = self._edf.decide(state, tasks, simulation)
            return Decision(decision.action, decision.task_id, f"outside contact; {decision.rationale}")

        capacity_s = max(0, math.floor(state.contact_remaining_s))
        if capacity_s == 0:
            return Decision(Action.IDLE, rationale="no whole-second contact capacity remains")

        candidates = []
        for record in tasks:
            if not simulation.can_transmit(record, require_deadline=True):
                continue
            duration_s = simulation.tx_duration(record)
            duration_bins = max(1, math.ceil(duration_s - 1e-12))
            if duration_bins <= capacity_s:
                candidates.append((record, duration_bins))
        if not candidates:
            decision = self._edf.decide(state, tasks, simulation)
            return Decision(decision.action, decision.task_id, f"no contact batch; {decision.rationale}")

        # Dynamic programming over candidate payloads and discretized contact
        # seconds. Keeping the value table makes the selected subset auditable.
        row_count = len(candidates)
        values = [[float("-inf")] * (capacity_s + 1) for _ in range(row_count + 1)]
        take = [[False] * (capacity_s + 1) for _ in range(row_count + 1)]
        values[0][0] = 0.0
        for row, (record, weight) in enumerate(candidates, start=1):
            previous = values[row - 1]
            current = values[row]
            value = record.task.mission_value
            for capacity in range(capacity_s + 1):
                current[capacity] = previous[capacity]
                if capacity >= weight and previous[capacity - weight] != float("-inf"):
                    packed_value = previous[capacity - weight] + value
                    if packed_value > current[capacity]:
                        current[capacity] = packed_value
                        take[row][capacity] = True

        best_capacity = max(
            range(capacity_s + 1),
            key=lambda capacity: (values[row_count][capacity], capacity),
        )
        if values[row_count][best_capacity] == float("-inf"):
            return Decision(Action.IDLE, rationale="contact knapsack selected no payload")

        remaining = best_capacity
        selected = []
        for row in range(row_count, 0, -1):
            if take[row][remaining]:
                record, weight = candidates[row - 1]
                selected.append(record)
                remaining -= weight
        if not selected:
            return Decision(Action.IDLE, rationale="contact knapsack selected no payload")

        first = min(selected, key=lambda record: (record.task.deadline_s, record.task.id))
        return Decision(
            Action.TRANSMIT,
            first.task.id,
            f"contact knapsack packed {len(selected)} payloads, "
            f"value={values[row_count][best_capacity]:.1f}",
        )

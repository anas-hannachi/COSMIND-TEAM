from __future__ import annotations

import random

from ..actions import Action, Decision


class RandomScheduler:
    """Seeded feasibility-constrained sanity baseline."""

    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def decide(self, state, tasks, simulation) -> Decision:
        if not tasks:
            return Decision(Action.IDLE, rationale="empty queue")
        pairs = simulation.feasible_pairs()
        if not pairs:
            return Decision(Action.IDLE, rationale="no deadline-feasible action")
        record, action = self.rng.choice(pairs)
        return Decision(action, record.task.id, "seeded feasible random task-action pair")

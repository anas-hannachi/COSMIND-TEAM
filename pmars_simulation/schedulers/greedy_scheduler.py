from __future__ import annotations

from dataclasses import dataclass

from ..actions import Action, Decision


@dataclass
class GreedyScheduler:
    """Immediate utility baseline across all currently eligible tasks.

    Unlike PredictiveScheduler, this baseline does not rank candidate routes by
    their projected delivery time, future transfer energy, or storage relief.
    It only scores the immediate action available at the current decision.
    """

    name: str = "greedy"
    value_weight: float = 1.0
    priority_weight: float = 0.35
    energy_weight: float = 0.40
    urgency_weight: float = 0.30
    process_penalty: float = 0.08

    def _score(self, record, action, state, simulation) -> float:
        task = record.task
        slack_s = max(task.deadline_s - state.time_s, 1.0)
        value = task.value_at(state.time_s) / max(task.mission_value, 1.0)
        priority = task.priority / 9.0
        urgency = min(1.0, 120.0 / slack_s)
        if action == Action.TRANSMIT:
            duration_s = simulation.tx_duration(record)
        elif action == Action.PROCESS:
            duration_s = simulation.process_duration(record)
        else:
            duration_s = 0.0
        energy_fraction = (
            simulation.energy.power(action) * duration_s / max(state.energy_j, 1.0)
            if action != Action.STORE
            else 0.0
        )
        score = (
            self.value_weight * value
            + self.priority_weight * priority
            + self.urgency_weight * urgency
            - self.energy_weight * energy_fraction
        )
        if action == Action.PROCESS:
            score -= self.process_penalty
        return score

    def decide(self, state, tasks, simulation) -> Decision:
        if not tasks:
            return Decision(Action.IDLE, rationale="empty queue")
        pairs = simulation.feasible_pairs()
        immediate_pairs = [pair for pair in pairs if pair[1] != Action.STORE]
        # A myopic policy should not choose a no-op STORE while an immediate
        # deadline-feasible PROCESS or TRANSMIT action exists. STORE remains a
        # fallback when the only viable route begins in a later contact.
        if immediate_pairs:
            pairs = immediate_pairs
        if not pairs:
            return Decision(Action.IDLE, rationale="no deadline-feasible immediate action")
        record, action = max(
            pairs,
            key=lambda pair: (
                self._score(pair[0], pair[1], state, simulation),
                -pair[0].task.deadline_s,
                pair[0].task.id,
            ),
        )
        score = self._score(record, action, state, simulation)
        return Decision(action, record.task.id, f"immediate utility score={score:.3f}")

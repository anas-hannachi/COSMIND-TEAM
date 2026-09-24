from __future__ import annotations

from dataclasses import dataclass

from ..actions import Action, Decision


@dataclass
class PredictiveScheduler:
    """Inspectable one-step receding-horizon scheduling heuristic.

    For every queued task, the scheduler considers raw downlink now,
    process-now followed by a feasible future result downlink, and store until
    a feasible raw contact.  It scores only deadline-feasible plans within a
    bounded horizon, executes the first action, then replans at the next state
    transition. It neither reserves capacity nor proves global optimality.
    """

    horizon_s: float = 300.0
    name: str = "predictive"
    value_weight: float = 4.0
    priority_weight: float = 1.5
    slack_weight: float = 0.5
    storage_relief_weight: float = 0.75
    energy_weight: float = 0.7
    wait_weight: float = 0.3
    critical_bonus: float = 0.5

    def _score(self, candidate, state, simulation) -> float:
        record = candidate["record"]
        task = record.task
        delivery_s = candidate["delivery_s"]
        value_fraction = task.value_at(delivery_s) / max(task.mission_value, 1.0)
        priority_fraction = task.priority / 9.0
        deadline_span_s = max(task.deadline_s - task.created_at_s, 1.0)
        slack_fraction = max(0.0, task.deadline_s - delivery_s) / deadline_span_s
        storage_relief = candidate["bytes_saved_mb"] / max(simulation.satellite.storage_total_mb, 1.0)
        energy_fraction = candidate["energy_j"] / max(state.energy_j, 1.0)
        wait_fraction = candidate["wait_s"] / max(self.horizon_s, 1.0)
        return (
            self.value_weight * value_fraction
            + self.priority_weight * priority_fraction
            + self.slack_weight * slack_fraction
            + self.storage_relief_weight * storage_relief
            + (self.critical_bonus if task.is_critical() else 0.0)
            - self.energy_weight * energy_fraction
            - self.wait_weight * wait_fraction
        )

    def decide(self, state, tasks, simulation) -> Decision:
        if not tasks:
            return Decision(Action.IDLE, rationale="empty queue")
        candidates = [
            candidate
            for record in tasks
            for candidate in simulation.plan_candidates(record, self.horizon_s)
        ]
        if not candidates:
            return Decision(Action.IDLE, rationale="no deadline-feasible predictive route")
        candidate = max(
            candidates,
            key=lambda item: (
                self._score(item, state, simulation),
                -item["record"].task.deadline_s,
                item["record"].task.id,
                item["first_action"].value,
            ),
        )
        score = self._score(candidate, state, simulation)
        rationale = (
            f"{candidate['route']}; predicted_delivery={candidate['delivery_s']:.1f}s; "
            f"score={score:.3f}; energy={candidate['energy_j']:.1f}J"
        )
        return Decision(candidate["first_action"], candidate["record"].task.id, rationale)

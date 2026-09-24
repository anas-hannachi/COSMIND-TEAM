from __future__ import annotations

from ..actions import Action, Decision


class RuleScheduler:
    """Transparent deadline/priority engineering baseline."""

    name = "rule"
    urgent_slack_s = 90.0

    def decide(self, state, tasks, simulation) -> Decision:
        if not tasks:
            return Decision(Action.IDLE, rationale="empty queue")

        def urgency(record):
            slack_s = max(0.0, record.task.deadline_s - state.time_s)
            return (record.task.is_critical(), -slack_s, record.task.priority, record.task.mission_value)

        ordered = sorted(tasks, key=urgency, reverse=True)
        # During a contact, deliver the most urgent deadline-feasible payload.
        for record in ordered:
            if simulation.can_transmit(record, require_deadline=True):
                return Decision(
                    Action.TRANSMIT,
                    record.task.id,
                    "highest urgency deadline-feasible downlink",
                )

        # Away from contact, reduce payload only if its output has a feasible
        # future contact before the task deadline.
        for record in ordered:
            slack_s = record.task.deadline_s - state.time_s
            if (
                simulation.can_process(record, require_future_delivery=True)
                and (not state.contact_available or slack_s <= self.urgent_slack_s or record.task.is_critical())
            ):
                return Decision(
                    Action.PROCESS,
                    record.task.id,
                    "process urgent or contact-unavailable task with feasible result downlink",
                )

        viable = [record for record in ordered if simulation.plan_candidates(record, 300.0)]
        if viable:
            return Decision(Action.STORE, viable[0].task.id, "retain highest urgency viable task")
        return Decision(Action.IDLE, rationale="no deadline-feasible rule action")

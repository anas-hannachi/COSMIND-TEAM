from ..actions import Action, Decision

class RuleScheduler:
    name = "rule"
    def decide(self, state, tasks, simulation):
        if not tasks: return Decision(Action.IDLE, rationale="empty queue")
        task = tasks[0]
        urgent = task.task.deadline_s - state.time_s < 90 or task.task.is_critical()
        if simulation.can_transmit(task) and (urgent or task.status.value == "processed"):
            return Decision(Action.TRANSMIT, task.task.id, "contact can finish urgent/preprocessed task")
        if simulation.can_process(task) and (not state.contact_available or urgent):
            return Decision(Action.PROCESS, task.task.id, "process while downlink is unavailable or urgent")
        return Decision(Action.STORE, task.task.id, "preserve task for later evaluation")

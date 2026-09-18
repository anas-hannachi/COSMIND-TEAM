from dataclasses import dataclass
from ..actions import Action, Decision

@dataclass
class PredictiveScheduler:
    horizon_s: float = 300.; name: str = "predictive"
    def decide(self, state, tasks, simulation):
        if not tasks: return Decision(Action.IDLE, rationale="empty queue")
        record = tasks[0]
        candidates = simulation.predict_candidates(record, self.horizon_s)
        plan, _ = max(candidates, key=lambda x: x[1])
        return Decision(plan[0], record.task.id, f"look-ahead candidate {'→'.join(a.value for a in plan)}")

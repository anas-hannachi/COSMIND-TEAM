from dataclasses import dataclass
from ..actions import Action, Decision

@dataclass
class GreedyScheduler:
    name: str = "greedy"; value_weight: float = 1.; energy_weight: float = .25; latency_weight: float = .15; freshness_weight: float = .3; deadline_weight: float = .4
    def decide(self, state, tasks, simulation):
        if not tasks: return Decision(Action.IDLE, rationale="empty queue")
        r = tasks[0]; value = r.task.value_at(state.time_s) / max(r.task.mission_value, 1)
        slack = max(r.task.deadline_s - state.time_s, 1); risk = min(1, 60 / slack)
        choices = [(Action.STORE, value - self.freshness_weight * r.task.freshness_decay - self.deadline_weight * risk)]
        if simulation.can_process(r):
            t = simulation.process_duration(r); e = simulation.energy.process_power_w * t / max(state.energy_j, 1)
            choices.append((Action.PROCESS, self.value_weight * value - self.energy_weight * e - self.deadline_weight * risk))
        if simulation.can_transmit(r):
            t = simulation.tx_duration(r); e = simulation.energy.transmit_power_w * t / max(state.energy_j, 1)
            choices.append((Action.TRANSMIT, self.value_weight * value - self.energy_weight * e - self.latency_weight * (t / max(slack, 1))))
        action = max(choices, key=lambda x: x[1])[0]
        return Decision(action, r.task.id, "normalized immediate utility")

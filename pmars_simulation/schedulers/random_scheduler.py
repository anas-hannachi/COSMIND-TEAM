import random
from ..actions import Action, Decision

class RandomScheduler:
    name = "random"
    def __init__(self, seed: int = 0): self.rng = random.Random(seed)
    def decide(self, state, tasks, simulation):
        feasible = [Action.STORE]
        if tasks and simulation.can_process(tasks[0]): feasible.append(Action.PROCESS)
        if tasks and simulation.can_transmit(tasks[0]): feasible.append(Action.TRANSMIT)
        return Decision(self.rng.choice(feasible), tasks[0].task.id if tasks else None, "seeded feasible random choice")

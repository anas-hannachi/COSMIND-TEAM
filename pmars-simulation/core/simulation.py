"""Simulation orchestrator.

This module should own time progression, task injection, state updates, and the
state-action-state loop. The implementation is intentionally left as a contract
for the user to fill in during Session 2 and beyond.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .satellite import Satellite
from .task import Task
from .task_queue import TaskQueue


class Simulation:
    """Top-level orchestrator for the digital twin.

    Responsibility:
    - coordinate tasks, queue, satellite state, and scheduling loop
    - advance time deterministically
    - provide a place to inject tasks and actions

    It must not:
    - encode a scheduler policy directly in the same object unless intentionally separated
    - directly mutate the scheduler decision logic during runtime
    """

    def __init__(self, *, seed: Optional[int] = None, initial_state: Optional[Satellite] = None):
        self.seed = seed
        self.satellite = initial_state or Satellite()
        self.task_queue = TaskQueue()
        self.time_s = 0.0

    def add_task(self, task: Task) -> None:
        """Add a task to the queue."""
        raise NotImplementedError("Implement Simulation.add_task().")

    def step(self) -> Dict[str, Any]:
        """Advance the simulation by one discrete step and return a state record."""
        raise NotImplementedError("Implement Simulation.step().")

    def run(self, steps: int = 1) -> List[Dict[str, Any]]:
        """Run a fixed number of steps and return the state history."""
        raise NotImplementedError("Implement Simulation.run().")

    def snapshot(self) -> Dict[str, Any]:
        """Return the current simulation snapshot."""
        raise NotImplementedError("Implement Simulation.snapshot().")

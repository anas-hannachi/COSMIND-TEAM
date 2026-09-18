from __future__ import annotations
from typing import Protocol
from ..actions import Decision
from ..core.satellite import SatelliteState
from ..core.task_queue import TaskRecord

class Scheduler(Protocol):
    name: str
    def decide(self, state: SatelliteState, tasks: list[TaskRecord], simulation: object) -> Decision: ...

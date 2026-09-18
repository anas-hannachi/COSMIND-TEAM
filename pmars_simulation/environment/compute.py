from dataclasses import dataclass
from ..core.task import Task
from .thermal import ThermalModel

@dataclass(frozen=True)
class ComputeModel:
    max_frequency_hz: float = 2.5e9; ram_total_mb: float = 4096
    def available_fraction(self, thermal: ThermalModel) -> float:
        return 0.5 if thermal.throttling else 1.0
    def processing_time(self, task: Task, thermal: ThermalModel) -> float:
        return task.base_processing_time_s / self.available_fraction(thermal)

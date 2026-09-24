from dataclasses import dataclass
from ..core.task import Task
from .thermal import ThermalModel

@dataclass(frozen=True)
class ComputeModel:
    max_frequency_hz: float = 2.5e9
    ram_total_mb: float = 4096
    capacity_units: float = 100.0
    throttled_capacity_fraction: float = 0.5

    def available_fraction(self, thermal: ThermalModel) -> float:
        return self.throttled_capacity_fraction if thermal.throttling else 1.0

    def available_capacity_units(self, thermal: ThermalModel) -> float:
        return self.capacity_units * self.available_fraction(thermal)

    def can_run(self, task: Task, memory_available_mb: float, thermal: ThermalModel) -> bool:
        return (
            task.memory_requirement_mb <= memory_available_mb
            and task.processing_demand <= self.available_capacity_units(thermal)
        )

    def processing_time(self, task: Task, thermal: ThermalModel) -> float:
        return task.base_processing_time_s / self.available_fraction(thermal)

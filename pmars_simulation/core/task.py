from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import exp, isfinite


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    STORED = "stored"
    PROCESSED = "processed"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    LATE = "late"
    UNFINISHED = "unfinished"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    type: str
    input_size_mb: float
    processing_demand: float
    base_processing_time_s: float
    processing_energy_estimate_j: float
    processed_output_mb: float
    priority: int
    mission_value: float
    deadline_s: float
    created_at_s: float
    freshness_decay: float
    memory_requirement_mb: float = 0.0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.type.strip():
            raise ValueError("task id and type must be non-empty")
        values = (self.input_size_mb, self.processing_demand, self.base_processing_time_s,
                  self.processing_energy_estimate_j, self.processed_output_mb, self.mission_value,
                  self.deadline_s, self.created_at_s, self.freshness_decay,
                  self.memory_requirement_mb)
        if not all(isfinite(float(x)) for x in values):
            raise ValueError("task numeric fields must be finite")
        if (self.input_size_mb < 0 or self.processing_demand < 0
                or self.processed_output_mb < 0 or self.memory_requirement_mb < 0):
            raise ValueError("task sizes, memory, and demand cannot be negative")
        if self.base_processing_time_s <= 0 or self.processing_energy_estimate_j < 0:
            raise ValueError("processing time must be positive and energy non-negative")
        if self.priority < 0 or self.mission_value < 0 or self.deadline_s < self.created_at_s:
            raise ValueError("invalid priority, value, or deadline")
        if not 0 <= self.freshness_decay <= 1:
            raise ValueError("freshness_decay must be in [0, 1]")

    def value_at(self, time_s: float) -> float:
        """Return freshness-adjusted value.

        Freshness decay is expressed per simulated minute.  Scenario time is in
        seconds, so converting here avoids accidental sub-second half-lives.
        """
        age_minutes = max(0.0, time_s - self.created_at_s) / 60.0
        return self.mission_value * exp(-self.freshness_decay * age_minutes)

    def is_critical(self) -> bool:
        return self.priority >= 8

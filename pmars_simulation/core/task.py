"""Task domain model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Task:
    """Single unit of mission work."""

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

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Task id must be a non-empty string.")
        if not isinstance(self.type, str) or not self.type.strip():
            raise ValueError("Task type must be a non-empty string.")

        for name in (
            "input_size_mb",
            "processing_demand",
            "base_processing_time_s",
            "processing_energy_estimate_j",
            "processed_output_mb",
            "mission_value",
            "deadline_s",
            "created_at_s",
            "freshness_decay",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"Task field '{name}' must be a finite numeric value.")

        if self.input_size_mb < 0:
            raise ValueError("Task input_size_mb cannot be negative.")
        if self.processing_demand < 0:
            raise ValueError("Task processing_demand cannot be negative.")
        if self.base_processing_time_s <= 0:
            raise ValueError("Task base_processing_time_s must be positive.")
        if self.processing_energy_estimate_j < 0:
            raise ValueError("Task processing_energy_estimate_j cannot be negative.")
        if self.processed_output_mb < 0:
            raise ValueError("Task processed_output_mb cannot be negative.")
        if not isinstance(self.priority, int):
            raise ValueError("Task priority must be an integer.")
        if self.priority < 0:
            raise ValueError("Task priority cannot be negative.")
        if self.mission_value < 0:
            raise ValueError("Task mission_value cannot be negative.")
        if self.deadline_s < self.created_at_s:
            raise ValueError("Task deadline_s must be greater than or equal to created_at_s.")
        if not 0.0 <= self.freshness_decay <= 1.0:
            raise ValueError("Task freshness_decay must be between 0 and 1 inclusive.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "input_size_mb": self.input_size_mb,
            "processing_demand": self.processing_demand,
            "base_processing_time_s": self.base_processing_time_s,
            "processing_energy_estimate_j": self.processing_energy_estimate_j,
            "processed_output_mb": self.processed_output_mb,
            "priority": self.priority,
            "mission_value": self.mission_value,
            "deadline_s": self.deadline_s,
            "created_at_s": self.created_at_s,
            "freshness_decay": self.freshness_decay,
        }

    def is_expired(self, current_time_s: float) -> bool:
        if not isinstance(current_time_s, (int, float)) or not math.isfinite(float(current_time_s)):
            raise ValueError("current_time_s must be a finite numeric value.")
        return float(current_time_s) >= self.deadline_s

    def urgency_score(self, current_time_s: float) -> float:
        if not isinstance(current_time_s, (int, float)) or not math.isfinite(float(current_time_s)):
            raise ValueError("current_time_s must be a finite numeric value.")

        slack = self.deadline_s - float(current_time_s)
        if slack <= 0:
            return self.mission_value + (self.priority * 10.0) + abs(slack)
        return self.mission_value + (self.priority * 10.0) + (1.0 / max(slack, 1e-9))

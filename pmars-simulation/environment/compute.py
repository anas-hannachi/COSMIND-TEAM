"""Compute model for PMARS Phase 2 simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ComputeModel:
    """Simple compute model representing CPU, memory, and estimated capacity."""

    max_cpu_frequency_hz: float = 2.5e9
    current_cpu_frequency_hz: float = 2.0e9
    cpu_utilization: float = 0.2
    ram_total_mb: float = 4096.0
    ram_available_mb: float = 2048.0
    load_average: float = 0.5
    queue_depth: int = 0
    available_compute_fraction: float = 1.0

    def __post_init__(self) -> None:
        if self.max_cpu_frequency_hz <= 0:
            raise ValueError("max_cpu_frequency_hz must be positive.")
        if self.current_cpu_frequency_hz <= 0:
            raise ValueError("current_cpu_frequency_hz must be positive.")
        if not 0.0 <= self.cpu_utilization <= 1.0:
            raise ValueError("cpu_utilization must be in [0, 1].")
        if self.ram_total_mb <= 0:
            raise ValueError("ram_total_mb must be positive.")
        if self.ram_available_mb < 0:
            raise ValueError("ram_available_mb cannot be negative.")

    def estimate_processing_time(self, base_processing_time_s: float, available_compute_fraction: float | None = None) -> float:
        if base_processing_time_s <= 0:
            raise ValueError("base_processing_time_s must be positive.")
        fraction = available_compute_fraction if available_compute_fraction is not None else self.available_compute_fraction
        if fraction <= 0:
            raise ValueError("available_compute_fraction must be positive.")
        return float(base_processing_time_s) / max(float(fraction), 1e-9)

    def apply_to_satellite(self, satellite: "Satellite", duration_s: float, action: str = "PROCESS") -> None:
        """Update the satellite's compute-related state."""
        from ..core.satellite import Satellite

        if not isinstance(satellite, Satellite):
            raise TypeError("satellite must be a Satellite instance.")
        if duration_s < 0:
            raise ValueError("duration_s cannot be negative.")

        if action == "PROCESS":
            satellite.cpu_available = max(0.0, min(1.0, self.available_compute_fraction))
            self.cpu_utilization = min(1.0, self.cpu_utilization + 0.1)
            satellite.memory_available_mb = max(0.0, satellite.memory_available_mb - 5.0 * duration_s)
        else:
            self.cpu_utilization = max(0.0, self.cpu_utilization - 0.05)
            satellite.cpu_available = max(0.2, min(1.0, self.available_compute_fraction + 0.05))

        satellite.cpu_available = max(0.0, min(1.0, satellite.cpu_available))
        satellite.queue_length = max(0, satellite.queue_length)
        self.load_average = max(0.0, self.load_average + (self.cpu_utilization * 0.1))
        self.available_compute_fraction = max(0.1, min(1.0, satellite.cpu_available))
        self.ram_available_mb = max(0.0, min(self.ram_total_mb, satellite.memory_available_mb))

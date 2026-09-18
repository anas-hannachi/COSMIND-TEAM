from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SatelliteState:
    time_s: float; energy_j: float; battery_percent: float; solar_power_w: float
    cpu_available: float; memory_available_mb: float; temperature_c: float
    storage_free_mb: float; queued_storage_mb: float; contact_available: bool
    bandwidth_mbps: float; latency_ms: float; contact_remaining_s: float; next_contact_s: float | None
    queue_length: int; critical_task_count: int


@dataclass
class Satellite:
    energy_j: float; battery_capacity_j: float; memory_available_mb: float; storage_total_mb: float
    time_s: float = 0.0; solar_power_w: float = 0.0; cpu_available: float = 1.0
    temperature_c: float = 20.0; storage_used_mb: float = 0.0; contact_available: bool = False
    bandwidth_mbps: float = 0.0; latency_ms: float = 0.0; contact_remaining_s: float = 0.0
    next_contact_s: float | None = None

    def validate(self) -> None:
        if not 0 <= self.energy_j <= self.battery_capacity_j: raise ValueError("energy outside battery bounds")
        if not 0 <= self.storage_used_mb <= self.storage_total_mb: raise ValueError("storage outside bounds")
        if not 0 <= self.cpu_available <= 1 or self.memory_available_mb < 0: raise ValueError("invalid compute state")

    def snapshot(self, queue_length: int, critical_task_count: int) -> SatelliteState:
        self.validate()
        return SatelliteState(self.time_s, self.energy_j, 100 * self.energy_j / self.battery_capacity_j,
            self.solar_power_w, self.cpu_available, self.memory_available_mb, self.temperature_c,
            self.storage_total_mb - self.storage_used_mb, self.storage_used_mb, self.contact_available,
            self.bandwidth_mbps, self.latency_ms, self.contact_remaining_s, self.next_contact_s,
            queue_length, critical_task_count)

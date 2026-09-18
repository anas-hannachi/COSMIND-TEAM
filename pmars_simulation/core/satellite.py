"""Satellite domain model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class SatelliteState:
    """Read-only snapshot of the satellite at a point in time."""

    time_s: float = 0.0
    energy_j: float = 0.0
    battery_percent: float = 0.0
    solar_power_w: float = 0.0
    cpu_available: float = 1.0
    memory_available_mb: float = 0.0
    temperature_c: float = 20.0
    storage_free_mb: float = 0.0
    queued_storage_mb: float = 0.0
    contact_available: bool = False
    bandwidth_mbps: float = 0.0
    latency_ms: float = 0.0
    contact_remaining_s: float = 0.0
    next_contact_s: float = 0.0
    queue_length: int = 0
    critical_task_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_s": self.time_s,
            "energy_j": self.energy_j,
            "battery_percent": self.battery_percent,
            "solar_power_w": self.solar_power_w,
            "cpu_available": self.cpu_available,
            "memory_available_mb": self.memory_available_mb,
            "temperature_c": self.temperature_c,
            "storage_free_mb": self.storage_free_mb,
            "queued_storage_mb": self.queued_storage_mb,
            "contact_available": self.contact_available,
            "bandwidth_mbps": self.bandwidth_mbps,
            "latency_ms": self.latency_ms,
            "contact_remaining_s": self.contact_remaining_s,
            "next_contact_s": self.next_contact_s,
            "queue_length": self.queue_length,
            "critical_task_count": self.critical_task_count,
        }


@dataclass
class Satellite:
    """Mutable digital twin of the spacecraft."""

    time_s: float = 0.0
    energy_j: float = 0.0
    battery_percent: float = 0.0
    solar_power_w: float = 0.0
    cpu_available: float = 1.0
    memory_available_mb: float = 0.0
    temperature_c: float = 20.0
    storage_free_mb: float = 0.0
    queued_storage_mb: float = 0.0
    contact_available: bool = False
    bandwidth_mbps: float = 0.0
    latency_ms: float = 0.0
    contact_remaining_s: float = 0.0
    next_contact_s: float = 0.0
    queue_length: int = 0
    critical_task_count: int = 0

    def validate(self) -> None:
        for field_name, value in {
            "time_s": self.time_s,
            "energy_j": self.energy_j,
            "battery_percent": self.battery_percent,
            "solar_power_w": self.solar_power_w,
            "cpu_available": self.cpu_available,
            "memory_available_mb": self.memory_available_mb,
            "temperature_c": self.temperature_c,
            "storage_free_mb": self.storage_free_mb,
            "queued_storage_mb": self.queued_storage_mb,
            "bandwidth_mbps": self.bandwidth_mbps,
            "latency_ms": self.latency_ms,
            "contact_remaining_s": self.contact_remaining_s,
            "next_contact_s": self.next_contact_s,
        }.items():
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"Satellite field '{field_name}' must be finite.")

        if self.time_s < 0:
            raise ValueError("Satellite time_s cannot be negative.")
        if self.energy_j < 0:
            raise ValueError("Satellite energy_j cannot be negative.")
        if not 0.0 <= self.battery_percent <= 100.0:
            raise ValueError("Satellite battery_percent must be between 0 and 100 inclusive.")
        if self.solar_power_w < 0:
            raise ValueError("Satellite solar_power_w cannot be negative.")
        if not 0.0 <= self.cpu_available <= 1.0:
            raise ValueError("Satellite cpu_available must lie in [0, 1].")
        if self.memory_available_mb < 0:
            raise ValueError("Satellite memory_available_mb cannot be negative.")
        if not -100.0 <= self.temperature_c <= 100.0:
            raise ValueError("Satellite temperature_c must remain within a sensible simulation range.")
        if self.storage_free_mb < 0:
            raise ValueError("Satellite storage_free_mb cannot be negative.")
        if self.queued_storage_mb < 0:
            raise ValueError("Satellite queued_storage_mb cannot be negative.")
        if self.bandwidth_mbps < 0:
            raise ValueError("Satellite bandwidth_mbps cannot be negative.")
        if self.latency_ms < 0:
            raise ValueError("Satellite latency_ms cannot be negative.")
        if self.contact_remaining_s < 0:
            raise ValueError("Satellite contact_remaining_s cannot be negative.")
        if self.next_contact_s < 0:
            raise ValueError("Satellite next_contact_s cannot be negative.")
        if self.queue_length < 0:
            raise ValueError("Satellite queue_length cannot be negative.")
        if self.critical_task_count < 0:
            raise ValueError("Satellite critical_task_count cannot be negative.")

    def snapshot(self) -> SatelliteState:
        self.validate()
        return SatelliteState(
            time_s=self.time_s,
            energy_j=self.energy_j,
            battery_percent=self.battery_percent,
            solar_power_w=self.solar_power_w,
            cpu_available=self.cpu_available,
            memory_available_mb=self.memory_available_mb,
            temperature_c=self.temperature_c,
            storage_free_mb=self.storage_free_mb,
            queued_storage_mb=self.queued_storage_mb,
            contact_available=self.contact_available,
            bandwidth_mbps=self.bandwidth_mbps,
            latency_ms=self.latency_ms,
            contact_remaining_s=self.contact_remaining_s,
            next_contact_s=self.next_contact_s,
            queue_length=self.queue_length,
            critical_task_count=self.critical_task_count,
        )

    def apply_action(self, action: str, *, duration_s: float = 0.0, **kwargs: Any) -> None:
        action_name = str(action).upper()
        if action_name not in {"PROCESS", "STORE", "TRANSMIT"}:
            raise ValueError(f"Unsupported action '{action}'.")
        if duration_s < 0:
            raise ValueError("duration_s cannot be negative.")

        self.time_s += float(duration_s)
        self.validate()

    def update_time(self, delta_s: float) -> None:
        if delta_s < 0:
            raise ValueError("delta_s cannot be negative.")
        self.time_s += float(delta_s)
        self.validate()

"""Communication model for PMARS Phase 2 simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ContactWindow:
    start_s: float
    end_s: float
    bandwidth_mbps: float
    latency_ms: float = 0.0
    packet_loss: float = 0.0

    def __post_init__(self) -> None:
        if self.start_s < 0:
            raise ValueError("ContactWindow start_s cannot be negative.")
        if self.end_s <= self.start_s:
            raise ValueError("ContactWindow end_s must be greater than start_s.")
        if self.bandwidth_mbps < 0:
            raise ValueError("bandwidth_mbps cannot be negative.")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative.")
        if not 0.0 <= self.packet_loss <= 1.0:
            raise ValueError("packet_loss must be between 0 and 1.")

    def contains(self, time_s: float) -> bool:
        return self.start_s <= time_s < self.end_s

    def remaining_time(self, time_s: float) -> float:
        return max(0.0, self.end_s - time_s)


@dataclass
class CommunicationModel:
    """Time-varying communication network model."""

    contact_windows: List[ContactWindow] = field(default_factory=list)
    current_bandwidth_mbps: float = 0.0
    current_latency_ms: float = 0.0
    packet_loss: float = 0.0
    contact_available: bool = False
    contact_remaining_s: float = 0.0

    def add_contact_window(self, window: ContactWindow) -> None:
        self.contact_windows.append(window)

    def current_contact(self, time_s: float) -> Optional[ContactWindow]:
        for window in self.contact_windows:
            if window.contains(time_s):
                return window
        return None

    def update_for_time(self, time_s: float) -> None:
        contact = self.current_contact(time_s)
        if contact is None:
            self.contact_available = False
            self.current_bandwidth_mbps = 0.0
            self.current_latency_ms = 0.0
            self.packet_loss = 0.0
            self.contact_remaining_s = 0.0
            return

        self.contact_available = True
        self.current_bandwidth_mbps = contact.bandwidth_mbps
        self.current_latency_ms = contact.latency_ms
        self.packet_loss = contact.packet_loss
        self.contact_remaining_s = contact.remaining_time(time_s)

    def transmission_time_s(self, data_size_mb: float, bandwidth_mbps: float | None = None, latency_ms: float | None = None) -> float:
        if data_size_mb < 0:
            raise ValueError("data_size_mb cannot be negative.")
        bw = self.current_bandwidth_mbps if bandwidth_mbps is None else bandwidth_mbps
        latency = self.current_latency_ms if latency_ms is None else latency_ms
        if bw <= 0:
            return float("inf")
        return (data_size_mb * 8.0 / bw) + (latency / 1000.0)

    def apply_to_satellite(self, satellite: "Satellite", time_s: float) -> None:
        from ..core.satellite import Satellite

        if not isinstance(satellite, Satellite):
            raise TypeError("satellite must be a Satellite instance.")
        self.update_for_time(time_s)
        satellite.contact_available = self.contact_available
        satellite.bandwidth_mbps = self.current_bandwidth_mbps
        satellite.latency_ms = self.current_latency_ms
        satellite.contact_remaining_s = self.contact_remaining_s

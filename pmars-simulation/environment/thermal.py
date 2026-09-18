"""Thermal model for PMARS Phase 2 simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThermalModel:
    """Simple explainable thermal model for a spacecraft SoC."""

    temp_c: float = 20.0
    thermal_headroom_c: float = 40.0
    throttling: bool = False
    cooling_rate_c_per_s: float = 0.02
    heating_rate_c_per_s: float = 0.08
    max_temp_c: float = 60.0

    def __post_init__(self) -> None:
        if self.max_temp_c <= 0:
            raise ValueError("max_temp_c must be positive.")

    def apply_processing(self, duration_s: float) -> None:
        if duration_s < 0:
            raise ValueError("duration_s cannot be negative.")
        self.temp_c += self.heating_rate_c_per_s * float(duration_s)
        self.update_state()

    def apply_idle(self, duration_s: float) -> None:
        if duration_s < 0:
            raise ValueError("duration_s cannot be negative.")
        self.temp_c -= self.cooling_rate_c_per_s * float(duration_s)
        self.update_state()

    def update_state(self) -> None:
        self.temp_c = max(-20.0, min(self.temp_c, self.max_temp_c + 5.0))
        self.thermal_headroom_c = max(0.0, self.max_temp_c - self.temp_c)
        self.throttling = self.temp_c >= (self.max_temp_c * 0.85)

    def apply_to_satellite(self, satellite: "Satellite") -> None:
        from ..core.satellite import Satellite

        if not isinstance(satellite, Satellite):
            raise TypeError("satellite must be a Satellite instance.")
        satellite.temperature_c = self.temp_c

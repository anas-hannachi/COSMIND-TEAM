"""Energy model for PMARS Phase 2 simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EnergyModel:
    """Simple energy model with bounded battery and action power assumptions.

    All coefficients are explicit simulation assumptions for Phase 2.
    They are not measured hardware values.
    """

    initial_energy_j: float = 5000.0
    battery_capacity_j: float = 8000.0
    solar_power_w: float = 60.0
    eclipse: bool = False
    idle_power_w: float = 18.0
    process_power_w: float = 45.0
    transmit_power_w: float = 80.0
    store_power_w: float = 10.0
    recent_consumption_w: float = 0.0
    predicted_remaining_energy_j: float = 5000.0

    def __post_init__(self) -> None:
        if self.battery_capacity_j <= 0:
            raise ValueError("battery_capacity_j must be positive.")
        if self.initial_energy_j < 0:
            raise ValueError("initial_energy_j cannot be negative.")
        if self.initial_energy_j > self.battery_capacity_j:
            raise ValueError("initial_energy_j cannot exceed battery_capacity_j.")

    def solar_input_w(self) -> float:
        return self.solar_power_w if not self.eclipse else 0.0

    def action_power_w(self, action: str) -> float:
        action_name = str(action).upper()
        if action_name == "PROCESS":
            return self.process_power_w
        if action_name == "TRANSMIT":
            return self.transmit_power_w
        if action_name == "STORE":
            return self.store_power_w
        return self.idle_power_w

    def action_energy_j(self, action: str, duration_s: float) -> float:
        if duration_s < 0:
            raise ValueError("duration_s cannot be negative.")
        return self.action_power_w(action) * float(duration_s)

    def apply_action(self, satellite: "Satellite", action: str, duration_s: float) -> None:
        """Apply energy change to the satellite's battery and energy state."""
        from ..core.satellite import Satellite

        if not isinstance(satellite, Satellite):
            raise TypeError("satellite must be a Satellite instance.")

        energy_cost = self.action_energy_j(action, duration_s)
        if action == "PROCESS":
            delta = -energy_cost
        elif action == "TRANSMIT":
            delta = -energy_cost
        elif action == "STORE":
            delta = -energy_cost
        else:
            delta = -(self.idle_power_w * float(duration_s))

        solar_gain = self.solar_input_w() * float(duration_s)
        satellite.energy_j = max(0.0, satellite.energy_j + solar_gain + delta)
        satellite.energy_j = min(satellite.energy_j, self.battery_capacity_j)

        if self.battery_capacity_j > 0:
            satellite.battery_percent = (satellite.energy_j / self.battery_capacity_j) * 100.0
        self.recent_consumption_w = max(0.0, self.action_power_w(action))
        self.predicted_remaining_energy_j = max(0.0, satellite.energy_j)

    def tick_idle(self, satellite: "Satellite", duration_s: float) -> None:
        """Advance the model over idle time."""
        from ..core.satellite import Satellite

        if not isinstance(satellite, Satellite):
            raise TypeError("satellite must be a Satellite instance.")
        solar_gain = self.solar_input_w() * float(duration_s)
        idle_cost = self.idle_power_w * float(duration_s)
        satellite.energy_j = max(0.0, satellite.energy_j + solar_gain - idle_cost)
        satellite.energy_j = min(satellite.energy_j, self.battery_capacity_j)
        satellite.battery_percent = (satellite.energy_j / self.battery_capacity_j) * 100.0 if self.battery_capacity_j > 0 else 0.0
        self.recent_consumption_w = self.idle_power_w
        self.predicted_remaining_energy_j = max(0.0, satellite.energy_j)

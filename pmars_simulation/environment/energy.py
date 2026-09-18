from dataclasses import dataclass
from ..core.satellite import Satellite

@dataclass(frozen=True)
class EnergyModel:
    capacity_j: float = 8000; idle_power_w: float = 18; process_power_w: float = 45
    transmit_power_w: float = 80; store_power_w: float = 10; solar_power_w: float = 60
    def power(self, action: str) -> float:
        return {"PROCESS": self.process_power_w, "TRANSMIT": self.transmit_power_w,
                "STORE": self.store_power_w, "IDLE": self.idle_power_w}[action]
    def evolve(self, satellite: Satellite, action: str, duration_s: float, sunlight: bool) -> float:
        consumed = self.power(action) * duration_s
        satellite.energy_j = min(self.capacity_j, max(0.0, satellite.energy_j - consumed + (self.solar_power_w * duration_s if sunlight else 0)))
        satellite.solar_power_w = self.solar_power_w if sunlight else 0.0
        return consumed

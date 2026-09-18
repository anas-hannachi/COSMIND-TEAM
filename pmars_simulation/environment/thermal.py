from dataclasses import dataclass

@dataclass
class ThermalModel:
    temperature_c: float = 20; max_temp_c: float = 60; heating_c_per_s: float = .08; cooling_c_per_s: float = .02
    @property
    def throttling(self) -> bool: return self.temperature_c >= self.max_temp_c * .85
    @property
    def headroom_c(self) -> float: return max(0, self.max_temp_c - self.temperature_c)
    def evolve(self, action: str, duration_s: float) -> None:
        self.temperature_c = max(-20, min(self.max_temp_c, self.temperature_c + (self.heating_c_per_s if action == "PROCESS" else -self.cooling_c_per_s) * duration_s))

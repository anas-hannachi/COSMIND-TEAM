from dataclasses import dataclass

@dataclass
class ThermalModel:
    temperature_c: float = 20
    max_temp_c: float = 60
    heating_c_per_s: float = .08
    cooling_c_per_s: float = .02
    throttle_at_fraction: float = .85

    def __post_init__(self) -> None:
        if self.max_temp_c <= -20:
            raise ValueError("max_temp_c must be above the thermal floor")
        if self.heating_c_per_s < 0 or self.cooling_c_per_s < 0:
            raise ValueError("thermal rates cannot be negative")
        if not 0 < self.throttle_at_fraction <= 1:
            raise ValueError("throttle_at_fraction must be in (0, 1]")

    @property
    def throttling(self) -> bool: return self.temperature_c >= self.max_temp_c * self.throttle_at_fraction
    @property
    def headroom_c(self) -> float: return max(0, self.max_temp_c - self.temperature_c)
    def evolve(self, action: str, duration_s: float) -> None:
        self.temperature_c = max(-20, min(self.max_temp_c, self.temperature_c + (self.heating_c_per_s if action == "PROCESS" else -self.cooling_c_per_s) * duration_s))

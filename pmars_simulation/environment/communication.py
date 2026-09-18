from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ContactWindow:
    start_s: float; end_s: float; bandwidth_start_mbps: float; bandwidth_end_mbps: float; latency_ms: float = 100
    def bandwidth_at(self, time_s: float) -> float:
        if not self.start_s <= time_s < self.end_s: return 0.0
        p = (time_s - self.start_s) / (self.end_s - self.start_s)
        return self.bandwidth_start_mbps + p * (self.bandwidth_end_mbps - self.bandwidth_start_mbps)

@dataclass(frozen=True)
class CommunicationModel:
    contacts: tuple[ContactWindow, ...]
    def current(self, time_s: float) -> ContactWindow | None:
        return next((c for c in self.contacts if c.start_s <= time_s < c.end_s), None)
    def next_contact(self, time_s: float) -> ContactWindow | None:
        return next((c for c in self.contacts if c.start_s > time_s), None)
    def transfer_time(self, size_mb: float, time_s: float) -> float:
        c = self.current(time_s)
        if not c: return float("inf")
        bw = c.bandwidth_at(time_s)
        return float("inf") if bw <= 0 else size_mb * 8 / bw + c.latency_ms / 1000
    def feasible(self, size_mb: float, time_s: float) -> bool:
        c = self.current(time_s)
        return bool(c and self.transfer_time(size_mb, time_s) <= c.end_s - time_s)

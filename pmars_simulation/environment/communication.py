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

    def earliest_feasible_transfer(
        self,
        size_mb: float,
        earliest_s: float,
        deadline_s: float,
    ) -> tuple[float, float] | None:
        """Return the earliest start and duration for a one-contact transfer.

        This is deliberately an inspectable approximation: capacity is evaluated
        at the proposed start time and transfers cannot span contacts.
        """
        for contact in self.contacts:
            if contact.end_s <= earliest_s:
                continue
            start_s = max(earliest_s, contact.start_s)
            if start_s >= contact.end_s:
                continue
            duration_s = self.transfer_time(size_mb, start_s)
            if duration_s <= contact.end_s - start_s and start_s + duration_s <= deadline_s:
                return start_s, duration_s
        return None

    def capacity_mb_until(self, end_s: float) -> float:
        """Approximate configured one-pass capacity up to ``end_s`` in MB."""
        capacity_mb = 0.0
        for contact in self.contacts:
            start_s = contact.start_s
            finish_s = min(contact.end_s, end_s)
            if finish_s <= start_s:
                continue
            start_bw = contact.bandwidth_at(start_s)
            end_bw = contact.bandwidth_at(finish_s - 1e-12)
            # Mbps * seconds / 8 = MB under the decimal networking convention.
            capacity_mb += (start_bw + end_bw) * 0.5 * (finish_s - start_s) / 8.0
        return capacity_mb

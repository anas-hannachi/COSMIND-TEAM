"""Integer-only pmars.contract.v1 records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractTask:
    id: str
    kind: str
    input_bytes: int
    output_bytes_est: int
    mem_req_bytes: int
    demand_milli: int
    base_proc_ms: int
    priority: int
    value_milli: int
    created_ms: int
    deadline_ms: int
    payload_bytes: int | None = None
    processed: bool = False
    actual_output_bytes: int | None = None
    science_payload: None = None

    def __post_init__(self) -> None:
        if not self.id or len(self.id.encode("ascii", errors="strict")) > 15:
            raise ValueError("task id must be 1-15 ASCII bytes")
        if not 0 <= self.priority <= 9:
            raise ValueError("priority must be in 0..9")
        if any(getattr(self, key) < 0 for key in (
            "input_bytes", "output_bytes_est", "mem_req_bytes", "demand_milli",
            "base_proc_ms", "value_milli", "created_ms", "deadline_ms",
        )):
            raise ValueError("task quantities must be nonnegative")
        for key in ("payload_bytes", "actual_output_bytes"):
            value = getattr(self, key)
            if value is not None and value < 0:
                raise ValueError(f"{key} must be nonnegative")


@dataclass(frozen=True)
class ContractState:
    now_ms: int = 0
    energy_mj: int = 0
    storage_used_bytes: int = 0
    storage_total_bytes: int = 0
    memory_available_bytes: int = 0
    compute_capacity_milli: int = 0
    throttle_fraction_milli: int = 1000
    processing_power_mw: int = 0
    transmit_power_mw: int = 0
    idle_power_mw: int = 0
    drain_horizon_ms: int = 2**63 - 1
    contacts: tuple[tuple[int, int, int, int, int], ...] = ()  # start, end, start/end bps, latency ms


@dataclass(frozen=True)
class ContractConfig:
    store_horizon_ms: int = 300_000
    urgent_slack_ms: int = 90_000


@dataclass(frozen=True)
class ContractDecision:
    action: str
    task_id: str | None = None
    reason_code: str = "NO_FEASIBLE_ACTION"

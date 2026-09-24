from __future__ import annotations

import math
import random
import simpy

from dataclasses import dataclass, field
from typing import Any

from ..actions import Action, ActionResult, Decision
from ..environment import (
    CommunicationModel,
    ComputeModel,
    EnergyModel,
    StorageModel,
    ThermalModel,
)
from .satellite import Satellite
from .task import Task, TaskStatus
from .task_queue import TaskQueue, TaskRecord


EPSILON = 1e-9
IDLE_QUANTUM_S = 5.0


@dataclass
class Simulation:
    """Single-satellite, non-preemptive discrete-event scheduling prototype.

    SimPy supplies the virtual-time environment.  The explicit control loop is
    intentionally small and inspectable: an action is non-preemptive, while
    arrivals, deadline expiries, and sunlight boundaries crossed during that
    action are processed at their actual simulated timestamps.
    """

    satellite: Satellite
    energy: EnergyModel
    compute: ComputeModel
    thermal: ThermalModel
    storage: StorageModel
    communication: CommunicationModel
    scheduler: object
    seed: int = 42
    sunlight_period_s: float = 600.0
    eclipse_period_s: float = 600.0
    task_arrivals: list[Task] = field(default_factory=list)
    mission_duration_s: float | None = None
    policy_seed: int | None = None
    queue: TaskQueue = field(default_factory=TaskQueue)
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    energy_consumed_j: float = 0.0
    energy_harvested_j: float = 0.0
    transmitted_data_mb: float = 0.0
    timely_transmitted_data_mb: float = 0.0
    processing_time_s: float = 0.0
    transmission_time_s: float = 0.0
    storage_area_mb_s: float = 0.0
    peak_storage_mb: float = 0.0
    min_energy_j: float = math.inf
    max_temperature_c: float = -math.inf
    failed_action_count: int = 0

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.env = simpy.Environment(initial_time=self.satellite.time_s)
        self.task_arrivals.sort(key=lambda task: (task.created_at_s, task.id))
        self._arrival_index = 0
        self.arrival_horizon_s = (
            float(self.mission_duration_s)
            if self.mission_duration_s is not None
            else max((task.created_at_s for task in self.task_arrivals), default=0.0)
        )
        out_of_scope = [
            task.id
            for task in self.task_arrivals
            if task.created_at_s > self.arrival_horizon_s + EPSILON
        ]
        if out_of_scope:
            raise ValueError(
                "task_arrivals contains tasks after mission_duration_s; "
                "generate arrivals only within the mission horizon "
                f"(first out-of-scope id: {out_of_scope[0]})"
            )
        self.drain_end_s = max(
            self.arrival_horizon_s,
            max((task.deadline_s for task in self.task_arrivals), default=self.arrival_horizon_s),
        )
        self.satellite.temperature_c = self.thermal.temperature_c
        self._sync_contact()
        self.min_energy_j = self.satellite.energy_j
        self.max_temperature_c = self.satellite.temperature_c

    @property
    def generated_count(self) -> int:
        return len(self.task_arrivals)

    def sunlight(self, time_s: float) -> bool:
        period = self.sunlight_period_s + self.eclipse_period_s
        if period <= 0:
            return False
        return time_s % period < self.sunlight_period_s

    def _next_sunlight_boundary(self, time_s: float) -> float | None:
        period = self.sunlight_period_s + self.eclipse_period_s
        if period <= 0:
            return None
        base = math.floor(time_s / period) * period
        sun_end = base + self.sunlight_period_s
        cycle_end = base + period
        if time_s < sun_end - EPSILON:
            return sun_end
        if time_s < cycle_end - EPSILON:
            return cycle_end
        return cycle_end + self.sunlight_period_s

    def _sync_contact(self) -> None:
        contact = self.communication.current(self.satellite.time_s)
        next_contact = self.communication.next_contact(self.satellite.time_s)
        self.satellite.contact_available = contact is not None
        self.satellite.bandwidth_mbps = (
            contact.bandwidth_at(self.satellite.time_s) if contact else 0.0
        )
        self.satellite.latency_ms = contact.latency_ms if contact else 0.0
        self.satellite.contact_remaining_s = (
            contact.end_s - self.satellite.time_s if contact else 0.0
        )
        self.satellite.next_contact_s = next_contact.start_s if next_contact else None

    def snapshot(self):
        self._sync_contact()
        return self.satellite.snapshot(
            len(self.queue),
            sum(record.task.is_critical() for record in self.queue.pending.values()),
        )

    def _event(
        self,
        event: str,
        *,
        record: TaskRecord | None = None,
        action: Action | None = None,
        rationale: str = "",
        reason: str = "",
        success: bool | None = None,
        before: dict[str, Any] | None = None,
    ) -> None:
        self._sync_contact()
        task = record.task if record else None
        row: dict[str, Any] = {
            "time_s": self.satellite.time_s,
            "event": event,
            "task_id": task.id if task else "",
            "task_type": task.type if task else "",
            "task_status": record.status.value if record else "",
            "action": action.value if action else "",
            "rationale": rationale,
            "reason": reason,
            "success": success,
            "payload_mb": record.payload_mb if record else 0.0,
            "deadline_s": task.deadline_s if task else "",
            "slack_s": (task.deadline_s - self.satellite.time_s) if task else "",
            "energy_j": self.satellite.energy_j,
            "storage_used_mb": self.satellite.storage_used_mb,
            "contact_available": self.satellite.contact_available,
            "bandwidth_mbps": self.satellite.bandwidth_mbps,
            "queue_length": len(self.queue),
        }
        if before:
            row.update({f"before_{key}": value for key, value in before.items()})
        self.events.append(row)

    def _record_state(self, record: TaskRecord | None = None) -> dict[str, Any]:
        return {
            "time_s": self.satellite.time_s,
            "energy_j": self.satellite.energy_j,
            "storage_used_mb": self.satellite.storage_used_mb,
            "temperature_c": self.satellite.temperature_c,
            "queue_length": float(len(self.queue)),
            "bandwidth_mbps": self.satellite.bandwidth_mbps,
            "task_status": record.status.value if record else "",
        }

    def _next_arrival_time(self) -> float | None:
        if self._arrival_index >= len(self.task_arrivals):
            return None
        candidate = self.task_arrivals[self._arrival_index].created_at_s
        return candidate if candidate <= self.arrival_horizon_s + EPSILON else None

    def _arrive_due(self) -> None:
        while self._arrival_index < len(self.task_arrivals):
            task = self.task_arrivals[self._arrival_index]
            if task.created_at_s > self.arrival_horizon_s + EPSILON:
                break
            if task.created_at_s > self.satellite.time_s + EPSILON:
                break
            self._arrival_index += 1
            if self.storage.can_store(self.satellite.storage_used_mb, task.input_size_mb):
                record = self.queue.add(task, task.created_at_s)
                self.satellite.storage_used_mb += task.input_size_mb
                self._event("admitted", record=record, reason="storage available")
            else:
                record = self.queue.reject(task, task.created_at_s, "storage capacity exceeded")
                self._event("rejected", record=record, reason=record.outcome_reason)
        self._assert_invariants()

    def _release_storage(self, record: TaskRecord) -> None:
        if not record.storage_accounted:
            return
        self.satellite.storage_used_mb -= record.payload_mb or 0.0
        if abs(self.satellite.storage_used_mb) < EPSILON:
            self.satellite.storage_used_mb = 0.0
        record.storage_accounted = False

    def _finalize_record(
        self,
        record: TaskRecord,
        status: TaskStatus,
        reason: str,
    ) -> None:
        if record.is_terminal or record.task.id not in self.queue.pending:
            return
        if status == TaskStatus.COMPLETED:
            self.queue.complete(record, self.satellite.time_s)
        elif status == TaskStatus.LATE:
            self.queue.mark_late(record, self.satellite.time_s, reason)
        else:
            self.queue.finalize(record, status, self.satellite.time_s, reason)
        self._release_storage(record)
        self._event(status.value, record=record, reason=reason)
        self._assert_invariants()

    def _expire_due(
        self,
        *,
        inclusive: bool,
        exclude_task_id: str | None = None,
    ) -> None:
        due: list[TaskRecord] = []
        for record in self.queue.pending.values():
            if record.task.id == exclude_task_id:
                continue
            is_due = (
                self.satellite.time_s >= record.task.deadline_s - EPSILON
                if inclusive
                else self.satellite.time_s > record.task.deadline_s + EPSILON
            )
            if is_due:
                due.append(record)
        for record in due:
            self._finalize_record(record, TaskStatus.EXPIRED, "deadline elapsed")

    def _next_boundary(self, end_s: float, active_task_id: str | None) -> float:
        candidates = [end_s]
        next_arrival = self._next_arrival_time()
        if next_arrival is not None and next_arrival > self.satellite.time_s + EPSILON:
            candidates.append(next_arrival)
        deadlines = [
            record.task.deadline_s
            for record in self.queue.pending.values()
            if record.task.id != active_task_id
            and record.task.deadline_s > self.satellite.time_s + EPSILON
        ]
        if deadlines:
            candidates.append(min(deadlines))
        sunlight_boundary = self._next_sunlight_boundary(self.satellite.time_s)
        if sunlight_boundary is not None and sunlight_boundary > self.satellite.time_s + EPSILON:
            candidates.append(sunlight_boundary)
        return min(candidates)

    def _evolve_segment(self, duration_s: float, action: Action) -> float:
        if duration_s <= EPSILON:
            return 0.0
        before_storage = self.satellite.storage_used_mb
        consumed, harvested = self.energy.evolve(
            self.satellite,
            action.value,
            duration_s,
            self.sunlight(self.satellite.time_s),
        )
        self.energy_consumed_j += consumed
        self.energy_harvested_j += harvested
        self.storage_area_mb_s += before_storage * duration_s
        self.thermal.evolve(action.value, duration_s)
        self.satellite.temperature_c = self.thermal.temperature_c
        self.satellite.time_s += duration_s
        if self.satellite.time_s > self.env.now + EPSILON:
            self.env.run(until=self.satellite.time_s)
        self.min_energy_j = min(self.min_energy_j, self.satellite.energy_j)
        self.max_temperature_c = max(self.max_temperature_c, self.satellite.temperature_c)
        self.peak_storage_mb = max(self.peak_storage_mb, self.satellite.storage_used_mb)
        if action == Action.PROCESS:
            self.processing_time_s += duration_s
        elif action == Action.TRANSMIT:
            self.transmission_time_s += duration_s
        return consumed

    def _advance(
        self,
        duration_s: float,
        action: Action,
        *,
        active_record: TaskRecord | None = None,
    ) -> float:
        duration_s = max(0.0, duration_s)
        end_s = min(self.satellite.time_s + duration_s, self.drain_end_s)
        actual_energy = 0.0
        active_task_id = active_record.task.id if active_record else None
        while self.satellite.time_s < end_s - EPSILON:
            boundary = self._next_boundary(end_s, active_task_id)
            actual_energy += self._evolve_segment(boundary - self.satellite.time_s, action)
            self._arrive_due()
            self._expire_due(inclusive=True, exclude_task_id=active_task_id)
        return actual_energy

    def process_duration(self, record: TaskRecord) -> float:
        return self.compute.processing_time(record.task, self.thermal)

    def tx_duration(self, record: TaskRecord) -> float:
        return self.communication.transfer_time(record.payload_mb or 0.0, self.satellite.time_s)

    def _has_energy_for(self, action: Action, duration_s: float) -> bool:
        # Conservative preflight: solar energy during an action is not spent in
        # advance. This avoids scheduling an action that begins with an empty
        # battery and makes feasibility checks easy to audit.
        return self.satellite.energy_j + EPSILON >= self.energy.power(action) * duration_s

    def can_process(
        self,
        record: TaskRecord,
        *,
        require_future_delivery: bool = False,
    ) -> bool:
        if record.task.id not in self.queue.pending or record.status == TaskStatus.PROCESSED:
            return False
        duration_s = self.process_duration(record)
        finish_s = self.satellite.time_s + duration_s
        if (
            finish_s >= record.task.deadline_s - EPSILON
            or finish_s > self.drain_end_s + EPSILON
            or not self.compute.can_run(record.task, self.satellite.memory_available_mb, self.thermal)
            or not self._has_energy_for(Action.PROCESS, duration_s)
        ):
            return False
        replacement_storage = (
            self.satellite.storage_used_mb - (record.payload_mb or 0.0)
            + record.task.processed_output_mb
        )
        if not 0.0 <= replacement_storage <= self.satellite.storage_total_mb + EPSILON:
            return False
        if require_future_delivery:
            transfer = self.communication.earliest_feasible_transfer(
                record.task.processed_output_mb,
                finish_s,
                min(record.task.deadline_s, self.drain_end_s),
            )
            if transfer is None:
                return False
        return True

    def can_transmit(self, record: TaskRecord, *, require_deadline: bool = False) -> bool:
        if record.task.id not in self.queue.pending:
            return False
        duration_s = self.tx_duration(record)
        if not math.isfinite(duration_s):
            return False
        finish_s = self.satellite.time_s + duration_s
        if (
            not self.communication.feasible(record.payload_mb or 0.0, self.satellite.time_s)
            or finish_s > self.drain_end_s + EPSILON
            or not self._has_energy_for(Action.TRANSMIT, duration_s)
        ):
            return False
        return not require_deadline or finish_s <= record.task.deadline_s + EPSILON

    def plan_candidates(self, record: TaskRecord, horizon_s: float) -> list[dict[str, Any]]:
        """Create transparent one-step rollout candidates for one task.

        No capacity is reserved. The scheduler sees explicit candidate routes
        and executes only the first action before replanning.
        """
        if record.task.id not in self.queue.pending:
            return []
        now_s = self.satellite.time_s
        task = record.task
        horizon_end_s = min(now_s + horizon_s, task.deadline_s, self.drain_end_s)
        candidates: list[dict[str, Any]] = []

        if self.can_transmit(record, require_deadline=True):
            duration_s = self.tx_duration(record)
            candidates.append({
                "record": record,
                "first_action": Action.TRANSMIT,
                "route": "transmit-now",
                "delivery_s": now_s + duration_s,
                "energy_j": self.energy.power(Action.TRANSMIT) * duration_s,
                "bytes_saved_mb": 0.0,
                "wait_s": 0.0,
            })

        if self.can_process(record, require_future_delivery=True):
            process_duration_s = self.process_duration(record)
            process_finish_s = now_s + process_duration_s
            transfer = self.communication.earliest_feasible_transfer(
                task.processed_output_mb,
                process_finish_s,
                min(task.deadline_s, self.drain_end_s),
            )
            if transfer is not None:
                transfer_start_s, transfer_duration_s = transfer
                delivery_s = transfer_start_s + transfer_duration_s
                if delivery_s <= horizon_end_s + EPSILON:
                    candidates.append({
                        "record": record,
                        "first_action": Action.PROCESS,
                        "route": "process-now-then-transmit",
                        "delivery_s": delivery_s,
                        "energy_j": (
                            self.energy.power(Action.PROCESS) * process_duration_s
                            + self.energy.power(Action.TRANSMIT) * transfer_duration_s
                        ),
                        "bytes_saved_mb": max(0.0, (record.payload_mb or 0.0) - task.processed_output_mb),
                        "wait_s": max(0.0, transfer_start_s - process_finish_s),
                    })

        # STORE is useful only when a raw transfer can begin later within the
        # look-ahead horizon. It avoids treating arbitrary waiting as progress.
        raw_transfer = self.communication.earliest_feasible_transfer(
            record.payload_mb or 0.0,
            now_s + EPSILON,
            min(task.deadline_s, self.drain_end_s),
        )
        if raw_transfer is not None:
            transfer_start_s, transfer_duration_s = raw_transfer
            delivery_s = transfer_start_s + transfer_duration_s
            if transfer_start_s > now_s + EPSILON and delivery_s <= horizon_end_s + EPSILON:
                candidates.append({
                    "record": record,
                    "first_action": Action.STORE,
                    "route": "store-until-raw-contact",
                    "delivery_s": delivery_s,
                    "energy_j": self.energy.power(Action.TRANSMIT) * transfer_duration_s,
                    "bytes_saved_mb": 0.0,
                    "wait_s": transfer_start_s - now_s,
                })
        return candidates

    def feasible_pairs(self) -> list[tuple[TaskRecord, Action]]:
        pairs: list[tuple[TaskRecord, Action]] = []
        for record in self.queue.ordered(self.satellite.time_s):
            if self.can_transmit(record, require_deadline=True):
                pairs.append((record, Action.TRANSMIT))
            if self.can_process(record, require_future_delivery=True):
                pairs.append((record, Action.PROCESS))
            if self.plan_candidates(record, horizon_s=300.0):
                pairs.append((record, Action.STORE))
        return pairs

    def _idle_duration(self) -> float:
        candidates = [IDLE_QUANTUM_S, max(0.0, self.drain_end_s - self.satellite.time_s)]
        next_arrival = self._next_arrival_time()
        if next_arrival is not None:
            candidates.append(max(0.0, next_arrival - self.satellite.time_s))
        if self.queue.pending:
            next_deadline = min(record.task.deadline_s for record in self.queue.pending.values())
            candidates.append(max(0.0, next_deadline - self.satellite.time_s))
        positive = [candidate for candidate in candidates if candidate > EPSILON]
        return min(positive) if positive else 0.0

    def execute(self, decision: Decision) -> ActionResult:
        if decision.action == Action.IDLE:
            duration_s = self._idle_duration()
            if duration_s <= EPSILON:
                return ActionResult(Action.IDLE, None, False, 0.0, 0.0, "no remaining time")
            before = self._record_state()
            energy_j = self._advance(duration_s, Action.IDLE)
            self._event("idle", action=Action.IDLE, rationale=decision.rationale, success=True, before=before)
            return ActionResult(Action.IDLE, None, True, duration_s, energy_j)

        record = self.queue.get(decision.task_id or "")
        if record is None:
            return ActionResult(decision.action, decision.task_id, False, 0.0, 0.0, "task unavailable")
        before = self._record_state(record)
        record.attempts += 1

        if decision.action == Action.PROCESS:
            if not self.can_process(record, require_future_delivery=False):
                return ActionResult(Action.PROCESS, record.task.id, False, 0.0, 0.0, "processing infeasible")
            duration_s = self.process_duration(record)
            record.status = TaskStatus.PROCESSING
            self._event("process_started", record=record, action=Action.PROCESS, rationale=decision.rationale, before=before)
            energy_j = self._advance(duration_s, Action.PROCESS, active_record=record)
            if record.task.id not in self.queue.pending:
                return ActionResult(Action.PROCESS, record.task.id, False, duration_s, energy_j, "task finalized during processing")
            old_payload_mb = record.payload_mb or 0.0
            new_payload_mb = record.task.processed_output_mb
            replacement_storage = self.satellite.storage_used_mb - old_payload_mb + new_payload_mb
            if replacement_storage > self.satellite.storage_total_mb + EPSILON:
                # Arrivals are admitted at their true timestamps while a
                # non-preemptive process action runs.  If an unusual task
                # expands during processing and concurrent admissions leave
                # no room for the result, discard the resident input and
                # record a single explicit failed outcome rather than ever
                # exceeding storage capacity.
                self._finalize_record(
                    record,
                    TaskStatus.FAILED,
                    "processed result does not fit after concurrent admissions",
                )
                return ActionResult(
                    Action.PROCESS,
                    record.task.id,
                    False,
                    duration_s,
                    energy_j,
                    "processed result storage infeasible",
                )
            self.satellite.storage_used_mb += new_payload_mb - old_payload_mb
            record.payload_mb = new_payload_mb
            record.processed_at_s = self.satellite.time_s
            record.status = TaskStatus.PROCESSED
            self._event("processed", record=record, action=Action.PROCESS, rationale=decision.rationale, success=True, before=before)
            self._assert_invariants()
            return ActionResult(Action.PROCESS, record.task.id, True, duration_s, energy_j)

        if decision.action == Action.STORE:
            duration_s = min(IDLE_QUANTUM_S, max(0.0, record.task.deadline_s - self.satellite.time_s))
            if duration_s <= EPSILON:
                self._expire_due(inclusive=True)
                return ActionResult(Action.STORE, record.task.id, False, 0.0, 0.0, "task deadline elapsed")
            record.stored = True
            self._event("store_started", record=record, action=Action.STORE, rationale=decision.rationale, before=before)
            energy_j = self._advance(duration_s, Action.STORE)
            if record.task.id in self.queue.pending and record.status != TaskStatus.PROCESSED:
                record.status = TaskStatus.STORED
            self._event("stored", record=record, action=Action.STORE, rationale=decision.rationale, success=True, before=before)
            return ActionResult(Action.STORE, record.task.id, True, duration_s, energy_j)

        if not self.can_transmit(record, require_deadline=False):
            return ActionResult(Action.TRANSMIT, record.task.id, False, 0.0, 0.0, "transmission infeasible")
        duration_s = self.tx_duration(record)
        payload_mb = record.payload_mb or 0.0
        self._event("transmit_started", record=record, action=Action.TRANSMIT, rationale=decision.rationale, before=before)
        energy_j = self._advance(duration_s, Action.TRANSMIT, active_record=record)
        if record.task.id not in self.queue.pending:
            return ActionResult(Action.TRANSMIT, record.task.id, False, duration_s, energy_j, "task finalized during transmission")
        self.transmitted_data_mb += payload_mb
        if self.satellite.time_s <= record.task.deadline_s + EPSILON:
            self.timely_transmitted_data_mb += payload_mb
        # Log the completed link action before terminalizing the task.  This
        # preserves the causal order in exported lifecycle traces:
        # transmit_started -> transmitted -> completed/late.
        self._event("transmitted", record=record, action=Action.TRANSMIT, rationale=decision.rationale, success=True, before=before)
        if self.satellite.time_s <= record.task.deadline_s + EPSILON:
            self._finalize_record(record, TaskStatus.COMPLETED, "timely delivery")
        else:
            self._finalize_record(record, TaskStatus.LATE, "delivery completed after deadline")
        return ActionResult(Action.TRANSMIT, record.task.id, True, duration_s, energy_j)

    def step(self) -> dict[str, Any]:
        self._arrive_due()
        self._expire_due(inclusive=True)
        state = self.snapshot()
        tasks = self.queue.ordered(state.time_s)
        decision = self.scheduler.decide(state, tasks, self)
        result = self.execute(decision)
        if not result.success and result.duration_s <= EPSILON:
            self.failed_action_count += 1
            fallback_duration = self._idle_duration()
            if fallback_duration > EPSILON:
                self._advance(fallback_duration, Action.IDLE)
        state = self.snapshot()
        row = {
            "time_s": state.time_s,
            "action": result.action.value,
            "task_id": result.task_id or "",
            "success": result.success,
            "reason": result.reason,
            "duration_s": result.duration_s,
            "energy_j": state.energy_j,
            "queue_length": state.queue_length,
            "storage_used_mb": self.satellite.storage_used_mb,
            "temperature_c": self.satellite.temperature_c,
        }
        self.history.append(row)
        self._assert_invariants()
        return row

    def run(self, duration_s: float | None = None) -> list[dict[str, Any]]:
        if duration_s is not None:
            requested_horizon_s = float(duration_s)
            latest_arrival_s = max(
                (task.created_at_s for task in self.task_arrivals),
                default=0.0,
            )
            if requested_horizon_s + EPSILON < latest_arrival_s:
                raise ValueError(
                    "run duration cannot precede a supplied task arrival; "
                    "filter or regenerate the workload first"
                )
            self.arrival_horizon_s = requested_horizon_s
            self.drain_end_s = max(
                self.arrival_horizon_s,
                max((task.deadline_s for task in self.task_arrivals), default=self.arrival_horizon_s),
            )
        while self.satellite.time_s < self.drain_end_s - EPSILON:
            self._arrive_due()
            self._expire_due(inclusive=True)
            if not self.queue.pending:
                next_arrival = self._next_arrival_time()
                if next_arrival is None:
                    break
                self._advance(next_arrival - self.satellite.time_s, Action.IDLE)
                continue
            self.step()
        self._arrive_due()
        self._expire_due(inclusive=True)
        for record in list(self.queue.pending.values()):
            self._finalize_record(record, TaskStatus.UNFINISHED, "drain horizon reached")
        self._assert_invariants(final=True)
        return self.history

    def _assert_invariants(self, *, final: bool = False) -> None:
        self.satellite.validate()
        expected_storage_mb = sum(
            record.payload_mb or 0.0
            for record in self.queue.pending.values()
            if record.storage_accounted
        )
        if not math.isclose(self.satellite.storage_used_mb, expected_storage_mb, abs_tol=1e-7):
            raise AssertionError(
                f"storage mismatch: state={self.satellite.storage_used_mb}, expected={expected_storage_mb}"
            )
        self.queue.validate_partition()
        if final:
            if len(self.queue.records) != self.generated_count:
                raise AssertionError("not every generated task entered the ledger")
            if self.queue.pending:
                raise AssertionError("active tasks remain after finalization")

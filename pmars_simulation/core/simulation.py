from __future__ import annotations
import random, simpy
from dataclasses import dataclass, field
from ..actions import Action, ActionResult, Decision
from ..environment import EnergyModel, ComputeModel, ThermalModel, StorageModel, CommunicationModel
from .satellite import Satellite
from .task import Task, TaskStatus
from .task_queue import TaskQueue, TaskRecord

@dataclass
class Simulation:
    satellite: Satellite; energy: EnergyModel; compute: ComputeModel; thermal: ThermalModel; storage: StorageModel; communication: CommunicationModel
    scheduler: object; seed: int = 42; sunlight_period_s: float = 600.; eclipse_period_s: float = 600.; task_arrivals: list[Task] = field(default_factory=list)
    queue: TaskQueue = field(default_factory=TaskQueue); history: list[dict] = field(default_factory=list); energy_consumed_j: float = 0.; peak_storage_mb: float = 0.
    def __post_init__(self): self.rng = random.Random(self.seed); self.env = simpy.Environment(); self.task_arrivals.sort(key=lambda t: t.created_at_s); self._arrival_index = 0
    def sunlight(self, time_s: float) -> bool: return time_s % (self.sunlight_period_s + self.eclipse_period_s) < self.sunlight_period_s
    def _sync_contact(self):
        c = self.communication.current(self.satellite.time_s); nxt = self.communication.next_contact(self.satellite.time_s)
        self.satellite.contact_available = c is not None; self.satellite.bandwidth_mbps = c.bandwidth_at(self.satellite.time_s) if c else 0.; self.satellite.latency_ms = c.latency_ms if c else 0.; self.satellite.contact_remaining_s = c.end_s-self.satellite.time_s if c else 0.; self.satellite.next_contact_s = nxt.start_s if nxt else None
    def _arrive(self):
        while self._arrival_index < len(self.task_arrivals) and self.task_arrivals[self._arrival_index].created_at_s <= self.satellite.time_s:
            task = self.task_arrivals[self._arrival_index]; self._arrival_index += 1
            if self.storage.can_store(self.satellite.storage_used_mb, task.input_size_mb): self.queue.add(task); self.satellite.storage_used_mb += task.input_size_mb
    def snapshot(self):
        self._sync_contact(); return self.satellite.snapshot(len(self.queue), sum(r.task.is_critical() for r in self.queue.pending.values()))
    def _advance(self, duration_s: float, action: Action):
        duration_s = max(0., duration_s); self.energy_consumed_j += self.energy.evolve(self.satellite, action.value, duration_s, self.sunlight(self.satellite.time_s)); self.thermal.evolve(action.value, duration_s); self.satellite.time_s += duration_s; self.env.run(until=self.satellite.time_s); self._arrive(); self.queue.expire(self.satellite.time_s); self.peak_storage_mb=max(self.peak_storage_mb,self.satellite.storage_used_mb)
    def process_duration(self, r: TaskRecord) -> float: return self.compute.processing_time(r.task, self.thermal)
    def tx_duration(self, r: TaskRecord) -> float: return self.communication.transfer_time(r.payload_mb or 0, self.satellite.time_s)
    def can_process(self, r: TaskRecord) -> bool:
        d=self.process_duration(r); return r.status != TaskStatus.PROCESSED and self.satellite.energy_j >= self.energy.process_power_w*d
    def can_transmit(self, r: TaskRecord) -> bool:
        d=self.tx_duration(r); return self.communication.feasible(r.payload_mb or 0,self.satellite.time_s) and self.satellite.energy_j >= self.energy.transmit_power_w*d
    def execute(self, decision: Decision) -> ActionResult:
        if decision.action == Action.IDLE: self._advance(5,Action.IDLE); return ActionResult(Action.IDLE,None,True,5,0)
        r=self.queue.get(decision.task_id or "")
        if not r: return ActionResult(decision.action,decision.task_id,False,0,0,"task unavailable")
        if decision.action == Action.PROCESS:
            if not self.can_process(r): return ActionResult(Action.PROCESS,r.task.id,False,0,0,"insufficient energy or already processed")
            d=self.process_duration(r); old=r.payload_mb or 0; self._advance(d,Action.PROCESS); r.payload_mb=r.task.processed_output_mb; r.status=TaskStatus.PROCESSED; self.satellite.storage_used_mb=max(0,self.satellite.storage_used_mb-old+r.payload_mb); return ActionResult(Action.PROCESS,r.task.id,True,d,self.energy.process_power_w*d)
        if decision.action == Action.STORE:
            r.stored=True; r.status=TaskStatus.STORED if r.status==TaskStatus.PENDING else r.status; self._advance(5,Action.STORE); return ActionResult(Action.STORE,r.task.id,True,5,self.energy.store_power_w*5)
        if not self.can_transmit(r): return ActionResult(Action.TRANSMIT,r.task.id,False,0,0,"contact/energy cannot complete transfer")
        d=self.tx_duration(r); self._advance(d,Action.TRANSMIT); self.satellite.storage_used_mb=max(0,self.satellite.storage_used_mb-(r.payload_mb or 0)); self.queue.complete(r,self.satellite.time_s); return ActionResult(Action.TRANSMIT,r.task.id,True,d,self.energy.transmit_power_w*d)
    def predict_candidates(self, r: TaskRecord, horizon_s: float):
        now=self.satellite.time_s; task=r.task; next_c=self.communication.next_contact(now); immediate_tx = self.can_transmit(r)
        plans=[]
        if immediate_tx: plans.append(((Action.TRANSMIT,), task.value_at(now)-self.energy.transmit_power_w*self.tx_duration(r)/100))
        if self.can_process(r):
            payload=task.processed_output_mb; c=self.communication.current(now) or next_c
            if c and c.start_s <= now+horizon_s: plans.append(((Action.PROCESS,Action.TRANSMIT),task.value_at(max(now,c.start_s))-self.energy.process_power_w*self.process_duration(r)/100))
        if next_c and next_c.start_s <= now+horizon_s:
            plans.append(((Action.STORE,Action.PROCESS,Action.TRANSMIT),task.value_at(next_c.start_s)-task.freshness_decay*10))
            plans.append(((Action.STORE,Action.TRANSMIT),task.value_at(next_c.start_s)-task.freshness_decay*10))
        return plans or [((Action.STORE,), task.value_at(now)-10)]
    def step(self):
        self._arrive(); state=self.snapshot(); tasks=self.queue.ordered(state.time_s); decision=self.scheduler.decide(state,tasks,self); result=self.execute(decision)
        if not result.success:
            self._advance(5, Action.IDLE)
        state=self.snapshot(); row={"time_s":state.time_s,"action":result.action.value,"task_id":result.task_id,"success":result.success,"energy_j":state.energy_j,"queue_length":state.queue_length,"storage_used_mb":self.satellite.storage_used_mb}; self.history.append(row); return row
    def run(self, duration_s: float):
        while self.satellite.time_s < duration_s: self.step()
        return self.history

"""Convert simulator snapshots into the integer contract representation."""

from .models import ContractState, ContractTask
from .units import capacity_bytes, deadline_ms, duration_ms, resident_bytes, scaled_milli, size_bytes


def contract_state(simulation) -> ContractState:
    sat = simulation.satellite
    contacts = tuple((duration_ms(item.start_s), deadline_ms(item.end_s),
                      max(0, int(item.bandwidth_start_mbps * 1_000_000)),
                      max(0, int(item.bandwidth_end_mbps * 1_000_000)),
                      duration_ms(item.latency_ms / 1000))
                     for item in simulation.communication.contacts)
    fraction = simulation.compute.available_fraction(simulation.thermal)
    return ContractState(
        now_ms=duration_ms(sat.time_s), energy_mj=max(0, int(sat.energy_j * 1000)),
        storage_used_bytes=resident_bytes(sat.storage_used_mb),
        storage_total_bytes=capacity_bytes(sat.storage_total_mb),
        memory_available_bytes=capacity_bytes(sat.memory_available_mb),
        compute_capacity_milli=scaled_milli(simulation.compute.capacity_units),
        throttle_fraction_milli=scaled_milli(fraction),
        processing_power_mw=scaled_milli(simulation.energy.process_power_w),
        transmit_power_mw=scaled_milli(simulation.energy.transmit_power_w),
        idle_power_mw=scaled_milli(simulation.energy.store_power_w),
        drain_horizon_ms=deadline_ms(simulation.drain_end_s), contacts=contacts,
    )


def contract_task(record) -> ContractTask:
    task = record.task
    return ContractTask(
        id=task.id, kind=task.type, input_bytes=size_bytes(task.input_size_mb),
        output_bytes_est=size_bytes(task.processed_output_mb),
        mem_req_bytes=capacity_bytes(task.memory_requirement_mb),
        demand_milli=scaled_milli(task.processing_demand),
        base_proc_ms=duration_ms(task.base_processing_time_s), priority=task.priority,
        value_milli=scaled_milli(task.mission_value), created_ms=duration_ms(task.created_at_s),
        deadline_ms=deadline_ms(task.deadline_s), payload_bytes=size_bytes(record.payload_mb or 0),
        processed=record.status.value == "processed",
    )

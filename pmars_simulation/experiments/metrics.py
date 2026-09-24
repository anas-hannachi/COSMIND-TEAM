from __future__ import annotations

import math

from ..core.task import TaskStatus


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def task_outcome_rows(sim) -> list[dict]:
    """Return one auditable row for every generated task."""
    rows: list[dict] = []
    for record in sorted(sim.queue.records.values(), key=lambda item: item.task.id):
        task = record.task
        terminal_time_s = record.finalized_at_s
        delivered = record.status in {TaskStatus.COMPLETED, TaskStatus.LATE}
        timely = record.status == TaskStatus.COMPLETED
        completion_time_s = record.completed_at_s if delivered else ""
        latency_s = (
            record.completed_at_s - task.created_at_s
            if record.completed_at_s is not None
            else ""
        )
        rows.append({
            "task_id": task.id,
            "task_type": task.type,
            "created_at_s": task.created_at_s,
            "deadline_s": task.deadline_s,
            "admitted_at_s": record.admitted_at_s if record.admitted_at_s is not None else "",
            "terminal_time_s": terminal_time_s if terminal_time_s is not None else "",
            "completion_time_s": completion_time_s,
            "latency_s": latency_s,
            "priority": task.priority,
            "critical": task.is_critical(),
            "input_size_mb": task.input_size_mb,
            "processed_output_mb": task.processed_output_mb,
            "final_payload_mb": record.payload_mb or 0.0,
            "memory_requirement_mb": task.memory_requirement_mb,
            "mission_value": task.mission_value,
            "freshness_adjusted_value": (
                task.value_at(record.completed_at_s) if timely and record.completed_at_s is not None else 0.0
            ),
            "terminal_status": record.status.value,
            "timely": timely,
            "outcome_reason": record.outcome_reason,
            "processed_at_s": record.processed_at_s if record.processed_at_s is not None else "",
            "attempts": record.attempts,
        })
    return rows


def calculate(sim) -> dict:
    """Calculate outcome-complete metrics from the full task ledger."""
    records = list(sim.queue.records.values())
    if len(records) != sim.generated_count:
        raise AssertionError("metrics requested before all generated tasks entered the ledger")
    if sim.queue.pending:
        raise AssertionError("metrics requested while active tasks remain")

    by_status = {
        status: [record for record in records if record.status == status]
        for status in (
            TaskStatus.COMPLETED,
            TaskStatus.REJECTED,
            TaskStatus.EXPIRED,
            TaskStatus.LATE,
            TaskStatus.UNFINISHED,
            TaskStatus.FAILED,
        )
    }
    generated = len(records)
    timely = by_status[TaskStatus.COMPLETED]
    admitted = [record for record in records if record.admitted_at_s is not None]
    critical = [record for record in records if record.task.is_critical()]
    timely_critical = [record for record in timely if record.task.is_critical()]
    timely_latencies = [
        record.completed_at_s - record.task.created_at_s
        for record in timely
        if record.completed_at_s is not None
    ]
    nominal_value_total = sum(record.task.mission_value for record in records)
    timely_nominal_value = sum(record.task.mission_value for record in timely)
    timely_fresh_value = sum(
        record.task.value_at(record.completed_at_s)
        for record in timely
        if record.completed_at_s is not None
    )
    non_timely_admitted = (
        len(by_status[TaskStatus.LATE])
        + len(by_status[TaskStatus.EXPIRED])
        + len(by_status[TaskStatus.UNFINISHED])
        + len(by_status[TaskStatus.FAILED])
    )
    contact_capacity_mb = sim.communication.capacity_mb_until(sim.drain_end_s)
    horizon_s = max(sim.drain_end_s, 1.0)
    outcome_sum = sum(len(items) for items in by_status.values())
    if outcome_sum != generated:
        raise AssertionError("terminal outcome partition does not equal generated tasks")

    return {
        "tasks_generated": generated,
        "tasks_admitted": len(admitted),
        "tasks_rejected": len(by_status[TaskStatus.REJECTED]),
        "tasks_completed_timely": len(timely),
        "tasks_late": len(by_status[TaskStatus.LATE]),
        "tasks_expired": len(by_status[TaskStatus.EXPIRED]),
        "tasks_unfinished": len(by_status[TaskStatus.UNFINISHED]),
        "tasks_failed": len(by_status[TaskStatus.FAILED]),
        "outcome_partition_count": outcome_sum,
        "task_completion_rate": len(timely) / generated if generated else 0.0,
        "critical_task_completion_rate": len(timely_critical) / len(critical) if critical else 0.0,
        "deadline_miss_rate_admitted": non_timely_admitted / len(admitted) if admitted else 0.0,
        "average_latency_s": _mean(timely_latencies),
        "median_latency_s": sorted(timely_latencies)[len(timely_latencies) // 2] if timely_latencies else 0.0,
        "p95_latency_s": _p95(timely_latencies),
        "mission_value_total": nominal_value_total,
        "timely_mission_value": timely_nominal_value,
        "timely_value_retention": timely_nominal_value / nominal_value_total if nominal_value_total else 0.0,
        "freshness_adjusted_timely_value": timely_fresh_value,
        "freshness_value_retention": timely_fresh_value / nominal_value_total if nominal_value_total else 0.0,
        "total_energy_consumed_j": sim.energy_consumed_j,
        "solar_energy_harvested_j": sim.energy_harvested_j,
        "energy_per_timely_task_j": sim.energy_consumed_j / len(timely) if timely else 0.0,
        "mission_efficiency": timely_nominal_value / sim.energy_consumed_j if sim.energy_consumed_j else 0.0,
        "minimum_battery_j": sim.min_energy_j,
        "final_battery_j": sim.satellite.energy_j,
        "total_transmitted_data_mb": sim.transmitted_data_mb,
        "timely_transmitted_data_mb": sim.timely_transmitted_data_mb,
        "contact_capacity_mb": contact_capacity_mb,
        "contact_utilization": sim.transmitted_data_mb / contact_capacity_mb if contact_capacity_mb else 0.0,
        "peak_storage_utilization": sim.peak_storage_mb / sim.satellite.storage_total_mb,
        "mean_storage_utilization": sim.storage_area_mb_s / (horizon_s * sim.satellite.storage_total_mb),
        "processing_time_s": sim.processing_time_s,
        "transmission_time_s": sim.transmission_time_s,
        "processing_duty_cycle": sim.processing_time_s / horizon_s,
        "maximum_temperature_c": sim.max_temperature_c,
        "failed_action_count": sim.failed_action_count,
        "arrival_horizon_s": sim.arrival_horizon_s,
        "drain_end_s": sim.drain_end_s,
    }

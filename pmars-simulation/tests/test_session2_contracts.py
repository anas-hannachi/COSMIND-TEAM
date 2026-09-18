"""Session 2 contract tests for Task, TaskQueue, SatelliteState, and Satellite."""

import pytest

from pmars_simulation.core.task import Task
from pmars_simulation.core.task_queue import TaskQueue
from pmars_simulation.core.satellite import Satellite, SatelliteState


def test_task_validates_required_fields_and_invariants() -> None:
    task = Task(
        id="task-1",
        type="telemetry",
        input_size_mb=100.0,
        processing_demand=25.0,
        base_processing_time_s=12.0,
        processing_energy_estimate_j=50.0,
        processed_output_mb=10.0,
        priority=5,
        mission_value=14.0,
        deadline_s=300.0,
        created_at_s=10.0,
        freshness_decay=0.1,
    )

    assert task.id == "task-1"
    assert task.type == "telemetry"
    assert task.to_dict()["id"] == "task-1"

    with pytest.raises(ValueError):
        Task(
            id="",
            type="telemetry",
            input_size_mb=10.0,
            processing_demand=1.0,
            base_processing_time_s=5.0,
            processing_energy_estimate_j=3.0,
            processed_output_mb=2.0,
            priority=1,
            mission_value=10.0,
            deadline_s=50.0,
            created_at_s=0.0,
            freshness_decay=0.15,
        )

    with pytest.raises(ValueError):
        Task(
            id="task-2",
            type="telemetry",
            input_size_mb=-1.0,
            processing_demand=1.0,
            base_processing_time_s=5.0,
            processing_energy_estimate_j=3.0,
            processed_output_mb=2.0,
            priority=1,
            mission_value=10.0,
            deadline_s=50.0,
            created_at_s=0.0,
            freshness_decay=0.15,
        )

    with pytest.raises(ValueError):
        Task(
            id="task-3",
            type="telemetry",
            input_size_mb=10.0,
            processing_demand=1.0,
            base_processing_time_s=0.0,
            processing_energy_estimate_j=3.0,
            processed_output_mb=2.0,
            priority=1,
            mission_value=10.0,
            deadline_s=50.0,
            created_at_s=0.0,
            freshness_decay=0.15,
        )


def test_task_queue_orders_tasks_and_supports_basic_operations() -> None:
    q = TaskQueue()

    assert len(q) == 0
    assert q.is_empty() is True

    task1 = Task(
        id="task-1",
        type="telemetry",
        input_size_mb=10.0,
        processing_demand=1.0,
        base_processing_time_s=5.0,
        processing_energy_estimate_j=3.0,
        processed_output_mb=2.0,
        priority=1,
        mission_value=5.0,
        deadline_s=50.0,
        created_at_s=0.0,
        freshness_decay=0.1,
    )

    task2 = Task(
        id="task-2",
        type="image",
        input_size_mb=15.0,
        processing_demand=3.0,
        base_processing_time_s=7.0,
        processing_energy_estimate_j=6.0,
        processed_output_mb=2.5,
        priority=4,
        mission_value=12.0,
        deadline_s=20.0,
        created_at_s=0.0,
        freshness_decay=0.2,
    )

    q.enqueue(task1)
    q.enqueue(task2)

    assert len(q) == 2
    assert q.peek() == task2
    assert q.sorted_tasks()[0] == task2

    popped = q.dequeue()
    assert popped == task2
    assert len(q) == 1
    assert q.peek() == task1

    q.clear()
    assert q.is_empty() is True


def test_satellite_state_snapshot_and_validation() -> None:
    sat = Satellite(
        time_s=12.5,
        energy_j=1500.0,
        battery_percent=87.0,
        solar_power_w=80.0,
        cpu_available=0.75,
        memory_available_mb=2000.0,
        temperature_c=22.0,
        storage_free_mb=500.0,
        queued_storage_mb=20.0,
        contact_available=True,
        bandwidth_mbps=50.0,
        latency_ms=15.0,
        contact_remaining_s=100.0,
        next_contact_s=300.0,
        queue_length=1,
        critical_task_count=0,
    )

    snapshot = sat.snapshot()
    assert isinstance(snapshot, SatelliteState)
    assert snapshot.time_s == 12.5
    assert snapshot.battery_percent == 87.0
    assert snapshot.contact_available is True
    assert snapshot.queue_length == 1

    sat.validate()

    sat2 = Satellite(energy_j=-1.0)
    with pytest.raises(ValueError):
        sat2.validate()

    sat3 = Satellite(battery_percent=101.0)
    with pytest.raises(ValueError):
        sat3.validate()


def test_single_task_can_enter_queue_and_satellite_can_be_inspected() -> None:
    task = Task(
        id="single-task",
        type="telemetry",
        input_size_mb=4.0,
        processing_demand=1.5,
        base_processing_time_s=6.0,
        processing_energy_estimate_j=10.0,
        processed_output_mb=1.0,
        priority=2,
        mission_value=9.0,
        deadline_s=120.0,
        created_at_s=0.0,
        freshness_decay=0.05,
    )

    queue = TaskQueue()
    queue.enqueue(task)

    sat = Satellite(
        time_s=0.0,
        energy_j=1000.0,
        battery_percent=100.0,
        solar_power_w=50.0,
        cpu_available=0.8,
        memory_available_mb=2048.0,
        temperature_c=20.0,
        storage_free_mb=800.0,
        queued_storage_mb=0.0,
        contact_available=False,
        bandwidth_mbps=0.0,
        latency_ms=0.0,
        contact_remaining_s=0.0,
        next_contact_s=120.0,
        queue_length=0,
        critical_task_count=0,
    )

    assert queue.peek() == task
    assert sat.snapshot().time_s == 0.0
    assert sat.snapshot().battery_percent == 100.0
    assert sat.snapshot().contact_available is False

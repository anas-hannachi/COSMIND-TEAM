from __future__ import annotations

import pytest

from pmars_simulation.actions import Action, Decision
from pmars_simulation.core.satellite import Satellite
from pmars_simulation.core.simulation import Simulation
from pmars_simulation.core.task import Task, TaskStatus
from pmars_simulation.environment import (
    CommunicationModel,
    ComputeModel,
    ContactWindow,
    EnergyModel,
    StorageModel,
    ThermalModel,
)
from pmars_simulation.experiments.metrics import calculate, task_outcome_rows
from pmars_simulation.experiments.runner import run
from pmars_simulation.experiments.sensitivity import _scaled_config, run_sensitivity
from pmars_simulation.experiments.trace import create_trace
from pmars_simulation.scenarios import build_simulation, generate_tasks, load_config
from pmars_simulation.schedulers.predictive_scheduler import PredictiveScheduler
from pmars_simulation.schedulers.edf_scheduler import EarliestDeadlineFirstScheduler
from pmars_simulation.schedulers.contact_knapsack_scheduler import ContactKnapsackScheduler


class IdleScheduler:
    name = "idle"

    def decide(self, state, tasks, simulation):
        return Decision(Action.IDLE, rationale="test idle")


class ProcessThenIdleScheduler:
    name = "process_then_idle"

    def decide(self, state, tasks, simulation):
        for record in tasks:
            if record.status != TaskStatus.PROCESSED:
                return Decision(Action.PROCESS, record.task.id, "test process")
        return Decision(Action.IDLE, rationale="test idle after processing")


class ProcessNamedThenIdleScheduler:
    name = "process_named_then_idle"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def decide(self, state, tasks, simulation):
        if simulation.queue.get(self.task_id) is not None:
            return Decision(Action.PROCESS, self.task_id, "test named process")
        return Decision(Action.IDLE, rationale="test idle")


def task(
    task_id: str,
    *,
    created_at_s: float = 0.0,
    deadline_s: float = 10.0,
    input_size_mb: float = 1.0,
    output_size_mb: float = 0.5,
    processing_time_s: float = 1.0,
    memory_mb: float = 64.0,
    mission_value: float = 10.0,
    priority: int = 5,
) -> Task:
    return Task(
        task_id,
        "test",
        input_size_mb,
        1.0,
        processing_time_s,
        45.0 * processing_time_s,
        output_size_mb,
        priority,
        mission_value,
        deadline_s,
        created_at_s,
        0.1,
        memory_mb,
    )


def simulation(tasks, *, storage_mb=10.0, contacts=(), scheduler=None, mission_duration_s=1.0) -> Simulation:
    return Simulation(
        satellite=Satellite(energy_j=8_000.0, battery_capacity_j=8_000.0, memory_available_mb=4_096.0, storage_total_mb=storage_mb),
        energy=EnergyModel(capacity_j=8_000.0, idle_power_w=1.0, process_power_w=45.0, transmit_power_w=80.0, store_power_w=1.0, solar_power_w=0.0),
        compute=ComputeModel(),
        thermal=ThermalModel(),
        storage=StorageModel(storage_mb),
        communication=CommunicationModel(tuple(contacts)),
        scheduler=scheduler or IdleScheduler(),
        task_arrivals=list(tasks),
        mission_duration_s=mission_duration_s,
        sunlight_period_s=0.0,
        eclipse_period_s=1.0,
    )


def test_task_value_decays_and_validates():
    item = task("a", deadline_s=30.0)
    assert item.value_at(60.0) < item.mission_value


def test_communication_rejects_contact_overrun():
    communication = CommunicationModel((ContactWindow(10, 20, 1, 1, 100),))
    assert communication.feasible(1, 19) is False
    assert communication.transfer_time(1, 10) == 8.1


def test_rejected_arrival_stays_in_generated_denominator():
    sim = simulation([task("too-large", input_size_mb=2.0)], storage_mb=1.0)
    sim.run()
    metrics = calculate(sim)
    assert metrics["tasks_generated"] == 1
    assert metrics["tasks_rejected"] == 1
    assert metrics["outcome_partition_count"] == 1
    assert sim.queue.records["too-large"].status == TaskStatus.REJECTED


def test_raw_expiry_releases_storage():
    sim = simulation([task("raw", deadline_s=1.0)], storage_mb=2.0)
    sim.run()
    assert sim.queue.records["raw"].status == TaskStatus.EXPIRED
    assert sim.satellite.storage_used_mb == 0.0


def test_processed_expiry_releases_processed_payload():
    sim = simulation(
        [task("processed", deadline_s=5.0, input_size_mb=2.0, output_size_mb=0.5)],
        storage_mb=3.0,
        scheduler=ProcessThenIdleScheduler(),
    )
    sim.run()
    record = sim.queue.records["processed"]
    assert record.processed_at_s is not None
    assert record.status == TaskStatus.EXPIRED
    assert sim.satellite.storage_used_mb == 0.0


def test_late_delivery_is_not_credited_as_timely():
    late_task = task("late", deadline_s=2.0, input_size_mb=1.0)
    horizon_task = task("horizon", deadline_s=10.0, input_size_mb=20.0)
    sim = simulation(
        [late_task, horizon_task],
        contacts=(ContactWindow(0, 10, 1, 1, 100),),
        mission_duration_s=0.0,
    )
    sim._arrive_due()
    result = sim.execute(Decision(Action.TRANSMIT, "late", "late-delivery test"))
    assert result.success
    assert sim.queue.records["late"].status == TaskStatus.LATE
    assert sim.queue.records["late"] not in sim.queue.completed
    sim._expire_due(inclusive=True)
    metrics = calculate(sim)
    assert metrics["tasks_completed_timely"] == 0
    assert metrics["tasks_late"] == 1
    assert metrics["timely_mission_value"] == 0.0


def test_all_generated_tasks_have_one_terminal_outcome():
    sim = build_simulation("normal", "predictive", 7)
    sim.run()
    metrics = calculate(sim)
    assert metrics["tasks_generated"] == metrics["outcome_partition_count"]
    assert metrics["tasks_unfinished"] == 0
    assert len(task_outcome_rows(sim)) == metrics["tasks_generated"]


def test_storage_and_energy_bounds_hold_after_full_run():
    sim = build_simulation("task_burst", "predictive", 3)
    sim.run()
    assert 0.0 <= sim.satellite.storage_used_mb <= sim.satellite.storage_total_mb
    assert 0.0 <= sim.satellite.energy_j <= sim.satellite.battery_capacity_j


def test_memory_requirement_is_enforced_for_processing():
    sim = simulation([task("memory", memory_mb=5_000.0)])
    sim._arrive_due()
    record = sim.queue.get("memory")
    assert record is not None
    assert sim.can_process(record) is False


def test_arrivals_after_mission_horizon_are_rejected_by_the_input_contract():
    with pytest.raises(ValueError, match="after mission_duration_s"):
        simulation([task("late-arrival", created_at_s=2.0)], mission_duration_s=1.0)


def test_expanding_process_result_never_overflows_storage_after_concurrent_arrival():
    growing = task(
        "growing",
        deadline_s=20.0,
        input_size_mb=1.0,
        output_size_mb=2.5,
        processing_time_s=2.0,
    )
    concurrent = task("concurrent", created_at_s=1.0, deadline_s=20.0, input_size_mb=1.0)
    sim = simulation(
        [growing, concurrent],
        storage_mb=3.0,
        scheduler=ProcessNamedThenIdleScheduler("growing"),
    )
    sim.run()
    assert sim.queue.records["growing"].status == TaskStatus.FAILED
    assert 0.0 <= sim.satellite.storage_used_mb <= sim.satellite.storage_total_mb


def test_workload_generation_is_scheduler_independent_and_reproducible():
    config = load_config("normal")
    first = generate_tasks(config, 42)
    second = generate_tasks(config, 42)
    assert first == second
    assert first != generate_tasks(config, 43)


def test_repeated_scheduler_run_is_reproducible():
    first = build_simulation("normal", "predictive", 7)
    second = build_simulation("normal", "predictive", 7)
    assert first.run() == second.run()
    assert calculate(first) == calculate(second)


def test_named_profiles_configure_compute_and_thermal_models():
    scenario_config = load_config("thermal_burst_stress")
    sim = build_simulation("thermal_burst_stress", "predictive", 4)
    assert scenario_config["model_profile"] == "thermal_stress_v1"
    assert sim.compute.capacity_units == scenario_config["compute"]["capacity_units"]
    assert sim.compute.throttled_capacity_fraction == 0.4
    assert sim.thermal.heating_c_per_s == 0.3
    assert sim.thermal.throttle_at_fraction == 0.6


def test_thermal_stress_scenario_reaches_its_throttle_threshold():
    sim = build_simulation("thermal_burst_stress", "rule", 100)
    sim.run(sim.mission_duration_s)
    assert sim.max_temperature_c >= sim.thermal.max_temp_c * sim.thermal.throttle_at_fraction


def test_sensitivity_scales_compute_and_thermal_profile_values():
    compute = _scaled_config("normal", "compute_capacity_units", 1.2)
    thermal = _scaled_config("normal", "thermal_heating_c_per_s", 1.5)
    contact = _scaled_config("normal", "contact_window_duration", 0.5)
    deadline = _scaled_config("normal", "deadline_s", 0.5)
    energy = _scaled_config("normal", "available_energy_j", 0.5)
    storage = _scaled_config("normal", "storage_mb", 0.5)
    assert compute["compute"]["capacity_units"] == pytest.approx(120.0)
    assert thermal["thermal"]["heating_c_per_s"] == pytest.approx(0.12)
    assert contact["contacts"][0]["end_s"] == pytest.approx(160.0)
    assert deadline["workload"]["deadline_s"] == [60.0, 300.0]
    assert energy["energy"]["initial_energy_j"] == pytest.approx(2500.0)
    assert storage["storage_mb"] == pytest.approx(1000.0)
    with pytest.raises(ValueError, match="finite and positive"):
        _scaled_config("normal", "process_power_w", float("nan"))


def test_edf_picks_earliest_deadline_feasible_task():
    earlier = task("earlier", deadline_s=12.0)
    later = task("later", deadline_s=20.0)
    sim = simulation(
        [later, earlier],
        contacts=(ContactWindow(0, 40, 1, 1, 100),),
        scheduler=EarliestDeadlineFirstScheduler(),
        mission_duration_s=0.0,
    )
    sim._arrive_due()
    decision = sim.scheduler.decide(sim.snapshot(), sim.queue.ordered(0.0), sim)
    assert decision.task_id == "earlier"
    assert decision.action == Action.TRANSMIT


def test_contact_knapsack_beats_single_largest_payload_value():
    small_a = task("small-a", deadline_s=30.0, input_size_mb=1.0, mission_value=7.0)
    small_b = task("small-b", deadline_s=30.0, input_size_mb=1.0, mission_value=7.0)
    large = task("large", deadline_s=30.0, input_size_mb=2.0, mission_value=12.0)
    sim = simulation(
        [small_a, small_b, large],
        contacts=(ContactWindow(0, 18, 1, 1, 100),),
        scheduler=ContactKnapsackScheduler(),
        mission_duration_s=0.0,
    )
    sim._arrive_due()
    decision = sim.scheduler.decide(sim.snapshot(), sim.queue.ordered(0.0), sim)
    assert decision.task_id in {"small-a", "small-b"}
    assert "packed 2 payloads" in decision.rationale
    assert "value=14.0" in decision.rationale


def test_contact_knapsack_selects_higher_value_subset_without_exact_fill():
    low_value_long = task("long-low", input_size_mb=10.0, mission_value=1.0, deadline_s=30.0)
    high_value_short = task("short-high", input_size_mb=9.0, mission_value=100.0, deadline_s=30.0)
    sim = simulation(
        [low_value_long, high_value_short],
        storage_mb=25.0,
        contacts=(ContactWindow(0, 10, 8, 8, 0),),
        scheduler=ContactKnapsackScheduler(),
        mission_duration_s=0.0,
    )
    sim._arrive_due()
    decision = sim.scheduler.decide(sim.snapshot(), sim.queue.ordered(0.0), sim)
    assert decision.action == Action.TRANSMIT
    assert decision.task_id == "short-high"
    assert "value=100.0" in decision.rationale


def test_contact_knapsack_selects_feasible_subset_when_contact_is_not_filled():
    tasks = [
        task(task_id, input_size_mb=3.0, mission_value=1.0, deadline_s=30.0)
        for task_id in ("three-a", "three-b", "three-c")
    ]
    sim = simulation(
        tasks,
        contacts=(ContactWindow(0, 10, 8, 8, 0),),
        scheduler=ContactKnapsackScheduler(),
        mission_duration_s=0.0,
    )
    sim._arrive_due()
    decision = sim.scheduler.decide(sim.snapshot(), sim.queue.ordered(0.0), sim)
    assert decision.action == Action.TRANSMIT
    assert decision.task_id in {"three-a", "three-b", "three-c"}
    assert "packed 3 payloads" in decision.rationale


def test_sensitivity_runner_exports_matched_policy_sweep(tmp_path):
    rows = run_sensitivity(
        parameters=("thermal_heating_c_per_s",),
        multipliers=(1.0,),
        scenarios=("normal",),
        schedulers=("greedy", "predictive"),
        seeds=[2],
        output=tmp_path,
        allow_dirty=True,
    )
    assert len(rows) == 2
    assert rows[0]["workload_sha256"] == rows[1]["workload_sha256"]
    assert (tmp_path / "raw_runs.csv").exists()
    assert (tmp_path / "paired_comparisons.csv").exists()
    assert (tmp_path / "manifest.json").exists()


def test_predictive_can_select_lower_edf_task_when_first_has_no_feasible_route():
    blocked = task("blocked", deadline_s=5.0, input_size_mb=100.0, output_size_mb=100.0)
    viable = task("viable", deadline_s=20.0, input_size_mb=0.1, output_size_mb=0.05)
    sim = simulation(
        [blocked, viable],
        contacts=(ContactWindow(0, 15, 1, 1, 100),),
        scheduler=PredictiveScheduler(horizon_s=30.0),
        mission_duration_s=0.0,
    )
    sim._arrive_due()
    decision = sim.scheduler.decide(sim.snapshot(), sim.queue.ordered(0.0), sim)
    assert decision.task_id == "viable"
    assert decision.action == Action.TRANSMIT


def test_predictive_process_candidate_requires_feasible_result_contact():
    item = task("compress", deadline_s=50.0, input_size_mb=4.0, output_size_mb=0.1)
    with_contact = simulation(
        [item],
        contacts=(ContactWindow(20, 30, 1, 1, 100),),
        mission_duration_s=0.0,
    )
    with_contact._arrive_due()
    record = with_contact.queue.get("compress")
    assert record is not None
    assert any(candidate["first_action"] == Action.PROCESS for candidate in with_contact.plan_candidates(record, 60.0))

    without_contact = simulation([item], mission_duration_s=0.0)
    without_contact._arrive_due()
    record = without_contact.queue.get("compress")
    assert record is not None
    assert all(candidate["first_action"] != Action.PROCESS for candidate in without_contact.plan_candidates(record, 60.0))


def test_trace_events_contain_before_after_state_and_rationale():
    sim = build_simulation("normal", "predictive", 2)
    sim.run()
    action_events = [event for event in sim.events if event["event"] in {"processed", "transmitted", "stored"}]
    assert action_events
    assert all("rationale" in event and "energy_j" in event and "storage_used_mb" in event for event in action_events)


def test_trace_export_is_generated_from_a_real_completed_task(tmp_path):
    summary = create_trace(scenario="normal", scheduler="predictive", seed=2, output=tmp_path)
    assert summary["terminal_status"] == TaskStatus.COMPLETED.value
    assert (tmp_path / "trace_demo.csv").exists()
    assert (tmp_path / "trace_demo.svg").exists()
    assert (tmp_path / "trace_demo.md").exists()


def test_runner_exports_matched_workloads_and_trace(tmp_path):
    rows = run(
        scenarios=("normal",),
        schedulers=("greedy", "predictive"),
        seeds=[2],
        output=tmp_path,
        evaluation_version="test",
        allow_dirty=True,
    )
    assert len(rows) == 2
    assert rows[0]["workload_sha256"] == rows[1]["workload_sha256"]
    assert (tmp_path / "raw_runs.csv").exists()
    assert (tmp_path / "figures" / "terminal_outcomes.svg").exists()
    assert (tmp_path / "trace" / "trace_demo.csv").exists()


def test_runner_can_append_non_overlapping_shards(tmp_path):
    first = run(
        scenarios=("normal",),
        schedulers=("greedy",),
        seeds=[2],
        output=tmp_path,
        evaluation_version="test-append",
        allow_dirty=True,
    )
    second = run(
        scenarios=("poor_link",),
        schedulers=("predictive",),
        seeds=[2],
        output=tmp_path,
        evaluation_version="test-append",
        allow_dirty=True,
        append=True,
    )
    assert len(first) == 1
    assert len(second) == 2
    assert (tmp_path / "configs" / "normal.yaml").exists()
    assert (tmp_path / "configs" / "poor_link.yaml").exists()
    commands = (tmp_path / "commands.txt").read_text(encoding="utf-8")
    assert "--scenarios normal" in commands
    assert "--scenarios poor_link" in commands

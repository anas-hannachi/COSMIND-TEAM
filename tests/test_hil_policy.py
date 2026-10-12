import ast
from pathlib import Path

import pytest

from pmars_simulation.contract.models import ContractConfig, ContractState, ContractTask
from pmars_simulation.policy import edf, rule
from pmars_simulation.experiments.metrics import calculate
from pmars_simulation.scenarios import BENCH_SCENARIO_NAMES, build_simulation, generate_tasks, load_config
from pmars_simulation.environment.thermal import ThermalModel


def _task(task_id: str, deadline: int, priority: int = 2) -> ContractTask:
    return ContractTask(task_id, "telemetry", 100, 50, 10, 100, 1000, priority,
                        1000, 0, deadline)


def test_pure_policy_selects_integer_candidates_without_simpy():
    state = ContractState(now_ms=0, energy_mj=100_000, storage_used_bytes=0,
                          storage_total_bytes=1000, memory_available_bytes=1000,
                          compute_capacity_milli=1_000_000, processing_power_mw=100,
                          contacts=((0, 20_000, 1_000_000, 1_000_000, 0),))
    tasks = [_task("b", 5000), _task("a", 4000)]
    assert edf.decide(state, tasks).task_id == "a"
    assert rule.decide(state, tasks, ContractConfig()).task_id == "a"
    package_root = Path(__file__).resolve().parents[1] / "pmars_simulation" / "policy"
    imported = []
    for source in package_root.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported.extend(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
        imported.extend(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert not any(name == "simpy" or name.startswith("simpy.") or name.endswith("core.simulation") for name in imported)


def test_transmit_heating_is_optional_and_default_off():
    legacy = ThermalModel(temperature_c=30, cooling_c_per_s=0.02)
    legacy.evolve("TRANSMIT", 10)
    assert legacy.temperature_c == pytest.approx(29.8)
    enabled = ThermalModel(temperature_c=30, cooling_c_per_s=0.02, transmit_heating_c_per_s=0.1)
    enabled.evolve("TRANSMIT", 10)
    assert enabled.temperature_c == pytest.approx(31.0)
def test_bench_scenarios_are_deterministic_and_have_lifecycle():
    for scenario in BENCH_SCENARIO_NAMES:
        config = load_config(scenario)
        tasks = generate_tasks(config, 100)
        for scheduler in ("random", "rule", "greedy", "edf", "contact_knapsack", "predictive"):
            first = build_simulation(scenario, scheduler, 100, tasks=tasks)
            first.run(config["mission_duration_s"])
            second = build_simulation(scenario, scheduler, 100, tasks=tasks)
            second.run(config["mission_duration_s"])
            assert calculate(first) == calculate(second)
            metrics = calculate(first)
            assert metrics["tasks_failed"] == 0
            assert metrics["outcome_partition_count"] == metrics["tasks_generated"]
        for scheduler in ("rule", "edf"):
            sim = build_simulation(scenario, scheduler, 100, tasks=tasks)
            sim.run(config["mission_duration_s"])
            events = sim.events
            kinds = [event["event"] for event in events]
            assert "completed" in kinds and "expired" in kinds
            lifecycle_ids = {event.get("task_id") for event in events if event["event"] == "processed"}
            assert any(
                any(event["event"] == "store_started" and event.get("task_id") == task_id for event in events)
                and any(event["event"] == "transmit_started" and event.get("task_id") == task_id for event in events)
                and any(event["event"] == "completed" and event.get("task_id") == task_id for event in events)
                for task_id in lifecycle_ids
            )

from __future__ import annotations

import hashlib
import json
import random

from dataclasses import asdict
from pathlib import Path

import yaml

from .core.satellite import Satellite
from .core.simulation import Simulation
from .core.task import Task
from .environment import (
    CommunicationModel,
    ComputeModel,
    ContactWindow,
    EnergyModel,
    StorageModel,
    ThermalModel,
)
from .schedulers import (
    ContactKnapsackScheduler,
    EarliestDeadlineFirstScheduler,
    GreedyScheduler,
    PredictiveScheduler,
    RandomScheduler,
    RuleScheduler,
)


ROOT = Path(__file__).resolve().parent.parent
SCENARIO_NAMES = (
    "normal",
    "low_energy",
    "poor_link",
    "task_burst",
    "critical",
    "energy_link_stress",
    "thermal_burst_stress",
)


def load_config(name: str) -> dict:
    if name not in SCENARIO_NAMES:
        raise ValueError(f"unknown scenario: {name}")
    with (ROOT / "scenarios" / f"{name}.yaml").open(encoding="utf-8") as handle:
        scenario = yaml.safe_load(handle)
    profile_name = scenario.get("model_profile", "synthetic_v1")
    profile_path = ROOT / "profiles" / f"{profile_name}.yaml"
    if not profile_path.is_file():
        raise ValueError(f"unknown model profile '{profile_name}' for scenario '{name}'")
    with profile_path.open(encoding="utf-8") as handle:
        profile = yaml.safe_load(handle)
    merged = {**profile, **scenario}
    for section in ("energy", "compute", "thermal"):
        merged[section] = {**profile.get(section, {}), **scenario.get(section, {})}
    merged["model_profile"] = profile_name
    return merged


def model_profile_sha256(profile_name: str) -> str:
    profile_path = ROOT / "profiles" / f"{profile_name}.yaml"
    if not profile_path.is_file():
        raise ValueError(f"unknown model profile: {profile_name}")
    return hashlib.sha256(profile_path.read_bytes()).hexdigest()


def config_sha256(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_tasks(config: dict, seed: int) -> list[Task]:
    """Generate a deterministic workload from a scenario and workload seed.

    Freshness decay is expressed per simulated minute. The workloads are
    deliberately synthetic stress configurations, not calibrated missions.
    """
    rng = random.Random(seed)
    time_s = 0.0
    tasks: list[Task] = []
    duration_s = config["mission_duration_s"]
    workload = config["workload"]
    # type, nominal size MB, priority, processed/raw ratio, freshness per min,
    # memory MB
    kinds = [
        ("telemetry", 3.0, 1, 0.20, 0.10, 64.0),
        ("earth_image", 40.0, 5, 0.70, 0.03, 1024.0),
        ("emergency", 12.0, 9, 0.90, 0.80, 256.0),
        ("science_image", 80.0, 4, 0.50, 0.005, 1536.0),
    ]
    while time_s < duration_s:
        time_s += rng.uniform(*workload["interarrival_s"])
        if time_s >= duration_s:
            break
        task_type, size_mb, priority, output_ratio, decay, memory_mb = rng.choice(kinds)
        if rng.random() < workload["critical_probability"]:
            task_type, priority, decay, memory_mb = "emergency", 9, 0.80, 256.0
        input_size_mb = size_mb * rng.uniform(0.7, 1.3)
        base_processing_time_s = max(2.0, input_size_mb * 0.25)
        deadline_s = time_s + rng.uniform(*workload["deadline_s"])
        tasks.append(Task(
            id=f"{seed}-{len(tasks)}",
            type=task_type,
            input_size_mb=input_size_mb,
            processing_demand=input_size_mb / 10.0,
            base_processing_time_s=base_processing_time_s,
            processing_energy_estimate_j=45.0 * base_processing_time_s,
            processed_output_mb=input_size_mb * output_ratio,
            priority=priority,
            mission_value=input_size_mb * priority,
            deadline_s=deadline_s,
            created_at_s=time_s,
            freshness_decay=decay,
            memory_requirement_mb=memory_mb,
        ))
    return tasks


def workload_sha256(tasks: list[Task]) -> str:
    payload = [asdict(task) for task in tasks]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def task_manifest_rows(tasks: list[Task]) -> list[dict]:
    return [asdict(task) for task in tasks]


def make_scheduler(name: str, policy_seed: int):
    schedulers = {
        "random": RandomScheduler(policy_seed),
        "rule": RuleScheduler(),
        "greedy": GreedyScheduler(),
        "edf": EarliestDeadlineFirstScheduler(),
        "contact_knapsack": ContactKnapsackScheduler(),
        "predictive": PredictiveScheduler(),
    }
    try:
        return schedulers[name]
    except KeyError as exc:
        raise ValueError(f"unknown scheduler: {name}") from exc


def build_simulation(
    name: str,
    scheduler_name: str,
    seed: int,
    *,
    policy_seed: int | None = None,
    tasks: list[Task] | None = None,
    config_override: dict | None = None,
) -> Simulation:
    config = config_override if config_override is not None else load_config(name)
    energy_config = config["energy"]
    contacts = tuple(ContactWindow(**contact) for contact in config["contacts"])
    policy_seed = policy_seed if policy_seed is not None else seed + 100_000
    workload = tasks if tasks is not None else generate_tasks(config, seed)
    compute_config = {
        "ram_total_mb": config.get("memory_mb", 4096.0),
        **config.get("compute", {}),
    }
    memory_available_mb = config.get("memory_mb", compute_config["ram_total_mb"])
    return Simulation(
        satellite=Satellite(
            energy_j=energy_config["initial_energy_j"],
            battery_capacity_j=energy_config["capacity_j"],
            memory_available_mb=memory_available_mb,
            storage_total_mb=config["storage_mb"],
        ),
        energy=EnergyModel(**{
            key: value
            for key, value in energy_config.items()
            if key != "initial_energy_j"
        }),
        compute=ComputeModel(**compute_config),
        thermal=ThermalModel(**config.get("thermal", {})),
        storage=StorageModel(config["storage_mb"]),
        communication=CommunicationModel(contacts),
        scheduler=make_scheduler(scheduler_name, policy_seed),
        seed=seed,
        sunlight_period_s=config["sunlight_s"],
        eclipse_period_s=config["eclipse_s"],
        task_arrivals=list(workload),
        mission_duration_s=config["mission_duration_s"],
        policy_seed=policy_seed,
    )

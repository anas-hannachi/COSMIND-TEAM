from __future__ import annotations

import argparse
import csv
import json
import math

from collections import defaultdict
from pathlib import Path

from ..analysis.statistics import mean_ci95
from ..scenarios import (
    SCENARIO_NAMES,
    build_simulation,
    config_sha256,
    generate_tasks,
    load_config,
    model_profile_sha256,
    workload_sha256,
)
from .metrics import calculate
from .runner import DEFAULT_SCHEDULERS, _git_is_dirty, _git_sha


PARAMETERS = (
    "process_power_w",
    "transmit_power_w",
    "solar_power_w",
    "contact_bandwidth",
    "contact_window_duration",
    "interarrival_s",
    "deadline_s",
    "available_energy_j",
    "storage_mb",
    "compute_capacity_units",
    "throttled_capacity_fraction",
    "thermal_heating_c_per_s",
    "thermal_cooling_c_per_s",
    "throttle_at_fraction",
)


def _scaled_config(name: str, parameter: str, multiplier: float) -> dict:
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("sensitivity multipliers must be finite and positive")
    config = load_config(name)
    if parameter in {"process_power_w", "transmit_power_w", "solar_power_w"}:
        config["energy"][parameter] *= multiplier
    elif parameter == "contact_bandwidth":
        for contact in config["contacts"]:
            contact["bandwidth_start_mbps"] *= multiplier
            contact["bandwidth_end_mbps"] *= multiplier
    elif parameter == "contact_window_duration":
        for contact in config["contacts"]:
            contact["end_s"] = contact["start_s"] + (
                contact["end_s"] - contact["start_s"]
            ) * multiplier
    elif parameter == "interarrival_s":
        config["workload"][parameter] = [value * multiplier for value in config["workload"][parameter]]
    elif parameter == "deadline_s":
        config["workload"][parameter] = [value * multiplier for value in config["workload"][parameter]]
    elif parameter == "available_energy_j":
        config["energy"]["initial_energy_j"] *= multiplier
    elif parameter == "storage_mb":
        config["storage_mb"] *= multiplier
    elif parameter == "compute_capacity_units":
        config["compute"]["capacity_units"] *= multiplier
    elif parameter == "throttled_capacity_fraction":
        config["compute"]["throttled_capacity_fraction"] *= multiplier
        config["compute"]["throttled_capacity_fraction"] = min(
            config["compute"]["throttled_capacity_fraction"], 1.0,
        )
    elif parameter in {"thermal_heating_c_per_s", "thermal_cooling_c_per_s", "throttle_at_fraction"}:
        key = parameter.removeprefix("thermal_")
        config["thermal"][key] *= multiplier
        if key == "throttle_at_fraction":
            config["thermal"][key] = min(config["thermal"][key], 1.0)
    else:
        raise ValueError(f"unknown sensitivity parameter: {parameter}")
    return config


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_sensitivity(
    *,
    parameters: tuple[str, ...] = ("process_power_w",),
    multipliers: tuple[float, ...] = (0.75, 1.0, 1.25),
    scenarios: tuple[str, ...] = SCENARIO_NAMES,
    schedulers: tuple[str, ...] = DEFAULT_SCHEDULERS,
    seeds=range(100, 120),
    output: str | Path = "results/sensitivity",
    allow_dirty: bool = False,
) -> list[dict]:
    """Run matched scheduler matrices while scaling one model assumption at a time."""
    source_tree_dirty = _git_is_dirty()
    if source_tree_dirty and not allow_dirty:
        raise RuntimeError("commit source changes before producing reproducible sensitivity artifacts")
    if not parameters or any(parameter not in PARAMETERS for parameter in parameters):
        raise ValueError(f"parameters must be selected from: {', '.join(PARAMETERS)}")
    if not multipliers or any(not math.isfinite(value) or value <= 0 for value in multipliers):
        raise ValueError("provide one or more finite positive multipliers")

    seed_list = list(seeds)
    source_sha = _git_sha()
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for scenario in scenarios:
        for parameter in parameters:
            for multiplier in multipliers:
                config = _scaled_config(scenario, parameter, multiplier)
                scenario_hash = config_sha256(config)
                for seed in seed_list:
                    tasks = generate_tasks(config, seed)
                    task_hash = workload_sha256(tasks)
                    for scheduler in schedulers:
                        policy_seed = seed + 100_000
                        sim = build_simulation(
                            scenario,
                            scheduler,
                            seed,
                            policy_seed=policy_seed,
                            tasks=tasks,
                            config_override=config,
                        )
                        sim.run(config["mission_duration_s"])
                        identity = {
                            "code_commit_sha": source_sha,
                            "scenario": scenario,
                            "parameter": parameter,
                            "multiplier": multiplier,
                            "model_profile": config["model_profile"],
                            "model_profile_sha256": model_profile_sha256(config["model_profile"]),
                            "scheduler": scheduler,
                            "workload_seed": seed,
                            "policy_seed": policy_seed,
                            "config_sha256": scenario_hash,
                            "workload_sha256": task_hash,
                        }
                        rows.append({**identity, **calculate(sim)})

    summary_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["scenario"], row["parameter"], row["multiplier"], row["scheduler"])
        summary_groups[key].append(row)
    summaries = []
    for key, group in sorted(summary_groups.items()):
        summary = dict(zip(("scenario", "parameter", "multiplier", "scheduler"), key))
        summary["sample_count"] = len(group)
        for metric in ("timely_value_retention", "task_completion_rate", "total_energy_consumed_j"):
            mean, standard_deviation, ci95 = mean_ci95([float(row[metric]) for row in group])
            summary[f"{metric}_mean"] = mean
            summary[f"{metric}_std"] = standard_deviation
            summary[f"{metric}_ci95"] = ci95
        summaries.append(summary)

    comparisons = []
    index = {
        (row["scenario"], row["parameter"], row["multiplier"], row["scheduler"], row["workload_seed"]): row
        for row in rows
    }
    baselines = tuple(
        name for name in ("greedy", "rule", "edf", "contact_knapsack")
        if name in schedulers
    )
    if "predictive" in schedulers:
        for scenario in scenarios:
            for parameter in parameters:
                for multiplier in multipliers:
                    for baseline in baselines:
                        differences = [
                            float(index[(scenario, parameter, multiplier, "predictive", seed)]["timely_value_retention"])
                            - float(index[(scenario, parameter, multiplier, baseline, seed)]["timely_value_retention"])
                            for seed in seed_list
                            if (scenario, parameter, multiplier, "predictive", seed) in index
                            and (scenario, parameter, multiplier, baseline, seed) in index
                        ]
                        mean, standard_deviation, ci95 = mean_ci95(differences)
                        comparisons.append({
                            "scenario": scenario,
                            "parameter": parameter,
                            "multiplier": multiplier,
                            "candidate": "predictive",
                            "baseline": baseline,
                            "metric": "timely_value_retention",
                            "paired_sample_count": len(differences),
                            "paired_difference_mean": mean,
                            "paired_difference_std": standard_deviation,
                            "paired_difference_ci95": ci95,
                            "ci95_low": mean - ci95,
                            "ci95_high": mean + ci95,
                        })

    _write_csv(output_path / "raw_runs.csv", rows)
    _write_csv(output_path / "summaries.csv", summaries)
    _write_csv(output_path / "paired_comparisons.csv", comparisons)
    manifest = {
        "experiment": "one-factor-at-a-time sensitivity analysis",
        "code_commit_sha": source_sha,
        "source_tree_clean": not source_tree_dirty,
        "scenarios": list(scenarios),
        "schedulers": list(schedulers),
        "parameters": list(parameters),
        "model_profiles": {
            profile: model_profile_sha256(profile)
            for profile in sorted({load_config(scenario)["model_profile"] for scenario in scenarios})
        },
        "multipliers": list(multipliers),
        "seeds": seed_list,
        "run_count": len(rows),
        "primary_metric": "timely_value_retention",
        "interpretation": "Scaled coefficients are sensitivity assumptions, not hardware measurements.",
    }
    (output_path / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run matched PMARS model-parameter sensitivity sweeps.")
    parser.add_argument("--parameters", nargs="+", choices=PARAMETERS, default=("process_power_w",))
    parser.add_argument("--multipliers", nargs="+", type=float, default=(0.75, 1.0, 1.25))
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIO_NAMES, default=SCENARIO_NAMES)
    parser.add_argument("--schedulers", nargs="+", choices=DEFAULT_SCHEDULERS, default=DEFAULT_SCHEDULERS)
    parser.add_argument("--seed-start", type=int, default=100)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--output", default="results/sensitivity")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    run_sensitivity(
        parameters=tuple(args.parameters),
        multipliers=tuple(args.multipliers),
        scenarios=tuple(args.scenarios),
        schedulers=tuple(args.schedulers),
        seeds=range(args.seed_start, args.seed_start + args.seeds),
        output=args.output,
        allow_dirty=args.allow_dirty,
    )


if __name__ == "__main__":
    main()

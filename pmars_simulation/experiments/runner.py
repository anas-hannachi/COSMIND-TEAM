from __future__ import annotations

import argparse
import csv
import gzip
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys

from datetime import datetime, timezone
from pathlib import Path

from ..analysis.plots import generate as generate_plots
from ..analysis.statistics import paired_comparisons, summarize_rows, write_csv
from ..scenarios import (
    ROOT,
    SCENARIO_NAMES,
    build_simulation,
    config_sha256,
    generate_tasks,
    load_config,
    model_profile_sha256,
    task_manifest_rows,
    workload_sha256,
)
from .metrics import calculate, task_outcome_rows


DEFAULT_SCHEDULERS = (
    "random",
    "rule",
    "greedy",
    "edf",
    "contact_knapsack",
    "predictive",
)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _git_is_dirty() -> bool:
    try:
        status_lines = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True,
        ).splitlines()
        # Generated evaluation artifacts intentionally change while a sharded
        # run is being assembled. They are not source changes and must not
        # prevent a later shard from recording the same frozen commit.
        for line in status_lines:
            path = line[3:].replace("\\", "/")
            if not path.startswith("results/"):
                return True
        return False
    except (OSError, subprocess.CalledProcessError):
        return True


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _metadata(
    evaluation_version: str,
    seeds: list[int],
    scenarios: tuple[str, ...],
    schedulers: tuple[str, ...],
    code_commit_sha: str,
    source_tree_clean: bool,
) -> dict:
    packages = {}
    for package in ("simpy", "PyYAML"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = "unavailable"
    return {
        "evaluation_version": evaluation_version,
        "code_commit_sha": code_commit_sha,
        "source_tree_clean": source_tree_clean,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependencies": packages,
        "workload_seed_protocol": "Each scenario/workload_seed is generated once and reused by every scheduler.",
        "policy_seed_protocol": "RandomScheduler uses policy_seed = workload_seed + 100000; other schedulers are deterministic.",
        "seeds": seeds,
        "scenarios": list(scenarios),
        "model_profiles": {
            profile: model_profile_sha256(profile)
            for profile in sorted({load_config(scenario)["model_profile"] for scenario in scenarios})
        },
        "schedulers": list(schedulers),
        "primary_metric": "timely_value_retention",
        "outcome_partition": "generated = timely + late + expired + rejected + unfinished + failed",
        "drain_policy": "Arrivals stop at scenario mission_duration_s; scheduling drains through the latest generated task deadline.",
    }


def _write_evaluation_readme(
    output_path: Path,
    *,
    evaluation_version: str,
    code_commit_sha: str,
    seeds: list[int],
    source_tree_clean: bool,
) -> None:
    output_path.joinpath("README.md").write_text(
        "# PMARS reproducible evaluation artifact\n\n"
        f"- Evaluation version: `{evaluation_version}`\n"
        f"- Frozen source commit: `{code_commit_sha}`\n"
        f"- Source tree clean: `{source_tree_clean}`\n"
        f"- Workload seeds: `{', '.join(map(str, seeds))}`\n"
        "- Matrix: every listed scheduler receives the identical generated workload for each scenario/seed pair.\n\n"
        "## Files\n\n"
        "- `raw_runs.csv`: one aggregate row per scenario, scheduler, and workload seed.\n"
        "- `task_outcomes.csv.gz`: compressed terminal-lifecycle audit rows for every generated task.\n"
        "- `workload_manifest.csv` and `workloads/`: fixed task inputs and SHA-256 hashes.\n"
        "- `profiles/`: exact physical-model assumptions and their hashes.\n"
        "- `summaries/`: mean/95% t-interval summaries and matched-seed Predictive comparisons.\n"
        "- `figures/`: SVG figures generated from `raw_runs.csv`.\n"
        "- `trace/`: a deterministic illustrative lifecycle trace generated from simulator events.\n\n"
        "The primary metric is `timely_value_retention`: nominal mission value of tasks delivered by their deadline divided by nominal value of all generated tasks. "
        "Freshness-adjusted value is a secondary sensitivity metric. All physical coefficients are modeled assumptions, not hardware measurements.\n",
        encoding="utf-8",
    )


def run(
    *,
    scenarios: tuple[str, ...] = SCENARIO_NAMES,
    schedulers: tuple[str, ...] = DEFAULT_SCHEDULERS,
    seeds=range(10),
    output: str | Path = "results/evaluation",
    evaluation_version: str = "development",
    allow_dirty: bool = False,
    append: bool = False,
) -> list[dict]:
    """Run a matched scheduler/scenario/seed matrix and write evidence files."""
    source_tree_dirty = _git_is_dirty()
    if source_tree_dirty and not allow_dirty:
        raise RuntimeError(
            "refusing to create a reproducibility artifact from a dirty source tree; "
            "commit the implementation first or pass allow_dirty=True for disposable development work"
        )
    code_commit_sha = _git_sha()
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "workloads").mkdir(exist_ok=True)
    (output_path / "configs").mkdir(exist_ok=True)
    (output_path / "profiles").mkdir(exist_ok=True)
    seed_list = list(seeds)
    rows = _read_csv(output_path / "raw_runs.csv") if append else []
    outcomes_path = output_path / "task_outcomes.csv.gz"
    outcomes = _read_csv(outcomes_path) if append else []
    workload_manifest = _read_csv(output_path / "workload_manifest.csv") if append else []
    for row in rows:
        if row.get("evaluation_version") != evaluation_version or row.get("code_commit_sha") != code_commit_sha:
            raise RuntimeError("cannot append a different evaluation version or source commit")
    existing_run_keys = {
        (row["scenario"], row["scheduler"], int(row["workload_seed"]))
        for row in rows
    }
    existing_workload_keys = {
        (row["scenario"], int(row["workload_seed"]))
        for row in workload_manifest
    }

    for scenario in scenarios:
        config = load_config(scenario)
        scenario_hash = config_sha256(config)
        shutil.copy2(ROOT / "scenarios" / f"{scenario}.yaml", output_path / "configs" / f"{scenario}.yaml")
        profile_name = config["model_profile"]
        profile_path = ROOT / "profiles" / f"{profile_name}.yaml"
        shutil.copy2(profile_path, output_path / "profiles" / profile_path.name)
        for workload_seed in seed_list:
            tasks = generate_tasks(config, workload_seed)
            task_hash = workload_sha256(tasks)
            workload_key = (scenario, workload_seed)
            if workload_key not in existing_workload_keys:
                workload_manifest.append({
                    "scenario": scenario,
                    "workload_seed": workload_seed,
                    "config_sha256": scenario_hash,
                    "workload_sha256": task_hash,
                    "generated_tasks": len(tasks),
                })
                existing_workload_keys.add(workload_key)
            with (output_path / "workloads" / f"{scenario}_seed_{workload_seed}.json").open("w", encoding="utf-8") as handle:
                json.dump(task_manifest_rows(tasks), handle, indent=2, sort_keys=True)
            for scheduler in schedulers:
                run_key = (scenario, scheduler, workload_seed)
                if run_key in existing_run_keys:
                    raise RuntimeError(f"duplicate run requested while appending: {run_key}")
                policy_seed = workload_seed + 100_000
                sim = build_simulation(
                    scenario,
                    scheduler,
                    workload_seed,
                    policy_seed=policy_seed,
                    tasks=tasks,
                )
                sim.run(config["mission_duration_s"])
                metrics = calculate(sim)
                identity = {
                    "evaluation_version": evaluation_version,
                    "code_commit_sha": code_commit_sha,
                    "scenario": scenario,
                    "scheduler": scheduler,
                    "workload_seed": workload_seed,
                    "policy_seed": policy_seed,
                    "config_sha256": scenario_hash,
                    "workload_sha256": task_hash,
                }
                rows.append({**identity, **metrics})
                outcomes.extend({**identity, **outcome} for outcome in task_outcome_rows(sim))
                existing_run_keys.add(run_key)

    _write_csv(output_path / "raw_runs.csv", rows)
    _write_csv(outcomes_path, outcomes)
    _write_csv(output_path / "workload_manifest.csv", workload_manifest)
    summaries = summarize_rows(rows)
    paired = paired_comparisons(rows)
    write_csv(output_path / "summaries" / "by_scenario_scheduler.csv", summaries)
    write_csv(output_path / "summaries" / "paired_predictive_vs_baselines.csv", paired)
    generate_plots(str(output_path / "raw_runs.csv"), str(output_path / "figures"))

    all_scenarios = tuple(sorted({row["scenario"] for row in rows}))
    all_schedulers = tuple(sorted({row["scheduler"] for row in rows}))
    all_seeds = sorted({int(row["workload_seed"]) for row in rows})
    manifest = _metadata(
        evaluation_version,
        all_seeds,
        all_scenarios,
        all_schedulers,
        code_commit_sha,
        not source_tree_dirty,
    )
    manifest["scenario_configs"] = {
        scenario: config_sha256(load_config(scenario)) for scenario in all_scenarios
    }
    manifest["model_profiles"] = {
        profile: model_profile_sha256(profile)
        for profile in sorted({load_config(scenario)["model_profile"] for scenario in all_scenarios})
    }
    manifest["run_count"] = len(rows)
    with (output_path / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    _write_evaluation_readme(
        output_path,
        evaluation_version=evaluation_version,
        code_commit_sha=code_commit_sha,
        seeds=all_seeds,
        source_tree_clean=not source_tree_dirty,
    )
    if "normal" in scenarios and "predictive" in schedulers and seed_list:
        from .trace import create_trace

        create_trace(
            scenario="normal",
            scheduler="predictive",
            seed=seed_list[0],
            output=output_path / "trace",
        )
    command = (
        f"python -m pmars_simulation.experiments.runner --seed-start {seed_list[0] if seed_list else 0} "
        f"--seeds {len(seed_list)} --output {output_path.as_posix()} "
        f"--evaluation-version {evaluation_version} "
        f"--scenarios {' '.join(scenarios)} --schedulers {' '.join(schedulers)}"
        f"{' --append' if append else ''}\n"
    )
    commands_path = output_path / "commands.txt"
    previous_commands = commands_path.read_text(encoding="utf-8") if append and commands_path.exists() else "python -m pytest\n"
    commands_path.write_text(previous_commands + command, encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible PMARS scheduler experiments.")
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=10, help="Number of consecutive workload seeds.")
    parser.add_argument("--output", default="results/evaluation")
    parser.add_argument("--evaluation-version", default="development")
    parser.add_argument("--scenarios", nargs="*", choices=SCENARIO_NAMES, default=SCENARIO_NAMES)
    parser.add_argument("--schedulers", nargs="*", choices=DEFAULT_SCHEDULERS, default=DEFAULT_SCHEDULERS)
    parser.add_argument("--allow-dirty", action="store_true", help="Allow disposable development output from uncommitted source.")
    parser.add_argument("--append", action="store_true", help="Append non-overlapping scenario/policy/seed runs to an existing artifact.")
    args = parser.parse_args()
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    run(
        scenarios=tuple(args.scenarios),
        schedulers=tuple(args.schedulers),
        seeds=range(args.seed_start, args.seed_start + args.seeds),
        output=args.output,
        evaluation_version=args.evaluation_version,
        allow_dirty=args.allow_dirty,
        append=args.append,
    )


if __name__ == "__main__":
    main()

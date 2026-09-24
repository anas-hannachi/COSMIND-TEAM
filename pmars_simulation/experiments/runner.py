from __future__ import annotations

import argparse
import csv
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
    task_manifest_rows,
    workload_sha256,
)
from .metrics import calculate, task_outcome_rows


DEFAULT_SCHEDULERS = ("random", "rule", "greedy", "predictive")


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _git_is_dirty() -> bool:
    try:
        return bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True,
        ).strip())
    except (OSError, subprocess.CalledProcessError):
        return True


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


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
        "- `task_outcomes.csv`: one terminal-lifecycle audit row per generated task.\n"
        "- `workload_manifest.csv` and `workloads/`: fixed task inputs and SHA-256 hashes.\n"
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
    seed_list = list(seeds)
    rows: list[dict] = []
    outcomes: list[dict] = []
    workload_manifest: list[dict] = []

    for scenario in scenarios:
        config = load_config(scenario)
        scenario_hash = config_sha256(config)
        shutil.copy2(ROOT / "scenarios" / f"{scenario}.yaml", output_path / "configs" / f"{scenario}.yaml")
        for workload_seed in seed_list:
            tasks = generate_tasks(config, workload_seed)
            task_hash = workload_sha256(tasks)
            workload_manifest.append({
                "scenario": scenario,
                "workload_seed": workload_seed,
                "config_sha256": scenario_hash,
                "workload_sha256": task_hash,
                "generated_tasks": len(tasks),
            })
            with (output_path / "workloads" / f"{scenario}_seed_{workload_seed}.json").open("w", encoding="utf-8") as handle:
                json.dump(task_manifest_rows(tasks), handle, indent=2, sort_keys=True)
            for scheduler in schedulers:
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

    _write_csv(output_path / "raw_runs.csv", rows)
    _write_csv(output_path / "task_outcomes.csv", outcomes)
    _write_csv(output_path / "workload_manifest.csv", workload_manifest)
    summaries = summarize_rows(rows)
    paired = paired_comparisons(rows)
    write_csv(output_path / "summaries" / "by_scenario_scheduler.csv", summaries)
    write_csv(output_path / "summaries" / "paired_predictive_vs_baselines.csv", paired)
    generate_plots(str(output_path / "raw_runs.csv"), str(output_path / "figures"))

    manifest = _metadata(
        evaluation_version,
        seed_list,
        scenarios,
        schedulers,
        code_commit_sha,
        not source_tree_dirty,
    )
    manifest["scenario_configs"] = {
        scenario: config_sha256(load_config(scenario)) for scenario in scenarios
    }
    manifest["run_count"] = len(rows)
    with (output_path / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    _write_evaluation_readme(
        output_path,
        evaluation_version=evaluation_version,
        code_commit_sha=code_commit_sha,
        seeds=seed_list,
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
    (output_path / "commands.txt").write_text(
        "python -m pytest\n"
        f"python -m pmars_simulation.experiments.runner --seed-start {seed_list[0] if seed_list else 0} "
        f"--seeds {len(seed_list)} --output {output_path.as_posix()} "
        f"--evaluation-version {evaluation_version}\n",
        encoding="utf-8",
    )
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
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import math
import statistics

from collections import defaultdict
from pathlib import Path


# Two-sided 95% Student-t critical values indexed by degrees of freedom.
T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
    13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
    19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
    25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
}
_TAIL_T95 = {30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980, 10**9: 1.960}


def t95(sample_count: int) -> float:
    """Return two-sided 95% Student-t critical value for sample size."""
    if sample_count <= 1:
        return 0.0
    degrees = sample_count - 1
    if degrees in T95:
        return T95[degrees]
    points = sorted(_TAIL_T95.items())
    for (lo_df, lo_value), (hi_df, hi_value) in zip(points, points[1:]):
        if lo_df <= degrees <= hi_df:
            lo_inv, hi_inv = 1 / lo_df, 1 / hi_df
            fraction = (1 / degrees - lo_inv) / (hi_inv - lo_inv)
            return lo_value + fraction * (hi_value - lo_value)
    return 1.960


def mean_ci95(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    mean = statistics.mean(values)
    if len(values) == 1:
        return mean, 0.0, 0.0
    standard_deviation = statistics.stdev(values)
    critical = t95(len(values))
    half_width = critical * standard_deviation / math.sqrt(len(values))
    return mean, standard_deviation, half_width


def summarize_rows(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["scenario"], row["scheduler"])].append(row)
    output: list[dict] = []
    for (scenario, scheduler), group in sorted(groups.items()):
        result = {
            "scenario": scenario,
            "scheduler": scheduler,
            "sample_count": len(group),
        }
        numeric_keys = [
            key for key in group[0]
            if key not in {
                "evaluation_version", "code_commit_sha", "scenario", "scheduler",
                "workload_seed", "policy_seed", "config_sha256", "workload_sha256",
            }
        ]
        for key in numeric_keys:
            values = [float(row[key]) for row in group]
            mean, standard_deviation, ci95 = mean_ci95(values)
            result[f"{key}_mean"] = mean
            result[f"{key}_std"] = standard_deviation
            result[f"{key}_ci95"] = ci95
        output.append(result)
    return output


def paired_comparisons(
    rows: list[dict],
    *,
    candidate_scheduler: str = "predictive",
    baselines: tuple[str, ...] = ("greedy", "rule", "edf", "contact_knapsack"),
    metric: str = "timely_value_retention",
) -> list[dict]:
    index = {
        (row["scenario"], row["scheduler"], int(row["workload_seed"])): row
        for row in rows
    }
    comparisons: list[dict] = []
    scenarios = sorted({row["scenario"] for row in rows})
    for scenario in scenarios:
        for baseline in baselines:
            differences: list[float] = []
            seeds = sorted({
                int(row["workload_seed"])
                for row in rows
                if row["scenario"] == scenario and row["scheduler"] == candidate_scheduler
            })
            for seed in seeds:
                candidate = index.get((scenario, candidate_scheduler, seed))
                reference = index.get((scenario, baseline, seed))
                if candidate is not None and reference is not None:
                    differences.append(float(candidate[metric]) - float(reference[metric]))
            mean, standard_deviation, ci95 = mean_ci95(differences)
            comparisons.append({
                "scenario": scenario,
                "candidate": candidate_scheduler,
                "baseline": baseline,
                "metric": metric,
                "paired_sample_count": len(differences),
                "paired_difference_mean": mean,
                "paired_difference_std": standard_deviation,
                "paired_difference_ci95": ci95,
                "ci95_low": mean - ci95,
                "ci95_high": mean + ci95,
            })
    return comparisons


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(results_path: str) -> list[dict]:
    """Backward-compatible CSV summary helper."""
    with open(results_path, newline="", encoding="utf-8") as handle:
        return summarize_rows(list(csv.DictReader(handle)))

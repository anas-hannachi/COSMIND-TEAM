from __future__ import annotations

import csv
import html
import math
import statistics

from collections import defaultdict
from pathlib import Path


COLORS = {
    "random": "#94a3b8",
    "rule": "#f59e0b",
    "greedy": "#2563eb",
    "edf": "#7c3aed",
    "contact_knapsack": "#0f766e",
    "predictive": "#16a34a",
}
SCHEDULERS = ("random", "rule", "greedy", "edf", "contact_knapsack", "predictive")
T95 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447,
       8: 2.365, 9: 2.306, 10: 2.262, 11: 2.228, 12: 2.201, 13: 2.179,
       14: 2.160, 15: 2.145, 16: 2.131, 17: 2.120, 18: 2.110, 19: 2.101,
       20: 2.093}


def _svg(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{body}</svg>'
    )


def _group_values(rows: list[dict], metric: str) -> dict[tuple[str, str], list[float]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["scenario"], row["scheduler"])].append(float(row[metric]))
    return grouped


def _mean_ci(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = statistics.mean(values)
    if len(values) == 1:
        return mean, 0.0
    return mean, T95.get(len(values), 1.96) * statistics.stdev(values) / math.sqrt(len(values))


def _legend(parts: list[str], *, left: float, y: float, labels: tuple[str, ...], colors: dict[str, str]) -> None:
    for index, label in enumerate(labels):
        x = left + index * 145
        parts.extend([
            f'<rect x="{x}" y="{y}" width="12" height="12" fill="{colors[label]}"/>',
            f'<text x="{x + 18}" y="{y + 11}" font-family="Arial" font-size="12">{html.escape(label)}</text>',
        ])


def _grouped_bar_chart(
    rows: list[dict],
    *,
    metric: str,
    title: str,
    y_label: str,
    output: Path,
    percent: bool = False,
) -> None:
    """Grouped mean bars with per-seed dots and 95% t-interval whiskers."""
    scenarios = sorted({row["scenario"] for row in rows})
    values = _group_values(rows, metric)
    summaries = {key: _mean_ci(item) for key, item in values.items()}
    maximum = max((mean + ci for mean, ci in summaries.values()), default=1.0)
    maximum = 1.0 if percent else max(maximum * 1.08, 1e-9)
    width, height = 1120, 520
    left, bottom, top, right = 80, 110, 65, 30
    plot_height = height - top - bottom
    plot_width = width - left - right
    group_width = plot_width / max(len(scenarios), 1)
    bar_width = min(32, group_width / (len(SCHEDULERS) + 1.5))
    bar_step = bar_width + 3
    cluster_width = len(SCHEDULERS) * bar_width + (len(SCHEDULERS) - 1) * 3
    parts = [
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold">{html.escape(title)}</text>',
        f'<text x="18" y="{top + plot_height / 2}" transform="rotate(-90 18 {top + plot_height / 2})" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(y_label)}</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111"/>',
    ]
    for tick in range(6):
        value = maximum * tick / 5
        y = top + plot_height * (1 - tick / 5)
        label = f"{value * 100:.0f}%" if percent else f"{value:.1f}"
        parts.extend([
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{label}</text>',
        ])
    for scenario_index, scenario in enumerate(scenarios):
        group_x = left + scenario_index * group_width
        for scheduler_index, scheduler in enumerate(SCHEDULERS):
            key = (scenario, scheduler)
            mean, ci = summaries.get(key, (0.0, 0.0))
            bar_height = plot_height * mean / maximum
            x = group_x + max(3, (group_width - cluster_width) / 2) + scheduler_index * bar_step
            y = top + plot_height - bar_height
            center_x = x + bar_width / 2
            whisker_y = top + plot_height * (1 - min(maximum, mean + ci) / maximum)
            whisker_low_y = top + plot_height * (1 - max(0.0, mean - ci) / maximum)
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{COLORS[scheduler]}" opacity="0.82"/>'
            )
            if ci:
                parts.extend([
                    f'<line x1="{center_x:.1f}" y1="{whisker_y:.1f}" x2="{center_x:.1f}" y2="{whisker_low_y:.1f}" stroke="#111"/>',
                    f'<line x1="{center_x - 4:.1f}" y1="{whisker_y:.1f}" x2="{center_x + 4:.1f}" y2="{whisker_y:.1f}" stroke="#111"/>',
                    f'<line x1="{center_x - 4:.1f}" y1="{whisker_low_y:.1f}" x2="{center_x + 4:.1f}" y2="{whisker_low_y:.1f}" stroke="#111"/>',
                ])
            for point_index, value in enumerate(values.get(key, [])):
                # A small deterministic horizontal offset makes all common-seed
                # observations visible without adding a plotting dependency.
                offset = ((point_index % 5) - 2) * 2.1
                point_y = top + plot_height * (1 - min(maximum, max(0.0, value)) / maximum)
                parts.append(
                    f'<circle cx="{center_x + offset:.1f}" cy="{point_y:.1f}" r="1.8" fill="#111" opacity="0.55"/>'
                )
        parts.append(
            f'<text x="{group_x + group_width / 2:.1f}" y="{top + plot_height + 20}" text-anchor="middle" font-family="Arial" font-size="11">{html.escape(scenario)}</text>'
        )
    _legend(parts, left=left, y=height - 45, labels=SCHEDULERS, colors=COLORS)
    parts.append(
        f'<text x="{width - right}" y="{height - 16}" text-anchor="end" font-family="Arial" font-size="10" fill="#475569">bars = mean; whiskers = 95% t interval; dots = individual workload seeds</text>'
    )
    output.write_text(_svg(width, height, "".join(parts)), encoding="utf-8")


def _tradeoff(rows: list[dict], output: Path) -> None:
    value_groups = _group_values(rows, "timely_value_retention")
    energy_groups = _group_values(rows, "total_energy_consumed_j")
    means_value = {key: _mean_ci(values)[0] for key, values in value_groups.items()}
    means_energy = {key: _mean_ci(values)[0] for key, values in energy_groups.items()}
    max_energy = max(means_energy.values(), default=1.0)
    width, height = 920, 530
    left, bottom, top, right = 90, 88, 65, 30
    plot_width, plot_height = width - left - right, height - top - bottom
    parts = [
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="460" y="30" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold">Value-energy trade-off by scenario and scheduler</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111"/>',
        f'<text x="{left + plot_width / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="13">Gross modeled action energy (J)</text>',
        f'<text x="18" y="{top + plot_height / 2}" transform="rotate(-90 18 {top + plot_height / 2})" text-anchor="middle" font-family="Arial" font-size="13">Timely mission-value retention</text>',
    ]
    for tick in range(6):
        x = left + plot_width * tick / 5
        y = top + plot_height * (1 - tick / 5)
        parts.extend([
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#e5e7eb"/>',
            f'<text x="{x:.1f}" y="{top + plot_height + 18}" text-anchor="middle" font-family="Arial" font-size="11">{max_energy * tick / 5:.0f}</text>',
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{20 * tick}%</text>',
        ])
    for (scenario, scheduler), value in means_value.items():
        energy = means_energy[(scenario, scheduler)]
        x = left + plot_width * energy / max(max_energy, 1e-9)
        y = top + plot_height * (1 - value)
        label = f"{scenario[:4]}-{scheduler[:4]}"
        parts.extend([
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{COLORS[scheduler]}"/>',
            f'<text x="{x + 7:.1f}" y="{y - 7:.1f}" font-family="Arial" font-size="9">{html.escape(label)}</text>',
        ])
    _legend(parts, left=left, y=height - 45, labels=SCHEDULERS, colors=COLORS)
    output.write_text(_svg(width, height, "".join(parts)), encoding="utf-8")


def _outcome_stack(rows: list[dict], output: Path) -> None:
    """Plot mean terminal-outcome fractions, preserving the full denominator."""
    scenarios = sorted({row["scenario"] for row in rows})
    outcome_fields = (
        ("timely", "tasks_completed_timely", "#16a34a"),
        ("late", "tasks_late", "#dc2626"),
        ("expired", "tasks_expired", "#f59e0b"),
        ("rejected", "tasks_rejected", "#7c3aed"),
        ("unfinished/failed", "_unfinished_failed", "#64748b"),
    )
    width, height = 1120, 520
    left, bottom, top, right = 80, 120, 65, 30
    plot_height = height - top - bottom
    plot_width = width - left - right
    group_width = plot_width / max(len(scenarios), 1)
    bar_width = min(32, group_width / (len(SCHEDULERS) + 1.5))
    bar_step = bar_width + 3
    cluster_width = len(SCHEDULERS) * bar_width + (len(SCHEDULERS) - 1) * 3
    parts = [
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="30" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold">Mean terminal outcomes over all generated tasks</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111"/>',
    ]
    for tick in range(6):
        y = top + plot_height * (1 - tick / 5)
        parts.extend([
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{tick * 20}%</text>',
        ])
    for scenario_index, scenario in enumerate(scenarios):
        group_x = left + scenario_index * group_width
        for scheduler_index, scheduler in enumerate(SCHEDULERS):
            group = [row for row in rows if row["scenario"] == scenario and row["scheduler"] == scheduler]
            x = group_x + max(3, (group_width - cluster_width) / 2) + scheduler_index * bar_step
            cumulative = 0.0
            for _label, field, color in outcome_fields:
                fractions = []
                for row in group:
                    generated = max(float(row["tasks_generated"]), 1.0)
                    count = (
                        float(row["tasks_unfinished"]) + float(row["tasks_failed"])
                        if field == "_unfinished_failed"
                        else float(row[field])
                    )
                    fractions.append(count / generated)
                value = statistics.mean(fractions) if fractions else 0.0
                segment_height = plot_height * value
                y = top + plot_height - cumulative * plot_height - segment_height
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{segment_height:.1f}" fill="{color}"/>'
                )
                cumulative += value
        parts.append(
            f'<text x="{group_x + group_width / 2:.1f}" y="{top + plot_height + 20}" text-anchor="middle" font-family="Arial" font-size="11">{html.escape(scenario)}</text>'
        )
    outcome_colors = {label: color for label, _field, color in outcome_fields}
    _legend(parts, left=left, y=height - 52, labels=tuple(outcome_colors), colors=outcome_colors)
    parts.append(
        f'<text x="80" y="{height - 16}" font-family="Arial" font-size="10" fill="#475569">Schedulers: random, rule, greedy, EDF, contact knapsack, predictive.</text>'
    )
    output.write_text(_svg(width, height, "".join(parts)), encoding="utf-8")


def generate(results_path: str = "results/raw_runs.csv", output: str = "results/figures") -> None:
    """Generate paper-ready SVGs from a validated raw-run CSV."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    with open(results_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    _grouped_bar_chart(
        rows,
        metric="timely_value_retention",
        title="Deadline-qualified mission-value retention",
        y_label="Timely value retention",
        output=output_path / "timely_value_retention.svg",
        percent=True,
    )
    _grouped_bar_chart(
        rows,
        metric="task_completion_rate",
        title="Timely task completion rate",
        y_label="Timely completion rate",
        output=output_path / "timely_task_completion.svg",
        percent=True,
    )
    _outcome_stack(rows, output_path / "terminal_outcomes.svg")
    _tradeoff(rows, output_path / "value_energy_tradeoff.svg")

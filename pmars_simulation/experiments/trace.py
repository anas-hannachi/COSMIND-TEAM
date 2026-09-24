from __future__ import annotations

import argparse
import csv
import html
import json

from pathlib import Path

from ..core.task import TaskStatus
from ..scenarios import build_simulation, generate_tasks, load_config, workload_sha256


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _timeline_svg(rows: list[dict], output: Path, title: str) -> None:
    """Write a dependency-free SVG timeline from actual simulator events."""
    width, height = 1080, 260
    left, right, line_y = 85, 40, 125
    times = [float(row["time_s"]) for row in rows] or [0.0]
    minimum, maximum = min(times), max(times)
    span = max(maximum - minimum, 1.0)
    parts = [
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="28" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{line_y}" x2="{width - right}" y2="{line_y}" stroke="#334155" stroke-width="2"/>',
    ]
    colors = {
        "admitted": "#2563eb",
        "process_started": "#7c3aed",
        "processed": "#8b5cf6",
        "store_started": "#f59e0b",
        "stored": "#d97706",
        "transmit_started": "#0891b2",
        "completed": "#16a34a",
        "late": "#dc2626",
        "expired": "#dc2626",
    }
    for index, row in enumerate(rows):
        event = str(row["event"])
        x = left + (width - left - right) * (float(row["time_s"]) - minimum) / span
        y_offset = -30 if index % 2 == 0 else 45
        label_y = line_y + y_offset
        color = colors.get(event, "#64748b")
        parts.extend([
            f'<line x1="{x:.1f}" y1="{line_y}" x2="{x:.1f}" y2="{label_y - (8 if y_offset > 0 else -8)}" stroke="{color}"/>',
            f'<circle cx="{x:.1f}" cy="{line_y}" r="6" fill="{color}"/>',
            f'<text x="{x:.1f}" y="{label_y}" text-anchor="middle" font-family="Arial" font-size="11">{html.escape(event)}</text>',
            f'<text x="{x:.1f}" y="{label_y + 14}" text-anchor="middle" font-family="Arial" font-size="10">t={float(row["time_s"]):.1f}s</text>',
        ])
    parts.append(
        '<text x="85" y="230" font-family="Arial" font-size="11" fill="#475569">Generated directly from the simulator event log; illustrative lifecycle trace, not an aggregate result.</text>'
    )
    output.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{"".join(parts)}</svg>',
        encoding="utf-8",
    )


def _compact_storage_events(rows: list[dict]) -> tuple[list[dict], int]:
    """Make a readable timeline while retaining every raw event in the CSV."""
    compact: list[dict] = []
    stored_events: list[dict] = []
    for row in rows:
        if row["event"] in {"store_started", "stored"}:
            stored_events.append(row)
            continue
        if stored_events:
            first = dict(stored_events[0])
            cycles = sum(event["event"] == "stored" for event in stored_events)
            first["event"] = f"stored ({cycles} wait cycles)"
            compact.append(first)
            stored_events = []
        compact.append(row)
    if stored_events:
        first = dict(stored_events[0])
        cycles = sum(event["event"] == "stored" for event in stored_events)
        first["event"] = f"stored ({cycles} wait cycles)"
        compact.append(first)
    return compact, sum(row["event"] == "stored" for row in rows)


def create_trace(
    *,
    scenario: str = "normal",
    scheduler: str = "predictive",
    seed: int = 100,
    output: str | Path = "results/trace",
) -> dict:
    """Run a deterministic simulation and export one real task lifecycle.

    A processed, timely-delivered task is preferred so the artifact exposes
    the full PROCESS -> TRANSMIT chain. If none exists, a timely direct
    downlink is used and the limitation is recorded in the Markdown file.
    """
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    config = load_config(scenario)
    tasks = generate_tasks(config, seed)
    sim = build_simulation(scenario, scheduler, seed, tasks=tasks)
    sim.run(config["mission_duration_s"])

    completed = [
        record for record in sim.queue.records.values()
        if record.status == TaskStatus.COMPLETED
    ]
    selected = next((record for record in completed if record.processed_at_s is not None), None)
    if selected is None:
        selected = completed[0] if completed else None
    if selected is None:
        raise RuntimeError("trace configuration produced no timely delivery; choose another deterministic seed")

    # Events are appended by the simulator in causal order.  Sort only by
    # time (Python's stable ordering preserves same-time causal order).
    rows = [event for event in sim.events if event.get("task_id") == selected.task.id]
    rows.sort(key=lambda row: float(row["time_s"]))
    timeline_rows, storage_wait_cycles = _compact_storage_events(rows)
    _write_csv(output_path / "trace_demo.csv", rows)
    _timeline_svg(
        timeline_rows,
        output_path / "trace_demo.svg",
        f"Illustrative PMARS lifecycle: task {selected.task.id}",
    )
    summary = {
        "scenario": scenario,
        "scheduler": scheduler,
        "workload_seed": seed,
        "workload_sha256": workload_sha256(tasks),
        "task_id": selected.task.id,
        "task_type": selected.task.type,
        "created_at_s": selected.task.created_at_s,
        "deadline_s": selected.task.deadline_s,
        "processed_at_s": selected.processed_at_s,
        "completed_at_s": selected.completed_at_s,
        "terminal_status": selected.status.value,
        "event_count": len(rows),
        "storage_wait_cycles": storage_wait_cycles,
    }
    (output_path / "trace_manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    lifecycle = " -> ".join(str(row["event"]) for row in timeline_rows)
    (output_path / "trace_demo.md").write_text(
        "# Illustrative execution trace\n\n"
        "This is a deterministic, simulator-generated lifecycle example. It is "
        "not an aggregate performance result.\n\n"
        f"- Scenario / policy / seed: `{scenario}` / `{scheduler}` / `{seed}`\n"
        f"- Task: `{selected.task.id}` ({selected.task.type})\n"
        f"- Arrival: {selected.task.created_at_s:.3f} s; deadline: {selected.task.deadline_s:.3f} s\n"
        f"- Terminal outcome: `{selected.status.value}` at {selected.completed_at_s:.3f} s\n"
        f"- Observed lifecycle: `{lifecycle}`\n"
        f"- Intermediate STORE wait cycles: {storage_wait_cycles} (compacted only in the SVG/line above)\n\n"
        "`trace_demo.csv` contains the exact timestamp, action, policy rationale, "
        "payload, deadline slack, energy, storage, link state, and task-state "
        "fields recorded by the simulator.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a deterministic PMARS task lifecycle trace.")
    parser.add_argument("--scenario", default="normal")
    parser.add_argument("--scheduler", default="predictive")
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--output", default="results/trace")
    args = parser.parse_args()
    summary = create_trace(
        scenario=args.scenario,
        scheduler=args.scheduler,
        seed=args.seed,
        output=args.output,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

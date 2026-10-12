"""Export deterministic scenario workloads as bounded contract JSON Lines."""

import argparse
import json
from pathlib import Path

from .codec import encode_message
from .models import ContractTask
from .units import capacity_bytes, deadline_ms, duration_ms, scaled_milli, size_bytes
from ..scenarios import generate_tasks, load_config


def export_workload(scenario: str, seed: int, output: str | Path) -> list[ContractTask]:
    config = load_config(scenario)
    tasks = []
    for task in generate_tasks(config, seed):
        tasks.append(ContractTask(
            id=task.id, kind=task.type, input_bytes=size_bytes(task.input_size_mb),
            output_bytes_est=size_bytes(task.processed_output_mb),
            mem_req_bytes=capacity_bytes(task.memory_requirement_mb),
            demand_milli=scaled_milli(task.processing_demand),
            base_proc_ms=duration_ms(task.base_processing_time_s), priority=task.priority,
            value_milli=scaled_milli(task.mission_value), created_ms=duration_ms(task.created_at_s),
            deadline_ms=deadline_ms(task.deadline_s), science_payload=None,
        ))
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(encode_message({"type": "config", "scenario": scenario, "seed": seed}, 0))
        for seq, task in enumerate(tasks, start=1):
            handle.write(encode_message({"type": "task_submit", "task": task.__dict__}, seq))
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps({"tasks": len(export_workload(args.scenario, args.seed, args.output)), "output": args.output}))


if __name__ == "__main__":
    main()

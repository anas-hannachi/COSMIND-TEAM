"""Engine-vs-simulator outcome comparison with simulator-faithful arrival handling.

Unlike tools/engine_parity.py (which gives the engine one action per arrival and runs it to completion only after
every task has been submitted), this harness mirrors the simulator's stepping: a task is submitted when engine time
reaches its created_ms, the engine is stepped until it idles before the next arrival, and an idle jump is capped at
min(IDLE_QUANTUM, next arrival), as in Simulation._idle_duration.

Usage: PYTHONPATH=. python tools/engine_parity_interleaved.py [scenarios_csv] [seeds_csv]
"""

import collections
import dataclasses
import sys
from types import SimpleNamespace

from pmars_simulation.contract.codec import ContractError
from pmars_simulation.contract.from_sim import contract_state, contract_task
from pmars_simulation.hil.driver import _load_host, _request
from pmars_simulation.scenarios import BENCH_SCENARIO_NAMES, build_simulation, generate_tasks, load_config
from tools.engine_parity import _simulator_run

IDLE_QUANTUM_MS = 5000
TERMINAL = {"completed", "late", "expired", "rejected", "failed"}


def native_run(host, scenario, scheduler, seed, seq):
    config = load_config(scenario)
    tasks = sorted(generate_tasks(config, seed), key=lambda t: (t.created_at_s, t.id))
    initial = contract_state(build_simulation(scenario, scheduler, seed, tasks=tasks))
    _request(host, {"type": "reset"}, seq)
    seq += 1
    base = {"type": "config", "now_ms": initial.now_ms, "energy_mj": initial.energy_mj,
            "storage_used_bytes": initial.storage_used_bytes, "storage_total_bytes": initial.storage_total_bytes,
            "memory_available_bytes": initial.memory_available_bytes,
            "compute_capacity_milli": initial.compute_capacity_milli,
            "throttle_fraction_milli": initial.throttle_fraction_milli,
            "processing_power_mw": initial.processing_power_mw, "transmit_power_mw": initial.transmit_power_mw,
            "store_power_mw": initial.idle_power_mw, "drain_horizon_ms": initial.drain_horizon_ms,
            "rule": scheduler == "rule"}
    _request(host, base, seq)
    seq += 1
    for contact in initial.contacts[:16]:
        _request(host, {**base, "contacts": [list(contact)], "contacts_append": True}, seq)
        seq += 1
    terminal = {}

    def drain(sequence):
        while True:
            response = _request(host, {"type": "event"}, sequence)
            sequence += 1
            if response["type"] == "ack":
                return sequence
            if response.get("task_id") and response.get("event_kind") in TERMINAL:
                terminal[response["task_id"]] = response["event_kind"]

    wire = [contract_task(SimpleNamespace(task=t, payload_mb=t.input_size_mb,
                                          status=SimpleNamespace(value="pending"))) for t in tasks]
    count, index, now = len(tasks), 0, initial.now_ms
    horizon_ms = int(config["mission_duration_s"] * 1000)
    for _ in range(200000):
        while index < count and wire[index].created_ms <= now:
            try:
                _request(host, {"type": "task_submit", "task": dataclasses.asdict(wire[index])}, seq)
            except ContractError:
                terminal[tasks[index].id] = "rejected"
            seq += 1
            seq = drain(seq)
            index += 1
        response = _request(host, {"type": "tick"}, seq)
        seq += 1
        seq = drain(seq)
        new_now = response.get("now_ms", now)
        if response.get("action") == "IDLE" or new_now == now:
            if index >= count and len(terminal) >= count:
                break
            if now >= horizon_ms and index >= count:
                break
            target = now + IDLE_QUANTUM_MS
            if index < count:
                target = min(target, wire[index].created_ms)
            target = max(target, now + 1)
            response = _request(host, {"type": "tick", "now_ms": target}, seq)
            seq += 1
            seq = drain(seq)
            new_now = response.get("now_ms", target)
        now = new_now
        if index >= count and len(terminal) >= count:
            break
        if now > horizon_ms + 10_000_000:
            break
    result = _request(host, {"type": "result"}, seq)
    seq += 1
    seq = drain(seq)
    for task in tasks:
        terminal.setdefault(task.id, "unfinished")
    return terminal, result, seq


def measure(scenarios, seeds):
    host_tmp, host = _load_host()
    seq = 0
    rows = {}
    pairs = collections.Counter()
    try:
        for scenario in scenarios:
            for scheduler in ("edf", "rule"):
                for seed in seeds:
                    terminal, result, seq = native_run(host, scenario, scheduler, seed, seq)
                    simulator, timely = _simulator_run(scenario, scheduler, seed)
                    diffs = [(simulator[k], terminal.get(k, "missing")) for k in simulator
                             if simulator[k] != terminal.get(k, "missing")]
                    row = rows.setdefault(scenario, collections.Counter())
                    row["tasks"] += len(simulator)
                    row["differences"] += len(diffs)
                    row["delivery_disagreements"] += sum(1 for a, b in diffs if "completed" in (a, b))
                    row["cases"] += 1
                    row["timely_count_match"] += int(timely == result.get("completed", 0))
                    pairs.update(diffs)
    finally:
        if host.stdin:
            host.stdin.close()
        host.wait(timeout=2)
        host_tmp.cleanup()
    return rows, pairs


def main():
    scenarios = sys.argv[1].split(",") if len(sys.argv) > 1 else list(BENCH_SCENARIO_NAMES)
    seeds = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else list(range(100, 105))
    rows, pairs = measure(scenarios, seeds)
    for scenario, row in rows.items():
        print(f"{scenario:18s} cases={row['cases']:3d} tasks={row['tasks']:5d} status_differences={row['differences']:4d} "
              f"({100 * row['differences'] / row['tasks']:.1f}%) delivery_disagreements={row['delivery_disagreements']:3d} "
              f"({100 * row['delivery_disagreements'] / row['tasks']:.1f}%) timely_count_match={row['timely_count_match']}/{row['cases']}")
    print("status pairs (simulator -> engine):", pairs.most_common(6))


if __name__ == "__main__":
    main()

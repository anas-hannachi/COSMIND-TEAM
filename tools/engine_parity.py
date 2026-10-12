"""Compare complete native engine outcomes with the simulator and enumerate differences."""

import dataclasses
import json
import sys
from types import SimpleNamespace

from pmars_simulation.contract.codec import ContractError
from pmars_simulation.contract.from_sim import contract_state, contract_task
from pmars_simulation.contract.units import duration_ms
from pmars_simulation.hil.driver import _load_host, _request
from pmars_simulation.policy import edf, rule
from pmars_simulation.scenarios import BENCH_SCENARIO_NAMES, build_simulation, generate_tasks, load_config


POLICIES = {"edf": edf.decide, "rule": rule.decide}
TERMINAL_EVENTS = {"completed", "late", "expired", "rejected", "failed"}


def _native_run(host, scenario, scheduler, seed, seq):
    config = load_config(scenario)
    tasks = generate_tasks(config, seed)
    sim = build_simulation(scenario, scheduler, seed, tasks=tasks)
    initial = contract_state(sim)
    _request(host, {"type": "reset"}, seq)
    seq += 1
    base = {"type": "config", "now_ms": initial.now_ms, "energy_mj": initial.energy_mj,
            "storage_used_bytes": initial.storage_used_bytes, "storage_total_bytes": initial.storage_total_bytes,
            "memory_available_bytes": initial.memory_available_bytes,
            "compute_capacity_milli": initial.compute_capacity_milli,
            "throttle_fraction_milli": initial.throttle_fraction_milli,
            "processing_power_mw": initial.processing_power_mw,
            "transmit_power_mw": initial.transmit_power_mw,
            "store_power_mw": initial.idle_power_mw, "drain_horizon_ms": initial.drain_horizon_ms,
            "rule": scheduler == "rule"}
    _request(host, base, seq)
    seq += 1
    for contact in initial.contacts[:16]:
        _request(host, {**base, "contacts": [list(contact)], "contacts_append": True}, seq)
        seq += 1

    terminal = {}
    submit_rejections = {"queue_full": 0, "admission_rejected": 0}

    def collect_events(sequence):
        while True:
            response = _request(host, {"type": "event"}, sequence)
            sequence += 1
            if response["type"] == "ack":
                return sequence
            task_id = response.get("task_id", "")
            event_name = response.get("event_kind")
            if task_id and event_name in TERMINAL_EVENTS:
                terminal[task_id] = event_name

    last_time_ms = 0
    for task in tasks:
        wire_task = contract_task(SimpleNamespace(task=task, payload_mb=task.input_size_mb,
                                                   status=SimpleNamespace(value="pending")))
        try:
            _request(host, {"type": "task_submit", "task": dataclasses.asdict(wire_task)}, seq)
        except ContractError as exc:
            code = "queue_full" if "queue_full" in str(exc) else "admission_rejected" if "admission_rejected" in str(exc) else None
            if code:
                submit_rejections[code] += 1
                terminal[task.id] = "rejected"
            else:
                raise
        seq += 1
        sequence = collect_events(seq)
        seq = sequence
        arrival_ms = wire_task.created_ms
        tick = {"type": "tick"}
        if arrival_ms > last_time_ms:
            tick["now_ms"] = arrival_ms
        response = _request(host, tick, seq)
        seq += 1
        last_time_ms = response.get("now_ms", last_time_ms)
        seq = collect_events(seq)

    horizon_ms = max(int(config["mission_duration_s"] * 1000),
                     max((duration_ms(task.deadline_s) for task in tasks), default=0))
    time_boundaries = sorted({duration_ms(value) for contact in config["contacts"]
                              for value in (contact["start_s"], contact["end_s"])} |
                             {duration_ms(task.deadline_s) for task in tasks})
    for _ in range(max(1, len(tasks) * 5)):
        if len(terminal) >= len(tasks) or last_time_ms >= horizon_ms:
            break
        response = _request(host, {"type": "tick"}, seq)
        seq += 1
        previous_time = last_time_ms
        last_time_ms = response.get("now_ms", last_time_ms)
        seq = collect_events(seq)
        if len(terminal) >= len(tasks):
            break
        if last_time_ms == previous_time and response.get("action") == "IDLE":
            next_time = next((moment for moment in time_boundaries if moment > last_time_ms), horizon_ms)
            response = _request(host, {"type": "tick", "now_ms": next_time}, seq)
            seq += 1
            last_time_ms = response.get("now_ms", next_time)
            seq = collect_events(seq)
    result = _request(host, {"type": "result"}, seq)
    seq += 1
    seq = collect_events(seq)
    for task in tasks:
        terminal.setdefault(task.id, "unfinished")
    return terminal, result, seq, config, tasks, submit_rejections


def _simulator_run(scenario, scheduler, seed):
    config = load_config(scenario)
    tasks = generate_tasks(config, seed)
    sim = build_simulation(scenario, scheduler, seed, tasks=tasks)
    sim.run(config["mission_duration_s"])
    statuses = {task_id: record.status.value for task_id, record in sim.queue.records.items()}
    statuses.update({record.task.id: record.status.value for record in sim.queue.rejected})
    return statuses, len(sim.queue.completed)


def _difference_cause(simulator_status, engine_status):
    if engine_status == "failed":
        return "C engine fails all active work when STORE cannot pay the next wait interval; simulator continues to its deadline/drain horizon."
    if engine_status == "rejected":
        return "Integer-byte admission/storage accounting and the serialized task_submit path differ from simulator arrival-time admission."
    if simulator_status == "completed" and engine_status == "expired":
        return "C engine has no solar recharge or thermal recovery and uses atomic integer action costs/durations; the simulator evolves those continuously."
    if engine_status == "completed" and simulator_status == "rejected":
        return "Admission/storage lifecycle differs: the engine reuses terminal slots and accounts resident integer bytes, while the simulator rejects at its own arrival-time capacity check."
    if simulator_status == "expired" and engine_status == "completed":
        return "Integer feasibility/tie decisions and atomic action timing differ from the simulator's float environment and freshness-decayed policy inputs."
    return "The integer engine and simulator use different admission, action timing, and continuous environment models."


def run_case(host, scenario, scheduler, seed, seq):
    c_status, result, seq, _, tasks, submit_rejections = _native_run(host, scenario, scheduler, seed, seq)
    py_status, py_timely = _simulator_run(scenario, scheduler, seed)
    for task in tasks:
        c_status.setdefault(task.id, "unfinished")
    diffs = []
    for task_id in sorted(set(py_status) | set(c_status)):
        expected, actual = py_status.get(task_id, "missing"), c_status.get(task_id, "missing")
        if expected != actual:
            diffs.append({"task_id": task_id, "simulator": expected, "engine": actual,
                          "cause": _difference_cause(expected, actual)})
    c_timely = result.get("completed", 0)
    return {"case": {"scenario": scenario, "scheduler": scheduler, "seed": seed}, "next_seq": seq,
            "tasks": len(tasks), "simulator_timely_completed": py_timely,
            "engine_timely_completed": c_timely, "status_differences": diffs,
            "timely_count_match": py_timely == c_timely, "submit_rejections": submit_rejections,
            "engine_dropped_events": result.get("dropped_events", 0)}


def main():
    scenarios = sys.argv[1].split(",") if len(sys.argv) > 1 else list(BENCH_SCENARIO_NAMES)
    seeds = [int(value) for value in sys.argv[2].split(",")] if len(sys.argv) > 2 else list(range(100, 105))
    temp, host = _load_host()
    try:
        all_cases = []
        sequence = 0
        for scenario in scenarios:
            for scheduler in ("edf", "rule"):
                for seed in seeds:
                    case = run_case(host, scenario, scheduler, seed, sequence)
                    sequence = case.pop("next_seq")
                    all_cases.append(case)
                    print(json.dumps(case, sort_keys=True))
    finally:
        if host.stdin:
            host.stdin.close()
        host.wait(timeout=2)
        temp.cleanup()
    total_differences = sum(len(case["status_differences"]) for case in all_cases)
    print(f"cases={len(all_cases)}, status_differences={total_differences}, "
          f"timely_count_mismatches={sum(not case['timely_count_match'] for case in all_cases)}")


if __name__ == "__main__":
    main()

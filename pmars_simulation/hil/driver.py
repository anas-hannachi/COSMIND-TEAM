"""Replay a full scenario while comparing the native C and Python policies."""

import argparse
import dataclasses
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..contract.models import ContractConfig
from ..contract.codec import ContractError, decode_message, encode_message
from ..contract.from_sim import contract_state as _contract_state
from ..contract.from_sim import contract_task as _contract_task
from ..policy import edf, rule
from ..policy.core import bounded_tasks
from ..scenarios import ROOT, build_simulation, generate_tasks, load_config


POLICIES = {"edf": edf.decide, "rule": rule.decide}
ACTION_NAMES = {0: "IDLE", 1: "PROCESS", 2: "STORE", 3: "TRANSMIT"}


def _load_host():
    source_root = ROOT
    if not (source_root / "firmware/host/pmars_host_stdio.c").is_file():
        raise RuntimeError("Native protocol sources are not installed with this wheel; run from a repository checkout or use `pip install -e .`.")
    temp = tempfile.TemporaryDirectory(prefix="pmars-hil-")
    executable = Path(temp.name) / "pmars_host_stdio"
    try:
        subprocess.run(["cc", "-std=c99", "-O1", "-Wall", "-Wextra", "-Werror",
                        "-I", str(source_root / "firmware/pmars_core/include"),
                        "-I", str(source_root / "firmware/esp32/components/pmars_proto/include"),
                        str(source_root / "firmware/pmars_core/src/pmars_core.c"),
                        str(source_root / "firmware/esp32/components/pmars_proto/proto.c"),
                        str(source_root / "firmware/host/pmars_host_stdio.c"), "-o", str(executable)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        temp.cleanup()
        raise RuntimeError("Could not compile the native protocol host; install a C compiler or run from a repository checkout.") from exc
    host = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)
    return temp, host


def _request(host, message: dict, seq: int) -> dict:
    try:
        encoded = encode_message(message, seq)
        if isinstance(host, subprocess.Popen):
            if host.stdin is None or host.stdout is None:
                raise RuntimeError("protocol host pipes are unavailable")
            host.stdin.write(encoded.decode("utf-8"))
            host.stdin.flush()
            response_line = host.stdout.readline().encode("utf-8")
        else:
            host.write(encoded)
            host.flush()
            response_line = host.readline()
    except (BrokenPipeError, OSError) as exc:
        raise RuntimeError("pmars_host_stdio stopped unexpectedly") from exc
    if not response_line:
        raise RuntimeError("pmars_host_stdio returned no response")
    response = decode_message(response_line)
    if response.get("type") == "error":
        raise ContractError(f"C protocol error: {response.get('code')} for {message.get('type')}: {message}")
    return response


def _protocol_decision(host, state, tasks, scheduler: str, seq: int):
    _request(host, {"type": "reset"}, seq)
    seq += 1
    residents = sum(task.payload_bytes or 0 for task in tasks)
    config = {
        "type": "config", "now_ms": state.now_ms, "rule": scheduler == "rule",
        "energy_mj": state.energy_mj,
        "storage_used_bytes": state.storage_used_bytes - residents,
        "storage_total_bytes": state.storage_total_bytes,
        "memory_available_bytes": state.memory_available_bytes,
        "compute_capacity_milli": state.compute_capacity_milli,
        "throttle_fraction_milli": state.throttle_fraction_milli,
        "processing_power_mw": state.processing_power_mw,
        "transmit_power_mw": state.transmit_power_mw,
        "store_power_mw": state.idle_power_mw,
        "drain_horizon_ms": state.drain_horizon_ms,
        "store_horizon_ms": ContractConfig().store_horizon_ms,
        "urgent_slack_ms": ContractConfig().urgent_slack_ms,
    }
    _request(host, config, seq)
    seq += 1
    # The wire contract carries a bounded contact horizon. Simulator contact
    # lists may be longer, so send the nearest upcoming windows only.
    for contact in state.contacts[:16]:
        contact_config = {**config, "contacts": [list(contact)], "contacts_append": True}
        _request(host, contact_config, seq)
        seq += 1
    for task in tasks:
        message = {"type": "task_submit", "task": dataclasses.asdict(task)}
        _request(host, message, seq)
        seq += 1
    decision = _request(host, {"type": "decide"}, seq)
    return decision, seq + 1


def replay(scenario: str, scheduler: str, seeds: range, output_dir: Path,
           port: str | None = None, baud: int = 115200) -> dict:
    if scheduler not in POLICIES:
        raise ValueError("host replay supports edf and rule")
    output_dir.mkdir(parents=True, exist_ok=True)
    temp = None
    if port:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("serial replay requires the optional pyserial==3.5 extra") from exc
        host = serial.Serial(port, baudrate=baud, timeout=5, write_timeout=5)
    else:
        temp, host = _load_host()
    transport_label = f"pyserial {baud} baud serial" if port else "pmars_host_stdio JSONL; host loopback only"
    summary = Counter()
    seed_rows = []
    seq = 0
    try:
        for seed in seeds:
            config = load_config(scenario)
            simulation = build_simulation(scenario, scheduler, seed,
                                          tasks=generate_tasks(config, seed))
            original_decide = simulation.scheduler.decide
            counts = Counter()
            def compare(snapshot, pending, sim):
                nonlocal seq
                state = _contract_state(sim)
                converted = [_contract_task(record) for record in pending]
                candidates = bounded_tasks(converted)
                py_decision = POLICIES[scheduler](state, converted, ContractConfig())
                c_decision, seq = _protocol_decision(host, state, candidates, scheduler, seq)
                c_pair = (c_decision["action"], c_decision["task_id"] or None)
                py_pair = (py_decision.action, py_decision.task_id)
                counts["decisions"] += 1
                counts["c_python_mismatches"] += c_pair != py_pair

                allowed_ids = {task.id for task in candidates}
                bounded_pending = [record for record in pending if record.task.id in allowed_ids]
                feasible = sim.feasible_pairs
                sim.feasible_pairs = lambda: [pair for pair in feasible()
                                                if pair[0].task.id in allowed_ids]
                try:
                    original = original_decide(snapshot, bounded_pending, sim)
                finally:
                    sim.feasible_pairs = feasible
                counts["integer_original_float_mismatches"] += py_pair != (
                    original.action.value, original.task_id
                )
                counts[f"action_{py_pair[0].lower()}"] += 1
                return original

            simulation.scheduler.decide = compare
            simulation.run(config["mission_duration_s"])
            counts["lifecycle_process"] = sum(row.get("action") == "PROCESS" for row in simulation.history)
            counts["lifecycle_store"] = sum(row.get("action") == "STORE" for row in simulation.history)
            counts["lifecycle_transmit"] = sum(row.get("action") == "TRANSMIT" for row in simulation.history)
            counts["terminal_completed"] = len(simulation.queue.completed)
            processed_ids = {row.get("task_id") for row in simulation.history
                             if row.get("action") == "PROCESS"}
            stored_ids = {row.get("task_id") for row in simulation.history
                          if row.get("action") == "STORE"}
            transmitted_ids = {row.get("task_id") for row in simulation.history
                               if row.get("action") == "TRANSMIT"}
            counts["full_lifecycle_tasks"] = sum(
                record.task.id in processed_ids & stored_ids & transmitted_ids
                for record in simulation.queue.completed
            )
            source = output_dir / f"{scenario}_{scheduler}_{seed}.jsonl"
            with source.open("w", encoding="utf-8") as handle:
                for row in simulation.history:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            report = {"type": "host_loopback" if not port else "serial_replay",
                      "transport": transport_label,
                      "scenario": scenario, "scheduler": scheduler, "seed": seed,
                      "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), **counts}
            seed_rows.append(report)
            summary.update(counts)
        observations_path = output_dir / "raw_observations.jsonl"
        observations = {}
        if observations_path.is_file():
            for line in observations_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    observations[(row.get("scenario"), row.get("scheduler"), row.get("seed"))] = row
        for row in seed_rows:
            observations[(row["scenario"], row["scheduler"], row["seed"])] = row
        with observations_path.open("w", encoding="utf-8") as handle:
            for key in sorted(observations):
                handle.write(json.dumps(observations[key], sort_keys=True) + "\n")
        readme = ["# Host protocol loopback", "", "The native stdio executable parses JSONL and calls the portable C core.",
                  "Host loopback only; this is not a hardware test.", ""]
        for row in seed_rows:
            readme.append(f"- {row['scenario']} {row['scheduler']} seed {row['seed']}: "
                          f"{row['decisions']} decisions, C/Python mismatches "
                          f"{row['c_python_mismatches']}, integer/original-float mismatches "
                          f"{row['integer_original_float_mismatches']}, PROCESS "
                          f"{row['lifecycle_process']}, STORE {row['lifecycle_store']}, "
                          f"TRANSMIT {row['lifecycle_transmit']}, completed {row['terminal_completed']}, "
                          f"full lifecycle tasks {row['full_lifecycle_tasks']}.")
        (output_dir / f"{scenario}_{scheduler}_summary.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    finally:
        if isinstance(host, subprocess.Popen):
            if host.stdin:
                host.stdin.close()
            host.wait(timeout=2)
        else:
            host.close()
        if temp is not None:
            temp.cleanup()
    return {"cases": len(seed_rows), "decisions": summary["decisions"],
            "c_python_mismatches": summary["c_python_mismatches"],
            "integer_original_float_mismatches": summary["integer_original_float_mismatches"],
            "output": str(output_dir), "transport": transport_label}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loopback", action="store_true")
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--scheduler", choices=("edf", "rule"), required=True)
    parser.add_argument("--seeds", default="100-104")
    parser.add_argument("--output", default="results/hil_demo")
    args = parser.parse_args()
    if not args.loopback:
        if not args.port:
            parser.error("choose --loopback or provide --port for serial protocol replay")
    start, end = (int(part) for part in args.seeds.split("-", 1))
    try:
        result = replay(args.scenario, args.scheduler, range(start, end + 1), Path(args.output),
                        port=args.port if not args.loopback else None, baud=args.baud)
    except RuntimeError as exc:
        parser.error(str(exc))
    result["utc"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

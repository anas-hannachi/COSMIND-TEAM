"""10,000 deterministic bounded-state comparisons of C and Python policies."""

import ctypes
import random
import subprocess
import tempfile
from pathlib import Path

from pmars_simulation.hil._cabi import CConfig, CContact, CDecision, CState, CTask
from pmars_simulation.contract.models import ContractConfig, ContractState, ContractTask
from pmars_simulation.policy import edf, rule


def _compile(temp: str) -> ctypes.CDLL:
    root = Path(__file__).resolve().parents[1]
    library = Path(temp) / "libpmars_core.so"
    subprocess.run(["cc", "-shared", "-fPIC", "-O1", "-Wall", "-Wextra", "-Werror",
                    "-I", str(root / "firmware/pmars_core/include"),
                    str(root / "firmware/pmars_core/src/pmars_core.c"), "-o", str(library)], check=True)
    core = ctypes.CDLL(str(library))
    core.pmars_decide.argtypes = [ctypes.POINTER(CState), ctypes.POINTER(CTask), ctypes.c_uint32,
                                  ctypes.POINTER(CConfig), ctypes.c_int, ctypes.POINTER(CDecision)]
    core.pmars_decide.restype = ctypes.c_int
    return core


def test_c_decisions_match_python_for_10000_bounded_states():
    rng = random.Random(0xC05A1D)
    action_names = {0: "IDLE", 1: "PROCESS", 2: "STORE", 3: "TRANSMIT"}
    with tempfile.TemporaryDirectory(prefix="pmars-fuzz-") as temp:
        core = _compile(temp)
        for case in range(10_000):
            count = 1 if case == 0 else rng.randrange(0, 33)
            now = rng.randrange(0, 100_000)
            contacts = []
            start = max(0, now - 10_000)
            for _ in range(rng.randrange(0, 5)):
                start += rng.randrange(1_000, 10_000)
                end = start + rng.randrange(2_000, 20_000)
                contacts.append((start, end, rng.randrange(64_000, 2_000_001),
                                 rng.randrange(64_000, 2_000_001), rng.randrange(0, 801)))
                start = end
            tasks = []
            resident_total = 0
            for i in range(count):
                size = rng.randrange(0, 100_000)
                payload = 2 if case == 0 and i == 0 else rng.randrange(0, 100_000)
                resident_total += payload
                tasks.append(ContractTask(
                    f"{case % 1000}-{i}", "telemetry", size, rng.randrange(0, 100_000),
                    rng.randrange(0, 200_000), (0 if case == 0 and i == 0 else rng.randrange(0, 100_000)), rng.randrange(1, 20_000),
                    rng.randrange(0, 10), rng.randrange(0, 1_000_000), 0,
                    max(0, now + rng.randrange(-1000, 100_000)), payload_bytes=payload,
                    processed=(False if case == 0 and i == 0 else bool(rng.randrange(0, 2))),
                    actual_output_bytes=(1 if case == 0 and i == 0 else
                                         (rng.randrange(0, 8) if rng.randrange(0, 5) == 0 else None)),
                ))
            state = ContractState(
                now_ms=now, energy_mj=rng.randrange(0, 10_000_000),
                storage_used_bytes=(resident_total - 1 if case == 0 else
                                    resident_total + rng.randrange(-3, 4)),
                storage_total_bytes=max(0, resident_total + rng.randrange(0, 1_000_000)),
                memory_available_bytes=rng.randrange(0, 500_000), compute_capacity_milli=rng.randrange(0, 200_000),
                throttle_fraction_milli=rng.randrange(400, 1001), processing_power_mw=rng.randrange(0, 100_000),
                transmit_power_mw=rng.randrange(0, 100_000), idle_power_mw=1000,
                drain_horizon_ms=now + rng.randrange(0, 200_000), contacts=tuple(contacts),
            )
            cstate = CState(state.now_ms, state.energy_mj, state.storage_used_bytes, state.storage_total_bytes,
                            state.memory_available_bytes, state.compute_capacity_milli, state.throttle_fraction_milli,
                            state.processing_power_mw, state.transmit_power_mw, state.idle_power_mw,
                            state.drain_horizon_ms)
            cstate.contact_count = len(contacts)
            for i, contact in enumerate(contacts):
                cstate.contacts[i] = CContact(*contact)
            c_tasks = (CTask * max(1, count))()
            for i, task in enumerate(tasks):
                c_tasks[i].id = task.id.encode("ascii")
                c_tasks[i].input_bytes = task.input_bytes
                c_tasks[i].payload_bytes = task.payload_bytes or 0
                c_tasks[i].output_bytes_est = task.output_bytes_est
                c_tasks[i].actual_output_bytes = task.actual_output_bytes if task.actual_output_bytes is not None else -1
                c_tasks[i].mem_req_bytes = task.mem_req_bytes
                c_tasks[i].demand_milli = task.demand_milli
                c_tasks[i].base_proc_ms = task.base_proc_ms
                c_tasks[i].priority = task.priority
                c_tasks[i].value_milli = task.value_milli
                c_tasks[i].created_ms = task.created_ms
                c_tasks[i].deadline_ms = task.deadline_ms
                c_tasks[i].processed = int(task.processed)
            cfg = ContractConfig()
            ccfg = CConfig(cfg.store_horizon_ms, cfg.urgent_slack_ms)
            for is_rule, decide in ((0, edf.decide), (1, rule.decide)):
                expected = decide(state, tasks, cfg)
                actual = CDecision()
                assert core.pmars_decide(ctypes.byref(cstate), c_tasks, count, ctypes.byref(ccfg),
                                         is_rule, ctypes.byref(actual)) == 0, case
                observed = (action_names[actual.action], actual.task_id.decode("ascii") or None)
                assert observed == (expected.action, expected.task_id), (case, is_rule, observed, expected)

import subprocess
from pathlib import Path

from pmars_simulation.contract.codec import decode_message, encode_message
from pmars_simulation.contract.limits import MAX_CONTACTS, MAX_LINE, MAX_TASKS


ROOT = Path(__file__).resolve().parents[1]


def test_hello_tick_and_result_expose_host_engine_state(tmp_path):
    binary = tmp_path / "pmars_host_stdio"
    subprocess.run([
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/pmars_core/include"),
        "-I", str(ROOT / "firmware/esp32/components/pmars_proto/include"),
        str(ROOT / "firmware/pmars_core/src/pmars_core.c"),
        str(ROOT / "firmware/esp32/components/pmars_proto/proto.c"),
        str(ROOT / "firmware/host/pmars_host_stdio.c"), "-o", str(binary),
    ], check=True)
    messages = [
        {"type": "hello"},
        {"type": "config", "now_ms": 0, "energy_mj": 10000, "storage_used_bytes": 0,
         "storage_total_bytes": 1000, "memory_available_bytes": 1000, "compute_capacity_milli": 100000,
         "throttle_fraction_milli": 1000, "processing_power_mw": 10, "transmit_power_mw": 10,
         "store_power_mw": 10, "drain_horizon_ms": 10000,
         "contacts": [[0, 1000, 1000000, 1000000, 0]]},
        {"type": "task_submit", "task": {"id": "t0", "input_bytes": 10, "payload_bytes": 10,
         "output_bytes_est": 5, "mem_req_bytes": 1, "demand_milli": 1, "base_proc_ms": 1,
         "priority": 1, "value_milli": 1, "created_ms": 0, "deadline_ms": 900}},
        {"type": "tick"}, {"type": "event"}, {"type": "event"},
        {"type": "event"}, {"type": "event"}, {"type": "result"},
    ]
    lines = b"".join(encode_message(message, seq) for seq, message in enumerate(messages))
    output = subprocess.run([str(binary)], input=lines, capture_output=True, check=True).stdout.splitlines(keepends=True)
    hello, config, admitted, tick, *events, result = [decode_message(line) for line in output]
    assert hello["contract_version"] == 1 and hello["target"] == "host"
    assert (hello["max_tasks"], hello["max_contacts"], hello["max_line"]) == (MAX_TASKS, MAX_CONTACTS, MAX_LINE)
    assert config["type"] == "config_ack" and admitted["task_id"] == "t0"
    assert tick["action"] == "TRANSMIT" and tick["task_id"] == "t0"
    assert tick["status"] == tick["terminal_outcome"] == "completed"
    assert tick["now_ms"] > 0 and tick["storage_used_bytes"] == 0
    assert [event["event_kind"] for event in events] == ["admitted", "transmit_started", "transmitted", "completed"]
    assert all(event["task_id"] == "t0" for event in events)
    assert result["type"] == "result" and result["completed"] == 1
    assert result["dropped_events"] == 0 and result["unfinished"] == 0

"""Regenerate the static protocol-error JSONL corpora from the contract codec."""

import json
import zlib
from pathlib import Path

from pmars_simulation.contract.codec import encode_message


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contract/fixtures/protocol_errors"


def task(task_id="t0", size=10):
    return {"id": task_id, "input_bytes": size, "payload_bytes": size,
            "output_bytes_est": 5, "mem_req_bytes": 1, "demand_milli": 1,
            "base_proc_ms": 1, "priority": 1, "value_milli": 1,
            "created_ms": 0, "deadline_ms": 60000}


def raw(payload, seq=0):
    body = {"v": 1, "seq": seq, **payload}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["crc"] = zlib.crc32(canonical) & 0xFFFFFFFF
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    valid = encode_message({"type": "tick"}, 0)
    start = valid.index(b'"crc":') + len(b'"crc":')
    end = valid.index(b",", start)
    bad_crc = valid[:start] + str(int(valid[start:end]) + 1).encode() + valid[end:]
    config = {"type": "config", "now_ms": 0, "energy_mj": 100000,
              "storage_used_bytes": 0, "storage_total_bytes": 10000,
              "memory_available_bytes": 10000, "compute_capacity_milli": 100000,
              "throttle_fraction_milli": 1000, "processing_power_mw": 10,
              "transmit_power_mw": 10, "store_power_mw": 10,
              "drain_horizon_ms": 100000, "contacts": [["bad"]]}
    fixtures = {
        "bad_crc": [bad_crc],
        "bad_version": [raw({"type": "tick", "v": 2})],
        "unknown_type": [encode_message({"type": "unknown"}, 0)],
        "bound_exceeded_tasks": [encode_message({"type": "tick", "tasks": [0] * 97}, 0)],
        "bound_exceeded_contacts": [encode_message({"type": "tick", "contacts": [[n * 10, n * 10 + 5, 1000, 1000, 0]
                                                                                 for n in range(17)]}, 0)],
        "line_too_long": [b"x" * 512 + b"\n"],
        "malformed_number": [encode_message({"type": "tick", "now_ms": 1.5}, 0),
                             encode_message({"type": "tick", "now_ms": 9223372036854775808}, 1)],
        "duplicate_task_id": [encode_message({"type": "task_submit", "task": task("same")}, 0),
                              encode_message({"type": "task_submit", "task": task("same")}, 1)],
        "queue_full": [encode_message({"type": "task_submit", "task": task(f"q{n:03d}")}, n)
                       for n in range(97)],
        "malformed_contacts": [encode_message(config, 0)],
        "bad_sequence_or_type": [encode_message({"type": "hello"}, 0),
                                 encode_message({"type": "hello"}, 0)],
        "admission_rejected": [encode_message({"type": "task_submit", "task": task("large", 100000001)}, 0)],
    }
    for name, lines in fixtures.items():
        (OUT / f"{name}.jsonl").write_bytes(b"".join(lines))


if __name__ == "__main__":
    main()

import json
import subprocess

import pytest

from pmars_simulation.contract.codec import ContractError, decode_message, encode_message


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contract" / "fixtures"


@pytest.fixture(scope="module")
def host_stdio(tmp_path_factory):
    binary = tmp_path_factory.mktemp("proto-host") / "pmars_host_stdio"
    subprocess.run([
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/pmars_core/include"),
        "-I", str(ROOT / "firmware/esp32/components/pmars_proto/include"),
        str(ROOT / "firmware/pmars_core/src/pmars_core.c"),
        str(ROOT / "firmware/esp32/components/pmars_proto/proto.c"),
        str(ROOT / "firmware/host/pmars_host_stdio.c"), "-o", str(binary),
    ], check=True)
    return binary


def _c_responses(host_stdio, lines):
    result = subprocess.run([str(host_stdio)], input=b"".join(lines), capture_output=True, check=True)
    return [decode_message(line) for line in result.stdout.splitlines(keepends=True)]


def _version_line(version, seq=0):
    payload = {"v": version, "seq": seq, "type": "tick"}
    import zlib
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["crc"] = zlib.crc32(canonical) & 0xFFFFFFFF
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def test_valid_fixture_is_consumed_by_python_and_native_parser(host_stdio):
    line = (FIXTURES / "valid.jsonl").read_bytes()
    assert decode_message(line)["type"] == "tick"
    response = _c_responses(host_stdio, [line])[0]
    assert response["type"] == "event" and response["action"] == "IDLE"


def test_native_parser_returns_structured_errors(host_stdio):
    bad_crc = bytearray(encode_message({"type": "tick"}, 0))
    bad_crc[8] = ord("0") if bad_crc[8] != ord("0") else ord("1")
    lines = [
        bytes(bad_crc), _version_line(2, 1), encode_message({"type": "not_a_message"}, 2),
        encode_message({"type": "tick", "tasks": [{}] * 97}, 3),
        encode_message({"type": "tick", "contacts": [[0, 1, 1, 1, 0]] * 17}, 4),
        encode_message({"type": "tick", "now_ms": 1.5}, 5),
        b"x" * 600 + b"\n",
    ]
    responses = _c_responses(host_stdio, lines)
    assert [item.get("code") for item in responses] == [
        "bad_crc", "bad_version", "unknown_type", "bound_exceeded",
        "bound_exceeded", "malformed_number", "line_too_long",
    ]

def test_python_codec_rejects_bounds_duplicates_and_non_integer_numbers(host_stdio):
    cases = [
        ({"type": "tick", "tasks": [{}] * 97}, "bound_exceeded"),
        ({"type": "tick", "contacts": [[0, 1, 1, 1, 0]] * 17}, "bound_exceeded"),
        ({"type": "tick", "tasks": [{"id": "same"}, {"id": "same"}]}, "duplicate_task_id"),
        ({"type": "tick", "now_ms": 1.5}, "malformed_number"),
        ({"type": "not_a_message"}, "unknown_type"),
    ]
    lines = []
    for message, expected in cases:
        line = encode_message(message, 0)
        with pytest.raises(ContractError, match=expected):
            decode_message(line)
        if expected != "duplicate_task_id":
            lines.append(line)
    native = _c_responses(host_stdio, lines)
    assert [item.get("code") for item in native] == [
        "bound_exceeded", "bound_exceeded", "malformed_number", "unknown_type",
    ]


def test_c_parser_reports_duplicate_ids_and_queue_full(host_stdio):
    messages = []
    seq = 0
    task = {"id": "same", "kind": "test", "input_bytes": 1, "payload_bytes": 1,
            "output_bytes_est": 1, "actual_output_bytes": None, "mem_req_bytes": 0,
            "demand_milli": 0, "base_proc_ms": 1, "priority": 1, "value_milli": 1,
            "created_ms": 0, "deadline_ms": 10000, "processed": False,
            "science_payload": None}
    for _ in range(2):
        messages.append(encode_message({"type": "task_submit", "task": task}, seq))
        seq += 1
    duplicate_response = _c_responses(host_stdio, messages)
    assert duplicate_response[-1].get("code") == "duplicate_task_id"

    messages = []
    for index in range(97):
        task["id"] = f"q{index}"
        messages.append(encode_message({"type": "task_submit", "task": task}, index))
    queue_responses = _c_responses(host_stdio, messages)
    assert queue_responses[-1].get("code") == "queue_full"

import json
import subprocess
from pathlib import Path

import pytest

from pmars_simulation.contract.codec import ContractError, decode_message


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EXPECTATIONS = json.loads(
    (ROOT / "contract/fixtures/protocol_error_fixtures.json").read_text(encoding="utf-8")
)


def _fixture_lines():
    directory = ROOT / "contract/fixtures/protocol_errors"
    return {name: (directory / f"{name}.jsonl").read_bytes().splitlines(keepends=True)
            for name in FIXTURE_EXPECTATIONS}


@pytest.fixture(scope="module")
def native_host(tmp_path_factory):
    binary = tmp_path_factory.mktemp("protocol-fixtures") / "pmars_host_stdio"
    subprocess.run([
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/pmars_core/include"),
        "-I", str(ROOT / "firmware/esp32/components/pmars_proto/include"),
        str(ROOT / "firmware/pmars_core/src/pmars_core.c"),
        str(ROOT / "firmware/esp32/components/pmars_proto/proto.c"),
        str(ROOT / "firmware/host/pmars_host_stdio.c"), "-o", str(binary),
    ], check=True)
    return binary


def _python_expected(name, lines):
    expected = FIXTURE_EXPECTATIONS[name]["expected_code"]
    seen_ids, seq_seen, accepted = set(), set(), 0
    for line in lines:
        try:
            message = decode_message(line)
        except ContractError as exc:
            assert expected in str(exc)
            return
        if name == "duplicate_task_id":
            task_id = message["task"]["id"]
            if task_id in seen_ids:
                assert expected == "duplicate_task_id"
                return
            seen_ids.add(task_id)
        elif name == "queue_full":
            accepted += 1
            if accepted > 96:
                assert expected == "queue_full"
                return
        elif name == "bad_sequence_or_type":
            seq = message["seq"]
            if seq in seq_seen:
                assert expected == "bad_sequence_or_type"
                return
            seq_seen.add(seq)
        elif name == "admission_rejected":
            assert message["task"]["payload_bytes"] > 100_000_000
            assert expected == "admission_rejected"
            return
    pytest.fail(f"fixture {name} did not trigger {expected}")


@pytest.mark.parametrize("name", sorted(FIXTURE_EXPECTATIONS))
def test_error_fixtures_are_consumed_by_python_codec_and_c_parser(native_host, name):
    lines = _fixture_lines()[name]
    _python_expected(name, lines)
    process = subprocess.run([str(native_host)], input=b"".join(lines), capture_output=True, check=True)
    replies = [decode_message(line) for line in process.stdout.splitlines(keepends=True)]
    assert replies[-1]["type"] == "error"
    assert replies[-1]["code"] == FIXTURE_EXPECTATIONS[name]["expected_code"]

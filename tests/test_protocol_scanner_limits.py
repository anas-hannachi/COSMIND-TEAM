import subprocess
import zlib
from pathlib import Path

from pmars_simulation.contract.codec import decode_message, encode_message


ROOT = Path(__file__).resolve().parents[1]


def _raw_crc(body):
    checksum = zlib.crc32(body.encode("latin1")) & 0xFFFFFFFF
    return f'{{"crc":{checksum},' + body[1:] + "\n"


def test_documented_scanner_accepts_unknown_keys_and_exposes_first_match_behavior(tmp_path):
    binary = tmp_path / "pmars_host_stdio"
    subprocess.run([
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/pmars_core/include"),
        "-I", str(ROOT / "firmware/esp32/components/pmars_proto/include"),
        str(ROOT / "firmware/pmars_core/src/pmars_core.c"),
        str(ROOT / "firmware/esp32/components/pmars_proto/proto.c"),
        str(ROOT / "firmware/host/pmars_host_stdio.c"), "-o", str(binary),
    ], check=True)

    unknown = encode_message({"type": "hello", "extension": "ignored"}, 0)
    assert decode_message(unknown)["extension"] == "ignored"
    duplicate_type = _raw_crc('{"type":"hello","type":"tick","seq":1,"v":1}')
    key_like_string = encode_message({"type": "hello", "note": 'literal "v":2'}, 2)
    output = subprocess.run([str(binary)], input=unknown + duplicate_type.encode() + key_like_string,
                            capture_output=True, check=True).stdout.splitlines(keepends=True)
    replies = [decode_message(line) for line in output]
    assert replies[0]["type"] == "hello_ack"  # Unknown extension was ignored.
    assert replies[1]["type"] == "hello_ack"  # First duplicate "type" wins.
    assert replies[2]["type"] == "hello_ack"  # Escaped key-like text stays inside its string value.

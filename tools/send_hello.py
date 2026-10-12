"""Send a CRC-valid `hello` to the firmware (or a host executable) and print the reply.

Serial:        python tools/send_hello.py --port COM5 [--baud 115200]
Host binary:   python tools/send_hello.py --host-binary ./pmars_host_stdio
The reply (`hello_ack`) reports target, IDF version, reset reason, free heap, stack high-water mark and the protocol limits.
Record it with your bench notes (Stage A/B evidence).
"""

import argparse
import json
import subprocess
import sys
import zlib


def hello_line(seq=1):
    body = json.dumps({"seq": seq, "type": "hello", "v": 1}, sort_keys=True, separators=(",", ":"))
    crc = zlib.crc32(body.encode("ascii")) & 0xFFFFFFFF
    return '{"crc":%d,%s\n' % (crc, body[1:])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--host-binary")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    if bool(args.port) == bool(args.host_binary):
        parser.error("give exactly one of --port or --host-binary")
    if args.host_binary:
        done = subprocess.run([args.host_binary], input=hello_line().encode("ascii"), capture_output=True, timeout=10)
        reply = done.stdout.decode("ascii", "replace").strip()
    else:
        try:
            import serial  # pyserial, optional extra: pip install .[hil]
        except ImportError:
            sys.exit("pyserial is required for --port (pip install pyserial==3.5)")
        with serial.Serial(args.port, args.baud, timeout=args.timeout) as link:
            link.reset_input_buffer()
            link.write(hello_line().encode("ascii"))
            link.flush()
            reply = link.readline().decode("ascii", "replace").strip()
    if not reply:
        sys.exit("no reply (check port, baud rate, and that the firmware is running)")
    print(reply)
    try:
        ok = json.loads(reply).get("type") == "hello_ack"
    except ValueError:
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

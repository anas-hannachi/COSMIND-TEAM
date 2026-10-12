import json
import subprocess
import sys

from pmars_simulation.hil.driver import _load_host
from tools.send_hello import hello_line


def test_hello_line_is_accepted_by_the_native_host_and_returns_hello_ack():
    temp, host = _load_host()
    try:
        host.stdin.write(hello_line(1))
        host.stdin.flush()
        reply = json.loads(host.stdout.readline())
    finally:
        host.stdin.close()
        host.wait(timeout=2)
        temp.cleanup()
    assert reply["type"] == "hello_ack" and reply["max_tasks"] == 96 and reply["contract_version"] == 1


def test_send_hello_cli_requires_exactly_one_transport():
    done = subprocess.run([sys.executable, "tools/send_hello.py"], capture_output=True, text=True)
    assert done.returncode != 0

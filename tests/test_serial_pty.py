import os
import pty
import select
import subprocess
import threading
import tty

import pytest

serial = pytest.importorskip("serial")
from pmars_simulation.hil.driver import replay


def test_pyserial_full_run_through_pty_bridge(tmp_path):
    from pmars_simulation.scenarios import ROOT

    master_fd, slave_fd = pty.openpty()
    tty.setraw(slave_fd)
    binary = tmp_path / "pmars_host_stdio"
    subprocess.run([
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/pmars_core/include"),
        "-I", str(ROOT / "firmware/esp32/components/pmars_proto/include"),
        str(ROOT / "firmware/pmars_core/src/pmars_core.c"),
        str(ROOT / "firmware/esp32/components/pmars_proto/proto.c"),
        str(ROOT / "firmware/host/pmars_host_stdio.c"), "-o", str(binary),
    ], check=True)
    host = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
    stop = threading.Event()

    def bridge():
        assert host.stdin is not None and host.stdout is not None
        while not stop.is_set():
            reads, _, _ = select.select([master_fd, host.stdout.fileno()], [], [], 0.05)
            for fd in reads:
                try:
                    block = os.read(fd, 4096)
                except OSError:
                    continue
                if not block:
                    continue
                if fd == master_fd:
                    host.stdin.write(block)
                    host.stdin.flush()
                else:
                    os.write(master_fd, block)

    thread = threading.Thread(target=bridge, daemon=True)
    thread.start()
    try:
        result = replay("bench_normal", "edf", range(100, 101), tmp_path / "serial-output",
                        port=os.ttyname(slave_fd), baud=115200)
        assert result["c_python_mismatches"] == 0
        assert result["integer_original_float_mismatches"] == 0
    finally:
        stop.set()
        thread.join(timeout=2)
        host.terminate()
        host.wait(timeout=2)
        os.close(master_fd)
        os.close(slave_fd)

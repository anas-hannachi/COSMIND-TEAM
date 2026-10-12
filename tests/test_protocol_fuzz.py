import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_crc_valid_protocol_mutations_survive_asan_ubsan(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("cc")
    assert compiler, "a C compiler is required for the native parser fuzz test"
    binary = tmp_path / "pmars_host_asan"
    command = [
        compiler, "-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
        "-Ifirmware/pmars_core/include", "-Ifirmware/esp32/components/pmars_proto/include",
        "firmware/host/pmars_host_stdio.c", "firmware/esp32/components/pmars_proto/proto.c",
        "firmware/pmars_core/src/pmars_core.c", "-o", str(binary),
    ]
    runtime_link_dir = os.environ.get("PMARS_SANITIZER_LIBRARY_DIR")
    if runtime_link_dir:
        command[1:1] = [f"-B{runtime_link_dir}/", f"-L{runtime_link_dir}"]
    subprocess.run(command, cwd=ROOT, check=True)
    env = dict(os.environ, PMARS_HOST_BINARY=str(binary))
    result = subprocess.run([sys.executable, str(ROOT / "protocol_fuzz.py"), "20000"],
                            cwd=ROOT, env=env, capture_output=True, timeout=300, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert "lines: 20000 exit code: 0 stderr bytes: 0" in result.stdout

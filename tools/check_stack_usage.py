"""Compile the portable C core/protocol and enforce documented stack budgets."""

import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("firmware/pmars_core/src/pmars_core.c",
           "firmware/esp32/components/pmars_proto/proto.c")
INCLUDES = ("firmware/pmars_core/include", "firmware/esp32/components/pmars_proto/include")
CRITICAL_CHAIN = ("pmars_proto_handle", "pmars_engine_step", "pmars_decide",
                  "pmars_plan_candidates", "pmars_can_process", "earliest_transfer",
                  "pmars_transfer_time_ms", "contact_at")
FRAME_BUDGET = 1024
CHAIN_BUDGET = 3072


def main():
    compiler = shutil.which("gcc") or shutil.which("cc")
    if not compiler:
        raise SystemExit("FAIL: gcc/cc is required for stack-usage checking")
    with tempfile.TemporaryDirectory(prefix="pmars-stack-") as temp:
        output = Path(temp)
        for index, source in enumerate(SOURCES):
            subprocess.run([compiler, "-std=c99", "-O1", "-fstack-usage", "-Wall", "-Wextra", "-Werror", "-c",
                            *[f"-I{ROOT / include}" for include in INCLUDES],
                            str(ROOT / source), "-o", str(output / f"source{index}.o")], check=True)
        frames = {}
        for report in output.glob("*.su"):
            for row in report.read_text(encoding="utf-8").splitlines():
                location, size, *_ = row.split("\t")
                frames[location.rsplit(":", 1)[-1]] = int(size)
        maximum = max(frames.values(), default=0)
        if maximum > FRAME_BUDGET:
            raise SystemExit(f"FAIL: frame {maximum} B exceeds {FRAME_BUDGET} B")
        missing = [name for name in CRITICAL_CHAIN if name not in frames]
        if missing:
            raise SystemExit(f"FAIL: stack report lacks critical functions: {missing}")
        chain = sum(frames[name] for name in CRITICAL_CHAIN)
        if chain > CHAIN_BUDGET:
            raise SystemExit(f"FAIL: critical call-chain estimate {chain} B exceeds {CHAIN_BUDGET} B")
        print(f"PASS: maximum frame {maximum} B / {FRAME_BUDGET} B; critical call-chain estimate "
              f"{chain} B / {CHAIN_BUDGET} B (host x86-64)")


if __name__ == "__main__":
    main()

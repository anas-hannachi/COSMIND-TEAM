"""Permanent C decision comparison against the original float simulator."""

import subprocess
import sys
from pathlib import Path


def test_c_vs_original_bench_scenarios_have_no_decision_mismatches():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "c_vs_original_check.py")],
        cwd=root, check=True, capture_output=True, text=True,
    )
    lines = result.stdout.splitlines()
    for scenario in ("bench_normal", "bench_burst", "bench_low_energy", "bench_poor_link"):
        rows = [line for line in lines if line.startswith(scenario)]
        assert len(rows) == 2, result.stdout
        assert all("mismatches=0" in row for row in rows), result.stdout

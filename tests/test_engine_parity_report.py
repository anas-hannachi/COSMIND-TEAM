import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_full_bench_engine_comparison_enumerates_every_difference_with_a_cause():
    result = subprocess.run([sys.executable, "tools/engine_parity.py"], cwd=ROOT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)},
                            capture_output=True, text=True, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{"case"')]
    assert len(rows) == 40
    for row in rows:
        assert "timely_count_match" in row
        assert row["engine_dropped_events"] == 0
        assert all(diff.get("task_id") and diff.get("cause") for diff in row["status_differences"])
        assert row["submit_rejections"]["queue_full"] == 0
        if row["case"]["scenario"] == "bench_burst":
            assert row["tasks"] > 96
    assert "status_differences=" in result.stdout.splitlines()[-1]

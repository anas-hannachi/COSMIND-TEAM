"""Regression guard for the simulator-faithful engine comparison (does not claim parity)."""

from tools.engine_parity_interleaved import measure


def test_interleaved_engine_comparison_stays_within_documented_bounds():
    rows, _ = measure(["bench_normal"], [100, 101])
    row = rows["bench_normal"]
    assert row["cases"] == 4
    # bench_normal differences are documented at ~3%; fail loudly on a regression toward the old 30% harness artifact.
    assert row["differences"] / row["tasks"] <= 0.08
    assert row["delivery_disagreements"] / row["tasks"] <= 0.04
    assert row["timely_count_match"] >= 3

import csv
import math
import tempfile
from pathlib import Path
import pytest

from pmars_simulation.analysis.statistics import t95
from pmars_simulation.contract.codec import decode_message, encode_message
from pmars_simulation.contract.units import capacity_bytes, deadline_ms, duration_ms, energy_mj, size_bytes
from pmars_simulation import scenarios
from pmars_simulation.scenarios import (
    BASE_SCENARIO_NAMES, build_simulation, generate_tasks, load_config,
    model_profile_sha256, model_profile_sha256_raw, workload_sha256,
)
from pmars_simulation.experiments.metrics import calculate


def test_contract_rounding_is_conservative():
    assert size_bytes(0.0000015) == 2
    assert duration_ms(0.0011) == 2
    assert energy_mj(0.0001) == 1
    assert capacity_bytes(0.0000019) == 1
    assert deadline_ms(0.0019) == 1


def test_codec_round_trip_and_crc_rejection():
    line = encode_message({"type": "tick", "now_ms": 12}, 4)
    assert decode_message(line)["now_ms"] == 12
    broken = bytearray(line)
    broken[-3] = ord("9")
    with pytest.raises(ValueError):
        decode_message(bytes(broken))


def test_student_t_values():
    assert t95(20) == 2.093
    assert t95(21) == pytest.approx(2.086, abs=0.001)
    assert t95(30) == pytest.approx(2.045, abs=0.001)


def test_profile_hash_normalizes_line_endings():
    config = load_config("normal")
    assert model_profile_sha256(config["model_profile"])
    assert model_profile_sha256_raw(config["model_profile"])
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "profiles").mkdir()
        profile = root / "profiles" / "test.yaml"
        scenarios.ROOT = root
        profile.write_bytes(b"a: 1\r\nb: 2\r\n")
        crlf_hash = model_profile_sha256("test")
        raw_hash = model_profile_sha256_raw("test")
        profile.write_bytes(b"a: 1\nb: 2\n")
        assert model_profile_sha256("test") == crlf_hash
        assert raw_hash != model_profile_sha256_raw("test")
    scenarios.ROOT = Path(__file__).resolve().parents[1]


def test_golden_v3_seeds_100_101():
    path = load_config.__globals__["ROOT"] / "results" / "evaluation_v3" / "raw_runs.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        frozen = {(r["scenario"], r["scheduler"], int(r["workload_seed"])): r for r in csv.DictReader(handle)}
    for scenario in BASE_SCENARIO_NAMES:
        config = load_config(scenario)
        for seed in (100, 101):
            tasks = generate_tasks(config, seed)
            sha = workload_sha256(tasks)
            for scheduler in ("random", "rule", "greedy", "edf", "contact_knapsack", "predictive"):
                sim = build_simulation(scenario, scheduler, seed, policy_seed=seed + 100_000, tasks=tasks)
                sim.run(config["mission_duration_s"])
                actual = calculate(sim)
                row = frozen[(scenario, scheduler, seed)]
                assert sha == row["workload_sha256"]
                for key in ("timely_value_retention", "tasks_completed_timely", "tasks_expired",
                            "tasks_rejected", "total_energy_consumed_j", "maximum_temperature_c"):
                    assert math.isclose(float(actual[key]), float(row[key]), rel_tol=1e-9, abs_tol=1e-12), (scenario, scheduler, seed, key)


def test_existing_workload_hashes_match_frozen_manifest():
    path = load_config.__globals__["ROOT"] / "results" / "evaluation_v3" / "workload_manifest.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        frozen = {(row["scenario"], int(row["workload_seed"])): row["workload_sha256"] for row in csv.DictReader(handle)}
    for scenario in BASE_SCENARIO_NAMES:
        config = load_config(scenario)
        for seed in range(100, 105):
            assert workload_sha256(generate_tasks(config, seed)) == frozen[(scenario, seed)]

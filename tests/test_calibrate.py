import csv
import shutil

import pytest
import yaml

from pmars_simulation.hil.calibrate import InsufficientTrials, measured_profile
from pmars_simulation.hil.measure import MEASUREMENT_COLUMNS, TEMPERATURE_COLUMNS
import pmars_simulation.scenarios as scenarios


def _write_synthetic(tmp_path):
    raw_path = tmp_path / "trials.csv"
    series_path = tmp_path / "temperature.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_COLUMNS)
        writer.writeheader()
        for action_index, action in enumerate(("idle", "process", "store", "transmit")):
            for trial in range(30):
                writer.writerow({
                    "board_sku": "test-only", "target": "test-only", "cpu_mhz": 240,
                    "avg_power_mw": 100 + action_index * 100 + trial,
                    "temp_min_mdc": 25000, "configuration": "synthetic",
                    "run_id": f"{action}-{trial}", "elapsed_us": 100000 + trial * 1000,
                    "success": "true", "ambient_temp_mdc": 24000, "action": action,
                    "input_bytes": 1000 + trial * 1000, "ram_total_internal_b": 300000,
                    "capacity_units": 100, "throttled_capacity_fraction": 0.5,
                    "max_temp_mdc": 85000, "throttle_at_mdc": 68000,
                    "energy_capacity_mj": 400000, "initial_energy_mj": 350000,
                    "solar_power_mw": 1000,
                })
    with series_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPERATURE_COLUMNS)
        writer.writeheader()
        for action in ("idle", "process", "store", "transmit"):
            for trial in range(30):
                initial = 25000
                delta = -200 if action in ("idle", "store") else 1000 if action == "process" else 500
                for index, temp in enumerate((initial, initial + delta)):
                    writer.writerow({"board_sku": "test-only", "target": "test-only",
                                     "configuration": "synthetic", "run_id": f"{action}-{trial}",
                                     "sample_index": index, "t_ms": index * 1000, "action": action,
                                     "temperature_mdc": temp, "ambient_temp_mdc": 24000})
    return raw_path, series_path


def test_synthetic_measurements_produce_profile_that_builds_simulation(tmp_path, monkeypatch):
    raw, series = _write_synthetic(tmp_path)
    profile = measured_profile(raw, series)
    assert profile["measurement_source"]["source_commit"] == "unavailable (not a git checkout)"
    assert profile["provenance"]["process_power_w"] == "measured"
    root = tmp_path / "project"
    shutil.copytree(scenarios.ROOT / "scenarios", root / "scenarios")
    (root / "profiles").mkdir()
    (root / "profiles" / "esp32_measured_v1.yaml").write_text(yaml.safe_dump(profile), encoding="utf-8")
    scenario_path = root / "scenarios" / "bench_normal.yaml"
    config = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    config["model_profile"] = "esp32_measured_v1"
    config.pop("energy", None)
    scenario_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(scenarios, "ROOT", root)
    loaded = scenarios.load_config("bench_normal")
    simulation = scenarios.build_simulation("bench_normal", "edf", 100, tasks=[])
    assert loaded["energy"]["process_power_w"] == profile["energy"]["process_power_w"]
    assert simulation.energy.process_power_w == profile["energy"]["process_power_w"]


def test_calibration_keeps_the_thirty_trial_refusal(tmp_path):
    raw, series = _write_synthetic(tmp_path)
    text = raw.read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    rows = [row for row in rows if row["action"] != "idle" or row["run_id"] != "idle-29"]
    with raw.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(InsufficientTrials):
        measured_profile(raw, series)

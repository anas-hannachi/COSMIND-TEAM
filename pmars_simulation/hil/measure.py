"""Append raw measurement rows without converting modeled output into measurements."""

import csv
from pathlib import Path


MEASUREMENT_COLUMNS = (
    "board_sku", "target", "psram_mb", "idf_version", "cpu_mhz", "supply_v",
    "input_energy_mj", "avg_power_mw", "peak_power_mw", "min_free_heap_internal_b",
    "min_free_heap_psram_b", "ram_total_internal_b", "temp_min_mdc", "temp_median_mdc", "temp_peak_mdc",
    "max_temp_mdc", "throttled", "throttle_at_mdc", "reset_reason", "failure_reason",
    "ambient_temp_mdc", "action", "task_type", "input_bytes", "actual_output_bytes",
    "configuration", "run_id", "elapsed_us", "energy_capacity_mj", "initial_energy_mj",
    "solar_power_mw", "capacity_units", "throttled_capacity_fraction", "success", "notes",
)

TEMPERATURE_COLUMNS = ("board_sku", "target", "configuration", "run_id", "sample_index",
                       "t_ms", "action", "temperature_mdc", "ambient_temp_mdc")


def append_raw(path: str | Path, row: dict) -> None:
    if row.get("source") == "simulator" or row.get("is_modeled") is True:
        raise ValueError("modeled values cannot be appended as measured hardware data")
    if not row.get("board_sku") or not row.get("target"):
        raise ValueError("board_sku and target are required measurement metadata")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    exists = target.exists() and target.stat().st_size > 0
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in MEASUREMENT_COLUMNS})


def append_temperature_sample(path: str | Path, row: dict) -> None:
    """Append one timestamped thermal sample to the separate raw time-series CSV."""
    if row.get("source") == "simulator" or row.get("is_modeled") is True:
        raise ValueError("modeled values cannot be appended as measured hardware data")
    if not row.get("board_sku") or not row.get("target") or not row.get("run_id"):
        raise ValueError("board_sku, target, and run_id are required time-series metadata")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    exists = target.exists() and target.stat().st_size > 0
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPERATURE_COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in TEMPERATURE_COLUMNS})

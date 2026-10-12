"""Derive a simulator profile from repeated raw measurements and temperature traces."""

import argparse
import csv
import hashlib
import math
import statistics
import subprocess
from pathlib import Path


class InsufficientTrials(ValueError):
    """Raw data do not contain the required number of trials per action/configuration."""


class MissingMeasurements(ValueError):
    """Raw measurements omit an input required by the simulator profile."""


def _read_csv(path: str | Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(row: dict, field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise MissingMeasurements(f"missing numeric measurement: {field}") from exc
    if not math.isfinite(value):
        raise MissingMeasurements(f"non-finite measurement: {field}")
    return value


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]


def _linear_fit(rows: list[dict]) -> dict:
    xs = [_number(row, "input_bytes") for row in rows]
    ys = [_number(row, "elapsed_us") / 1_000_000 for row in rows]
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        raise MissingMeasurements("process trials must vary input_bytes for a processing-time fit")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    return {"method": "ordinary least squares: elapsed_seconds = intercept + slope * input_bytes",
            "intercept_s": intercept, "slope_s_per_byte": slope,
            "sample_count": len(rows), "r_squared": 1.0 - sum((y - (intercept + slope * x)) ** 2
                 for x, y in zip(xs, ys)) / max(1e-30, sum((y - mean_y) ** 2 for y in ys))}


def _thermal_rates(rows: list[dict]) -> tuple[float, float, float]:
    runs: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        action = row.get("action", "").lower()
        runs.setdefault((action, row.get("run_id", "")), []).append(row)
    slopes = {"process": [], "transmit": [], "idle": [], "store": []}
    for (action, _), samples in runs.items():
        if action not in slopes:
            continue
        samples.sort(key=lambda row: _number(row, "sample_index"))
        for first, second in zip(samples, samples[1:]):
            dt = (_number(second, "t_ms") - _number(first, "t_ms")) / 1000
            if dt <= 0:
                raise MissingMeasurements("time-series samples must have increasing t_ms per run")
            delta = (_number(second, "temperature_mdc") - _number(first, "temperature_mdc")) / 1000
            slopes[action].append(delta / dt)
    for action in ("process", "transmit", "idle", "store"):
        if not slopes[action]:
            raise MissingMeasurements(f"no temperature time series for action={action}")
    heating = statistics.median([value for value in slopes["process"] if value > 0]) if any(
        value > 0 for value in slopes["process"]) else 0.0
    transmit = statistics.median([value for value in slopes["transmit"] if value > 0]) if any(
        value > 0 for value in slopes["transmit"]) else 0.0
    cooling_samples = [abs(value) for action in ("idle", "store") for value in slopes[action] if value < 0]
    if not cooling_samples:
        raise MissingMeasurements("idle/store traces contain no measured cooling")
    return heating, statistics.median(cooling_samples), transmit


def _source_commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path.parent, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable (not a git checkout)"


def measured_profile(raw_csv: str | Path, timeseries_csv: str | Path,
                     configuration: str | None = None) -> dict:
    path, series_path = Path(raw_csv), Path(timeseries_csv)
    rows = _read_csv(path)
    series = _read_csv(series_path)
    if not rows or not series:
        raise InsufficientTrials("trial and temperature time-series CSVs must both contain data rows")
    configs = {row.get("configuration", "") for row in rows}
    if configuration is None:
        if len(configs) != 1:
            raise MissingMeasurements("select --configuration when raw CSV contains multiple configurations")
        configuration = next(iter(configs))
    rows = [row for row in rows if row.get("configuration") == configuration and row.get("success", "").lower() == "true"]
    series = [row for row in series if row.get("configuration") == configuration]
    if not configuration or not rows:
        raise InsufficientTrials("selected configuration has no successful retained raw trials")
    by_action: dict[str, list[dict]] = {}
    for row in rows:
        by_action.setdefault(row.get("action", "").lower(), []).append(row)
    actions = ("idle", "process", "store", "transmit")
    if any(len(by_action.get(action, [])) < 30 for action in actions):
        raise InsufficientTrials("need at least 30 successful raw trials for each action and configuration")

    power = {}
    for action in actions:
        values = [_number(row, "avg_power_mw") for row in by_action[action]]
        power[action] = {"median_mw": statistics.median(values), "p95_mw": _p95(values),
                         "spread_mw": [min(values), max(values)], "trials": len(values)}

    fields = ("cpu_mhz", "ram_total_internal_b", "capacity_units", "throttled_capacity_fraction",
              "max_temp_mdc", "throttle_at_mdc", "energy_capacity_mj", "initial_energy_mj", "solar_power_mw")
    medians = {field: statistics.median([_number(row, field) for row in rows]) for field in fields}
    thermal = _thermal_rates(series)
    process_fit = _linear_fit(by_action["process"])
    temp_start = statistics.median([_number(row, "temp_min_mdc") for row in rows])
    throttle_fraction = medians["throttle_at_mdc"] / medians["max_temp_mdc"]
    if not 0 < throttle_fraction <= 1:
        raise MissingMeasurements("measured throttle_at_mdc/max_temp_mdc must be in (0, 1]")
    digest = hashlib.sha256(path.read_bytes() + series_path.read_bytes()).hexdigest()
    profile = {
        "profile_version": "esp32_measured_v1",
        "energy": {
            "capacity_j": medians["energy_capacity_mj"] / 1000,
            "initial_energy_j": medians["initial_energy_mj"] / 1000,
            "idle_power_w": power["idle"]["median_mw"] / 1000,
            "process_power_w": power["process"]["median_mw"] / 1000,
            "transmit_power_w": power["transmit"]["median_mw"] / 1000,
            "store_power_w": power["store"]["median_mw"] / 1000,
            "solar_power_w": medians["solar_power_mw"] / 1000,
        },
        "compute": {
            "max_frequency_hz": medians["cpu_mhz"] * 1_000_000,
            "ram_total_mb": medians["ram_total_internal_b"] / 1_000_000,
            "capacity_units": medians["capacity_units"],
            "throttled_capacity_fraction": medians["throttled_capacity_fraction"],
        },
        "thermal": {
            "temperature_c": temp_start / 1000,
            "max_temp_c": medians["max_temp_mdc"] / 1000,
            "heating_c_per_s": thermal[0], "cooling_c_per_s": thermal[1],
            "transmit_heating_c_per_s": thermal[2], "throttle_at_fraction": throttle_fraction,
        },
        "provenance": {key: "measured" for key in (
            "capacity_j", "initial_energy_j", "idle_power_w", "process_power_w", "transmit_power_w",
            "store_power_w", "solar_power_w", "max_frequency_hz", "ram_total_mb", "capacity_units",
            "throttled_capacity_fraction", "temperature_c", "max_temp_c", "heating_c_per_s",
            "cooling_c_per_s", "transmit_heating_c_per_s", "throttle_at_fraction",
        )},
        "measurement_source": {
            "raw_sha256": digest, "configuration": configuration,
            "source_commit": _source_commit(path), "trial_count": len(rows),
            "power_statistics": power, "processing_time_fit": process_fit,
            "thermal_rate_method": "median adjacent temperature/time slopes grouped by run_id and action",
        },
    }
    return profile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_csv")
    parser.add_argument("--timeseries", required=True)
    parser.add_argument("--configuration")
    parser.add_argument("--output", default="profiles/esp32_measured_v1.yaml")
    args = parser.parse_args()
    try:
        profile = measured_profile(args.raw_csv, args.timeseries, args.configuration)
    except (OSError, InsufficientTrials, MissingMeasurements) as exc:
        parser.error(str(exc))
    import yaml
    Path(args.output).write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()

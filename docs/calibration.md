# Calibrating the simulation

The checked-in energy, compute, thermal, link, and task parameters are assumptions for a software prototype. Do not describe simulation results as device or mission measurements.

The concrete Phase-3 bench protocol is documented in [`phase3_hardware_protocol.md`](phase3_hardware_protocol.md), and a LaTeX-ready manuscript section is provided in [`phase3_latex_insert.tex`](phase3_latex_insert.tex). These documents describe planned measurements only; they do not report completed hardware results.

## Collect repeatable device measurements

Measure idle, process, store, and transmit actions separately on the selected ESP32 board. Retain at least 30 successful trials per action and configuration. For each trial, record:

- board SKU, target, PSRAM, ESP-IDF version, CPU frequency, supply, and ambient temperature;
- task type, input/output bytes, and configuration;
- elapsed time, externally measured input energy, and average/peak power;
- internal/PSRAM free heap and chip temperature;
- total internal RAM, measured compute capacity, throttle capacity fraction/threshold, battery capacity/initial charge, solar input when applicable;
- action name and whether the run completed successfully.

Warm up and retain at least 30 successful trials for each action/configuration, plus all failures and throttling observations. Keep raw readings unchanged; derive statistics separately. Record serial/Wi-Fi transfer only for the transport used, and mark emulation explicitly.

`calibration_measurements.csv` is the action-trial template. `calibration_timeseries_template.csv` is a separate raw time-series format; each run records monotonically increasing `sample_index` and `t_ms`, action, chip temperature, and ambient temperature. For thermal rates, stabilize ambient temperature, then log a fixed-rate temperature series during sustained PROCESS, TRANSMIT, IDLE, and STORE. The tool fits median adjacent temperature/time slopes within runs. It fits process seconds against input bytes by ordinary least squares; coefficients are recorded as measurement metadata because per-task base times remain workload inputs. Per-action average power is summarized by median, p95, and min/max spread.

## Update model parameters

Named model profiles live in `profiles/`; scenario files select one with `model_profile` and can override profile values for scenario-specific stress cases. Profiles contain energy, compute, and thermal assumptions; scenarios contain workload and contact conditions. A future measured profile should:

1. Keep the raw measurement file and the device metadata with the experiment artifacts.
2. Add a named model profile with the source measurement file hash and derived parameter values.
3. Add the measured compute and thermal coefficients to the profile and verify that the scenario resolves to those values.
4. Keep the existing synthetic scenarios unchanged so the published `evaluation_v1` can still be reproduced.

Never overwrite frozen evaluation artifacts with new measurements. Use a new evaluation version and record the source revision, profile hash, workload seeds, and derivation method in its manifest. Generate a profile with `python -m pmars_simulation.hil.calibrate RAW.csv --timeseries TEMPERATURE.csv --configuration CONFIG --output profiles/esp32_measured_v1.yaml`. The tool refuses empty templates, fewer than 30 successful trials per action/configuration, missing model inputs, or incomplete thermal traces. Source revision is recorded as a commit hash or `unavailable (not a git checkout)`.

## Sensitivity analysis

Before hardware data is available, measure how conclusions depend on assumptions:

1. Choose one parameter family at a time (for example, process power, contact bandwidth, or task arrival rate).
2. Define a low, central, and high value from a documented plausible range. These are sensitivity values, not measurements.
3. Run every scheduler against identical workloads and seeds at each value.
4. Save each run matrix separately and compare paired per-seed differences across the parameter values.
5. Report when a scheduler ranking changes, and include cases where Predictive loses to a baseline.

The `pmars_simulation.experiments.sensitivity` runner supports one-factor sweeps for processing/transmit/solar power, contact bandwidth, task interarrival time, compute capacity, and thermal rates. It writes raw runs, confidence-interval summaries, paired Predictive comparisons, and a manifest with profile hashes. Memory and contact-schedule timing sweeps remain future extensions.

## Combined stress cases

`energy_link_stress` combines a low-energy setting with sparse, low-bandwidth, high-latency contacts. `thermal_burst_stress` combines burst arrivals with an explicitly harsher thermal profile. These are designed synthetic stress cases; they are not estimates of a particular orbit or hardware board.

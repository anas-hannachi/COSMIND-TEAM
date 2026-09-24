# Calibrating the simulation

The checked-in energy, compute, thermal, link, and task parameters are assumptions for a software prototype. Do not describe simulation results as device or mission measurements until these parameters have been calibrated.

## Collect repeatable device measurements

Use the target board (or document the closest available substitute) and profile representative task types separately. For each run, record:

- board model, OS image, software version, and ambient temperature;
- task type, input size, output size, and configuration;
- wall-clock processing time and energy consumed;
- peak resident memory and peak device temperature;
- whether the run completed successfully.

Repeat each task/configuration enough times to estimate a distribution, and record idle power separately. Keep the raw readings unchanged; derive medians and uncertainty ranges in a separate file or report. Measure radio energy and transfer throughput independently for each link mode where hardware is available.

The companion `calibration_measurements.csv` file is an empty column template. Each row should represent one measured run. Leave unavailable values blank and record the reason; do not substitute modeled values and label them as measurements.

## Update model parameters

The scenario YAML files currently configure workload generation, energy values, storage capacity, solar/eclipse timing, and contact windows. Compute and thermal model coefficients are currently defaults in Python. A calibrated profile should therefore:

1. Keep the raw measurement file and the device metadata with the experiment artifacts.
2. Add a named model profile with the source measurement file hash and derived parameter values.
3. Extend `build_simulation` to load compute and thermal coefficients from that profile before using the profile in a benchmark.
4. Keep the existing synthetic scenarios unchanged so the published `evaluation_v1` can still be reproduced.

Never overwrite the frozen `evaluation_v1` artifacts with recalibrated results. Use a new evaluation version and record the source commit, profile hash, workload seeds, and parameter derivation method in its manifest.

## Sensitivity analysis

Before hardware data is available, measure how conclusions depend on assumptions:

1. Choose one parameter family at a time (for example, process power, contact bandwidth, or task arrival rate).
2. Define a low, central, and high value from a documented plausible range. These are sensitivity values, not measurements.
3. Run every scheduler against identical workloads and seeds at each value.
4. Save each run matrix separately and compare paired per-seed differences across the parameter values.
5. Report when a scheduler ranking changes, and include cases where Predictive loses to a baseline.

The `pmars_simulation.experiments.sensitivity` runner supports one-factor sweeps for processing/transmit/solar power, contact bandwidth, and task interarrival time. It writes raw runs, confidence-interval summaries, paired Predictive comparisons, and a manifest. Compute, thermal, and memory sensitivities still require configurable model-profile support before they can be swept by that runner.

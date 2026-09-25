# Calibrating the simulation

The checked-in energy, compute, thermal, link, and task parameters are assumptions for a software prototype. Do not describe simulation results as device or mission measurements until these parameters have been calibrated.

The concrete Phase-3 bench protocol is documented in [`phase3_hardware_protocol.md`](phase3_hardware_protocol.md), and a LaTeX-ready manuscript section is provided in [`phase3_latex_insert.tex`](phase3_latex_insert.tex). These documents describe planned measurements only; they do not report completed hardware results.

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

Named model profiles live in `profiles/`; scenario files select one with `model_profile` and can override profile values for scenario-specific stress cases. Profiles contain the energy, compute, and thermal assumptions; scenarios contain workload and contact conditions. A calibrated profile should:

1. Keep the raw measurement file and the device metadata with the experiment artifacts.
2. Add a named model profile with the source measurement file hash and derived parameter values.
3. Add the measured compute and thermal coefficients to the profile and verify that the scenario resolves to those values.
4. Keep the existing synthetic scenarios unchanged so the published `evaluation_v1` can still be reproduced.

Never overwrite the frozen `evaluation_v1` artifacts with recalibrated results. Use a new evaluation version and record the source commit, profile hash, workload seeds, and parameter derivation method in its manifest.

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

# Future hardware prototype validation plan

This plan connects the simulator to a later bench prototype. It does not claim that the current parameter values match flight hardware.

## 1. Select and describe the target

Choose a representative onboard-compute board and record its exact model, memory, storage, power supply, operating system, cooling setup, and measurement equipment. Keep this device description with the raw measurements so results can be repeated on the same setup.

## 2. Profile representative workloads

For each task family, record the input, configuration, output size, wall time, energy at the board input, peak memory, and peak temperature. Include at least:

- a small telemetry transform;
- image compression at several image sizes and compression settings;
- one representative science or inference workload;
- an idle measurement for the same board and operating conditions.

Run repeated trials per configuration and retain every raw trial. Record failures and thermal throttling rather than dropping those runs. The starter columns are in [`calibration_measurements.csv`](calibration_measurements.csv).

## 3. Measure communications separately

For each intended link mode, record payload size, throughput, latency, transfer energy, and contact start/end timing. Prefer replayable measured traces or a documented link emulator over a single nominal bandwidth value. The current simulator cannot transfer a task across multiple contact windows, so log cases that exceed one window for future model work.

## 4. Create a measured profile

Create a new named profile from the measured distributions; keep the synthetic profiles intact. Record the raw-data file hash, the statistic used for each model parameter, and the profile version. When measurements vary, use distributions or conservative percentile values rather than silently substituting a single average.

## 5. Compare predictions before using the model for design choices

Replay the same workload/configuration on the board and in simulation. Compare process and transfer duration, energy, memory, temperature, and task outcomes. Report prediction error and uncertainty for each quantity, then decide and document acceptable tolerances with the project team. Recalibrate when a model change falls outside those tolerances.

## 6. Grow toward a satellite prototype

Start with a hardware-in-the-loop bench that runs the simulator's action interface against the board. Add measured contact traces and power limits, then test brownouts, missed contacts, thermal throttling, and storage exhaustion. Keep safe-state behavior and fault recovery explicit before connecting any radio or flight-like hardware.

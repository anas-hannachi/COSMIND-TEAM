# Future hardware prototype validation plan

This plan connects the simulator to a later bench prototype. It does not claim that the current parameter values match flight hardware.

## 1. Select and describe the target

Select the ESP32 target and exact board SKU, PSRAM, supply, ESP-IDF version, CPU frequency, and input-side measurement equipment. Keep this description with raw observations. Current defaults and open choices are listed in [`hardware_decisions.md`](hardware_decisions.md).

## 2. Profile representative workloads

For each task family, record input and actual output bytes, configuration, elapsed time, input energy, internal/PSRAM heap, and chip and ambient temperature. Include at least:

- a small telemetry transform;
- deterministic synthetic compression at several buffer sizes;
- one selected numeric workload (vision and inference are out of scope here);
- an idle measurement for the same board and operating conditions.

Warm up, then retain at least 30 trials per configuration. Preserve failures and software throttling. The starter columns are in [`calibration_measurements.csv`](calibration_measurements.csv).

## 3. Measure communications separately

For serial or optional Wi-Fi tests, record payload size, throughput, latency, input energy, and interval. Emulated link results remain labelled emulated. The current simulator cannot transfer a task across multiple contact windows; log such cases as a known gap.

## 4. Create a measured profile

Create a new named profile from the measured distributions; keep the synthetic profiles intact. Record the raw-data file hash, the statistic used for each model parameter, and the profile version. When measurements vary, use distributions or conservative percentile values rather than silently substituting a single average.

## 5. Compare predictions before using the model for design choices

Replay the same workload/configuration on the board and in simulation. Compare process and transfer duration, energy, memory, temperature, and task outcomes. Report prediction error and uncertainty for each quantity, then decide and document acceptable tolerances with the project team. Recalibrate when a model change falls outside those tolerances.

## 6. Grow toward a satellite prototype

Start with a hardware-in-the-loop bench that runs the simulator's action interface against the board. Add measured contact traces and power limits, then test brownouts, missed contacts, thermal throttling, and storage exhaustion. Keep safe-state behavior and fault recovery explicit before connecting any radio or flight-like hardware.

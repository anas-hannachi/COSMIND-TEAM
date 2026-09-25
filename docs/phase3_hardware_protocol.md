# Phase-3 hardware-in-the-loop protocol

This protocol defines the first hardware work for PMARS. It is a measurement plan, not a record of completed measurements. No hardware result may be added to the paper until raw runs, metadata, and derived statistics are committed.

## 1. Baseline platform

Use a Raspberry Pi 5 with 8 GB RAM as the representative compute board. Record the exact board revision, operating-system image, kernel, storage device, cooling solution, power supply, and firmware. Use the same board for all repeated trials unless a comparison study is explicitly declared.

Recommended bench equipment:

- Raspberry Pi 5 8 GB with active cooling;
- official 27 W USB-C supply or a documented laboratory supply;
- calibrated input-side power monitor capable of measuring the 5 V rail and transient current, such as an INA228/INA260-class monitor or laboratory power analyzer;
- host computer for timestamped logging;
- external ambient-temperature sensor;
- optional external thermal probe for cross-checking the board telemetry;
- network switch or controlled Wi-Fi access point for repeatable communication tests.

The input-side monitor measures board energy. Software CPU counters alone are not sufficient for an energy claim.

## 2. Workloads

Run at least these workload families:

1. telemetry transform: parse and transform a fixed synthetic telemetry record;
2. image compression: compress fixed images at documented dimensions and quality settings;
3. science or inference workload: execute one documented representative kernel or model;
4. idle: measure the board with the benchmark process waiting but the system otherwise unchanged.

For each family, test at least three input sizes or configurations. Use a warm-up phase followed by at least 30 retained trials per configuration. Record failures, throttling, thermal warnings, and outliers; do not silently discard them.

## 3. Per-trial measurements

For every trial record:

- UTC start and end time;
- device, OS, kernel, software, commit, and configuration identifiers;
- ambient temperature and humidity when available;
- task family and input/output sizes;
- wall-clock duration;
- input energy, average power, and peak power;
- peak resident memory;
- minimum, median, and peak board temperature;
- CPU frequency and throttling flags;
- success or failure and failure reason.

Keep raw samples unchanged. Derive medians, interquartile ranges, 95% intervals, and failure rates in separate generated files.

## 4. Communication measurements

Measure communication separately from compute. For each link mode and payload size, record throughput, one-way or round-trip latency, transfer energy at the board input, contact start and end timestamps, retransmissions, and failures. Start with a controlled Ethernet or Wi-Fi link emulator if no flight-like radio is available. Do not describe this as radio validation.

Record transfers that exceed one contact window because the simulator currently models transfers as single-contact operations. These cases should become future model tests rather than being silently excluded.

## 5. Simulation calibration

Create a new named measured profile only after the raw data are complete. For each calibrated parameter, record:

- raw-data file hash;
- statistic used, such as median or 95th percentile;
- unit conversion;
- uncertainty or observed spread;
- profile version;
- source commit.

Keep `synthetic_v1`, `thermal_stress_v1`, and frozen `evaluation_v2` unchanged. Use a new evaluation version for calibrated results.

## 6. Acceptance checks

Before using a measured profile for scheduling conclusions:

- repeat the same task/configuration in simulation and on the board;
- compare duration, energy, memory, temperature, output size, and task outcome;
- report median error and variation, not only one average;
- document tolerance thresholds before inspecting policy rankings;
- rerun the matched workload after calibration;
- preserve the original synthetic result as a separate baseline.

A successful bench run demonstrates model calibration for the tested workload and platform only. It does not establish spacecraft qualification, orbital validity, radiation tolerance, or flight readiness.

## 7. Required artifacts

The Phase-3 evidence bundle should contain:

- raw measurement CSV or JSONL files;
- device and instrument metadata;
- calibration scripts;
- named measured profile YAML;
- profile hash and source-data hash;
- simulation-versus-measurement comparison tables;
- uncertainty and failure summaries;
- reproducibility commands;
- a new evaluation manifest;
- updated figures clearly labeled as measured-profile results.

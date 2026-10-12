# ESP32 Phase-3 hardware measurement protocol

This is a plan for future bench work. The selected board and all thresholds remain open in
[`hardware_decisions.md`](hardware_decisions.md). Do not mix measured board data with synthetic simulator
outputs.

## Configuration and instrumentation

For each configuration, record exact board SKU/revision, ESP32 target, PSRAM size, ESP-IDF version and
commit, build flags, CPU frequency, supply voltage, USB/UART mode, workload version, and room conditions.
Measure input-side power with an identified external monitor; record model, calibration traceability,
resolution, sample rate, bandwidth, shunt, wiring, and limitations. The board does not measure its own
energy. Record ambient temperature separately from on-chip or external sensor readings. Log internal and
PSRAM free/peak heap separately, reset reason, software throttle state, failures, and dropped events.

## Trial protocol

Use a warm-up, then retain at least 30 trials per configuration. Preserve every trial, including failures,
timeouts, throttling, and outliers. Raw observations are append-only and never edited; derived summaries are
written separately with the raw file hash and analysis command. Record Wi-Fi or serial payload throughput
and latency only for the transport actually measured. An emulated link is labelled emulated.

Each observation records task/input/output bytes, elapsed microseconds, input energy mJ, average and peak
power mW, heap minima, temperature min/median/peak, reset reason, and failure reason. The empty schema is
[`calibration_measurements.csv`](calibration_measurements.csv).

## Analysis and reporting

Report medians and spread, plus p95 where useful. Keep hardware measurements, simulation metrics, and
extrapolations in separate tables. Any profile derived from measurements must be versioned separately,
record the raw-data SHA-256, selected statistic, unit conversions, spread, and source revision. Keep
`synthetic_v1`, `thermal_stress_v1`, and frozen evaluation files unchanged. The simulator currently models
transfers as one-contact atomic operations; record interrupted or multi-contact transfers as a known model
gap rather than silently simplifying those observations.

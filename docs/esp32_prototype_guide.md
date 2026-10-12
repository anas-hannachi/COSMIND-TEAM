# ESP32 prototype guide

Current evidence: Python integer policies, the native C core, and the JSONL stdio executable compile on the host. Protocol fixtures, sanitizer fuzzing, lockstep replay, task-slot reuse, and host stack-budget checks are exercised. The firmware app is wired to the same protocol and core, but no ESP-IDF build, board boot, sensor read, radio transfer, or physical workload measurement has been completed. `idf.py` is unavailable in this environment; no firmware build or boot is claimed. Values in `esp32_assumed_v1.yaml` remain assumptions.

## Stage A — Bench setup (READY)

Select the exact board/SKU and PSRAM; see [`hardware_decisions.md`](hardware_decisions.md). A USB cable is
the wiring-free starting setup. Use internal SRAM only. Install the pinned ESP-IDF release and record board,
supply, and host details before collecting any measurements.

## Stage B — Protocol and scheduler port (PARTIAL)

`pmars.contract.v1` defines integer task fields, a 96 task bound, and Python framing. The native C parser checks protocol version, sequence, CRC, message type, bounds, and several structured errors. The stdio executable and ESP32 app share the protocol handler and lifecycle core. The parser currently uses a bounded lightweight scanner rather than a general JSON implementation; schema edge cases still need broader hardening. Run host protocol tests with `pytest tests/test_protocol.py`.

The C selector workspace is engine-owned, so large task copies do not sit on the firmware call stack. CI budgets each host-x86-64 function frame at 1,024 bytes and the selected `proto_handle -> engine_step -> decide -> plan_candidates -> can_process -> earliest_transfer -> transfer_time -> contact_at` path at 3,072 bytes. The latest host report measured a maximum frame of 864 bytes and a 2,336-byte estimate for that chain (`python tools/check_stack_usage.py`). These are host estimates, not ESP32 stack measurements. The main task is configured for 6,144 bytes and protocol metadata reports FreeRTOS stack high-water words, free heap, minimum observed free heap, IDF version, target, and reset reason.

## Stage C — Scheduling demo (PARTIAL)

The HIL driver replays through the native protocol executable or pyserial and compares decisions against the simulator. Run `python -m pmars_simulation.hil.driver --loopback --scenario bench_normal --scheduler edf --seeds 100-104` (repeat with `--scheduler rule`). A PTY test covers serial framing. Autonomous real-time firmware modes are not implemented; host transmissions are emulated. **Lockstep mode is the exact, simulator-faithful path** (the host owns time and state, the board decides). **Autonomous mode is an emulation with simplified physics** (no solar/eclipse, no thermal evolution; STORE waits in 5 s quanta like the simulator) whose outcomes are only comparable to the simulator as described in `docs/engine_fidelity.md`.

## Stage D — Physical workload measurement (BLOCKED-ON-HARDWARE)

Implement/enable the bounded telemetry and deterministic compression workloads after the board is selected.
Capture elapsed time, actual output bytes, internal/PSRAM heap, external input energy, temperature, failures,
and reset reason using [`esp32_measurement_protocol.md`](esp32_measurement_protocol.md).

## Stage E — Measurement profile and comparison (BLOCKED-ON-HARDWARE)

Retain at least 30 trials per configuration, derive profiles separately from raw data, hash source files,
and compare matching task streams. Never write a measured profile from assumptions.

## Stage F — Optional AI (OUT OF SCOPE)

AI, vision, inference, camera drivers, and classifiers are out of scope. This stage is only an extension point.

## Build and monitor

```sh
cd firmware/esp32
. "$IDF_PATH/export.sh"
idf.py set-target esp32s3
idf.py build
idf.py size
idf.py -p PORT flash monitor
```

The same project may be configured for the classic target with `idf.py set-target esp32`. ESP-IDF is not
installed in the current build environment; flash, static RAM, stack, and image sizes are therefore not
reported. Do not estimate these values from a host build.

### First ten minutes

1. Confirm the board SKU and target silkscreen.
2. Connect USB and install ESP-IDF v5.3.2.
3. Run `idf.py set-target esp32s3 && idf.py build && idf.py size`; save the actual build and size output.
4. Flash and monitor with `idf.py -p PORT flash monitor`; verify a `pmars.contract.v1` request/reply exchange over the selected console.
5. Record the console type and board details in the open-decisions table.

For host comparisons, run `python -m pmars_simulation.hil.driver --loopback --scenario bench_normal --scheduler edf --seeds 100-104` and repeat with `--scheduler rule`. A physical serial replay uses `--port PORT --baud 115200` and a matching protocol endpoint. Collect raw action trials and time-series observations using [`esp32_measurement_protocol.md`](esp32_measurement_protocol.md), then derive a profile with `python -m pmars_simulation.hil.calibrate RAW.csv --timeseries TEMPERATURE.csv --configuration CONFIG --output profiles/esp32_measured_v1.yaml`. Calibration requires at least 30 successful trials per action and is blocked until those real measurements exist.

### Current Kconfig and interfaces

The scaffold exposes virtual/`esp_timer` clock and emulated/serial link choices. Temperature defaults to
emulated; on-chip is a future backend. Power monitor is external/host-side; the board cannot reliably
self-measure its own energy. No PSRAM is required. The esp32s3 default is USB Serial/JTAG; UART remains a
console option.

# Hardware team handoff - ESP32 scheduling prototype

Read this first. Everything below was verified **on a host computer only**. **ESP-IDF has never been built here, and no
ESP32 has been flashed.** Your first `idf.py build` and first boot are real firsts; budget time for toolchain fixes.

## What you are getting
| Piece | Where | Status |
|---|---|---|
| Decision logic (EDF, Rule), integer-only, portable C | `firmware/pmars_core/` | Verified: matches the original simulator at 99.7-100% of decisions (rounding edges only), 10,000+ case fuzz vs Python |
| Serial message protocol (JSONL + CRC-32, bounded, no malloc) | `firmware/esp32/components/pmars_proto/`, `firmware/host/` | Verified on host: fixtures for 12 error classes, 100k+ fuzzed lines under ASan/UBSan, no crashes |
| ESP-IDF app wiring (console -> protocol -> core) | `firmware/esp32/main/main.c` | **Compile-checked logic only; never built with ESP-IDF** |
| Host replay tool (loopback and serial) | `python -m pmars_simulation.hil.driver` | Verified loopback + PTY serial test; real serial untested |
| ESP32 bench scenarios + **assumed** profile | `scenarios/bench_*.yaml`, `profiles/esp32_assumed_v1.yaml` | All values are placeholders, tagged `assumed` |
| Calibration (raw data -> measured profile) | `pmars_simulation/hil/calibrate.py` | Refuses < 30 trials per action; tested with synthetic data only |

## First hour
1. `pip install -r requirements-dev.txt && python -m pytest` (expect all green).
2. Install ESP-IDF **5.3.2**, then `cd firmware/esp32 && idf.py set-target esp32s3 && idf.py build` (also try `esp32`).
   If the build fails, fix it and tell us what changed. Report which exact board/SKU and PSRAM you have
   (see `docs/hardware_decisions.md`, all items OPEN).
3. Flash, open the monitor, run `python tools/send_hello.py --port <PORT>` (add `--baud` if you changed it); `hello_ack` returns target, IDF version, reset
   reason, free heap and stack high-water mark. **Record the stack high-water mark** - the 6,144-byte main stack is sized from
   host estimates (max frame 864 B), not from ESP32 measurements.
4. Replay: `python -m pmars_simulation.hil.driver --port <PORT> --baud 115200 --scenario bench_normal --scheduler edf --seeds 100-104`.

## Things to watch (known risks, unverified on hardware)
- Console idle loop sleeps one tick (`vTaskDelay(1)`); if you still see task-watchdog resets, raise `CONFIG_FREERTOS_HZ` or the delay.
- Static engine memory is ~16.6 KB; whole firmware is designed to fit internal SRAM (PSRAM optional).
- Temperature source defaults to **emulated**; the on-chip sensor is supported on ESP32-S3 (verify the driver for your target).
  Energy cannot be self-measured by the board; use an external power monitor and log it on the host.
- Transmission is **emulated** (serial); do not describe it as a radio link.

## Two modes - know which one you are using
- **Lockstep** (host sends state, board decides): exact, simulator-faithful. Use this for decision-parity evidence (Stage B/C).
- **Autonomous** (board keeps its own virtual clock/queue): an emulation with simplified physics (no solar/eclipse, no thermal
  evolution). Delivered-task outcomes match the simulator in 3 of 4 bench scenarios and differ by 4% in `bench_burst`
  (see `docs/engine_fidelity.md`). **Do not present autonomous results as simulator-equivalent.**

## Your deliverables (see `docs/esp32_prototype_guide.md`, stages A-E)
- A: board inventory, toolchain versions, boot log.  B: matching decisions on identical inputs, error handling.
- C: a recorded PROCESS -> STORE -> TRANSMIT -> completed lifecycle trace.
- D: **raw** measurements, >= 30 retained trials per action/config, failures and throttling kept, nothing edited
  (`docs/esp32_measurement_protocol.md`, `docs/calibration_measurements.csv`, `docs/calibration_timeseries_template.csv`).
- E: run `hil/calibrate.py` on the raw data -> `profiles/esp32_measured_v1.yaml` (never hand-edit it).
  Never label a modelled number as measured.

## Do not claim
"flight-ready", "radiation-tested", "validated radio link", "calibrated" (before step E), or that autonomous mode equals the simulator.
Safe wording: *"We have reproducible scheduling simulations and a concrete ESP32 hardware-in-the-loop plan. The current results are
synthetic; the next phase ports the scheduler and measures real board behavior."*

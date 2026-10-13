# PMARS Phase-2 Scheduler Prototype

**A reproducible satellite task-scheduling simulator with an ESP32-S3 software prototype path.**

PMARS explores how an onboard scheduler can choose **PROCESS**, **STORE**, and **TRANSMIT** actions for time-sensitive satellite tasks. This repository is a research prototype for IASTAM Track 1 / Problem 1. The discrete-event simulator is not flight software, and its modeled energy, storage, compute, thermal, radio, and workload values are assumptions rather than board measurements.

> **Current evidence:** reproducible scheduling simulations and firmware scaffolding are available. No ESP32 firmware boot, radio behavior, power, or temperature measurements are claimed. The next phase is to run the scheduler on the selected board and measure its behavior.

## What is in the repository

- A SimPy virtual-time satellite environment with finite battery, solar and eclipse cycles, storage and compute limits, thermal evolution, changing contact windows, deadlines, and freshness decay.
- An outcome-complete task ledger: each generated task ends as timely delivery, late delivery, expiry, admission rejection, unfinished, or failed.
- Six reproducible policies: seeded feasible random, transparent rule, immediate-utility greedy, feasibility-aware EDF, contact-batch knapsack, and bounded one-step predictive heuristic.
- Seven deterministic synthetic scenarios, including combined energy/link stress and thermal burst stress.
- Versioned physical-model profiles whose hashes are recorded in experiment manifests.
- Matched-seed experiment and sensitivity runners that export run metrics, per-task outcomes, summaries, paired comparisons, figures, workloads, and lifecycle traces.
- A portable C candidate selector, integer task contract, pure EDF/Rule policy modules, host tests, and ESP-IDF firmware scaffolding for an ESP32-S3 target.

### Scheduler scope

The Predictive policy is a bounded heuristic. It scores routes it can project as deadline-feasible: direct downlink, processing followed by a feasible downlink, or storage until a feasible downlink. It does not guarantee a global optimum or reserve future capacity. The `contact_knapsack` implementation in `evaluation_v2` had a capacity-reconstruction defect; commit `24b8649` repaired it and added counterexample tests. Use the corrected `evaluation_v3` evidence. Neither policy is a global mission optimizer.

## Quick start: simulator

Use Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m ruff check --select F pmars_simulation tests
python -m pytest
```

PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m ruff check --select F pmars_simulation tests
python -m pytest
```

GitHub Actions runs the regression suite on Python 3.11 and 3.12. The tests cover lifecycle accounting, resource limits, deterministic workloads, scheduler selection, profile resolution, sensitivity sweeps, and trace generation.

## Reproduce the corrected evaluation

The runner requires a clean, committed source tree so its manifest can identify the exact revision. From the repository root, run:

```bash
python -m pmars_simulation.experiments.runner \
  --seed-start 100 --seeds 20 \
  --output results/evaluation_v3 \
  --evaluation-version evaluation_v3
```

This executes 7 scenarios × 6 policies × 20 common workload seeds (840 simulations). Development/tuning seeds are 0–9. Each scheduler receives identical generated tasks for a given scenario and seed.

The output includes aggregate runs, compressed task outcomes, workload files and hashes, confidence intervals, paired comparisons, SVG figures, a simulator-generated lifecycle trace, and a manifest with source revision, package versions, scenario hashes, seed protocol, and model-profile hashes. See [the corrected evaluation summary](docs/results_summary_v3.md) for results and interpretation limits. Older evidence remains under `results/evaluation_v1/` and `results/evaluation_v2/`.

## Sensitivity analysis

After committing source changes, the default sweep evaluates processing-power multipliers of 75%, 100%, and 125% across the original scenarios and schedulers, using 20 seeds per scenario and multiplier:

```bash
python -m pmars_simulation.experiments.sensitivity --output results/sensitivity
```

Use `--parameters`, `--scenarios`, `--seed-start`, `--seeds`, and `--multipliers` to customize a sweep. Supported assumptions include power, contact bandwidth and duration, task interarrival, deadline tightness, initial energy, storage, compute capacity, and thermal rates. Multipliers are sensitivity assumptions, not measurements. The focused one-seed screening results in [the sensitivity summary](docs/sensitivity_v3_summary.md) are directional, not multi-seed inferential evidence.

## ESP32-S3 prototype

The firmware directory contains a portable scheduler core, protocol and task-contract code, host-side test scaffolding, and ESP-IDF project scaffolding. Follow the [ESP32 prototype guide](docs/esp32_prototype_guide.md) for build setup and the [measurement protocol](docs/esp32_measurement_protocol.md) before collecting board data. ESP32-S3 is the current target; confirm the exact SKU and available memory before bench work.

The simulator remains synthetic. Do not interpret its energy, timing, thermal, or radio outputs as ESP32 measurements or radio validation. See [calibration guidance](docs/calibration.md) for the measurement plan and data templates.

## Project map

| Path | Contents |
| --- | --- |
| `pmars_simulation/core/` | Task lifecycle and discrete-event simulation loop |
| `pmars_simulation/environment/` | Energy, compute, thermal, storage, and radio models |
| `pmars_simulation/schedulers/` | Six scheduling policies |
| `firmware/` | Portable C scheduler, host scaffolding, and ESP-IDF project |
| `contract/` | Task and protocol schemas, limits, and fixtures |
| `scenarios/`, `profiles/` | Synthetic mission scenarios and named model assumptions |
| `tests/` | Simulator and scheduler regression tests |
| `results/` | Versioned evaluations and generated evidence |
| `docs/` | Calibration, evaluation, demonstration, and hardware guides |

## Metrics and interpretation

The primary metric is **timely mission-value retention**:

```text
sum(nominal mission value of tasks delivered by their deadline)
---------------------------------------------------------------
sum(nominal mission value of all generated tasks)
```

Secondary metrics include timely task and critical-task completion, terminal outcomes, latency, modeled gross energy, battery extrema, contact and storage use, processing duty cycle, and temperature. Freshness-adjusted value is a sensitivity metric because its decay parameters are synthetic. Interpret paired comparisons with their confidence intervals and report scenarios where Predictive does not win; a positive mean alone is insufficient evidence.

## Known limitations and next steps

- Measure power, compute time, compression, memory, and thermal behavior on the selected ESP32 board.
- Replace synthetic contacts and workloads with mission data or a documented channel/orbit model.
- Extend the heuristic with multi-satellite contacts, preemption, shared-link reservations, and formal optimization baselines.
- Profile real compression or inference workloads on hardware before making device-level efficiency claims.

**Accurate project summary:** “We have reproducible scheduling simulations and a concrete ESP32 hardware-in-the-loop plan. The current results are synthetic; our next phase ports the scheduler and measures real board behavior.”

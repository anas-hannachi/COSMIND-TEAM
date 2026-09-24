# PMARS Phase-2 scheduler prototype

This repository is a reproducible, discrete-event software prototype for the IASTAM Track 1 / Problem 1 research phase: scheduling onboard **PROCESS**, **STORE**, and **TRANSMIT** actions for time-sensitive satellite tasks.

It is a simulator, not a flight implementation and not a Raspberry Pi measurement study. Its energy, storage, CPU, thermal, link, and workload values are explicit modeling assumptions that should be calibrated in later hardware-in-the-loop work.

## What the project implements

- A SimPy virtual-time satellite environment with finite battery, solar/eclipse cycles, storage, RAM/compute eligibility, thermal evolution, time-varying contact windows, deadlines, and freshness decay.
- An outcome-complete task ledger. Every generated task ends in exactly one state: timely delivery, late delivery, expiry, rejection at admission, unfinished, or failed.
- Four reproducible policies: seeded feasible `random`, transparent `rule`, immediate-utility `greedy`, and a bounded one-step-rollout `predictive` heuristic.
- Five deterministic synthetic scenarios: `normal`, `low_energy`, `poor_link`, `task_burst`, and `critical`.
- A matched-seed experiment runner that exports workload manifests, per-run metrics, per-task outcomes, summaries, paired comparisons, SVG figures, and a simulator-generated lifecycle trace.

The Predictive policy is deliberately described as a heuristic. It scores only routes it can project as deadline-feasible (raw downlink now, process then a feasible downlink, or store until a feasible downlink); it does not claim global optimization or capacity reservation.

## Quick start

Use Python 3.11 or newer. Create and activate a virtual environment, then install the development dependencies.

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m ruff check --select F pmars_simulation tests
python -m pytest
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m ruff check --select F pmars_simulation tests
python -m pytest
```

GitHub Actions runs this regression suite on Python 3.11 and 3.12 for pushes to `main` and pull requests.
The same workflow checks for undefined names and unused imports with Ruff before running the tests.

## Project map

- `pmars_simulation/core/` - task lifecycle and the discrete-event simulation loop;
- `pmars_simulation/environment/` - energy, compute, thermal, storage, and radio models;
- `pmars_simulation/schedulers/` - Random, Rule, Greedy, and Predictive policies;
- `scenarios/` - five synthetic mission configurations;
- `tests/` - lifecycle, feasibility, determinism, and resource-bound regression tests;
- `results/evaluation_v1/` - reproducible evaluation inputs, summaries, and generated evidence.

The regression suite covers rejected arrivals, storage release on expiry, late-delivery accounting, terminal-outcome partitioning, resource bounds, deterministic workloads and policies, predictive-route feasibility, and trace generation.

## Reproduce the held-out evaluation

Commit the source first. The runner intentionally refuses a dirty source tree so every artifact identifies an exact commit.

```bash
python -m pmars_simulation.experiments.runner --seed-start 100 --seeds 20 --output results/evaluation_v1 --evaluation-version evaluation_v1
```

This runs 5 scenarios x 4 policies x 20 common workload seeds = 400 simulations. Development/tuning seeds are 0-9; the checked-in evaluation uses held-out seeds 100-119.

The output directory contains:

- `raw_runs.csv` - one aggregate metric row per scenario/policy/seed;
- `task_outcomes.csv` - one terminal audit row per generated task;
- `workloads/` and `workload_manifest.csv` - the exact matched workloads and SHA-256 hashes;
- `summaries/` - mean/95% t-interval summaries and paired Predictive-vs-baseline differences;
- `figures/` - SVG plots generated from the raw runs;
- `trace/` - one deterministic arrival -> decision -> process/transmit -> outcome example from real simulator events;
- `manifest.json` - source commit, package versions, scenario hashes, seed protocol, and run metadata.

## Sensitivity analysis

After committing source changes, use the one-factor-at-a-time runner to check whether results depend on modeled assumptions. The default sweep scales processing power to 75%, 100%, and 125% of its configured value across all scenarios and schedulers, using 20 seeds for each scenario and multiplier. Every scheduler receives the same generated workload for a given scenario, parameter, multiplier, and seed:

```bash
python -m pmars_simulation.experiments.sensitivity --output results/sensitivity_v1
```

Choose other parameters, scenarios, seed ranges, or multipliers with `--parameters`, `--scenarios`, `--seed-start`, `--seeds`, and `--multipliers`. Supported parameters are `process_power_w`, `transmit_power_w`, `solar_power_w`, `contact_bandwidth`, and `interarrival_s`. The output includes per-run metrics, summary confidence intervals, paired Predictive-versus-baseline comparisons, and a manifest with hashes. Multipliers are sensitivity assumptions, not measured physical values. See [`docs/calibration.md`](docs/calibration.md) before interpreting or replacing them with hardware measurements.

## Metrics and interpretation

The primary metric is **timely mission-value retention**:

```text
sum(nominal mission value of tasks delivered by their deadline)
-------------------------------------------------------------
sum(nominal mission value of all generated tasks)
```

Secondary metrics include timely task/critical-task completion, late/expired/rejected outcomes, latency, modeled gross energy, battery extrema, contact use, storage use, processing duty cycle, and temperature. Freshness-adjusted value is reported only as a sensitivity metric because its decay parameters are synthetic.

For each scenario and workload seed, every scheduler receives exactly the same generated tasks. Predictive comparisons with Greedy and Rule are paired by workload seed. A positive mean alone is not a result: interpret the paired 95% interval and include scenarios where Predictive does not win.

## Known scope and future work

- Calibrate power, compute time, compression, memory, and thermal parameters with a Raspberry Pi or representative onboard-compute platform.
- Replace synthetic contacts/workloads with mission data or a validated channel/orbit model.
- Extend the heuristic to multi-satellite contacts, preemption, shared-link reservations, and formal optimization baselines.
- Add hardware-in-the-loop workload profiling (for example, real compression or inference latency/energy) before claiming device-level efficiency.
- See [`docs/calibration.md`](docs/calibration.md) for a measurement protocol and a template for collecting hardware data.

# Paper evidence summary: evaluation_v1

This file is a concise guide to the checked-in held-out evaluation artifacts. All values below were calculated from `raw_runs.csv`; full-precision source values are in `summaries/`.

## Protocol

- Frozen simulator commit: `e6ac49de98e5173d09bd6655febf86ba4733a85d`
- Evaluation matrix: 5 scenarios x 4 schedulers x 20 held-out common workload seeds (100-119) = 400 runs.
- Primary metric: timely mission-value retention = nominal value of tasks delivered by their deadline / nominal value of all generated tasks.
- Uncertainty: two-sided 95% paired Student-t intervals for Predictive minus the named baseline, matched by scenario and workload seed.
- Deadline drain: arrivals stop at the 3,600 s mission horizon; execution drains through the latest generated deadline.

## Integrity checks

- 400 unique run rows and 142,496 task-outcome rows were exported.
- Every run satisfies `generated == timely + late + expired + rejected + unfinished + failed`.
- No run has unfinished tasks, failed tasks, or failed actions.
- Every scheduler saw the same workload SHA-256 for each scenario/seed pair; there were zero cross-policy hash mismatches.

## Primary held-out result

Numbers are mean timely value retention in percent +/- 95% t interval across 20 held-out seeds. The final two columns are paired Predictive differences in percentage points, with 95% paired intervals.

| Scenario | Predictive | Greedy | Rule | Predictive - Greedy | Predictive - Rule |
|---|---:|---:|---:|---:|---:|
| critical | 4.719 +/- 0.264 | 4.284 +/- 0.246 | 5.741 +/- 0.295 | +0.434 [0.240, 0.629] | -1.022 [-1.334, -0.710] |
| low_energy | 0.516 +/- 0.137 | 0.065 +/- 0.058 | 0.096 +/- 0.081 | +0.451 [0.320, 0.582] | +0.420 [0.284, 0.556] |
| normal | 9.247 +/- 0.301 | 8.934 +/- 0.450 | 13.408 +/- 0.707 | +0.313 [0.060, 0.566] | -4.161 [-4.821, -3.501] |
| poor_link | 0.370 +/- 0.066 | 0.375 +/- 0.067 | 0.368 +/- 0.065 | -0.005 [-0.008, -0.001] | +0.002 [-0.008, 0.012] |
| task_burst | 2.610 +/- 0.073 | 1.427 +/- 0.080 | 2.626 +/- 0.077 | +1.183 [1.084, 1.282] | -0.016 [-0.129, 0.097] |

Interpretation:

- Predictive has clear primary-metric wins over both Greedy and Rule in `low_energy`, and a clear win over Greedy in `task_burst`, `critical`, and `normal`.
- Predictive does not dominate: Rule is clearly better in `normal` and `critical`; Greedy is marginally better in `poor_link`; and Predictive versus Rule is inconclusive in `poor_link` and `task_burst` on the primary metric.
- These are synthetic scenario results for this simulator. They are not hardware, orbital, or flight-performance claims.

## Useful secondary trade-off evidence

In `task_burst`, Predictive retained statistically indistinguishable primary value versus Rule (-0.016 percentage points, paired 95% interval [-0.129, 0.097]) while using 16,613 J less modeled action energy on average (paired 95% interval [-17,454, -15,772]) and reducing mean timely-delivery latency by 130.4 s (paired 95% interval [-134.3, -126.6]). Its mean gross modeled energy was 93,942 J, versus 110,554 J for Rule.

In `low_energy`, Predictive produced the strongest primary result but had longer mean timely latency (173.4 s) than Greedy (57.6 s) and Rule (92.7 s). This should be described as a value-latency trade-off, not an unqualified win.

## Trace and figures

- `trace/trace_demo.md`, `trace/trace_demo.csv`, and `trace/trace_demo.svg` provide a deterministic live example from `normal`, Predictive, seed 100: admission -> processing -> stored waiting -> transmission -> timely completion.
- `figures/timely_value_retention.svg` and `figures/timely_task_completion.svg` show means, seed dots, and 95% t intervals.
- `figures/terminal_outcomes.svg` shows terminal-outcome fractions over all generated tasks.
- `figures/value_energy_tradeoff.svg` shows mean modeled energy versus the primary value metric.

## Limits and future work

The simulator deliberately uses synthetic workload, link, energy, compute, and freshness parameters. It has no Raspberry Pi measurement, real compression/inference profile, calibrated orbit/contact trace, multi-satellite coordination, preemption, or shared-link reservation. Future work should profile representative compression/inference workloads on a Raspberry Pi or equivalent onboard computer; calibrate energy, compute, memory, and thermal models; replace synthetic contacts with validated orbit/link traces; and evaluate multi-satellite, preemptive, and optimization-based policies.

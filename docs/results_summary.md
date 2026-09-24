# Evaluation v2 summary

The checked-in `results/evaluation_v2/` artifact contains 840 matched runs: seven synthetic scenarios, six schedulers, and the same 20 workload seeds (100–119) per scenario. It records 344,970 task outcomes. The manifest identifies source commit `667714aabcae2ea3447816f9622cbbbc6c5bbc33`, a clean source tree, dependency versions, scenario/profile hashes, and the seed protocol. `task_outcomes.csv.gz` is a gzip-compressed CSV; decompress it with `gzip -dk task_outcomes.csv.gz` to inspect individual task lifecycles.

## Timely mission-value retention

Values below are the mean across 20 seeds for the best-performing policy in each scenario. The summaries directory contains all policy means and 95% t-intervals. The paired-comparison file reports Predictive-versus-baseline intervals; these are nominal intervals and are not adjusted for multiple comparisons.

| Scenario | Highest mean | Retention |
| --- | --- | ---: |
| `critical` | Rule | 5.74% |
| `energy_link_stress` | Rule | 0.43% |
| `low_energy` | Predictive | 0.52% |
| `normal` | Rule | 13.41% |
| `poor_link` | EDF | 0.38% |
| `task_burst` | Contact knapsack | 2.77% |
| `thermal_burst_stress` | Contact knapsack | 2.59% |

The simple Rule policy has the highest macro-average scenario mean (3.59%), followed by EDF (3.15%), Contact knapsack (3.04%), Predictive (2.88%), Greedy (2.38%), and Random (2.07%). The macro-average weights each scenario equally. These low absolute retention rates show that the modeled workloads are demanding and the schedulers still leave substantial nominal value undelivered on time. They do not support a claim that Predictive is the overall winner.

The strongest evidence for the new reference policies is scenario-specific: contact knapsack leads in both burst scenarios, EDF leads in the poor-link case, and Predictive leads in low energy. No one policy leads every scenario. The energy/link case remains a near-floor stress test; the thermal burst profile reaches the configured 60 °C model ceiling, so its throttling behavior is exercised.

## Interpretation

These are simulator results under explicitly synthetic coefficients and generated workloads. They are useful for regression, policy comparison, and identifying failure modes. They are not evidence of satellite performance or calibrated energy, thermal, radio, or compute behavior.

The next research improvement should target the Predictive policy’s cross-scenario objective and state projection. It trails Rule by about 4.16 percentage points in the normal scenario and does not lead the aggregate comparison. Add targeted tests for resource contention and contact horizons, then compare changes on new held-out seeds while keeping this artifact frozen. Hardware-in-the-loop calibration can follow when the physical prototype exists.

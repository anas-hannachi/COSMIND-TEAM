# Evaluation v3 summary

`results/evaluation_v3/` is the corrected full evaluation generated from source commit `24b8649`. It contains 7 scenarios x 6 policies x 20 matched seeds = 840 runs, the complete terminal ledger, paired comparisons, summaries, figures, profile copies, workload hashes, and a simulator-generated lifecycle trace.

## Corrected macro-averages

| Policy | Timely mission-value retention (%) |
| --- | ---: |
| Rule | 3.591 |
| Contact Knapsack | 3.501 |
| EDF | 3.152 |
| Predictive | 2.878 |
| Greedy | 2.376 |
| Random | 2.069 |

The corrected Contact Knapsack mean increases from the historical evaluation_v2 value of 3.045% to 3.501%. The other macro-averages are unchanged at the displayed precision. This is a corrected simulator comparison, not hardware or spacecraft validation.

The v3 terminal ledger contains 27,737 completed outcomes, 303,590 expiries, and 13,643 admission rejections, totaling 344,970 outcomes. No unfinished or failed terminal outcomes are present in the exported ledger.

## Interpretation

Rule remains the highest observed macro-average. Corrected Contact Knapsack is second in the macro-average, but policy performance remains regime-dependent. Predictive retains its clearest observed advantage in low energy, and EDF remains competitive in communication-constrained conditions. The corrected baseline should be compared using v3 results, not the provisional historical CK* observations from evaluation_v2.

All coefficients, workloads, contacts, thermal behavior, and mission values remain synthetic assumptions. The v3 result does not establish hardware or spacecraft performance.

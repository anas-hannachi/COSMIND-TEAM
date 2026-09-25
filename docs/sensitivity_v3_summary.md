# Sensitivity screening v3

This exploratory one-factor screening study was generated from source commit `044701d81fe1c7e816d83581e907424106a40657`.

It covers four representative scenarios (`normal`, `low_energy`, `poor_link`, and `task_burst`), six schedulers, six parameters, three multipliers (0.75, 1.00, 1.25), and one matched workload seed (100), for 432 scheduler runs. The single-seed design is screening evidence, not a replacement for multi-seed confidence intervals.

## Mean timely-value retention across screening rows

| Parameter | 0.75x | 1.00x | 1.25x |
| --- | ---: | ---: | ---: |
| Available initial energy | 3.106% | 3.103% | 3.119% |
| Contact bandwidth | 2.328% | 3.103% | 3.917% |
| Contact-window duration | 2.427% | 3.103% | 3.616% |
| Interarrival time | 2.458% | 3.103% | 3.925% |
| Deadline range | 3.087% | 3.103% | 3.203% |
| Storage capacity | 3.116% | 3.103% | 3.095% |

The screening result suggests that communication opportunity and arrival pressure have larger effects on absolute retention than the tested energy or storage multipliers. This is directional evidence only because each condition uses one workload seed and the factors are varied independently.

The complete raw runs, summaries, paired comparisons, and manifest are in `results/sensitivity_v3/`. Multipliers are modeled sensitivity assumptions, not hardware measurements.

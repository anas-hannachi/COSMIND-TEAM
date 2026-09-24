# PMARS reproducible evaluation artifact

- Evaluation version: `evaluation_v1`
- Frozen source commit: `e6ac49de98e5173d09bd6655febf86ba4733a85d`
- Source tree clean: `True`
- Workload seeds: `100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119`
- Matrix: every listed scheduler receives the identical generated workload for each scenario/seed pair.

## Files

- `raw_runs.csv`: one aggregate row per scenario, scheduler, and workload seed.
- `task_outcomes.csv`: one terminal-lifecycle audit row per generated task.
- `workload_manifest.csv` and `workloads/`: fixed task inputs and SHA-256 hashes.
- `summaries/`: mean/95% t-interval summaries and matched-seed Predictive comparisons.
- `figures/`: SVG figures generated from `raw_runs.csv`.
- `trace/`: a deterministic illustrative lifecycle trace generated from simulator events.

The primary metric is `timely_value_retention`: nominal mission value of tasks delivered by their deadline divided by nominal value of all generated tasks. Freshness-adjusted value is a secondary sensitivity metric. All physical coefficients are modeled assumptions, not hardware measurements.

# PMARS demonstration

The repository's deterministic trace is the recommended jury demonstration. It uses the simulator event log rather than a hand-written example.

## Reproduce the trace

```powershell
.\.venv\Scripts\python.exe -m pmars_simulation.experiments.trace --scenario normal --scheduler predictive --seed 100 --output results\demonstration
```

The command writes:

- `trace_demo.csv`: exact event rows, including time, task, action, rationale, payload, deadline slack, energy, storage, contact state, bandwidth, and queue state;
- `trace_demo.svg`: a compact PROCESS/STORE/TRANSMIT lifecycle timeline;
- `trace_demo.md`: a human-readable summary;
- `trace_manifest.json`: task identity, workload hash, deadlines, timestamps, and terminal status.

## Jury walkthrough

Show one satellite state at a decision point with:

- battery energy and minimum battery;
- occupied and total storage;
- temperature and thermal-throttling state;
- current contact availability;
- remaining contact time and bandwidth;
- queue length and task deadlines;
- selected action and scheduler rationale.

Then follow the task through PROCESS, any STORE wait cycles, TRANSMIT, and timely completion. Explain that the trace is illustrative simulator evidence, not aggregate performance evidence or hardware measurement.

## Interpretation

The trace demonstrates the decision interface and lifecycle accounting. It does not establish that Predictive is globally superior. Aggregate conclusions come only from the frozen or explicitly versioned evaluation artifacts.

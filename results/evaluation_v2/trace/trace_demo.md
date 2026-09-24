# Illustrative execution trace

This is a deterministic, simulator-generated lifecycle example. It is not an aggregate performance result.

- Scenario / policy / seed: `normal` / `predictive` / `100`
- Task: `100-1` (telemetry)
- Arrival: 30.440 s; deadline: 369.294 s
- Terminal outcome: `completed` at 105.576 s
- Observed lifecycle: `admitted -> process_started -> processed -> stored (14 wait cycles) -> transmit_started -> transmitted -> completed`
- Intermediate STORE wait cycles: 14 (compacted only in the SVG/line above)

`trace_demo.csv` contains the exact timestamp, action, policy rationale, payload, deadline slack, energy, storage, link state, and task-state fields recorded by the simulator.

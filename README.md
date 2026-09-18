# PMARS — Phase 2 Software Simulation

Discrete-event satellite digital twin for evaluating PROCESS, STORE, and TRANSMIT scheduling under energy, compute, thermal, storage, communication, deadline, and freshness constraints.

All energy, compute, and link coefficients are **simulation assumptions**, not Raspberry Pi measurements. Phase 3 should replace selected assumptions with hardware profiling.

## Run

```bash
python -m pip install -r requirements.txt
pytest
python -m pmars_simulation.experiments.runner --seeds 10 --output results
```

Generate figures after results exist:

```bash
python -c "from pmars_simulation.analysis.plots import generate; generate()"
```

Scenarios use identical generated workload streams for every scheduler when scenario and seed match. The four schedulers are `random`, `rule`, `greedy`, and `predictive`.

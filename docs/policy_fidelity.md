# Policy fidelity ledger

The permanent bound-cost command is `python tools/bound_cost.py`. It compares Python EDF and Rule policies at every decision against the unmodified original float simulator, with no filtering or monkeypatching of the original. For seeds 200–203 it reported zero mismatches in `bench_normal`, `bench_burst`, `bench_low_energy`, and `bench_poor_link`; maximum observed pending counts were 7, 19, 11, and 9. It also reported zero mismatches for `task_burst`, `energy_link_stress`, and `thermal_burst_stress`, whose maximum pending counts were 72, 59, and 71. Thus those exercised streams stayed below the shared 96 task bound; the observed bound cost was 0% in these runs. This is finite workload evidence, not a general proof.

The shared contract limit is 96 tasks. If a stream exceeds it, the policy retains the 96 earliest-deadline candidates, with priority/value/id tie-breaking. The original simulator remains unbounded. `tools/equivalence_check.py` filters the reference feasibility pairs to that same bounded candidate set; it is explicitly a secondary bounded-reference check and must not be cited as bound-cost evidence.

Run `python tools/equivalence_check.py --seeds 300-303` for that secondary check. No hardware behavior or measured energy profile is established by the host comparisons. Float-to-integer edge behavior outside the exercised workloads remains uncharacterized.

The fresh secondary bounded-reference run on seeds 300–303 produced one EDF mismatch in `task_burst` (1/4,849 decisions, 99.979% agreement); all other scenario/policy pairs in that run had zero mismatches. This is distinct from the zero-mismatch bound-cost measurement above and remains classified as unclassified by the harness.

## Agreement is 99.7-100%, not exactly 100%

Policy-level agreement with the original float simulator depends on the seed set. Examples measured at Round 6: on
`bench_burst` seeds 400-402 the C core and the Python integer reference agree with each other and both differ from the
simulator in 2 of 658 decisions per policy (a task with ~10 s of slack near a contact boundary, where conservative integer
rounding changes feasibility by under 1 ms); on `low_energy` seeds 500-501, 1 of ~1,935 decisions. Treat "99.7-100%
depending on seeds" as the accurate figure; it is the enumerated integer-rounding class, not a logic difference.
Every other scenario/policy pair on the exercised seeds (including 500-501 for all 7 original and 4 bench scenarios)
had zero mismatches.

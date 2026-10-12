# Native engine outcome comparison

**Scope.** This compares the C lifecycle engine (autonomous mode) with the original float simulator. The exact,
simulator-faithful path is **lockstep mode**, where the host sends the state and the board only decides; that path is
verified separately (see `docs/policy_fidelity.md`). Autonomous mode is an **emulation with simplified physics**.

**Command.** `PYTHONPATH=. python tools/engine_parity_interleaved.py` (bench scenarios, seeds 100-104, EDF and Rule,
through the JSONL protocol). The harness mirrors the simulator's stepping: a task is submitted when engine time reaches
its `created_ms`, the engine runs until it idles before the next arrival, and idle jumps are capped at
min(5 s, next arrival) as in `Simulation._idle_duration`. `tools/engine_parity.py` (older) gave the engine one action per
arrival and ran it only after all tasks were submitted, so most deadlines had already passed; its ~52% difference figure
measured that harness, not the engine, and is superseded.

**Result (Round 6, host run, 40 cases).**

| Scenario | Tasks | Status labels differing | Delivered-task disagreement | Timely-completed count equal |
|---|---|---|---|---|
| bench_normal | 426 | 14 (3.3%) | 0 (0.0%) | 10/10 |
| bench_poor_link | 426 | 32 (7.5%) | 0 (0.0%) | 10/10 |
| bench_low_energy | 426 | 334 (78.4%) | 0 (0.0%) | 10/10 |
| bench_burst | 1,502 | 117 (7.8%) | 60 (4.0%) | 1/10 |

"Delivered-task disagreement" counts tasks that one side completed and the other did not. Most label differences are
different failure labels for tasks neither side delivered (simulator `expired` vs engine `rejected` 174, `failed` 158,
`unfinished` 34 in the low-volume scenarios).

**Known causes of remaining differences.**
1. The engine has no solar recharge, eclipse schedule, battery capacity cap, or continuous idle drain; energy only
   decreases. This is why `bench_low_energy` labels differ (the engine marks all pending work `failed` when a STORE wait
   cannot be paid; the simulator lets tasks run to `expired`).
2. Admission storage is checked in integer resident bytes at `task_submit`, which differs in timing from the simulator's
   arrival-time check. This is the source of the `bench_burst` delivered-task disagreements (`rejected`/`completed` swaps).
3. No thermal evolution or throttle in the engine; freshness decay is not modelled (it does not affect EDF/Rule decisions).

**Fixed this round.** The engine's STORE now lasts `min(5 s, task deadline - now)`, matching `simulation.py`; it
previously jumped to the next contact or up to `store_horizon_ms`, skipping arrivals. On the same corrected harness and the same seeds (100-102), this reduced `bench_burst` label
differences from 14.0% to 6.8% and `bench_poor_link` from 9.4% to 6.2%; `bench_normal` (3.1%) and `bench_low_energy` (80.5%) were
unchanged. The table above uses seeds 100-104 after the fix.

**Do not claim** that autonomous mode reproduces simulator outcomes. Claim only: decisions are identical in lockstep
mode; autonomous mode matches delivered-task outcomes in three of four bench scenarios and is a documented emulation.

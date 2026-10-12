"""Secondary bounded-reference EDF/Rule comparison against the float scheduler."""

import sys
from collections import Counter

from pmars_simulation.contract.from_sim import contract_state as _contract_state
from pmars_simulation.contract.from_sim import contract_task as _contract_task
from pmars_simulation.contract.models import ContractConfig
from pmars_simulation.policy import edf, rule
from pmars_simulation.policy.core import bounded_tasks
from pmars_simulation.scenarios import SCENARIO_NAMES, build_simulation, generate_tasks, load_config


POLICIES = {"edf": edf.decide, "rule": rule.decide}


def run_case(scenario, seed, scheduler_name):
    config = load_config(scenario)
    tasks = generate_tasks(config, seed)
    sim = build_simulation(scenario, scheduler_name, seed, tasks=tasks)
    original_decide = sim.scheduler.decide
    pure_decide = POLICIES[scheduler_name]
    counts = Counter()

    def compare(snapshot, pending, simulation):
        state = _contract_state(simulation)
        converted = [_contract_task(record) for record in pending]
        pure = pure_decide(state, converted, ContractConfig())
        bounded = bounded_tasks(converted)
        bounded_ids = {task.id for task in bounded}
        bounded_pending = [record for record in pending if record.task.id in bounded_ids]
        original_feasible = simulation.feasible_pairs
        simulation.feasible_pairs = lambda: [pair for pair in original_feasible()
                                               if pair[0].task.id in bounded_ids]
        try:
            original = original_decide(snapshot, bounded_pending, simulation)
        finally:
            simulation.feasible_pairs = original_feasible
        if (pure.action, pure.task_id) == (original.action.value, original.task_id):
            counts["agree"] += 1
        else:
            counts["mismatch"] += 1
            reason = "unclassified"
            counts[reason] += 1
        counts["decisions"] += 1
        return original

    sim.scheduler.decide = compare
    sim.run(config["mission_duration_s"])
    return counts


def main():
    scenarios = sys.argv[1].split(",") if len(sys.argv) > 1 else list(SCENARIO_NAMES)
    seeds = [int(value) for value in sys.argv[2].split(",")] if len(sys.argv) > 2 else [100, 101, 102, 103]
    for scenario in scenarios:
        for scheduler in ("edf", "rule"):
            aggregate = Counter()
            for seed in seeds:
                aggregate.update(run_case(scenario, seed, scheduler))
            rate = 100.0 * aggregate["agree"] / max(1, aggregate["decisions"])
            print(f"{scenario},{scheduler},decisions={aggregate['decisions']},agreement={rate:.3f}%,"
                  f"mismatch={aggregate['mismatch']},unclassified={aggregate['unclassified']},"
                  "comparison=bounded-reference")


if __name__ == "__main__":
    main()

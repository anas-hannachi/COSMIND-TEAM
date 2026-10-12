"""Measure the 96-candidate policy against the original unbounded simulator."""

from collections import Counter

from pmars_simulation.contract.models import ContractConfig
from pmars_simulation.policy import edf, rule
from pmars_simulation.scenarios import build_simulation, generate_tasks, load_config
from tools.equivalence_check import _contract_state, _contract_task


POLICIES = {"edf": edf.decide, "rule": rule.decide}
BENCH = ("bench_normal", "bench_burst", "bench_low_energy", "bench_poor_link")
BURST = ("task_burst", "energy_link_stress", "thermal_burst_stress")
SEEDS = (200, 201, 202, 203)


def run_case(scenario: str, scheduler: str, seed: int) -> Counter:
    config = load_config(scenario)
    simulation = build_simulation(scenario, scheduler, seed,
                                  tasks=generate_tasks(config, seed))
    original = simulation.scheduler.decide
    counts = Counter()

    def compare(snapshot, pending, sim):
        tasks = [_contract_task(record) for record in pending]
        state = _contract_state(sim)
        pure = POLICIES[scheduler](state, tasks, ContractConfig())
        # Do not filter `pending` or feasible pairs here: this is deliberately
        # the original, unbounded simulator decision.
        float_decision = original(snapshot, pending, sim)
        counts["decisions"] += 1
        counts["mismatch"] += (pure.action, pure.task_id) != (
            float_decision.action.value, float_decision.task_id
        )
        counts["over_bound"] += len(pending) > 96
        counts["max_pending"] = max(counts["max_pending"], len(pending))
        return float_decision

    simulation.scheduler.decide = compare
    simulation.run(config["mission_duration_s"])
    return counts


def measure(scenarios=BENCH + BURST, seeds=SEEDS):
    result = {}
    for scenario in scenarios:
        for scheduler in ("edf", "rule"):
            total = Counter()
            for seed in seeds:
                counts = run_case(scenario, scheduler, seed)
                total.update({key: value for key, value in counts.items() if key != "max_pending"})
                total["max_pending"] = max(total["max_pending"], counts["max_pending"])
            result[(scenario, scheduler)] = total
    return result


def main() -> None:
    results = measure()
    for (scenario, scheduler), counts in results.items():
        rate = counts["mismatch"] / max(1, counts["decisions"])
        print(f"{scenario},{scheduler},decisions={counts['decisions']},mismatches={counts['mismatch']},"
              f"rate={rate:.4%},over96_decisions={counts['over_bound']},"
              f"max_pending={counts['max_pending']},comparison=unmodified-original")


if __name__ == "__main__":
    main()

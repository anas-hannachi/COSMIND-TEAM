"""Decision-point parity against the untouched float simulator."""

import pytest

from pmars_simulation.scenarios import BASE_SCENARIO_NAMES, BENCH_SCENARIO_NAMES
from tools.equivalence_check import run_case


SCENARIOS = BASE_SCENARIO_NAMES + BENCH_SCENARIO_NAMES


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("scheduler", ("edf", "rule"))
@pytest.mark.parametrize("seed", (100, 101, 102, 103))
def test_policy_agreement_at_every_decision(scenario, scheduler, seed):
    counts = run_case(scenario, seed, scheduler)
    agreement = counts["agree"] / max(1, counts["decisions"])
    required = 1.0 if scheduler == "edf" else 0.999
    assert agreement >= required, (scenario, scheduler, seed, dict(counts))

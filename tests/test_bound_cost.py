from tools.bound_cost import BENCH, BURST, SEEDS, measure


def test_96_task_bound_cost_against_unmodified_original():
    results = measure()
    for (scenario, scheduler), counts in results.items():
        rate = counts["mismatch"] / max(1, counts["decisions"])
        if scenario in BENCH:
            assert counts["mismatch"] == 0, (scenario, scheduler, dict(counts))
        elif scenario in BURST:
            assert rate <= 0.005, (scenario, scheduler, rate, dict(counts), SEEDS)

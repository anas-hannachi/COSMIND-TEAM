"""The Python reference applies the same deterministic 96-task decision bound."""

from pmars_simulation.contract.models import ContractState, ContractTask
from pmars_simulation.policy import edf, rule
from pmars_simulation.policy.core import bounded_tasks


def _task(index: int, deadline: int) -> ContractTask:
    return ContractTask(
        id=f"t{index:03}", kind="test", input_bytes=1, output_bytes_est=1,
        mem_req_bytes=0, demand_milli=0, base_proc_ms=1, priority=(9 if index == 96 else 1),
        value_milli=1, created_ms=0, deadline_ms=deadline, payload_bytes=1,
    )


def test_more_than_96_candidates_use_earliest_deadlines_for_both_policies():
    tasks = [_task(index, index + 1) for index in range(96)] + [_task(96, 1000)]
    bounded = bounded_tasks(tasks)
    assert len(bounded) == 96
    assert {task.id for task in bounded} == {f"t{index:03}" for index in range(96)}
    state = ContractState(now_ms=0, energy_mj=100000, storage_used_bytes=97,
                          storage_total_bytes=97, memory_available_bytes=0,
                          transmit_power_mw=100, contacts=((0, 10000, 1000000, 1000000, 0),))
    assert edf.decide(state, tasks) == edf.decide(state, bounded)
    assert rule.decide(state, tasks) == rule.decide(state, bounded)

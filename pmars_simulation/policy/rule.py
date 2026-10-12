"""Pure integer Rule policy."""

from ..contract.models import ContractConfig, ContractDecision, ContractState, ContractTask
from .core import bounded_tasks, can_process, can_transmit, plan_candidates


def _urgency(task: ContractTask, now_ms: int):
    slack = max(0, task.deadline_ms - now_ms)
    return (-int(task.priority >= 8), slack, -task.priority, -task.value_milli,
            task.id.encode("ascii"))


def decide(state: ContractState, tasks: list[ContractTask], cfg: ContractConfig | None = None) -> ContractDecision:
    cfg = cfg or ContractConfig()
    ordered = sorted(bounded_tasks(tasks), key=lambda t: _urgency(t, state.now_ms))
    for task in ordered:
        if can_transmit(task, state, True):
            return ContractDecision("TRANSMIT", task.id, "URGENT_DEADLINE_FEASIBLE")
    contact = any(start <= state.now_ms < end for start, end, _, _, _ in state.contacts[:16])
    for task in ordered:
        slack = task.deadline_ms - state.now_ms
        if can_process(task, state, True) and (not contact or slack <= cfg.urgent_slack_ms or task.priority >= 8):
            return ContractDecision("PROCESS", task.id, "PROCESS_WITH_FEASIBLE_DELIVERY")
    for task in ordered:
        if plan_candidates(task, state, cfg):
            return ContractDecision("STORE", task.id, "WAIT_FOR_FEASIBLE_CONTACT")
    return ContractDecision("IDLE")

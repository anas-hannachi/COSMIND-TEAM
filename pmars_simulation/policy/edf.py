"""Pure integer EDF policy."""

from ..contract.models import ContractConfig, ContractDecision, ContractState, ContractTask
from .core import bounded_tasks, feasible_pairs


def decide(state: ContractState, tasks: list[ContractTask], cfg: ContractConfig | None = None) -> ContractDecision:
    pairs = feasible_pairs(bounded_tasks(tasks), state, cfg or ContractConfig())
    if not pairs:
        return ContractDecision("IDLE")
    immediate = [pair for pair in pairs if pair[1] != "STORE"]
    candidates = immediate or pairs
    task, action = min(candidates, key=lambda pair: (
        pair[0].deadline_ms, {"TRANSMIT": 0, "PROCESS": 1, "STORE": 2}[pair[1]], pair[0].id.encode("ascii")
    ))
    return ContractDecision(action, task.id, "FEASIBLE_EARLIEST_DEADLINE")

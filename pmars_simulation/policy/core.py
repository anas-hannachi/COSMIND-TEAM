"""Integer feasibility primitives used by Python and the portable C port."""

from ..contract.models import ContractConfig, ContractState, ContractTask


def bounded_tasks(tasks: list[ContractTask]) -> list[ContractTask]:
    """The firmware evaluates only the 96 earliest-deadline tasks, with stable ties."""
    return sorted(tasks, key=lambda t: (t.deadline_ms, -t.priority, -t.value_milli,
                                        t.id.encode("ascii")))[:96]


def ordered(tasks: list[ContractTask]) -> list[ContractTask]:
    """Contract order: deadline, priority, value, then byte-wise ASCII id."""
    return sorted(tasks, key=lambda t: (t.deadline_ms, -t.priority, -t.value_milli, t.id.encode("ascii")))


def _contact(state: ContractState, t_ms: int):
    for start, end, bps0, bps1, latency_ms in state.contacts[:16]:
        if start <= t_ms < end:
            bps = bps0 + ((bps1 - bps0) * (t_ms - start)) // max(1, end - start)
            return start, end, bps, latency_ms
    return None


def transfer_time_ms(size_bytes: int, t_ms: int, state: ContractState) -> int | None:
    """Transfer duration, rounded up, evaluated at its proposed start."""
    current = _contact(state, t_ms)
    if current is None or current[2] <= 0:
        return None
    bits_ms = size_bytes * 8 * 1000
    duration = (bits_ms + current[2] - 1) // current[2]
    return duration + current[3]


def earliest_feasible_transfer(size_bytes: int, earliest_ms: int, deadline_ms: int, state: ContractState):
    for start, end, _, _, _ in state.contacts[:16]:
        at = max(earliest_ms, start)
        if at >= end:
            continue
        duration = transfer_time_ms(size_bytes, at, state)
        if duration is not None and duration <= end - at and at + duration <= deadline_ms:
            return at, duration
    return None


def has_energy_for(action: str, duration_ms: int, state: ContractState) -> bool:
    power = {"PROCESS": state.processing_power_mw, "TRANSMIT": state.transmit_power_mw,
             "STORE": state.idle_power_mw}.get(action, state.idle_power_mw)
    return state.energy_mj >= (power * duration_ms + 999) // 1000


def can_process(task: ContractTask, state: ContractState, require_future_delivery: bool = False) -> bool:
    if task.processed:
        return False
    fraction = max(1, state.throttle_fraction_milli)
    duration = (task.base_proc_ms * 1000 + fraction - 1) // fraction
    finish = state.now_ms + duration
    if finish >= task.deadline_ms or finish > state.drain_horizon_ms:
        return False
    if task.mem_req_bytes > state.memory_available_bytes:
        return False
    if task.demand_milli * 1000 > state.compute_capacity_milli * state.throttle_fraction_milli:
        return False
    if not has_energy_for("PROCESS", duration, state):
        return False
    resident = task.payload_bytes if task.payload_bytes is not None else task.input_bytes
    output = task.actual_output_bytes if task.actual_output_bytes is not None else task.output_bytes_est
    replacement = state.storage_used_bytes - resident + output
    if not 0 <= replacement <= state.storage_total_bytes:
        return False
    return not require_future_delivery or earliest_feasible_transfer(
        output, finish, min(task.deadline_ms, state.drain_horizon_ms), state
    ) is not None


def can_transmit(task: ContractTask, state: ContractState, require_deadline: bool = False) -> bool:
    resident = task.payload_bytes if task.payload_bytes is not None else task.input_bytes
    duration = transfer_time_ms(resident, state.now_ms, state)
    contact = _contact(state, state.now_ms)
    if duration is None or contact is None or duration > contact[1] - state.now_ms:
        return False
    finish = state.now_ms + duration
    if finish > state.drain_horizon_ms or not has_energy_for("TRANSMIT", duration, state):
        return False
    return not require_deadline or finish <= task.deadline_ms


def store_viable(task: ContractTask, state: ContractState, cfg: ContractConfig) -> bool:
    resident = task.payload_bytes if task.payload_bytes is not None else task.input_bytes
    route = earliest_feasible_transfer(resident, state.now_ms,
                                       min(task.deadline_ms, state.drain_horizon_ms), state)
    return bool(route and route[0] > state.now_ms and route[0] + route[1] <= state.now_ms + cfg.store_horizon_ms)


def feasible_pairs(tasks: list[ContractTask], state: ContractState, cfg: ContractConfig):
    pairs = []
    for task in ordered(tasks):
        if can_transmit(task, state, True):
            pairs.append((task, "TRANSMIT"))
        if can_process(task, state, True):
            pairs.append((task, "PROCESS"))
        if plan_candidates(task, state, cfg):
            pairs.append((task, "STORE"))
    return pairs


def plan_candidates(task: ContractTask, state: ContractState, cfg: ContractConfig) -> bool:
    """Whether any one-step route in the Rule rollout is viable within the horizon."""
    if can_transmit(task, state, require_deadline=True):
        return True
    finish = state.now_ms + ((task.base_proc_ms * 1000 + max(1, state.throttle_fraction_milli) - 1)
                             // max(1, state.throttle_fraction_milli))
    output = task.actual_output_bytes if task.actual_output_bytes is not None else task.output_bytes_est
    if can_process(task, state, require_future_delivery=True):
        transfer = earliest_feasible_transfer(output, finish,
            min(task.deadline_ms, state.drain_horizon_ms), state)
        if transfer and transfer[0] + transfer[1] <= state.now_ms + cfg.store_horizon_ms:
            return True
    resident = task.payload_bytes if task.payload_bytes is not None else task.input_bytes
    route = earliest_feasible_transfer(resident, state.now_ms,
        min(task.deadline_ms, state.drain_horizon_ms), state)
    return bool(route and route[0] > state.now_ms and
                route[0] + route[1] <= state.now_ms + cfg.store_horizon_ms)

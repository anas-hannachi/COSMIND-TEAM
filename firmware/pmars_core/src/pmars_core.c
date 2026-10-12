#include "pmars_core.h"
#include <limits.h>
#include <string.h>

static int64_t min64(int64_t a, int64_t b) { return a < b ? a : b; }
static int64_t max64(int64_t a, int64_t b) { return a > b ? a : b; }
static int64_t floor_div(int64_t numerator, int64_t denominator) {
    int64_t quotient = numerator / denominator;
    int64_t remainder = numerator % denominator;
    return quotient - ((remainder != 0 && numerator < 0) ? 1 : 0);
}
static int add64(int64_t a, int64_t b, int64_t *out) {
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) return 0;
    *out = a + b; return 1;
}
static int mul_div_ceil(int64_t value, int64_t multiplier, int64_t divisor, int64_t *out) {
    int64_t product;
    if (value < 0 || multiplier < 0 || divisor <= 0 || value > INT64_MAX / max64(1, multiplier)) return 0;
    product = value * multiplier;
    *out = product / divisor + (product % divisor != 0);
    return 1;
}
static int id_cmp(const char *a, const char *b) { return strcmp(a, b); }
static int urgency_before(const pmars_task_t *a, const pmars_task_t *b, int64_t now_ms) {
    int64_t as = max64(0, a->deadline_ms - now_ms), bs = max64(0, b->deadline_ms - now_ms);
    if ((a->priority >= 8) != (b->priority >= 8)) return a->priority >= 8;
    if (as != bs) return as < bs;
    if (a->priority != b->priority) return a->priority > b->priority;
    if (a->value_milli != b->value_milli) return a->value_milli > b->value_milli;
    return id_cmp(a->id, b->id) < 0;
}
static int contact_at(int64_t time_ms, const pmars_state_t *state, uint32_t *index, int64_t *bps) {
    uint32_t i;
    for (i = 0U; i < state->contact_count && i < PMARS_MAX_CONTACTS; ++i) {
        const pmars_contact_t *contact = &state->contacts[i];
        if (contact->start_ms <= time_ms && time_ms < contact->end_ms) {
            int64_t span = contact->end_ms - contact->start_ms;
            int64_t delta = contact->bps_end - contact->bps_start;
            if (span <= 0 || (delta != 0 && time_ms - contact->start_ms > INT64_MAX / max64(1, delta < 0 ? -delta : delta))) return 0;
            *bps = contact->bps_start + floor_div(delta * (time_ms - contact->start_ms), span);
            *index = i;
            return *bps > 0;
        }
    }
    return 0;
}
int pmars_transfer_time_ms(int64_t size_bytes, int64_t start_ms, const pmars_state_t *state, int64_t *duration_ms) {
    uint32_t index = 0U;
    int64_t bps = 0, transfer = 0, sum = 0;
    if (size_bytes < 0 || state == 0 || duration_ms == 0 || !contact_at(start_ms, state, &index, &bps)) return 0;
    if (!mul_div_ceil(size_bytes, INT64_C(8000), bps, &transfer)) return 0;
    if (!add64(transfer, state->contacts[index].latency_ms, &sum)) return 0;
    *duration_ms = sum;
    return 1;
}
static int earliest_transfer(int64_t size_bytes, int64_t earliest_ms, int64_t deadline_ms,
                            const pmars_state_t *state, int64_t *start_out, int64_t *duration_out) {
    uint32_t i;
    for (i = 0U; i < state->contact_count && i < PMARS_MAX_CONTACTS; ++i) {
        const pmars_contact_t *c = &state->contacts[i];
        int64_t start = max64(earliest_ms, c->start_ms), duration = 0, finish = 0;
        if (c->end_ms <= earliest_ms || start >= c->end_ms) continue;
        if (pmars_transfer_time_ms(size_bytes, start, state, &duration) &&
            duration <= c->end_ms - start && add64(start, duration, &finish) && finish <= deadline_ms) {
            *start_out = start; *duration_out = duration; return 1;
        }
    }
    return 0;
}
static int enough_energy(int64_t power_mw, int64_t duration_ms, const pmars_state_t *state) {
    int64_t cost = 0;
    return mul_div_ceil(power_mw, duration_ms, 1000, &cost) && state->energy_mj >= cost;
}
static int task_output(const pmars_task_t *task, int64_t *out) {
    *out = task->actual_output_bytes >= 0 ? task->actual_output_bytes : task->output_bytes_est;
    return *out >= 0;
}
static int process_duration(const pmars_task_t *task, const pmars_state_t *state, int64_t *duration) {
    return mul_div_ceil(task->base_proc_ms, 1000, max64(1, state->throttle_fraction_milli), duration);
}
int pmars_can_process(const pmars_task_t *task, const pmars_state_t *state, int require_future_delivery) {
    int64_t duration = 0, finish = 0, output = 0, resident, replacement = 0, xfer_start = 0, xfer_duration = 0;
    if (task == 0 || state == 0) return 0;
    resident = task->payload_bytes;
    if (task->processed || resident < 0 || !task_output(task, &output)) return 0;
    if (!process_duration(task, state, &duration) || !add64(state->now_ms, duration, &finish)) return 0;
    if (finish >= task->deadline_ms || finish > state->drain_horizon_ms || task->mem_req_bytes > state->memory_available_bytes) return 0;
    if (task->demand_milli > 0 && (state->compute_capacity_milli > INT64_MAX / max64(1, state->throttle_fraction_milli) ||
        task->demand_milli > state->compute_capacity_milli * state->throttle_fraction_milli / 1000)) return 0;
    if (!enough_energy(state->processing_power_mw, duration, state)) return 0;
    if (!add64(state->storage_used_bytes - resident, output, &replacement) ||
        replacement < 0 || replacement > state->storage_total_bytes) return 0;
    if (!require_future_delivery) return 1;
    return earliest_transfer(output, finish, min64(task->deadline_ms, state->drain_horizon_ms),
                            state, &xfer_start, &xfer_duration);
}
int pmars_can_transmit(const pmars_task_t *task, const pmars_state_t *state, int require_deadline) {
    uint32_t index = 0U;
    int64_t bps = 0, duration = 0, finish = 0;
    if (task == 0 || state == 0 || task->payload_bytes < 0 ||
        !contact_at(state->now_ms, state, &index, &bps) ||
        !pmars_transfer_time_ms(task->payload_bytes, state->now_ms, state, &duration)) return 0;
    if (duration > state->contacts[index].end_ms - state->now_ms ||
        !add64(state->now_ms, duration, &finish) || finish > state->drain_horizon_ms ||
        !enough_energy(state->transmit_power_mw, duration, state)) return 0;
    return !require_deadline || finish <= task->deadline_ms;
}
int pmars_plan_candidates(const pmars_task_t *task, const pmars_state_t *state, const pmars_config_t *config) {
    int64_t duration = 0, finish = 0, output = 0, at = 0, transfer = 0, horizon = 0, resident;
    if (task == 0 || state == 0 || config == 0) return 0;
    resident = task->payload_bytes;
    if (pmars_can_transmit(task, state, 1)) return 1;
    if (task_output(task, &output) && process_duration(task, state, &duration) &&
        add64(state->now_ms, duration, &finish) && pmars_can_process(task, state, 1) &&
        earliest_transfer(output, finish, min64(task->deadline_ms, state->drain_horizon_ms), state, &at, &transfer) &&
        add64(at, transfer, &horizon) && horizon <= state->now_ms + config->store_horizon_ms) return 1;
    if (resident >= 0 && earliest_transfer(resident, state->now_ms, min64(task->deadline_ms, state->drain_horizon_ms),
        state, &at, &transfer) && at > state->now_ms && add64(at, transfer, &horizon) &&
        horizon <= state->now_ms + config->store_horizon_ms) return 1;
    return 0;
}
static int action_rank(pmars_action_t action) {
    return action == PMARS_TRANSMIT ? 0 : action == PMARS_PROCESS ? 1 : 2;
}
static const pmars_task_t *selected_task(const pmars_task_t *tasks, const uint16_t *indices, uint32_t position) {
    return &tasks[indices == 0 ? position : indices[position]];
}
int pmars_decide(const pmars_state_t *state, const pmars_task_t *tasks, uint32_t count,
                 const pmars_config_t *config, int rule, pmars_decision_t *out) {
    uint16_t selected[PMARS_MAX_TASKS];
    const uint16_t *indices = 0;
    uint32_t i, best = PMARS_MAX_TASKS;
    pmars_action_t best_action = PMARS_IDLE;
    int has_immediate = 0;
    if (state != 0 && tasks != 0 && config != 0 && out != 0 && count > PMARS_MAX_TASKS) {
        uint32_t used = 0U;
        indices = selected;
        for (i = 0U; i < count; ++i) {
            uint32_t at;
            for (at = 0U; at < used; ++at) {
                const pmars_task_t *a = &tasks[i], *b = &tasks[selected[at]];
                if (a->deadline_ms < b->deadline_ms ||
                    (a->deadline_ms == b->deadline_ms && a->priority > b->priority) ||
                    (a->deadline_ms == b->deadline_ms && a->priority == b->priority && a->value_milli > b->value_milli) ||
                    (a->deadline_ms == b->deadline_ms && a->priority == b->priority &&
                     a->value_milli == b->value_milli && id_cmp(a->id, b->id) < 0)) break;
            }
            if (at >= PMARS_MAX_TASKS && used == PMARS_MAX_TASKS) continue;
            if (used < PMARS_MAX_TASKS) used++;
            if (at < PMARS_MAX_TASKS) {
                uint32_t move = used - 1U;
                while (move > at) { selected[move] = selected[move - 1U]; move--; }
                selected[at] = (uint16_t)i;
            }
        }
        count = used;
    }
    if (state == 0 || tasks == 0 || config == 0 || out == 0 ||
        state->contact_count > PMARS_MAX_CONTACTS || state->now_ms < 0 || state->energy_mj < 0) return -1;
    if (rule) {
        for (i = 0U; i < count; ++i) if (pmars_can_transmit(selected_task(tasks, indices, i), state, 1) &&
            (best == PMARS_MAX_TASKS || urgency_before(selected_task(tasks, indices, i), selected_task(tasks, indices, best), state->now_ms))) { best = i; best_action = PMARS_TRANSMIT; }
        if (best == PMARS_MAX_TASKS) {
            uint32_t contact_i = 0U; int64_t bps = 0;
            int contact = contact_at(state->now_ms, state, &contact_i, &bps);
            for (i = 0U; i < count; ++i) {
                const pmars_task_t *task = selected_task(tasks, indices, i);
                int64_t slack = task->deadline_ms - state->now_ms;
                if (pmars_can_process(task, state, 1) && (!contact || slack <= config->urgent_slack_ms || task->priority >= 8) &&
                    (best == PMARS_MAX_TASKS || urgency_before(task, selected_task(tasks, indices, best), state->now_ms))) { best = i; best_action = PMARS_PROCESS; }
            }
        }
        if (best == PMARS_MAX_TASKS) for (i = 0U; i < count; ++i) if (pmars_plan_candidates(selected_task(tasks, indices, i), state, config) &&
            (best == PMARS_MAX_TASKS || urgency_before(selected_task(tasks, indices, i), selected_task(tasks, indices, best), state->now_ms))) { best = i; best_action = PMARS_STORE; }
    } else {
        for (i = 0U; i < count; ++i) {
            if (pmars_can_transmit(selected_task(tasks, indices, i), state, 1)) has_immediate = 1;
            if (pmars_can_process(selected_task(tasks, indices, i), state, 1)) has_immediate = 1;
        }
        for (i = 0U; i < count; ++i) {
            pmars_action_t action = PMARS_IDLE;
            const pmars_task_t *task = selected_task(tasks, indices, i);
            if (pmars_can_transmit(task, state, 1)) action = PMARS_TRANSMIT;
            else if (pmars_can_process(task, state, 1)) action = PMARS_PROCESS;
            else if (!has_immediate && pmars_plan_candidates(task, state, config)) action = PMARS_STORE;
            if (action == PMARS_IDLE) continue;
            if (best == PMARS_MAX_TASKS || task->deadline_ms < selected_task(tasks, indices, best)->deadline_ms ||
                (task->deadline_ms == selected_task(tasks, indices, best)->deadline_ms && action_rank(action) < action_rank(best_action)) ||
                (task->deadline_ms == selected_task(tasks, indices, best)->deadline_ms && action_rank(action) == action_rank(best_action) && id_cmp(task->id, selected_task(tasks, indices, best)->id) < 0)) {
                best = i; best_action = action;
            }
        }
        if (!has_immediate && best == PMARS_MAX_TASKS) for (i = 0U; i < count; ++i) if (pmars_plan_candidates(selected_task(tasks, indices, i), state, config) &&
            (best == PMARS_MAX_TASKS || selected_task(tasks, indices, i)->deadline_ms < selected_task(tasks, indices, best)->deadline_ms ||
             (selected_task(tasks, indices, i)->deadline_ms == selected_task(tasks, indices, best)->deadline_ms && id_cmp(selected_task(tasks, indices, i)->id, selected_task(tasks, indices, best)->id) < 0))) {
            best = i; best_action = PMARS_STORE;
        }
    }
    out->action = best_action; out->reason_code = best == PMARS_MAX_TASKS ? 0U : 1U; out->task_id[0] = '\0';
    if (best != PMARS_MAX_TASKS) (void)memcpy(out->task_id, selected_task(tasks, indices, best)->id, PMARS_ID_BYTES);
    return 0;
}

static void push_event(pmars_engine_t *engine, pmars_event_kind_t kind, uint32_t index) {
    uint32_t slot;
    if (engine->event_count == PMARS_MAX_EVENTS) { engine->events_dropped++; return; }
    slot = (engine->event_head + engine->event_count) % PMARS_MAX_EVENTS;
    engine->events[slot].kind = kind;
    engine->events[slot].task_index = (uint16_t)index;
    engine->events[slot].time_ms = engine->state.now_ms;
    engine->events[slot].task_id[0] = '\0';
    if (index < engine->task_count) (void)memcpy(engine->events[slot].task_id, engine->tasks[index].id, PMARS_ID_BYTES);
    engine->event_count++;
}

int pmars_status_terminal(pmars_task_status_t status) {
    return status == PMARS_TASK_COMPLETED || status == PMARS_TASK_LATE ||
           status == PMARS_TASK_EXPIRED || status == PMARS_TASK_REJECTED ||
           status == PMARS_TASK_UNFINISHED || status == PMARS_TASK_FAILED;
}

static void set_status(pmars_engine_t *engine, uint32_t index, pmars_task_status_t status) {
    if (!pmars_status_terminal(engine->statuses[index]) && pmars_status_terminal(status) && engine->active_count > 0U)
        engine->active_count--;
    engine->statuses[index] = status;
    if (status == PMARS_TASK_COMPLETED) engine->completed_count++;
    else if (status == PMARS_TASK_LATE) engine->late_count++;
    else if (status == PMARS_TASK_EXPIRED) engine->expired_count++;
    else if (status == PMARS_TASK_REJECTED) engine->rejected_count++;
    else if (status == PMARS_TASK_FAILED) engine->failed_count++;
}

void pmars_engine_init(pmars_engine_t *engine, const pmars_state_t *state,
                       const pmars_config_t *config, int rule) {
    if (engine == 0) return;
    (void)memset(engine, 0, sizeof(*engine));
    if (state != 0) engine->state = *state;
    if (config != 0) engine->config = *config;
    engine->rule = (uint8_t)(rule != 0);
}

int pmars_engine_admit(pmars_engine_t *engine, const pmars_task_t *task) {
    uint32_t index;
    if (engine == 0 || task == 0) return 0;
    for (index = 0U; index < engine->task_count; ++index)
        if (pmars_status_terminal(engine->statuses[index])) break;
    if (index == engine->task_count && engine->task_count < PMARS_MAX_TASKS) engine->task_count++;
    else if (index == engine->task_count) return 0;
    if (task->payload_bytes < 0 || task->deadline_ms <= engine->state.now_ms ||
        task->payload_bytes > engine->state.storage_total_bytes - engine->state.storage_used_bytes) {
        engine->tasks[index] = *task;
        engine->statuses[index] = PMARS_TASK_REJECTED;
        engine->rejected_count++;
        push_event(engine, PMARS_EVENT_REJECT, index);
        return 0;
    }
    engine->tasks[index] = *task;
    engine->statuses[index] = task->processed ? PMARS_TASK_PROCESSED : PMARS_TASK_PENDING;
    engine->active_count++;
    engine->state.storage_used_bytes += task->payload_bytes;
    push_event(engine, PMARS_EVENT_ADMIT, index);
    return 1;
}

int pmars_engine_step(pmars_engine_t *engine) {
    pmars_decision_t decision;
    uint32_t indices[PMARS_MAX_TASKS], count = 0U, i, chosen = PMARS_MAX_TASKS;
    if (engine == 0 || engine->task_count == 0U) return 0;
    for (i = 0U; i < engine->task_count; ++i) {
        if (engine->statuses[i] != PMARS_TASK_PENDING && engine->statuses[i] != PMARS_TASK_PROCESSED) continue;
        if (engine->state.now_ms >= engine->tasks[i].deadline_ms) {
            set_status(engine, i, PMARS_TASK_EXPIRED);
            if (engine->state.storage_used_bytes >= engine->tasks[i].payload_bytes)
                engine->state.storage_used_bytes -= engine->tasks[i].payload_bytes;
            push_event(engine, PMARS_EVENT_EXPIRED, i);
            continue;
        }
        engine->scratch_tasks[count] = engine->tasks[i]; indices[count++] = i;
    }
    if (count == 0U) return 0;
    if (pmars_decide(&engine->state, engine->scratch_tasks, count,
                     &engine->config, engine->rule, &decision) != 0) return -1;
    if (decision.action == PMARS_IDLE) return 0;
    for (i = 0U; i < count; ++i) if (strcmp(engine->scratch_tasks[i].id, decision.task_id) == 0) { chosen = i; break; }
    if (chosen == PMARS_MAX_TASKS) return -1;
    i = indices[chosen];
    if (decision.action == PMARS_PROCESS) {
        int64_t duration, output, cost, finish;
        if (!process_duration(&engine->tasks[i], &engine->state, &duration) ||
            !task_output(&engine->tasks[i], &output) ||
            !mul_div_ceil(engine->state.processing_power_mw, duration, 1000, &cost) ||
            !add64(engine->state.now_ms, duration, &finish) || cost > engine->state.energy_mj) return -1;
        engine->state.now_ms = finish;
        engine->state.energy_mj -= cost;
        if (!add64(engine->state.storage_used_bytes - engine->tasks[i].payload_bytes, output,
                   &engine->state.storage_used_bytes) || engine->state.storage_used_bytes < 0 ||
            engine->state.storage_used_bytes > engine->state.storage_total_bytes) return -1;
        engine->tasks[i].payload_bytes = output;
        engine->tasks[i].processed = 1U;
        engine->statuses[i] = PMARS_TASK_PROCESSED;
        push_event(engine, PMARS_EVENT_PROCESS_START, i);
        push_event(engine, PMARS_EVENT_PROCESSED, i);
        return 1;
    }
    if (decision.action == PMARS_TRANSMIT) {
        int64_t duration, cost, finish;
        if (!pmars_transfer_time_ms(engine->tasks[i].payload_bytes, engine->state.now_ms,
                                    &engine->state, &duration) ||
            !mul_div_ceil(engine->state.transmit_power_mw, duration, 1000, &cost) ||
            !add64(engine->state.now_ms, duration, &finish) || cost > engine->state.energy_mj) return -1;
        push_event(engine, PMARS_EVENT_TRANSMIT_START, i);
        engine->state.now_ms = finish;
        engine->state.energy_mj -= cost;
        if (engine->state.storage_used_bytes >= engine->tasks[i].payload_bytes)
            engine->state.storage_used_bytes -= engine->tasks[i].payload_bytes;
        set_status(engine, i, finish <= engine->tasks[i].deadline_ms ? PMARS_TASK_COMPLETED : PMARS_TASK_LATE);
        push_event(engine, PMARS_EVENT_TRANSMITTED, i);
        push_event(engine, engine->statuses[i] == PMARS_TASK_COMPLETED ? PMARS_EVENT_COMPLETED : PMARS_EVENT_LATE, i);
        return 1;
    }
    push_event(engine, PMARS_EVENT_STORE, i);
    {
        int64_t start = engine->state.now_ms;
        int64_t next = start + PMARS_IDLE_QUANTUM_MS;
        uint32_t c; /* simulator: min(IDLE_QUANTUM_S, deadline - now) */
        if (engine->tasks[i].deadline_ms < next) next = engine->tasks[i].deadline_ms;
        if (next <= engine->state.now_ms) next = engine->state.now_ms + 1;
        if (engine->state.store_power_mw > 0) {
            int64_t cost = 0;
            if (!mul_div_ceil(engine->state.store_power_mw, next - start, 1000, &cost)) return -1;
            if (cost > engine->state.energy_mj) {
                engine->state.now_ms = start + engine->state.energy_mj * 1000 / engine->state.store_power_mw;
                engine->state.energy_mj = 0;
                for (c = 0U; c < count; ++c) if (engine->statuses[indices[c]] == PMARS_TASK_PENDING ||
                    engine->statuses[indices[c]] == PMARS_TASK_PROCESSED) {
                    set_status(engine, indices[c], PMARS_TASK_FAILED);
                    push_event(engine, PMARS_EVENT_FAILED, indices[c]);
                }
            } else {
                engine->state.energy_mj -= cost;
                engine->state.now_ms = next;
            }
        } else engine->state.now_ms = next;
    }
    return 1;
}

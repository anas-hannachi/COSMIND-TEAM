#include "pmars_proto.h"
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static void copy_label(char *out, size_t capacity, const char *value) {
    size_t n = 0U;
    if (capacity == 0U) return;
    if (value != NULL) while (value[n] != '\0' && n + 1U < capacity) { out[n] = value[n]; n++; }
    out[n] = '\0';
}

static const char *status_name(pmars_task_status_t status) {
    switch (status) {
        case PMARS_TASK_PENDING: return "pending";
        case PMARS_TASK_PROCESSED: return "processed";
        case PMARS_TASK_COMPLETED: return "completed";
        case PMARS_TASK_LATE: return "late";
        case PMARS_TASK_EXPIRED: return "expired";
        case PMARS_TASK_REJECTED: return "rejected";
        case PMARS_TASK_UNFINISHED: return "unfinished";
        case PMARS_TASK_FAILED: return "failed";
        default: return "unknown";
    }
}

static const char *event_name(pmars_event_kind_t kind) {
    switch (kind) {
        case PMARS_EVENT_ADMIT: return "admitted";
        case PMARS_EVENT_REJECT: return "rejected";
        case PMARS_EVENT_PROCESS_START: return "process_started";
        case PMARS_EVENT_PROCESSED: return "processed";
        case PMARS_EVENT_STORE: return "stored";
        case PMARS_EVENT_TRANSMIT_START: return "transmit_started";
        case PMARS_EVENT_TRANSMITTED: return "transmitted";
        case PMARS_EVENT_COMPLETED: return "completed";
        case PMARS_EVENT_LATE: return "late";
        case PMARS_EVENT_EXPIRED: return "expired";
        case PMARS_EVENT_FAILED: return "failed";
        default: return "unknown";
    }
}

static uint32_t crc_step(uint32_t crc, const unsigned char *data, size_t length) {
    size_t i;
    unsigned bit;
    for (i = 0; i < length; ++i) {
        crc ^= data[i];
        for (bit = 0; bit < 8U; ++bit)
            crc = (crc >> 1U) ^ ((crc & 1U) ? UINT32_C(0xedb88320) : 0U);
    }
    return crc;
}

static uint32_t crc_bytes(const char *data, size_t length) {
    return crc_step(UINT32_MAX, (const unsigned char *)data, length) ^ UINT32_MAX;
}

int pmars_proto_line_valid(const char *line, size_t length) {
    return line != NULL && length > 0U && length <= PMARS_PROTO_MAX_LINE && line[length - 1U] == '\n';
}

static const char *key_value(const char *json, const char *key) {
    char needle[40];
    int n = snprintf(needle, sizeof(needle), "\"%s\":", key);
    const char *found;
    if (n < 0 || (size_t)n >= sizeof(needle)) return NULL;
    found = strstr(json, needle);
    return found == NULL ? NULL : found + (size_t)n;
}

static int read_int(const char *json, const char *key, int64_t *value) {
    const char *p = key_value(json, key);
    uint64_t magnitude = 0U;
    int negative = 0;
    if (p == NULL || value == NULL) return 0;
    if (*p == '-') { negative = 1; p++; }
    if (*p < '0' || *p > '9') return 0;
    if (*p == '0' && p[1] >= '0' && p[1] <= '9') return 0;
    while (*p >= '0' && *p <= '9') {
        unsigned digit = (unsigned)(*p - '0');
        if (magnitude > (UINT64_MAX - digit) / 10U) return 0;
        magnitude = magnitude * 10U + digit;
        p++;
    }
    if (*p != ',' && *p != '}' && *p != ']') return 0;
    if (negative) {
        if (magnitude > (uint64_t)INT64_MAX + 1U) return 0;
        *value = magnitude == (uint64_t)INT64_MAX + 1U ? INT64_MIN : -(int64_t)magnitude;
    } else {
        if (magnitude > INT64_MAX) return 0;
        *value = (int64_t)magnitude;
    }
    return 1;
}

static int read_string(const char *json, const char *key, char *out, size_t capacity) {
    const char *p = key_value(json, key);
    size_t n = 0U;
    if (p == NULL || *p != '\"' || out == NULL || capacity == 0U) return 0;
    p++;
    while (*p != '\0' && *p != '\"') {
        if (*p == '\\' || (unsigned char)*p < 0x20U || n + 1U >= capacity) return 0;
        out[n++] = *p++;
    }
    if (*p != '\"') return 0;
    out[n] = '\0';
    return 1;
}

static int read_bool(const char *json, const char *key, uint8_t *value) {
    const char *p = key_value(json, key);
    if (p == NULL || value == NULL) return 0;
    if (strncmp(p, "true", 4U) == 0 && (p[4] == ',' || p[4] == '}' || p[4] == ']')) { *value = 1U; return 1; }
    if (strncmp(p, "false", 5U) == 0 && (p[5] == ',' || p[5] == '}' || p[5] == ']')) { *value = 0U; return 1; }
    return 0;
}

static int read_contacts(const char *json, pmars_state_t *state, int append) {
    const char *p = key_value(json, "contacts");
    uint32_t count = append ? state->contact_count : 0U;
    if (p == NULL) { if (!append) state->contact_count = 0U; return 1; }
    if (*p++ != '[') return 0;
    while (*p != ']' && *p != '\0') {
        int64_t values[5];
        unsigned field;
        if (count >= PMARS_MAX_CONTACTS || *p++ != '[') return 0;
        for (field = 0U; field < 5U; ++field) {
            uint64_t magnitude = 0U;
            int negative = 0;
            if (*p == '-') { negative = 1; p++; }
            if (*p < '0' || *p > '9') return 0;
            while (*p >= '0' && *p <= '9') {
                unsigned digit = (unsigned)(*p++ - '0');
                if (magnitude > ((uint64_t)INT64_MAX + (unsigned)negative - digit) / 10U) return 0;
                magnitude = magnitude * 10U + digit;
            }
            values[field] = negative ? -(int64_t)magnitude : (int64_t)magnitude;
            if (field < 4U) { if (*p++ != ',') return 0; }
        }
        if (*p++ != ']') return 0;
        state->contacts[count++] = (pmars_contact_t){values[0], values[1], values[2], values[3], values[4]};
        if (*p == ',') p++;
        else if (*p != ']') return 0;
    }
    if (*p != ']') return 0;
    state->contact_count = count;
    return 1;
}

static int crc_valid(const char *json, size_t length, uint32_t *crc_value) {
    const char *crc = strstr(json, "\"crc\":");
    const char *p;
    const char *prefix_end, *suffix_start;
    uint64_t value = 0U;
    const char *body;
    size_t body_length;
    uint32_t calculated;
    if (crc == NULL) return 0;
    p = crc + 6;
    if (*p < '0' || *p > '9') return 0;
    while (*p >= '0' && *p <= '9') {
        value = value * 10U + (unsigned)(*p - '0');
        if (value > UINT32_MAX) return 0;
        p++;
    }
    if ((*p != ',' && *p != '}') || p >= json + length) return 0;
    if (crc == json + 1) {
        if (*p != ',') return 0;
        calculated = crc_step(UINT32_MAX, (const unsigned char *)"{", 1U);
        body = p + 1;
        body_length = length - (size_t)(body - json);
        calculated = crc_step(calculated, (const unsigned char *)body, body_length) ^ UINT32_MAX;
    } else {
        if (crc[-1] != ',') return 0;
        prefix_end = crc - 1;
        suffix_start = p;
        calculated = crc_step(UINT32_MAX, (const unsigned char *)json,
                              (size_t)(prefix_end - json));
        calculated = crc_step(calculated, (const unsigned char *)suffix_start,
                              length - (size_t)(suffix_start - json)) ^ UINT32_MAX;
    }
    if (calculated != (uint32_t)value) return 0;
    if (crc_value != NULL) *crc_value = (uint32_t)value;
    return 1;
}

static int emit_body(const char *body, char *output, size_t capacity) {
    uint32_t crc;
    int n;
    size_t length;
    if (body == NULL || output == NULL || capacity == 0U || body[0] != '{') return 0;
    length = strlen(body);
    crc = crc_bytes(body, length);
    n = snprintf(output, capacity, "{\"crc\":%" PRIu32 ",%s\n", crc, body + 1);
    return n > 0 && (size_t)n < capacity;
}

static int emit_error(uint32_t seq, const char *code, char *output, size_t capacity) {
    char body[160];
    (void)snprintf(body, sizeof(body), "{\"code\":\"%s\",\"seq\":%" PRIu32 ",\"type\":\"error\",\"v\":1}", code, seq);
    return emit_body(body, output, capacity);
}

static size_t array_object_count(const char *json, const char *key) {
    const char *p = key_value(json, key);
    size_t count = 0U;
    int depth = 0, quoted = 0, escaped = 0, primitive = 0;
    if (p == NULL || *p != '[') return 0U;
    ++p; /* Count elements inside the outer array, not the array itself. */
    for (; *p != '\0'; ++p) {
        if (quoted) {
            if (escaped) escaped = 0;
            else if (*p == '\\') escaped = 1;
            else if (*p == '\"') quoted = 0;
            continue;
        }
        if (depth == 0) {
            if (*p == ']') return count;
            if (*p == ',' || *p == ' ' || *p == '\t') { primitive = 0; continue; }
            if (!primitive && *p != '{' && *p != '[' && *p != '\"') { count++; primitive = 1; }
            else if (*p == '{' || *p == '[' || *p == '\"') { count++; primitive = 1; }
        }
        if (*p == '\"') quoted = 1;
        else if (*p == '{' || *p == '[') depth++;
        else if ((*p == '}' || *p == ']') && depth > 0) { depth--; primitive = 0; }
    }
    return SIZE_MAX;
}

void pmars_proto_init(pmars_proto_session_t *session) {
    if (session == NULL) return;
    (void)memset(session, 0, sizeof(*session));
    copy_label(session->firmware_version, sizeof(session->firmware_version), "0.1.0");
    copy_label(session->git_sha, sizeof(session->git_sha), "unavailable");
    copy_label(session->target, sizeof(session->target), "host");
    copy_label(session->idf_version, sizeof(session->idf_version), "host");
    copy_label(session->reset_reason, sizeof(session->reset_reason), "host");
    session->scratch_state.energy_mj = INT64_C(1000000);
    session->scratch_state.storage_total_bytes = INT64_C(100000000);
    session->scratch_state.memory_available_bytes = INT64_C(100000000);
    session->scratch_state.compute_capacity_milli = 100000;
    session->scratch_state.throttle_fraction_milli = 1000;
    session->scratch_state.drain_horizon_ms = INT64_MAX;
    session->engine.state = session->scratch_state;
    session->engine.config.store_horizon_ms = 300000;
    session->engine.config.urgent_slack_ms = 90000;
}

void pmars_proto_set_platform(pmars_proto_session_t *session, const char *target,
                              const char *idf_version, const char *reset_reason,
                              uint32_t stack_high_water, uint32_t free_heap_bytes) {
    if (session == NULL) return;
    copy_label(session->target, sizeof(session->target), target);
    copy_label(session->idf_version, sizeof(session->idf_version), idf_version);
    copy_label(session->reset_reason, sizeof(session->reset_reason), reset_reason);
    session->stack_high_water = stack_high_water;
    session->free_heap_bytes = free_heap_bytes;
    if (session->min_free_heap_bytes == 0U || free_heap_bytes < session->min_free_heap_bytes)
        session->min_free_heap_bytes = free_heap_bytes;
}

int pmars_proto_handle(pmars_proto_session_t *session, const char *line, size_t length,
                       char *output, size_t output_capacity) {
    char json[PMARS_PROTO_MAX_LINE + 1U], type[24];
    int64_t version = 0, seq_number = 0, value = 0;
    uint32_t seq;
    size_t n, i;
    if (session == NULL || output == NULL || output_capacity == 0U) return 0;
    if (!pmars_proto_line_valid(line, length)) return emit_error(session->has_seq ? session->last_seq : 0U,
                                                                 length > PMARS_PROTO_MAX_LINE ? "line_too_long" : "malformed_line",
                                                                 output, output_capacity);
    n = length - 1U;
    if (n >= sizeof(json)) return emit_error(session->has_seq ? session->last_seq : 0U, "line_too_long", output, output_capacity);
    (void)memcpy(json, line, n); json[n] = '\0';
    if (json[0] != '{' || json[n - 1U] != '}' || !crc_valid(json, n, NULL))
        return emit_error(session->has_seq ? session->last_seq : 0U, "bad_crc", output, output_capacity);
    if (!read_int(json, "v", &version) || version != 1)
        return emit_error(session->has_seq ? session->last_seq : 0U, "bad_version", output, output_capacity);
    if (!read_int(json, "seq", &seq_number) || seq_number < 0 || seq_number > UINT32_MAX)
        return emit_error(session->has_seq ? session->last_seq : 0U, "malformed_number", output, output_capacity);
    seq = (uint32_t)seq_number;
    if ((session->has_seq && seq <= session->last_seq) || !read_string(json, "type", type, sizeof(type)))
        return emit_error(seq, "bad_sequence_or_type", output, output_capacity);
    if (array_object_count(json, "tasks") > PMARS_CONTRACT_MAX_TASKS ||
        array_object_count(json, "contacts") > PMARS_CONTRACT_MAX_CONTACTS)
        return emit_error(seq, "bound_exceeded", output, output_capacity);

    if (strcmp(type, "hello") == 0 || strcmp(type, "hello_ack") == 0) {
        (void)snprintf(session->body, sizeof(session->body),
            "{\"contract_version\":1,\"firmware_version\":\"%s\",\"free_heap_bytes\":%" PRIu32 ",\"git_sha\":\"%s\",\"idf_version\":\"%s\",\"max_contacts\":%u,\"max_line\":%u,\"max_tasks\":%u,\"reset_reason\":\"%s\",\"seq\":%" PRIu32 ",\"stack_high_water_words\":%" PRIu32 ",\"target\":\"%s\",\"type\":\"hello_ack\",\"v\":1}",
            session->firmware_version, session->free_heap_bytes, session->git_sha,
            session->idf_version, PMARS_MAX_CONTACTS, PMARS_PROTO_MAX_LINE, PMARS_MAX_TASKS,
            session->reset_reason, seq, session->stack_high_water, session->target);
    } else if (strcmp(type, "reset") == 0) {
        pmars_state_t *state = &session->scratch_state;
        (void)memset(state, 0, sizeof(*state));
        state->energy_mj = INT64_C(1000000);
        state->storage_total_bytes = INT64_C(100000000);
        state->memory_available_bytes = INT64_C(100000000);
        state->compute_capacity_milli = 100000;
        state->throttle_fraction_milli = 1000;
        state->drain_horizon_ms = INT64_MAX;
        { pmars_config_t defaults = {300000, 90000};
          pmars_engine_init(&session->engine, state, &defaults, 0); }
        session->min_free_heap_bytes = session->free_heap_bytes;
        (void)snprintf(session->body, sizeof(session->body), "{\"seq\":%" PRIu32 ",\"type\":\"reset_ack\",\"v\":1}", seq);
    } else if (strcmp(type, "config") == 0) {
        pmars_state_t *state = &session->scratch_state;
        pmars_config_t cfg = session->engine.config;
        uint8_t rule_flag = 0U;
        uint8_t append_contacts = 0U;
        *state = session->engine.state;
        if (!read_int(json, "now_ms", &state->now_ms) ||
            !read_int(json, "energy_mj", &state->energy_mj) ||
            !read_int(json, "storage_used_bytes", &state->storage_used_bytes) ||
            !read_int(json, "storage_total_bytes", &state->storage_total_bytes) ||
            !read_int(json, "memory_available_bytes", &state->memory_available_bytes) ||
            !read_int(json, "compute_capacity_milli", &state->compute_capacity_milli) ||
            !read_int(json, "throttle_fraction_milli", &state->throttle_fraction_milli) ||
            !read_int(json, "processing_power_mw", &state->processing_power_mw) ||
            !read_int(json, "transmit_power_mw", &state->transmit_power_mw) ||
            !read_int(json, "store_power_mw", &state->store_power_mw) ||
            !read_int(json, "drain_horizon_ms", &state->drain_horizon_ms))
            return emit_error(seq, "malformed_number", output, output_capacity);
        (void)read_bool(json, "contacts_append", &append_contacts);
        if (!read_contacts(json, state, append_contacts != 0U))
            return emit_error(seq, "malformed_contacts", output, output_capacity);
        if (read_int(json, "store_horizon_ms", &value)) cfg.store_horizon_ms = value;
        if (read_int(json, "urgent_slack_ms", &value)) cfg.urgent_slack_ms = value;
        (void)read_bool(json, "rule", &rule_flag);
        pmars_engine_init(&session->engine, state, &cfg, rule_flag != 0U);
        (void)snprintf(session->body, sizeof(session->body), "{\"seq\":%" PRIu32 ",\"type\":\"config_ack\",\"v\":1}", seq);
    } else if (strcmp(type, "task_submit") == 0) {
        char id[PMARS_ID_BYTES];
        const char *task_key = strstr(json, "\"task\":{");
        const char *task_json = task_key == NULL ? NULL : task_key + 8;
        pmars_task_t *task = &session->scratch_task;
        (void)memset(task, 0, sizeof(*task));
        task->actual_output_bytes = PMARS_NO_OUTPUT;
        if (task_json == NULL || !read_string(task_json, "id", id, sizeof(id)) ||
            !read_int(task_json, "input_bytes", &task->input_bytes) ||
            !read_int(task_json, "payload_bytes", &task->payload_bytes) ||
            !read_int(task_json, "output_bytes_est", &task->output_bytes_est) ||
            !read_int(task_json, "mem_req_bytes", &task->mem_req_bytes) ||
            !read_int(task_json, "demand_milli", &task->demand_milli) ||
            !read_int(task_json, "base_proc_ms", &task->base_proc_ms) ||
            !read_int(task_json, "priority", &task->priority) ||
            !read_int(task_json, "value_milli", &task->value_milli) ||
            !read_int(task_json, "created_ms", &task->created_ms) ||
            !read_int(task_json, "deadline_ms", &task->deadline_ms))
            return emit_error(seq, "malformed_number", output, output_capacity);
        if (read_int(task_json, "actual_output_bytes", &value)) task->actual_output_bytes = value;
        (void)read_bool(task_json, "processed", &task->processed);
        for (i = 0; i < session->engine.task_count; ++i)
            if (!pmars_status_terminal(session->engine.statuses[i]) && strcmp(session->engine.tasks[i].id, id) == 0)
                return emit_error(seq, "duplicate_task_id", output, output_capacity);
        (void)strcpy(task->id, id);
        if (session->engine.active_count >= PMARS_MAX_TASKS) {
            session->engine.rejected_count++;
            return emit_error(seq, "queue_full", output, output_capacity);
        }
        if (!pmars_engine_admit(&session->engine, task)) return emit_error(seq, "admission_rejected", output, output_capacity);
        (void)snprintf(session->body, sizeof(session->body),
            "{\"accepted\":true,\"seq\":%" PRIu32 ",\"status\":\"pending\",\"task_id\":\"%s\",\"type\":\"event\",\"v\":1}", seq, task->id);
    } else if (strcmp(type, "decide") == 0 || strcmp(type, "tick") == 0) {
        uint32_t count = 0U;
        pmars_decision_t decision;
        pmars_config_t cfg = session->engine.config;
        for (i = 0; i < session->engine.task_count; ++i) {
            if (session->engine.statuses[i] == PMARS_TASK_PENDING || session->engine.statuses[i] == PMARS_TASK_PROCESSED) {
                session->engine.scratch_tasks[count] = session->engine.tasks[i];
                count++;
            }
        }
        if (key_value(json, "now_ms") != NULL) {
            if (!read_int(json, "now_ms", &value) || value < session->engine.state.now_ms)
                return emit_error(seq, "malformed_number", output, output_capacity);
            session->engine.state.now_ms = value;
        }
        if (pmars_decide(&session->engine.state, session->engine.scratch_tasks, count, &cfg, session->engine.rule, &decision) != 0)
            return emit_error(seq, "decision_failed", output, output_capacity);
        if (strcmp(type, "tick") == 0) {
            int step_result = pmars_engine_step(&session->engine);
            const char *action = decision.action == PMARS_PROCESS ? "PROCESS" : decision.action == PMARS_STORE ? "STORE" :
                                 decision.action == PMARS_TRANSMIT ? "TRANSMIT" : "IDLE";
            const char *status = "none";
            const char *terminal = "none";
            char task_id[PMARS_ID_BYTES] = "";
            for (i = 0U; i < session->engine.task_count; ++i) {
                if (decision.task_id[0] != '\0' && strcmp(session->engine.tasks[i].id, decision.task_id) == 0) {
                    (void)memcpy(task_id, session->engine.tasks[i].id, sizeof(task_id));
                    status = status_name(session->engine.statuses[i]);
                    if (pmars_status_terminal(session->engine.statuses[i])) terminal = status;
                    break;
                }
            }
            (void)snprintf(session->body, sizeof(session->body),
                "{\"action\":\"%s\",\"energy_mj\":%lld,\"now_ms\":%lld,\"seq\":%" PRIu32 ",\"status\":\"%s\",\"storage_used_bytes\":%lld,\"task_id\":\"%s\",\"terminal_outcome\":\"%s\",\"type\":\"event\",\"v\":1}",
                action, (long long)session->engine.state.energy_mj, (long long)session->engine.state.now_ms,
                seq, status, (long long)session->engine.state.storage_used_bytes, task_id, terminal);
            if (step_result < 0) return emit_error(seq, "step_failed", output, output_capacity);
        } else {
            const char *action = decision.action == PMARS_PROCESS ? "PROCESS" : decision.action == PMARS_STORE ? "STORE" :
                                 decision.action == PMARS_TRANSMIT ? "TRANSMIT" : "IDLE";
            (void)snprintf(session->body, sizeof(session->body), "{\"action\":\"%s\",\"seq\":%" PRIu32 ",\"task_id\":\"%s\",\"type\":\"decision\",\"v\":1}",
                           action, seq, decision.task_id);
        }
    } else if (strcmp(type, "event") == 0) {
        if (session->engine.event_count == 0U) {
            (void)snprintf(session->body, sizeof(session->body), "{\"seq\":%" PRIu32 ",\"type\":\"ack\",\"v\":1}", seq);
        } else {
            const pmars_event_t *event = &session->engine.events[session->engine.event_head];
            (void)snprintf(session->body, sizeof(session->body),
                "{\"event_kind\":\"%s\",\"seq\":%" PRIu32 ",\"task_id\":\"%s\",\"task_index\":%u,\"time_ms\":%lld,\"type\":\"event\",\"v\":1}",
                event_name(event->kind), seq, event->task_id, (unsigned)event->task_index,
                (long long)event->time_ms);
            session->engine.event_head = (session->engine.event_head + 1U) % PMARS_MAX_EVENTS;
            session->engine.event_count--;
        }
    } else if (strcmp(type, "result") == 0) {
        for (i = 0U; i < session->engine.task_count; ++i) {
            if (!pmars_status_terminal(session->engine.statuses[i])) {
                if (session->engine.state.storage_used_bytes >= session->engine.tasks[i].payload_bytes)
                    session->engine.state.storage_used_bytes -= session->engine.tasks[i].payload_bytes;
                session->engine.statuses[i] = PMARS_TASK_UNFINISHED;
                if (session->engine.active_count > 0U) session->engine.active_count--;
                session->engine.unfinished_count++;
            }
        }
        (void)snprintf(session->body, sizeof(session->body),
            "{\"completed\":%" PRIu32 ",\"dropped_events\":%" PRIu32 ",\"expired\":%" PRIu32 ",\"free_heap_bytes\":%" PRIu32 ",\"late\":%" PRIu32 ",\"min_free_heap_bytes\":%" PRIu32 ",\"rejected\":%" PRIu32 ",\"seq\":%" PRIu32 ",\"stack_high_water_words\":%" PRIu32 ",\"type\":\"result\",\"unfinished\":%" PRIu32 ",\"v\":1}",
            session->engine.completed_count, session->engine.events_dropped, session->engine.expired_count,
            session->free_heap_bytes, session->engine.late_count, session->min_free_heap_bytes,
            session->engine.rejected_count, seq, session->stack_high_water,
            session->engine.unfinished_count);
    } else {
        return emit_error(seq, "unknown_type", output, output_capacity);
    }
    session->last_seq = seq;
    session->has_seq = 1U;
    return emit_body(session->body, output, output_capacity);
}

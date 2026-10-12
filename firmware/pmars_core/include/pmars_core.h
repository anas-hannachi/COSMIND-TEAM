#ifndef PMARS_CORE_H
#define PMARS_CORE_H
#include <stdint.h>
#include "../../../contract/limits.h"

#define PMARS_IDLE_QUANTUM_MS 5000 /* matches simulation.py IDLE_QUANTUM_S = 5.0 */
#define PMARS_MAX_TASKS PMARS_CONTRACT_MAX_TASKS
#define PMARS_MAX_CONTACTS PMARS_CONTRACT_MAX_CONTACTS
#define PMARS_MAX_EVENTS 128U
#define PMARS_ID_BYTES 16U
#define PMARS_NO_OUTPUT INT64_C(-1)

typedef enum { PMARS_IDLE = 0, PMARS_PROCESS = 1, PMARS_STORE = 2, PMARS_TRANSMIT = 3 } pmars_action_t;
typedef struct { int64_t start_ms, end_ms, bps_start, bps_end, latency_ms; } pmars_contact_t;
typedef struct {
    char id[PMARS_ID_BYTES];
    int64_t input_bytes, payload_bytes, output_bytes_est, actual_output_bytes;
    int64_t mem_req_bytes, demand_milli, base_proc_ms, priority, value_milli;
    int64_t created_ms, deadline_ms;
    uint8_t processed;
} pmars_task_t;
typedef struct {
    int64_t now_ms, energy_mj, storage_used_bytes, storage_total_bytes;
    int64_t memory_available_bytes, compute_capacity_milli, throttle_fraction_milli;
    int64_t processing_power_mw, transmit_power_mw, store_power_mw, drain_horizon_ms;
    pmars_contact_t contacts[PMARS_MAX_CONTACTS];
    uint32_t contact_count;
} pmars_state_t;
typedef struct { int64_t store_horizon_ms, urgent_slack_ms; } pmars_config_t;
typedef struct { pmars_action_t action; char task_id[PMARS_ID_BYTES]; uint16_t reason_code; } pmars_decision_t;
typedef enum {
    PMARS_EVENT_ADMIT = 1, PMARS_EVENT_REJECT, PMARS_EVENT_PROCESS_START,
    PMARS_EVENT_PROCESSED, PMARS_EVENT_STORE, PMARS_EVENT_TRANSMIT_START,
    PMARS_EVENT_TRANSMITTED, PMARS_EVENT_COMPLETED, PMARS_EVENT_LATE,
    PMARS_EVENT_EXPIRED, PMARS_EVENT_FAILED
} pmars_event_kind_t;
typedef struct { pmars_event_kind_t kind; uint16_t task_index; int64_t time_ms; char task_id[PMARS_ID_BYTES]; } pmars_event_t;
typedef enum {
    PMARS_TASK_PENDING = 0, PMARS_TASK_PROCESSED, PMARS_TASK_COMPLETED,
    PMARS_TASK_LATE, PMARS_TASK_EXPIRED, PMARS_TASK_REJECTED,
    PMARS_TASK_UNFINISHED, PMARS_TASK_FAILED
} pmars_task_status_t;
typedef struct {
    pmars_state_t state;
    pmars_config_t config;
    pmars_task_t tasks[PMARS_MAX_TASKS];
    /* Static engine-owned selector workspace keeps large copies off task stacks. */
    pmars_task_t scratch_tasks[PMARS_MAX_TASKS];
    pmars_task_status_t statuses[PMARS_MAX_TASKS];
    uint32_t task_count;
    uint32_t active_count;
    uint32_t completed_count, late_count, expired_count, rejected_count, failed_count, unfinished_count;
    uint32_t events_dropped;
    pmars_event_t events[PMARS_MAX_EVENTS];
    uint32_t event_head, event_count;
    uint8_t rule;
} pmars_engine_t;

/* All quantities use contract units; loops are bounded by the constants above. */
int pmars_transfer_time_ms(int64_t size_bytes, int64_t start_ms, const pmars_state_t *state, int64_t *duration_ms);
int pmars_can_process(const pmars_task_t *task, const pmars_state_t *state, int require_future_delivery);
int pmars_can_transmit(const pmars_task_t *task, const pmars_state_t *state, int require_deadline);
int pmars_plan_candidates(const pmars_task_t *task, const pmars_state_t *state, const pmars_config_t *config);
int pmars_decide(const pmars_state_t *state, const pmars_task_t *tasks, uint32_t count,
                 const pmars_config_t *config, int rule, pmars_decision_t *out);
void pmars_engine_init(pmars_engine_t *engine, const pmars_state_t *state,
                       const pmars_config_t *config, int rule);
int pmars_engine_admit(pmars_engine_t *engine, const pmars_task_t *task);
int pmars_engine_step(pmars_engine_t *engine);
int pmars_status_terminal(pmars_task_status_t status);
#endif

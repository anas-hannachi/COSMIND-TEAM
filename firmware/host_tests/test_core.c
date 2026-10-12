#include "pmars_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    pmars_state_t s = {0};
    pmars_config_t c = {300000, 90000};
    pmars_task_t t[97] = {0};
    pmars_decision_t d;
    pmars_engine_t engine;
    s.energy_mj = INT64_C(1000000); s.storage_total_bytes = 10000; s.memory_available_bytes = 10000;
    s.compute_capacity_milli = 100000; s.throttle_fraction_milli = 1000;
    s.processing_power_mw = 100; s.transmit_power_mw = 100; s.drain_horizon_ms = 100000;
    s.contact_count = 1; s.contacts[0] = (pmars_contact_t){0, 20000, 1000000, 1000000, 0};
    (void)strcpy(t[0].id, "later"); t[0].deadline_ms = 200; t[0].priority = 1; t[0].value_milli = 100;
    t[0].input_bytes = 100; t[0].payload_bytes = 100; t[0].output_bytes_est = 50; t[0].actual_output_bytes = PMARS_NO_OUTPUT;
    t[0].mem_req_bytes = 10; t[0].demand_milli = 100; t[0].base_proc_ms = 10;
    (void)strcpy(t[1].id, "first"); t[1].deadline_ms = 100; t[1].priority = 2; t[1].value_milli = 100;
    t[1].input_bytes = 100; t[1].payload_bytes = 100; t[1].output_bytes_est = 50; t[1].actual_output_bytes = PMARS_NO_OUTPUT;
    t[1].mem_req_bytes = 10; t[1].demand_milli = 100; t[1].base_proc_ms = 10;
    assert(pmars_decide(&s, t, 2, &c, 0, &d) == 0);
    assert(d.action == PMARS_TRANSMIT && strcmp(d.task_id, "first") == 0);
    assert(pmars_decide(&s, t, 2, &c, 1, &d) == 0);
    assert(d.action == PMARS_TRANSMIT && strcmp(d.task_id, "first") == 0);
    (void)strcpy(t[96].id, "extra"); t[96].deadline_ms = 1;
    assert(pmars_decide(&s, t, 97, &c, 0, &d) == 0);
    assert(pmars_transfer_time_ms(INT64_MAX, 0, &s, &s.now_ms) == 0);
    s.now_ms = 0; s.energy_mj = 1000000; s.storage_used_bytes = 0;
    s.contacts[0] = (pmars_contact_t){20000, 30000, 1000000, 1000000, 0};
    (void)memset(&t[0], 0, sizeof(t[0]));
    (void)strcpy(t[0].id, "lifecycle"); t[0].input_bytes = 10; t[0].payload_bytes = 10;
    t[0].output_bytes_est = 5; t[0].actual_output_bytes = PMARS_NO_OUTPUT;
    t[0].deadline_ms = 60000; t[0].mem_req_bytes = 1; t[0].demand_milli = 1;
    t[0].base_proc_ms = 10;
    pmars_engine_init(&engine, &s, &c, 0);
    assert(pmars_engine_admit(&engine, &t[0]) == 1);
    assert(pmars_engine_step(&engine) == 1 && engine.statuses[0] == PMARS_TASK_PROCESSED);
    /* STORE waits in IDLE_QUANTUM (5 s) steps, like the simulator, until the contact at 20 s opens, then TRANSMIT. */
    assert(pmars_engine_step(&engine) == 1 && engine.state.now_ms == 10 + PMARS_IDLE_QUANTUM_MS);
    {
        uint32_t guard;
        for (guard = 0U; guard < 10U && engine.statuses[0] != PMARS_TASK_COMPLETED; ++guard)
            assert(pmars_engine_step(&engine) == 1);
        assert(guard <= 5U && engine.statuses[0] == PMARS_TASK_COMPLETED);
        assert(engine.state.now_ms >= 20000 && engine.state.now_ms < 30000);
    }
    assert(engine.state.storage_used_bytes == 0 && engine.state.energy_mj >= 0);
    assert(pmars_engine_step(&engine) == 0 && engine.statuses[0] == PMARS_TASK_COMPLETED);
    s.now_ms = 0; s.energy_mj = 1000000; s.storage_used_bytes = 0;
    s.contacts[0] = (pmars_contact_t){0, 100000, 100000000, 100000000, 0};
    pmars_engine_init(&engine, &s, &c, 0);
    for (uint32_t n = 0; n < 150U; ++n) {
        (void)memset(&t[0], 0, sizeof(t[0]));
        (void)snprintf(t[0].id, sizeof(t[0].id), "burst%03u", n);
        t[0].input_bytes = 1; t[0].payload_bytes = 1; t[0].output_bytes_est = 1;
        t[0].actual_output_bytes = PMARS_NO_OUTPUT; t[0].deadline_ms = 90000;
        assert(pmars_engine_admit(&engine, &t[0]) == 1);
        assert(pmars_engine_step(&engine) == 1);
        assert(engine.active_count == 0U);
    }
    assert(engine.task_count <= PMARS_MAX_TASKS && engine.completed_count == 150U);
    return 0;
}

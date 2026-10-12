#ifndef PMARS_PROTO_H
#define PMARS_PROTO_H
#include <stddef.h>
#include <stdint.h>
#include "pmars_core.h"
#include "../../../../../contract/limits.h"

#define PMARS_PROTO_MAX_LINE PMARS_CONTRACT_MAX_LINE
#define PMARS_PROTO_OUTPUT_BYTES 512U
typedef struct {
    pmars_engine_t engine;
    pmars_state_t scratch_state;
    pmars_task_t scratch_task;
    char body[PMARS_PROTO_OUTPUT_BYTES];
    char firmware_version[24], git_sha[41], target[12], idf_version[24], reset_reason[20];
    uint32_t free_heap_bytes, min_free_heap_bytes, stack_high_water;
    uint32_t last_seq;
    uint8_t has_seq;
} pmars_proto_session_t;

void pmars_proto_init(pmars_proto_session_t *session);
void pmars_proto_set_platform(pmars_proto_session_t *session, const char *target,
                              const char *idf_version, const char *reset_reason,
                              uint32_t stack_high_water, uint32_t free_heap_bytes);
int pmars_proto_line_valid(const char *line, size_t length);
int pmars_proto_handle(pmars_proto_session_t *session, const char *line, size_t length,
                       char *output, size_t output_capacity);
#endif

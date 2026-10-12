#include "esp_task_wdt.h"
#include "esp_err.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "pmars_hal.h"
#include "pmars_proto.h"
#include <stdio.h>

static pmars_proto_session_t session;
static char console_line[PMARS_PROTO_MAX_LINE + 1U];
static char console_output[PMARS_PROTO_OUTPUT_BYTES];

void app_main(void) {
    size_t length = 0U;
    int ch, oversized = 0;
    char reset_reason[20];
    pmars_proto_init(&session);
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    (void)snprintf(reset_reason, sizeof(reset_reason), "reason_%d", (int)esp_reset_reason());
    for (;;) {
        uint32_t stack_words = (uint32_t)uxTaskGetStackHighWaterMark(NULL);
        const char *target =
#if CONFIG_IDF_TARGET_ESP32S3
            "esp32s3";
#elif CONFIG_IDF_TARGET_ESP32
            "esp32";
#else
            "unknown";
#endif
        pmars_proto_set_platform(&session, target, esp_get_idf_version(), reset_reason,
                                 stack_words, esp_get_free_heap_size());
        (void)pmars_hal_clock_ms();
        (void)pmars_hal_temperature_mdc();
        (void)esp_task_wdt_reset();
        ch = getchar();
        if (ch == EOF) { vTaskDelay(1); continue; } /* exactly one tick: pdMS_TO_TICKS(1) is 0 at the default 100 Hz tick rate */
        if (ch == '\n') {
            if (length < PMARS_PROTO_MAX_LINE) console_line[length++] = (char)ch;
            else { oversized = 1; console_line[PMARS_PROTO_MAX_LINE] = '\n'; }
            size_t passed = oversized ? PMARS_PROTO_MAX_LINE + 1U : length;
            if (pmars_proto_handle(&session, console_line, passed, console_output, sizeof(console_output))) {
                fputs(console_output, stdout);
                fflush(stdout);
            }
            length = 0U; oversized = 0;
        } else if (length < PMARS_PROTO_MAX_LINE) console_line[length++] = (char)ch;
        else oversized = 1;
    }
}

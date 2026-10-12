#include "pmars_hal.h"
#include "esp_timer.h"
int64_t pmars_hal_clock_ms(void) { return esp_timer_get_time() / 1000; }
int32_t pmars_hal_temperature_mdc(void) { return 25000; }

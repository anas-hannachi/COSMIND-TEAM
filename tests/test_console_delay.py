"""The console loop must sleep at least one real FreeRTOS tick.

pdMS_TO_TICKS(1) evaluates to 0 ticks at the ESP-IDF default 100 Hz tick rate, and vTaskDelay(0) only yields to
equal-priority tasks, which can starve IDLE0 and trip the task watchdog.
"""

import re
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "firmware" / "esp32" / "main" / "main.c"


def test_console_idle_delay_is_never_zero_ticks():
    delays = [expr.replace(" ", "") for expr in re.findall(r"vTaskDelay\(([^;]*)\);", MAIN.read_text(encoding="utf-8"))]
    assert delays, "the console loop must yield with vTaskDelay when no input is available"
    assert "pdMS_TO_TICKS(1)" not in delays
    assert "0" not in delays

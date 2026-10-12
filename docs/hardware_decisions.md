# Hardware decisions and provenance

All ESP32 profile values are assumptions. No board data has been collected. The firmware target defaults to
ESP32-S3 and uses internal SRAM only; PSRAM is optional for bounded workload buffers.

| Decision | Current default | Owner | Status |
|---|---|---|---|
| Exact board/SKU | ESP32-S3 development board; SKU TBD | hardware team | OPEN |
| PSRAM size | 0 MB required; preferably 8 MB optional | hardware team | OPEN |
| Camera | No camera | hardware team | OPEN |
| Power monitor | None on board; host-side input monitor TBD | hardware team | OPEN |
| Temperature method | Emulated default; on-chip S3 or external sensor to be selected | hardware team | OPEN |
| Communications claim | USB serial protocol; any link is emulated | hardware team | OPEN |
| Success thresholds | Agree after board and workloads selected | hardware team | OPEN |

## Documentation check

Implementation notes use ESP-IDF v5.3.2 documentation as the verified reference. ESP32-S3 has 512 KB
on-chip SRAM and a single-precision FPU; classic ESP32 has 520 KB SRAM. Free heap available to this
application is smaller and depends on the board, SDK configuration, and reserved memory. ESP-IDF v5.3.2
documents an ESP32-S3 internal temperature sensor and warns that it measures chip temperature rather than
ambient. The v5 API uses `driver/temperature_sensor.h` (component `esp_driver_tsens`). USB Serial/JTAG and
UART console selections are ESP-IDF options. Classic ESP32 uses the emulated temperature backend until its
target-specific driver is selected.
All policy arithmetic is integer. Firmware uses fixed bounded storage and reports actual free heap at runtime.
No static RAM or flash budget is claimed until `idf.py size` has run with the selected board configuration.

The v3 manifests record legacy raw-byte profile hashes (including Windows CRLF on the original machine).
New profile hashes normalize CRLF to LF; `model_profile_sha256_raw` preserves the legacy behavior.

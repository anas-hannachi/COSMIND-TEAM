# ESP32 measurement protocol

Choose and record board SKU/revision, target, PSRAM, ESP-IDF version, CPU MHz, supply voltage, USB/UART
mode, and room conditions. Use an identified external input-side power monitor and record model, resolution,
sample rate, bandwidth, shunt, calibration record, wiring, and limitations. The board does not measure its
own input energy. Record ambient temperature separately from on-chip/external readings. Capture internal
and PSRAM free/peak heap separately, software throttle state, reset reason, and failures.

Warm up each configuration and retain at least 30 trials. Keep every raw observation, including failures,
throttling, resets, and outliers. Raw files are append-only; summaries and comparisons go to separate
derived files with the raw SHA-256. Record serial or Wi-Fi throughput and latency only when that transport
is actually used. Wi-Fi software emulation is not radio validation. Do not claim a link mode was tested if
the firmware uses the emulated backend.

Use `docs/calibration_measurements.csv` for trials and record `action` as idle/process/store/transmit. Retain at least 30 successful trials per action and configuration. Use `docs/calibration_timeseries_template.csv` for temperature samples with increasing `sample_index` and `t_ms` per `run_id`. After a stable ambient soak, log fixed-interval temperature under sustained process, transmit, idle, and store load. Calibration derives median adjacent temperature/time slopes and an ordinary least squares fit of processing seconds versus input bytes. Never enter modeled quantities as measured values. Report hardware measurements, simulator output, and extrapolation separately.

# Protocol loopback and serial replay

The HIL driver launches the native `pmars_host_stdio` JSONL executable and sends reset, configuration, task submissions, and decision requests through the versioned CRC-checked codec. It compares the C protocol decisions with Python policy decisions throughout a simulator run. `--port` uses pyserial 3.5 for a serial endpoint; the PTY regression test exercises that host transport. Both modes are host emulation and do not establish radio behavior or hardware performance.

```sh
python -m pmars_simulation.hil.driver --loopback --scenario bench_normal --scheduler edf --seeds 100-104
python -m pmars_simulation.hil.driver --loopback --scenario bench_normal --scheduler rule --seeds 100-104
python -m pmars_simulation.hil.driver --port /dev/ttyUSB0 --baud 115200 --scenario bench_normal --scheduler edf --seeds 100-104
```

The report records the selected transport, decision mismatch counts, and run summaries. Loopback builds the native executable on demand; a serial endpoint must run the matching newline-delimited protocol. Firmware ESP-IDF build and board verification are tracked separately in the prototype guide.

# Host protocol loopback

The native stdio executable parses JSONL and calls the portable C core.
Host loopback only; this is not a hardware test.

- bench_normal edf seed 100: 109 decisions, C/Python mismatches 0, integer/original-float mismatches 0, PROCESS 25, STORE 26, TRANSMIT 42, completed 42, full lifecycle tasks 9.
- bench_normal edf seed 101: 101 decisions, C/Python mismatches 0, integer/original-float mismatches 0, PROCESS 24, STORE 25, TRANSMIT 41, completed 41, full lifecycle tasks 4.
- bench_normal edf seed 102: 108 decisions, C/Python mismatches 0, integer/original-float mismatches 0, PROCESS 26, STORE 26, TRANSMIT 41, completed 41, full lifecycle tasks 10.
- bench_normal edf seed 103: 103 decisions, C/Python mismatches 0, integer/original-float mismatches 0, PROCESS 22, STORE 29, TRANSMIT 40, completed 40, full lifecycle tasks 9.
- bench_normal edf seed 104: 99 decisions, C/Python mismatches 0, integer/original-float mismatches 0, PROCESS 22, STORE 26, TRANSMIT 42, completed 42, full lifecycle tasks 11.

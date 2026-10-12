# pmars.contract.v1

The contract is the integer-only boundary between the Python reference and embedded C. MB is decimal
(1,000,000 bytes). Times are milliseconds, sizes bytes, energy mJ, power mW, temperature milli-degC,
bandwidth bits/s, and scaled scalar metadata uses thousandths. Python integers are signed 64 bit in the
wire model; firmware time may wrap at signed 32 bit only after a reset (sessions must be shorter than
2^31 ms and compare times by signed subtraction).

Task ids are 1–15 ASCII bytes, task kinds are metadata labels, and `science_payload` remains null. The
contract omits freshness decay and estimated processing energy. Tie order is deadline ascending,
priority descending, value descending, then byte-wise id ascending. The simulator instead orders the
third key by exponentially freshness-decayed value; that is the known policy fidelity divergence.

JSON Lines messages have `v`, monotonic `seq`, and CRC-32 over the canonical sorted-key compact JSON
object excluding `crc`. Lines are at most 512 bytes. Bounds are MAX_TASKS=96, MAX_CONTACTS=16,
MAX_LINE=512. A decision with more than 96 pending tasks evaluates only the 96 earliest deadlines,
breaking ties by priority descending, value descending, then byte-wise id ascending. Python and C use
this same bound; it does not claim parity with the original simulator's unbounded queue. Invalid
framing, schema, CRC, version, or bounds produce a structured error and do not change state. PROCESS
replaces the resident input payload with measured output when present, otherwise
estimated output. STORE waits up to 5000 ms or the next deadline. TRANSMIT is one-contact atomic and
finishes COMPLETED if finish <= deadline, otherwise LATE. Expiry is inclusive (`now >= deadline`).
Terminal outcomes are completed, late, expired, rejected, unfinished, and failed. Resource reservations
are made before an action; unused reservations are released on completion or failure. An action crossing
a deadline is recorded late/expired after its atomic completion; it is not preempted.

Each task carries `payload_bytes` (the current resident size) and `processed` (whether PROCESS has already
run). Initially the payload equals `input_bytes`. PROCESS changes it to `actual_output_bytes` when supplied
by a workload backend, otherwise `output_bytes_est`, and sets `processed=true`; processed tasks cannot be
processed again. Delivery and STORE planning use the current payload. Each contact tuple contains start/end
milliseconds, start/end bps, and `latency_ms`; latency is added to transfer duration. STORE planning searches
from `now_ms` and requires a strictly later start. PROCESS duration is
`ceil(base_proc_ms * 1000 / throttle_fraction_milli)`.

`codec.py` implements bounded framing and CRC. Task JSON uses the dataclass field names in
`pmars_simulation.contract.models`; message schemas in `schema/` describe the common envelopes.

The portable C handler is a bounded, `strstr`-based scanner rather than a general JSON parser. It does not
validate the complete JSON grammar or reject unknown keys, and duplicate keys use the first matching substring,
unlike Python's decoder which retains the last key. CRC-valid hostile input can therefore be interpreted differently
from Python. Escaped quote-like key text remains escaped in the wire string and is not treated as an envelope key
in the tested case. The protocol assumes a trusted host endpoint; do not expose this parser directly to an untrusted
network. `tests/test_protocol_scanner_limits.py` pins unknown-key, duplicate-key, and escaped-key-text behavior so
a future parser replacement must deliberately update these compatibility tests.

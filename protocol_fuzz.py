"""CRC-valid mutation harness for the portable C protocol parser."""

import collections
import os
import random
import subprocess
import sys
import zlib


random.seed(991)


def line(body):
    crc = zlib.crc32(body.encode("latin1")) & 0xFFFFFFFF
    return '{"crc":%d,%s' % (crc, body[1:])


TASK = ('{"id":"t1","input_bytes":1000,"payload_bytes":1000,"output_bytes_est":500,'
        '"mem_req_bytes":10,"demand_milli":100,"base_proc_ms":100,"priority":3,'
        '"value_milli":1000,"created_ms":0,"deadline_ms":60000}')
BASES = [
    '{"seq":%d,"type":"hello","v":1}',
    '{"contacts":[[0,50000,256000,256000,50],[90000,110000,256000,256000,50]],'
    '"drain_horizon_ms":900000,"energy_mj":900000,"memory_available_bytes":300000,'
    '"now_ms":0,"compute_capacity_milli":100000,"processing_power_mw":600,'
    '"rule":false,"seq":%d,"store_power_mw":300,"storage_total_bytes":256000,'
    '"storage_used_bytes":0,"throttle_fraction_milli":1000,"transmit_power_mw":800,'
    '"type":"config","v":1}',
    '{"seq":%d,"task":' + TASK + ',"type":"task_submit","v":1}',
    '{"now_ms":5,"seq":%d,"type":"decide","v":1}',
    '{"seq":%d,"type":"tick","v":1}',
    '{"seq":%d,"type":"reset","v":1}',
]
JUNK = ["[", "{", "]", "}", '"', "\\", "9" * 30, "-", "-9223372036854775809",
        "99999999999999999999", ",", ":", "null", "true", "1e5", "\x01", "\x7f",
        "[[[[[[[[", '"tasks":[', '"contacts":[[1,2,3', '"id":"', "\xff"]


def mutate(value):
    chars = list(value)
    for _ in range(random.randint(1, 4)):
        choice = random.random()
        index = random.randrange(len(chars))
        if choice < 0.3:
            chars[index] = random.choice(JUNK)
        elif choice < 0.5:
            chars.insert(index, random.choice(JUNK))
        elif choice < 0.7:
            del chars[index:index + random.randint(1, 12)]
        elif choice < 0.85:
            chars[index] = chr(random.randrange(256))
        else:
            chars = chars[:index]
        if not chars:
            chars = ["{"]
    return "".join(chars)


def main():
    count = int(sys.argv[1])
    messages, sequence = [], 1
    for _ in range(count):
        base = random.choice(BASES)
        base = base % sequence if "%d" in base else base
        sequence += 1
        if random.random() < 0.15:
            sequence = max(1, sequence - random.randint(0, 3))
        mutated = mutate(base)
        if not mutated.startswith("{"):
            mutated = "{" + mutated
        message = line(mutated) if random.random() < 0.9 else mutated
        if len(message) > 520 and random.random() < 0.7:
            message = message[:random.randint(500, 520)]
        messages.append(message)
    binary = os.environ.get("PMARS_HOST_BINARY", "./build/pmars_host_asan")
    env = dict(os.environ)
    runtime_path = env.pop("PMARS_HOST_LD_LIBRARY_PATH", None)
    if runtime_path:
        env["LD_LIBRARY_PATH"] = runtime_path
    result = subprocess.run([binary], input=("\n".join(messages) + "\n").encode("latin1"),
                            capture_output=True, timeout=300, env=env)
    print(f"lines: {count} exit code: {result.returncode} stderr bytes: {len(result.stderr)}")
    if result.stderr:
        print(result.stderr.decode("latin1")[:1800])
    replies = result.stdout.decode("latin1").splitlines()
    counts = collections.Counter()
    for reply in replies:
        if '"code":"' in reply:
            counts["error:" + reply.split('"code":"', 1)[1].split('"', 1)[0]] += 1
        elif '"type":"' in reply:
            counts[reply.split('"type":"', 1)[1].split('"', 1)[0]] += 1
    print("reply types:", counts.most_common(9))
    if result.returncode != 0 or result.stderr:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

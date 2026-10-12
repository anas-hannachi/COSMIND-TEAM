"""ctypes declarations matching firmware/pmars_core/include/pmars_core.h."""

import ctypes


class CContact(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
                ("start_ms", "end_ms", "bps_start", "bps_end", "latency_ms")]


class CTask(ctypes.Structure):
    _fields_ = [("id", ctypes.c_char * 16)] + [(name, ctypes.c_int64) for name in (
        "input_bytes", "payload_bytes", "output_bytes_est", "actual_output_bytes", "mem_req_bytes",
        "demand_milli", "base_proc_ms", "priority", "value_milli", "created_ms", "deadline_ms",
    )] + [("processed", ctypes.c_uint8)]


class CState(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in (
        "now_ms", "energy_mj", "storage_used_bytes", "storage_total_bytes", "memory_available_bytes",
        "compute_capacity_milli", "throttle_fraction_milli", "processing_power_mw", "transmit_power_mw",
        "store_power_mw", "drain_horizon_ms",
    )] + [("contacts", CContact * 16), ("contact_count", ctypes.c_uint32)]


class CConfig(ctypes.Structure):
    _fields_ = [("store_horizon_ms", ctypes.c_int64), ("urgent_slack_ms", ctypes.c_int64)]


class CDecision(ctypes.Structure):
    _fields_ = [("action", ctypes.c_int), ("task_id", ctypes.c_char * 16),
                ("reason_code", ctypes.c_uint16)]

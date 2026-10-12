"""Conversions to contract units (MB is decimal, 1 MB = 1,000,000 bytes)."""

import math


def size_bytes(mb: float) -> int:
    """Round sizes to nearest byte."""
    return int(math.floor(mb * 1_000_000 + 0.5))


def duration_ms(seconds: float) -> int:
    """Round durations upward so transfer and processing estimates are conservative."""
    return math.ceil(seconds * 1000)


def energy_mj(joules: float) -> int:
    """Round energy costs upward; never understate a cost."""
    return math.ceil(joules * 1000)


def capacity_bytes(mb: float) -> int:
    """Round available capacities downward."""
    return math.floor(mb * 1_000_000)


def resident_bytes(mb: float) -> int:
    """Use payload rounding for resident storage accounting to keep states consistent."""
    return size_bytes(mb)


def deadline_ms(seconds: float) -> int:
    """Round deadlines downward so the contract never extends a deadline."""
    return math.floor(seconds * 1000)


def scaled_milli(value: float) -> int:
    """Round nonnegative scalar metadata to nearest thousandth."""
    return int(math.floor(value * 1000 + 0.5))

"""Bounded JSONL framing and CRC-32 helpers for pmars.contract.v1."""

import json
import zlib

from .limits import MAX_CONTACTS, MAX_LINE, MAX_TASKS

CONTRACT_VERSION = 1
MESSAGE_TYPES = {
    "hello", "hello_ack", "config", "config_ack", "task_submit", "tick", "decide",
    "decision", "reset", "reset_ack", "error", "event", "result", "ack",
}


class ContractError(ValueError):
    """Invalid or oversized contract message."""


def encode_message(message: dict, seq: int) -> bytes:
    if "v" in message or "seq" in message or "crc" in message:
        raise ContractError("reserved_envelope_field")
    payload = {"v": CONTRACT_VERSION, "seq": seq, **message}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["crc"] = zlib.crc32(canonical.encode("utf-8")) & 0xFFFFFFFF
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(line) > MAX_LINE:
        raise ContractError("line_too_long")
    return line


def decode_message(line: bytes) -> dict:
    if len(line) > MAX_LINE:
        raise ContractError("line_too_long")
    try:
        message = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid_json") from exc
    if not isinstance(message, dict) or type(message.get("v")) is not int or message.get("v") != CONTRACT_VERSION:
        raise ContractError("bad_version")
    if type(message.get("seq")) is not int or not 0 <= message["seq"] <= 0xFFFFFFFF:
        raise ContractError("invalid_sequence")
    if message.get("type") not in MESSAGE_TYPES:
        raise ContractError("unknown_type")
    tasks, contacts = message.get("tasks", []), message.get("contacts", [])
    if not isinstance(tasks, list) or not isinstance(contacts, list):
        raise ContractError("invalid_bounds_field")
    if len(tasks) > MAX_TASKS or len(contacts) > MAX_CONTACTS:
        raise ContractError("bound_exceeded")
    for contact in contacts:
        if (not isinstance(contact, (list, tuple)) or len(contact) != 5 or
                any(type(value) is not int for value in contact)):
            raise ContractError("malformed_contacts")
    task_ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    if len(task_ids) != len(tasks) or any(not isinstance(task_id, str) for task_id in task_ids):
        raise ContractError("invalid_task")
    if len(task_ids) != len(set(task_ids)):
        raise ContractError("duplicate_task_id")

    def validate_numbers(value):
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return
        if isinstance(value, float):
            raise ContractError("malformed_number")
        if isinstance(value, int):
            if not -(1 << 63) <= value < (1 << 63):
                raise ContractError("malformed_number")
            return
        if isinstance(value, list):
            for item in value:
                validate_numbers(item)
        elif isinstance(value, dict):
            for item in value.values():
                validate_numbers(item)

    validate_numbers(message)
    crc = message.pop("crc", None)
    canonical = json.dumps(message, sort_keys=True, separators=(",", ":"))
    if crc != zlib.crc32(canonical.encode("utf-8")) & 0xFFFFFFFF:
        raise ContractError("bad_crc")
    return message

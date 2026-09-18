from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class Action(StrEnum): PROCESS="PROCESS"; STORE="STORE"; TRANSMIT="TRANSMIT"; IDLE="IDLE"
@dataclass(frozen=True)
class Decision:
    action: Action; task_id: str | None = None; rationale: str = ""
@dataclass(frozen=True)
class ActionResult:
    action: Action; task_id: str | None; success: bool; duration_s: float; energy_j: float; reason: str = ""

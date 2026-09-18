from __future__ import annotations
from dataclasses import dataclass, field
from .task import Task, TaskStatus


@dataclass(slots=True)
class TaskRecord:
    task: Task
    status: TaskStatus = TaskStatus.PENDING
    payload_mb: float | None = None
    stored: bool = False
    completed_at_s: float | None = None
    attempts: int = 0

    def __post_init__(self) -> None:
        if self.payload_mb is None:
            self.payload_mb = self.task.input_size_mb


@dataclass
class TaskQueue:
    pending: dict[str, TaskRecord] = field(default_factory=dict)
    completed: list[TaskRecord] = field(default_factory=list)
    failed: list[TaskRecord] = field(default_factory=list)

    def add(self, task: Task) -> None:
        if task.id in self.pending or any(r.task.id == task.id for r in self.completed + self.failed):
            raise ValueError(f"duplicate task id: {task.id}")
        self.pending[task.id] = TaskRecord(task)

    def ordered(self, time_s: float) -> list[TaskRecord]:
        return sorted(self.pending.values(), key=lambda r: (r.task.deadline_s, -r.task.priority, -r.task.value_at(time_s), r.task.id))

    def get(self, task_id: str) -> TaskRecord | None:
        return self.pending.get(task_id)

    def complete(self, record: TaskRecord, time_s: float) -> None:
        self.pending.pop(record.task.id, None)
        record.status, record.completed_at_s = TaskStatus.COMPLETED, time_s
        self.completed.append(record)

    def expire(self, time_s: float) -> list[TaskRecord]:
        expired = [r for r in self.pending.values() if time_s > r.task.deadline_s]
        for record in expired:
            self.pending.pop(record.task.id); record.status = TaskStatus.EXPIRED; self.failed.append(record)
        return expired

    def __len__(self) -> int: return len(self.pending)

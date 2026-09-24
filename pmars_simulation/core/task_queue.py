from __future__ import annotations

from dataclasses import dataclass, field

from .task import Task, TaskStatus


TERMINAL_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.REJECTED,
    TaskStatus.EXPIRED,
    TaskStatus.LATE,
    TaskStatus.UNFINISHED,
    TaskStatus.FAILED,
})


@dataclass(slots=True)
class TaskRecord:
    """One immutable-arrival task plus its mutable simulator lifecycle state."""

    task: Task
    status: TaskStatus = TaskStatus.PENDING
    payload_mb: float | None = None
    stored: bool = False
    completed_at_s: float | None = None
    admitted_at_s: float | None = None
    finalized_at_s: float | None = None
    outcome_reason: str = ""
    storage_accounted: bool = False
    attempts: int = 0
    processed_at_s: float | None = None

    def __post_init__(self) -> None:
        if self.payload_mb is None:
            self.payload_mb = self.task.input_size_mb

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass
class TaskQueue:
    """A full task ledger plus the subset of tasks still resident onboard.

    Metrics are derived from ``records`` rather than from a combination of
    queue buckets. This prevents rejected or terminal tasks from silently
    disappearing from scheduler-comparison denominators.
    """

    pending: dict[str, TaskRecord] = field(default_factory=dict)
    records: dict[str, TaskRecord] = field(default_factory=dict)
    completed: list[TaskRecord] = field(default_factory=list)
    rejected: list[TaskRecord] = field(default_factory=list)
    expired: list[TaskRecord] = field(default_factory=list)
    late: list[TaskRecord] = field(default_factory=list)
    unfinished: list[TaskRecord] = field(default_factory=list)
    failed: list[TaskRecord] = field(default_factory=list)

    def _register(self, record: TaskRecord) -> TaskRecord:
        task_id = record.task.id
        if task_id in self.records:
            raise ValueError(f"duplicate task id: {task_id}")
        self.records[task_id] = record
        return record

    def add(self, task: Task, time_s: float) -> TaskRecord:
        record = self._register(TaskRecord(
            task=task,
            admitted_at_s=time_s,
            storage_accounted=True,
        ))
        self.pending[task.id] = record
        return record

    def reject(self, task: Task, time_s: float, reason: str) -> TaskRecord:
        record = self._register(TaskRecord(
            task=task,
            status=TaskStatus.REJECTED,
            finalized_at_s=time_s,
            outcome_reason=reason,
        ))
        self.rejected.append(record)
        return record

    def ordered(self, time_s: float) -> list[TaskRecord]:
        return sorted(
            self.pending.values(),
            key=lambda record: (
                record.task.deadline_s,
                -record.task.priority,
                -record.task.value_at(time_s),
                record.task.id,
            ),
        )

    def get(self, task_id: str) -> TaskRecord | None:
        return self.pending.get(task_id)

    def finalize(
        self,
        record: TaskRecord,
        status: TaskStatus,
        time_s: float,
        reason: str = "",
    ) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"{status} is not terminal")
        if record.is_terminal or record.task.id not in self.pending:
            raise ValueError(f"task {record.task.id} already finalized or not active")

        self.pending.pop(record.task.id)
        record.status = status
        record.finalized_at_s = time_s
        record.outcome_reason = reason
        destinations = {
            TaskStatus.COMPLETED: self.completed,
            TaskStatus.REJECTED: self.rejected,
            TaskStatus.EXPIRED: self.expired,
            TaskStatus.LATE: self.late,
            TaskStatus.UNFINISHED: self.unfinished,
            TaskStatus.FAILED: self.failed,
        }
        destinations[status].append(record)

    def complete(self, record: TaskRecord, time_s: float) -> None:
        record.completed_at_s = time_s
        self.finalize(record, TaskStatus.COMPLETED, time_s, "timely delivery")

    def mark_late(self, record: TaskRecord, time_s: float, reason: str) -> None:
        record.completed_at_s = time_s
        self.finalize(record, TaskStatus.LATE, time_s, reason)

    def mark_failed(self, record: TaskRecord, time_s: float, reason: str) -> None:
        self.finalize(record, TaskStatus.FAILED, time_s, reason)

    def expire(
        self,
        time_s: float,
        *,
        inclusive: bool = False,
        exclude_task_id: str | None = None,
    ) -> list[TaskRecord]:
        def is_due(record: TaskRecord) -> bool:
            if record.task.id == exclude_task_id:
                return False
            return time_s >= record.task.deadline_s if inclusive else time_s > record.task.deadline_s

        expired = [record for record in self.pending.values() if is_due(record)]
        for record in expired:
            self.finalize(record, TaskStatus.EXPIRED, time_s, "deadline elapsed")
        return expired

    def finalize_unfinished(
        self,
        time_s: float,
        reason: str = "drain horizon reached",
    ) -> list[TaskRecord]:
        records = list(self.pending.values())
        for record in records:
            self.finalize(record, TaskStatus.UNFINISHED, time_s, reason)
        return records

    @property
    def terminal_records(self) -> list[TaskRecord]:
        return [record for record in self.records.values() if record.is_terminal]

    def validate_partition(self) -> None:
        """Verify that each registered task is in exactly one lifecycle state."""
        active_ids = set(self.pending)
        terminal_lists = (
            self.completed,
            self.rejected,
            self.expired,
            self.late,
            self.unfinished,
            self.failed,
        )
        terminal_ids = [record.task.id for bucket in terminal_lists for record in bucket]
        if len(terminal_ids) != len(set(terminal_ids)):
            raise AssertionError("a task occurs in more than one terminal outcome bucket")
        if active_ids.intersection(terminal_ids):
            raise AssertionError("an active task also has a terminal outcome")
        if active_ids.union(terminal_ids) != set(self.records):
            raise AssertionError("task ledger is missing an active or terminal task")

    def __len__(self) -> int:
        return len(self.pending)

"""TaskQueue domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .task import Task


@dataclass
class TaskQueue:
    """Ordered collection of pending tasks.

    Responsibility:
    - own the pending backlog
    - support enqueue/dequeue/peek operations
    - keep queue metrics visible for the scheduler

    It must not:
    - choose a PROCESS / STORE / TRANSMIT action
    - directly alter the satellite state
    - hide the fact that queue behavior is part of the system model
    """

    tasks: List[Task] = field(default_factory=list)

    def __len__(self) -> int:
        """Return the number of queued tasks."""
        return len(self.tasks)

    def enqueue(self, task: Task) -> None:
        """Add a task to the queue."""
        if not isinstance(task, Task):
            raise TypeError("task must be a Task instance.")
        self.tasks.append(task)

    def __order_key(self, task: Task):
        return (task.deadline_s, -task.priority, task.created_at_s, task.id)

    def dequeue(self) -> Optional[Task]:
        """Remove and return the next task according to queue policy."""
        if not self.tasks:
            return None
        ordered = self.sorted_tasks()
        task = ordered[0]
        self.tasks.remove(task)
        return task

    def peek(self) -> Optional[Task]:
        """Return the next task without removing it."""
        if not self.tasks:
            return None
        return self.sorted_tasks()[0]

    def clear(self) -> None:
        """Remove all queued tasks."""
        self.tasks.clear()

    def sorted_tasks(self, *, by: str = "deadline") -> List[Task]:
        """Return a deterministically ordered copy of the tasks."""
        if by == "deadline":
            return sorted(self.tasks, key=self.__order_key)
        if by == "priority":
            return sorted(self.tasks, key=lambda task: (-task.priority, task.deadline_s, task.created_at_s, task.id))
        raise ValueError(f"Unsupported ordering '{by}'.")

    def is_empty(self) -> bool:
        """Return whether the queue contains tasks."""
        return len(self.tasks) == 0

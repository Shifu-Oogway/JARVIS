"""Framework-free domain entities (the heart of the clean-architecture core)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.enums import AgentRole, TaskStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Task:
    objective: str
    role: AgentRole
    id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_now)

    def mark(self, status: TaskStatus, *, result: str | None = None, error: str | None = None) -> None:
        self.status = status
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error


@dataclass(slots=True)
class Plan:
    """A decomposed user request: an ordered/parallel set of tasks."""
    request: str
    tasks: list[Task] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))

    def ready_tasks(self, done: set[str]) -> list[Task]:
        """Tasks whose dependencies are all satisfied (enables parallel dispatch)."""
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING and set(t.depends_on).issubset(done)
        ]

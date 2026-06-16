"""Domain enumerations shared across layers."""
from enum import StrEnum


class AgentRole(StrEnum):
    RESEARCH = "research"
    CODING = "coding"
    PLANNING = "planning"
    ANALYSIS = "analysis"
    EXECUTIVE = "executive"
    AUTOMATION = "automation"
    MEMORY = "memory"
    MAINTENANCE = "maintenance"


class AgentStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

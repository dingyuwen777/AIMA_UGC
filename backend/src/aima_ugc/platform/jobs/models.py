"""持久化 Job Runtime 的稳定模型和错误类型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, Self
from uuid import UUID


@dataclass(frozen=True, slots=True)
class JobRecord:
    """`jobs` 当前快照。"""

    id: UUID
    job_type: str
    payload_version: str
    payload: dict[str, object]
    result: object | None
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    internal_idempotency_key: str
    request_id: str | None
    priority: int
    attempt: int
    lease_takeover_count: int
    max_attempts: int
    timeout_seconds: int
    attempt_started_at: datetime | None
    attempt_deadline_at: datetime | None
    progress: int
    available_at: datetime
    lease_owner: str | None
    lease_token: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    cancel_requested_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class JobAttemptEvent:
    """Job Attempt 的不可变事件记录。"""

    id: UUID
    job_id: UUID
    event_seq: int
    attempt: int
    lease_takeover_count: int
    event_type: Literal[
        "claimed",
        "lease_taken_over",
        "retry_scheduled",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
        "lease_lost",
    ]
    worker_id: str | None
    lease_token_fingerprint: str | None
    reason_code: str | None
    safe_detail: str | None
    happened_at: datetime


class JobExecutionContextProtocol(Protocol):
    """Handler 可用的最小执行上下文边界。"""

    def heartbeat(self, *, progress: int) -> None: ...

    def cancel_requested(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class JobHandlerResult:
    """Handler 显式返回的状态转换意图。"""

    outcome: Literal["succeeded", "retry", "failed", "cancelled"]
    result: dict[str, object] | None = None
    error_code: str | None = None

    @classmethod
    def succeeded(cls, result: dict[str, object] | None = None) -> Self:
        return cls(outcome="succeeded", result=result)

    @classmethod
    def retry(cls, error_code: str) -> Self:
        return cls(outcome="retry", error_code=error_code)

    @classmethod
    def failed(cls, error_code: str) -> Self:
        return cls(outcome="failed", error_code=error_code)

    @classmethod
    def cancelled(cls) -> Self:
        return cls(outcome="cancelled")


class LeaseLostError(RuntimeError):
    """Lease 已失效或调用者不再持有当前 Fencing Token。"""


class JobIdempotencyConflict(RuntimeError):
    """同一内部幂等键被用于不同 Payload。"""


type JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
type JobEventType = Literal[
    "claimed",
    "lease_taken_over",
    "retry_scheduled",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "lease_lost",
]

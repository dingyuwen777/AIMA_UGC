"""Collection Run/Scope 父事实的稳定模型和创建入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast
from uuid import UUID

type CollectionRunTrigger = Literal["scheduled", "manual", "api", "backfill"]
type CollectionRunStatus = Literal[
    "queued",
    "running",
    "partial_success",
    "succeeded",
    "failed",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class CollectionScopeDefinition:
    """创建 Scope 所需的稳定业务身份。"""

    platform: str
    source_type: str
    source_value: str
    operation_group: str

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return self.platform, self.source_type, self.source_value, self.operation_group


@dataclass(frozen=True, slots=True)
class CollectionRunRecord:
    """`collection_runs` 当前快照。"""

    id: UUID
    job_id: UUID
    manual_plan_id: UUID | None
    occurrence_id: UUID | None
    trigger_type: CollectionRunTrigger
    config_snapshot: dict[str, object]
    status: CollectionRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    requested_count: int
    succeeded_count: int
    failed_count: int
    content_count: int
    comment_count: int
    error_summary: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CollectionScopeRecord:
    """`collection_scopes` 当前快照。"""

    id: UUID
    run_id: UUID
    platform: str
    source_type: str
    source_value: str
    operation_group: str
    status: str
    pagination_state: dict[str, object]
    progress: int
    stop_reason: str | None
    stats: dict[str, object]
    started_at: datetime | None
    finished_at: datetime | None

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return self.platform, self.source_type, self.source_value, self.operation_group


@dataclass(frozen=True, slots=True)
class CollectionExecution:
    """同一事务创建的 Run 与 Scope 集合。"""

    run: CollectionRunRecord
    scopes: tuple[CollectionScopeRecord, ...]


class CollectionExecutionRepository(Protocol):
    """Collection 执行父事实的最小持久化边界。"""

    def create_queued_run(
        self,
        *,
        job_id: UUID,
        trigger_type: CollectionRunTrigger,
        config_snapshot: dict[str, object],
        scopes: tuple[CollectionScopeDefinition, ...],
        manual_plan_id: UUID | None,
        occurrence_id: UUID | None,
    ) -> CollectionExecution: ...


class UnsupportedCollectionTriggerError(ValueError):
    """当前阶段不支持请求的 Run 触发方式。"""


class InvalidCollectionRunPlanBindingError(ValueError):
    """Run 的 trigger、Plan 与 Occurrence 关系不一致。"""


class DuplicateCollectionScopeError(ValueError):
    """同一 Run 的 Scope 业务身份重复。"""


class CollectionExecutionService:
    """校验 Run/Scope 与 Plan/Occurrence 创建语义，并委托唯一 Repository 写入。"""

    _SUPPORTED_TRIGGERS = frozenset({"scheduled", "manual", "api", "backfill"})

    def __init__(self, repository: CollectionExecutionRepository) -> None:
        self._repository = repository

    def create_run(
        self,
        *,
        job_id: UUID,
        trigger_type: str,
        config_snapshot: dict[str, object],
        scopes: tuple[CollectionScopeDefinition, ...] | list[CollectionScopeDefinition],
        manual_plan_id: UUID | None = None,
        occurrence_id: UUID | None = None,
    ) -> CollectionExecution:
        """创建 queued Run/Scopes；事务提交或回滚由调用方负责。"""
        if trigger_type not in self._SUPPORTED_TRIGGERS:
            raise UnsupportedCollectionTriggerError(
                f"unsupported collection trigger: {trigger_type}"
            )

        if trigger_type == "scheduled":
            if occurrence_id is None or manual_plan_id is not None:
                raise InvalidCollectionRunPlanBindingError(
                    "scheduled run requires occurrence_id and forbids manual_plan_id"
                )
        elif occurrence_id is not None:
            raise InvalidCollectionRunPlanBindingError(
                "manual/api/backfill run must not reference occurrence_id"
            )

        scope_sequence = tuple(scopes)
        identities = [scope.identity for scope in scope_sequence]
        if len(identities) != len(set(identities)):
            raise DuplicateCollectionScopeError("collection scope identity must be unique per run")

        return self._repository.create_queued_run(
            job_id=job_id,
            trigger_type=cast(CollectionRunTrigger, trigger_type),
            config_snapshot=dict(config_snapshot),
            scopes=scope_sequence,
            manual_plan_id=manual_plan_id,
            occurrence_id=occurrence_id,
        )
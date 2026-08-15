"""Collection Plan 与 Schedule Occurrence 的稳定领域边界。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

_FIRST_RELEASE_TIMEZONE = "Asia/Shanghai"
_FORBIDDEN_CONFIG_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "cookies",
        "password",
        "secret",
        "token",
        "access_token",
    }
)

type CollectionOccurrenceStatus = Literal["enqueued", "skipped"]


class UnsupportedPlanTimezoneError(ValueError):
    """Plan 使用了首版尚未开放的时区。"""


class DuplicatePlanPlatformError(ValueError):
    """同一 Plan 重复声明平台。"""


class DuplicatePlanKeywordPackError(ValueError):
    """同一 Plan 重复绑定关键词包。"""


class UnsafePlanConfigError(ValueError):
    """Plan 平台业务配置包含 Secret 形态字段。"""


@dataclass(frozen=True, slots=True)
class PlanPlatformDefinition:
    """Plan 对一个平台的 Provider 配置选择与业务配置。"""

    platform: str
    provider_config_id: UUID
    config: dict[str, object]

    def __post_init__(self) -> None:
        if not self.platform.strip():
            raise ValueError("plan platform 不能为空")
        _reject_secret_keys(self.config)


@dataclass(frozen=True, slots=True)
class CollectionPlanDefinition:
    """创建 Plan 所需的稳定父事实；不解释 Scheduler 策略语义。"""

    name: str
    enabled: bool
    schedule_expr: str | None
    timezone: str
    schedule_version: int
    misfire_policy: str
    max_catch_up_runs: int
    detail_policy: str
    comment_policy: str
    request_budget: int
    created_by: UUID | None
    platforms: tuple[PlanPlatformDefinition, ...]
    keyword_pack_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("plan name 不能为空")
        if self.schedule_expr is not None and not self.schedule_expr.strip():
            raise ValueError("schedule_expr 只能为空或非空表达式")
        if not self.timezone.strip():
            raise ValueError("timezone 不能为空")
        if self.schedule_version < 1:
            raise ValueError("schedule_version 必须大于等于 1")
        if not self.misfire_policy.strip():
            raise ValueError("misfire_policy 不能为空")
        if self.max_catch_up_runs < 0:
            raise ValueError("max_catch_up_runs 不能小于 0")
        if not self.detail_policy.strip():
            raise ValueError("detail_policy 不能为空")
        if not self.comment_policy.strip():
            raise ValueError("comment_policy 不能为空")
        if self.request_budget < 0:
            raise ValueError("request_budget 不能小于 0")


@dataclass(frozen=True, slots=True)
class CollectionPlanRecord:
    """`collection_plans` 与关联配置的聚合快照。"""

    id: UUID
    name: str
    enabled: bool
    schedule_expr: str | None
    timezone: str
    schedule_version: int
    next_run_at: datetime | None
    last_scheduled_at: datetime | None
    misfire_policy: str
    max_catch_up_runs: int
    detail_policy: str
    comment_policy: str
    request_budget: int
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    platforms: tuple[PlanPlatformDefinition, ...]
    keyword_pack_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class CollectionScheduleOccurrenceRecord:
    """一个 Plan 版本在逻辑调度时刻的唯一提交事实。"""

    id: UUID
    plan_id: UUID
    schedule_version: int
    scheduled_for: datetime
    job_id: UUID | None
    status: CollectionOccurrenceStatus
    skip_reason: str | None
    created_at: datetime


class CollectionPlanningRepository(Protocol):
    """Plan/Occurrence 的 Collection Owner 持久化边界。"""

    def create_plan(self, definition: CollectionPlanDefinition) -> CollectionPlanRecord: ...

    def get_plan(self, plan_id: UUID) -> CollectionPlanRecord | None: ...

    def create_occurrence(
        self,
        *,
        plan_id: UUID,
        schedule_version: int,
        scheduled_for: datetime,
        job_id: UUID | None,
        status: CollectionOccurrenceStatus,
        skip_reason: str | None,
    ) -> CollectionScheduleOccurrenceRecord: ...


class CollectionPlanningService:
    """只校验已冻结的 Plan/Occurrence 结构，不执行 Scheduler 策略。"""

    def __init__(self, repository: CollectionPlanningRepository) -> None:
        self._repository = repository

    def create_plan(self, definition: CollectionPlanDefinition) -> CollectionPlanRecord:
        """创建显式 Plan；首版时区固定为 Asia/Shanghai。"""
        if definition.timezone != _FIRST_RELEASE_TIMEZONE:
            raise UnsupportedPlanTimezoneError(
                f"first release plan timezone must be {_FIRST_RELEASE_TIMEZONE}"
            )

        platforms = [platform.platform for platform in definition.platforms]
        if len(platforms) != len(set(platforms)):
            raise DuplicatePlanPlatformError("plan platform identity must be unique")

        if len(definition.keyword_pack_ids) != len(set(definition.keyword_pack_ids)):
            raise DuplicatePlanKeywordPackError("plan keyword pack identity must be unique")

        return self._repository.create_plan(definition)

    def record_enqueued_occurrence(
        self,
        *,
        plan_id: UUID,
        schedule_version: int,
        scheduled_for: datetime,
        job_id: UUID,
    ) -> CollectionScheduleOccurrenceRecord:
        """记录调用方已决定入队的 Occurrence，不推导调度策略。"""
        _validate_occurrence_time(schedule_version, scheduled_for)
        return self._repository.create_occurrence(
            plan_id=plan_id,
            schedule_version=schedule_version,
            scheduled_for=scheduled_for,
            job_id=job_id,
            status="enqueued",
            skip_reason=None,
        )

    def record_skipped_occurrence(
        self,
        *,
        plan_id: UUID,
        schedule_version: int,
        scheduled_for: datetime,
        skip_reason: str,
    ) -> CollectionScheduleOccurrenceRecord:
        """记录调用方显式决定跳过的 Occurrence，不推导跳过原因。"""
        _validate_occurrence_time(schedule_version, scheduled_for)
        if not skip_reason.strip():
            raise ValueError("skipped occurrence 必须提供 skip_reason")
        return self._repository.create_occurrence(
            plan_id=plan_id,
            schedule_version=schedule_version,
            scheduled_for=scheduled_for,
            job_id=None,
            status="skipped",
            skip_reason=skip_reason,
        )


def _validate_occurrence_time(schedule_version: int, scheduled_for: datetime) -> None:
    if schedule_version < 1:
        raise ValueError("schedule_version 必须大于等于 1")
    if scheduled_for.utcoffset() is None:
        raise ValueError("scheduled_for 必须包含时区")


def _reject_secret_keys(value: object, *, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _FORBIDDEN_CONFIG_KEYS:
                raise UnsafePlanConfigError(f"{path} 不允许包含 Secret 字段: {key}")
            _reject_secret_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            _reject_secret_keys(child, path=f"{path}[{index}]")

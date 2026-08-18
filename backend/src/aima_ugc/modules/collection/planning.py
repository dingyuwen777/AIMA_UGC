"""Collection Plan 与 Schedule Occurrence 的稳定领域边界。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from aima_ugc.contracts.collection import CollectionDecisionPolicyV1

_FIRST_RELEASE_TIMEZONE = "Asia/Shanghai"
_FIRST_RELEASE_MISFIRE_POLICY = "latest_only"
_FIRST_RELEASE_MAX_CATCH_UP_RUNS = 0
_FIRST_RELEASE_DETAIL_POLICY = "on_change"
_FIRST_RELEASE_COMMENT_POLICY = "adaptive"
_FORBIDDEN_CONFIG_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "password",
        "secret",
        "token",
        "access_token",
    }
)
_FORBIDDEN_CONFIG_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_cookie",
    "_credential",
    "_password",
    "_secret",
    "_token",
)

type CollectionOccurrenceStatus = Literal["enqueued", "skipped"]


class UnsupportedPlanTimezoneError(ValueError):
    """Plan 使用了首版尚未开放的时区。"""


class UnsupportedPlanMisfirePolicyError(ValueError):
    """Plan 使用了首版尚未批准的停机恢复策略。"""


class UnsupportedPlanCatchUpError(ValueError):
    """Plan 请求了首版尚未批准的历史补跑次数。"""


class DuplicatePlanPlatformError(ValueError):
    """同一 Plan 重复声明平台。"""


class DuplicatePlanKeywordPackError(ValueError):
    """同一 Plan 重复绑定关键词包。"""


class UnsafePlanConfigError(ValueError):
    """Plan 平台业务配置包含 Secret 形态字段。"""


class EmptyPlanExecutionSurfaceError(ValueError):
    """Plan 没有任何可执行平台或关键词包。"""


class UnsupportedPlanDecisionPolicyError(ValueError):
    """Plan 使用了首版未支持的详情/评论策略。"""


@dataclass(frozen=True, slots=True)
class PlanPlatformDefinition:
    """Plan 对一个平台的 Provider 配置选择与业务配置。"""

    platform: str
    provider_config_id: UUID
    config: dict[str, object]

    def __post_init__(self) -> None:
        normalized_platform = self.platform.strip()
        if not normalized_platform:
            raise ValueError("plan platform 不能为空")
        object.__setattr__(self, "platform", normalized_platform)
        _reject_secret_keys(self.config)


@dataclass(frozen=True, slots=True)
class CollectionPlanDefinition:
    """创建 Plan 所需的稳定父事实；Scheduler 仅执行已批准策略。"""

    name: str
    enabled: bool
    schedule_expr: str | None
    timezone: str
    schedule_version: int
    misfire_policy: str
    max_catch_up_runs: int
    detail_policy: str
    comment_policy: str
    created_by: UUID | None
    platforms: tuple[PlanPlatformDefinition, ...]
    keyword_pack_ids: tuple[UUID, ...]
    decision_policy: CollectionDecisionPolicyV1 = field(
        default_factory=CollectionDecisionPolicyV1
    )

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
        if not self.platforms:
            raise EmptyPlanExecutionSurfaceError("plan platform 至少需要一个")
        if not self.keyword_pack_ids:
            raise EmptyPlanExecutionSurfaceError("plan keyword pack 至少需要一个")


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
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    platforms: tuple[PlanPlatformDefinition, ...]
    keyword_pack_ids: tuple[UUID, ...]
    decision_policy: CollectionDecisionPolicyV1 = field(
        default_factory=CollectionDecisionPolicyV1
    )


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
    """校验 Plan/Occurrence 结构与首版 Scheduler 策略。"""

    def __init__(self, repository: CollectionPlanningRepository) -> None:
        self._repository = repository

    def create_plan(self, definition: CollectionPlanDefinition) -> CollectionPlanRecord:
        """创建显式 Plan；在持久化前拒绝当前 Worker 无法执行的配置。"""
        if definition.timezone != _FIRST_RELEASE_TIMEZONE:
            raise UnsupportedPlanTimezoneError(
                f"first release plan timezone must be {_FIRST_RELEASE_TIMEZONE}"
            )
        if definition.misfire_policy != _FIRST_RELEASE_MISFIRE_POLICY:
            raise UnsupportedPlanMisfirePolicyError(
                f"first release misfire_policy must be {_FIRST_RELEASE_MISFIRE_POLICY}"
            )
        if definition.max_catch_up_runs != _FIRST_RELEASE_MAX_CATCH_UP_RUNS:
            raise UnsupportedPlanCatchUpError(
                f"first release max_catch_up_runs must be {_FIRST_RELEASE_MAX_CATCH_UP_RUNS}"
            )
        if (
            definition.detail_policy != _FIRST_RELEASE_DETAIL_POLICY
            or definition.comment_policy != _FIRST_RELEASE_COMMENT_POLICY
        ):
            raise UnsupportedPlanDecisionPolicyError(
                "first release only supports detail_policy=on_change and comment_policy=adaptive"
            )

        platforms = [platform.platform for platform in definition.platforms]
        if len(platforms) != len(set(platforms)):
            raise DuplicatePlanPlatformError("plan platform identity must be unique")
        if len(definition.keyword_pack_ids) != len(set(definition.keyword_pack_ids)):
            raise DuplicatePlanKeywordPackError("plan keyword pack identity must be unique")

        if definition.schedule_expr is not None:
            # 延迟 import 避免 planning/scheduler 的领域类型循环；这里只做语法/时区可执行性验证。
            from .scheduler import next_schedule_time

            next_schedule_time(
                definition.schedule_expr,
                definition.timezone,
                datetime(2000, 1, 1, tzinfo=UTC),
            )
        return self._repository.create_plan(definition)

    def record_enqueued_occurrence(
        self,
        *,
        plan_id: UUID,
        schedule_version: int,
        scheduled_for: datetime,
        job_id: UUID,
    ) -> CollectionScheduleOccurrenceRecord:
        """记录 Scheduler 已决定入队的 Occurrence，不在此层执行 Job。"""
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
        """记录 Scheduler 已决定跳过的 Occurrence。"""
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


def _is_sensitive_config_key(normalized: str) -> bool:
    return normalized in _FORBIDDEN_CONFIG_KEYS or normalized.endswith(
        _FORBIDDEN_CONFIG_SUFFIXES
    )


def _reject_secret_keys(value: object, *, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if _is_sensitive_config_key(normalized):
                raise UnsafePlanConfigError(f"{path} 不允许包含 Secret 字段: {key}")
            _reject_secret_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            _reject_secret_keys(child, path=f"{path}[{index}]")

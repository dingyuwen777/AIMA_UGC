"""Canonical Content/Comment 摄取领域入口与轻量内存验证实现。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Protocol, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1

_BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
_ResultT_co = TypeVar("_ResultT_co", covariant=True)
_INMEMORY_FIELD_NAMES = frozenset(
    {
        "content_type",
        "title",
        "text",
        "metrics.like_count",
    }
)


class ContentIngestionRepository(Protocol[_ResultT_co]):
    """ContentIngestionService 需要的 Owner Repository 能力。"""

    def ingest_content(self, observation: CanonicalContentV1) -> _ResultT_co: ...

    def ingest_comment(self, observation: CanonicalCommentV1) -> _ResultT_co: ...


class ContentIngestionService[ResultT]:
    """Canonical 摄取唯一生产入口；数据库细节由 Content Owner Repository 实现。"""

    def __init__(self, repository: ContentIngestionRepository[ResultT]) -> None:
        self._repository = repository

    def ingest_content(self, observation: CanonicalContentV1) -> ResultT:
        return self._repository.ingest_content(observation)

    def ingest_comment(self, observation: CanonicalCommentV1) -> ResultT:
        return self._repository.ingest_comment(observation)


@dataclass(frozen=True, slots=True)
class ContentCurrent:
    platform: str
    external_content_id: str
    content_type: str
    title: str | None
    text: str | None
    like_count: int | None
    first_seen_at: datetime
    last_seen_at: datetime
    current_version: int


@dataclass(frozen=True, slots=True)
class ContentVersion:
    version_no: int
    title: str | None
    text: str | None
    content_type: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class MetricObservation:
    like_count: int | None
    reason: str
    observed_at: datetime
    business_date: date


@dataclass(frozen=True, slots=True)
class IngestionResult:
    target_id: UUID | None
    version_no: int
    version_created: bool
    metric_recorded: bool


class InMemoryContentRepository:
    """无数据库的 Content 领域 Fake；支持字段级 Current freshness 语义验证。"""

    def __init__(self) -> None:
        self._contents: dict[tuple[str, str], ContentCurrent] = {}
        self._field_observed_at: dict[tuple[str, str], dict[str, datetime]] = {}
        self.versions: list[ContentVersion] = []
        self.metric_observations: list[MetricObservation] = []
        self._metric_days: set[tuple[str, str, date]] = set()

    def get_content(self, platform: str, external_content_id: str) -> ContentCurrent | None:
        return self._contents.get((platform, external_content_id))

    def ingest_content(self, observation: CanonicalContentV1) -> IngestionResult:
        key = (observation.platform, observation.external_content_id)
        current = self._contents.get(key)
        business_date = observation.observed_at.astimezone(_BUSINESS_TZ).date()

        if current is None:
            current = ContentCurrent(
                platform=observation.platform,
                external_content_id=observation.external_content_id,
                content_type=observation.content_type,
                title=observation.title if "title" in observation.observed_fields else None,
                text=observation.text if "text" in observation.observed_fields else None,
                like_count=(
                    observation.metrics.like_count
                    if "metrics.like_count" in observation.observed_fields
                    else None
                ),
                first_seen_at=observation.observed_at,
                last_seen_at=observation.observed_at,
                current_version=1,
            )
            self._contents[key] = current
            self._field_observed_at[key] = {
                field: observation.observed_at
                for field in observation.observed_fields
                if field in _INMEMORY_FIELD_NAMES
            }
            self.versions.append(_version(current, observation.observed_at))
            self._append_metric(
                key,
                MetricObservation(
                    like_count=current.like_count,
                    reason="initial",
                    observed_at=observation.observed_at,
                    business_date=business_date,
                ),
            )
            return IngestionResult(None, 1, True, True)

        field_freshness = self._field_observed_at.setdefault(key, {})
        candidate_values: dict[str, Any] = {
            "content_type": observation.content_type,
            "title": observation.title,
            "text": observation.text,
            "metrics.like_count": observation.metrics.like_count,
        }
        accepted: dict[str, Any] = {}
        for field in observation.observed_fields:
            if field not in _INMEMORY_FIELD_NAMES:
                continue
            previous_at = field_freshness.get(field)
            if previous_at is not None and observation.observed_at < previous_at:
                continue
            accepted[field] = candidate_values[field]
            field_freshness[field] = observation.observed_at

        updated = replace(
            current,
            content_type=accepted.get("content_type", current.content_type),
            title=accepted.get("title", current.title),
            text=accepted.get("text", current.text),
            like_count=accepted.get("metrics.like_count", current.like_count),
            first_seen_at=min(current.first_seen_at, observation.observed_at),
            last_seen_at=max(current.last_seen_at, observation.observed_at),
        )
        business_changed = (updated.content_type, updated.title, updated.text) != (
            current.content_type,
            current.title,
            current.text,
        )
        if business_changed:
            updated = replace(updated, current_version=current.current_version + 1)
            self.versions.append(_version(updated, observation.observed_at))

        metric_recorded = False
        if "metrics.like_count" in observation.observed_fields:
            if observation.metrics.like_count != current.like_count:
                reason = "changed"
            elif not self._has_metric_on_day(key, business_date):
                reason = "daily_checkpoint"
            else:
                reason = ""
            if reason:
                self._append_metric(
                    key,
                    MetricObservation(
                        like_count=observation.metrics.like_count,
                        reason=reason,
                        observed_at=observation.observed_at,
                        business_date=business_date,
                    ),
                )
                metric_recorded = True

        self._contents[key] = updated
        return IngestionResult(None, updated.current_version, business_changed, metric_recorded)

    def ingest_comment(self, observation: CanonicalCommentV1) -> IngestionResult:
        raise NotImplementedError(
            "内存验证实现当前只覆盖 Content；Comment 由 PostgreSQL 集成测试验证"
        )

    def _append_metric(
        self,
        key: tuple[str, str],
        observation: MetricObservation,
    ) -> None:
        self.metric_observations.append(observation)
        self._metric_days.add((*key, observation.business_date))

    def _has_metric_on_day(self, key: tuple[str, str], business_date: date) -> bool:
        return (*key, business_date) in self._metric_days


def _version(content: ContentCurrent, observed_at: datetime) -> ContentVersion:
    return ContentVersion(
        version_no=content.current_version,
        title=content.title,
        text=content.text,
        content_type=content.content_type,
        observed_at=observed_at,
    )
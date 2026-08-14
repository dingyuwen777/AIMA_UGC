"""Canonical Content 稀疏摄取与 Current/History 领域语义。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aima_ugc.contracts.canonical import CanonicalContentV1

_BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


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
    version_no: int
    version_created: bool
    metric_recorded: bool


class InMemoryContentRepository:
    """领域测试用 Repository；与生产 PostgreSQL Repository 共享同一摄取决策。"""

    def __init__(self) -> None:
        self._contents: dict[tuple[str, str], ContentCurrent] = {}
        self.versions: list[ContentVersion] = []
        self.metric_observations: list[MetricObservation] = []
        self._metric_days: set[tuple[str, str, date]] = set()

    def get_content(self, platform: str, external_content_id: str) -> ContentCurrent | None:
        return self._contents.get((platform, external_content_id))

    def save_content(self, content: ContentCurrent) -> None:
        self._contents[(content.platform, content.external_content_id)] = content

    def append_version(self, version: ContentVersion) -> None:
        self.versions.append(version)

    def append_metric(self, key: tuple[str, str], observation: MetricObservation) -> None:
        self.metric_observations.append(observation)
        self._metric_days.add((*key, observation.business_date))

    def has_metric_on_day(self, key: tuple[str, str], business_date: date) -> bool:
        return (*key, business_date) in self._metric_days


class ContentIngestionService:
    """只依据 observed_fields 合并 Canonical Content。"""

    def __init__(self, repository: InMemoryContentRepository) -> None:
        self._repository = repository

    def ingest_content(self, observation: CanonicalContentV1) -> IngestionResult:
        key = (observation.platform, observation.external_content_id)
        current = self._repository.get_content(*key)
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
            self._repository.save_content(current)
            self._repository.append_version(_version(current, observation.observed_at))
            self._repository.append_metric(
                key,
                MetricObservation(
                    like_count=current.like_count,
                    reason="initial",
                    observed_at=observation.observed_at,
                    business_date=business_date,
                ),
            )
            return IngestionResult(1, True, True)

        updated = replace(
            current,
            content_type=(
                observation.content_type
                if "content_type" in observation.observed_fields
                else current.content_type
            ),
            title=observation.title if "title" in observation.observed_fields else current.title,
            text=observation.text if "text" in observation.observed_fields else current.text,
            like_count=(
                observation.metrics.like_count
                if "metrics.like_count" in observation.observed_fields
                else current.like_count
            ),
            last_seen_at=max(current.last_seen_at, observation.observed_at),
        )
        business_changed = (updated.content_type, updated.title, updated.text) != (
            current.content_type,
            current.title,
            current.text,
        )
        if business_changed:
            updated = replace(updated, current_version=current.current_version + 1)
            self._repository.append_version(_version(updated, observation.observed_at))

        metric_recorded = False
        if "metrics.like_count" in observation.observed_fields:
            if updated.like_count != current.like_count:
                reason = "changed"
            elif not self._repository.has_metric_on_day(key, business_date):
                reason = "daily_checkpoint"
            else:
                reason = ""
            if reason:
                self._repository.append_metric(
                    key,
                    MetricObservation(
                        like_count=updated.like_count,
                        reason=reason,
                        observed_at=observation.observed_at,
                        business_date=business_date,
                    ),
                )
                metric_recorded = True

        self._repository.save_content(updated)
        return IngestionResult(updated.current_version, business_changed, metric_recorded)


def _version(content: ContentCurrent, observed_at: datetime) -> ContentVersion:
    return ContentVersion(
        version_no=content.current_version,
        title=content.title,
        text=content.text,
        content_type=content.content_type,
        observed_at=observed_at,
    )

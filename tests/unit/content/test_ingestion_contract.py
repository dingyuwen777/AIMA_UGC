"""Stage 6 Content Ingestion 领域行为测试。"""

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.content.ingestion import (
    ContentIngestionService,
    InMemoryContentRepository,
)


OBSERVED_AT = datetime(2026, 8, 14, 3, 0, tzinfo=UTC)
SOURCE = CanonicalSourceV1(
    provider_name="tikhub",
    operation="search_notes",
    provider_attempt_id="attempt-1",
    raw_artifact_id=UUID("00000000-0000-0000-0000-000000000101"),
    source_type="keyword_search",
    source_value="爱玛",
    item_locator="note:note-1",
    observed_at=OBSERVED_AT,
)


def _content(
    *, title: str, likes: int, observed_at: datetime = OBSERVED_AT
) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xhs",
        external_content_id="note-1",
        content_type="image",
        title=title,
        text="保留正文",
        observed_at=observed_at,
        metrics=CanonicalMetricsV1(like_count=likes),
        source=SOURCE.model_copy(update={"observed_at": observed_at}),
        observed_fields=["content_type", "title", "text", "metrics.like_count"],
    )


def test_sparse_update_a_b_a_and_metric_decrease_keep_history() -> None:
    repository = InMemoryContentRepository()
    service = ContentIngestionService(repository)

    first = service.ingest_content(_content(title="A", likes=10))
    second = service.ingest_content(_content(title="B", likes=20))
    third = service.ingest_content(_content(title="A", likes=8))

    assert first.version_no == 1
    assert second.version_no == 2
    assert third.version_no == 3
    current = repository.get_content("xhs", "note-1")
    assert current is not None
    assert current.title == "A"
    assert current.text == "保留正文"
    assert current.like_count == 8
    assert [item.title for item in repository.versions] == ["A", "B", "A"]
    assert [item.like_count for item in repository.metric_observations] == [10, 20, 8]


def test_unobserved_field_is_not_cleared_and_daily_checkpoint_is_singleton() -> None:
    repository = InMemoryContentRepository()
    service = ContentIngestionService(repository)
    service.ingest_content(_content(title="A", likes=10))

    next_observed_at = datetime(2026, 8, 15, 2, 0, tzinfo=UTC)
    sparse = CanonicalContentV1(
        platform="xhs",
        external_content_id="note-1",
        content_type="image",
        title="A",
        text=None,
        observed_at=next_observed_at,
        metrics=CanonicalMetricsV1(like_count=10),
        source=SOURCE.model_copy(update={"observed_at": next_observed_at}),
        observed_fields=["content_type", "title", "metrics.like_count"],
    )
    service.ingest_content(sparse)
    service.ingest_content(sparse)

    current = repository.get_content("xhs", "note-1")
    assert current is not None
    assert current.text == "保留正文"
    reasons = [item.reason for item in repository.metric_observations]
    assert reasons.count("daily_checkpoint") == 1

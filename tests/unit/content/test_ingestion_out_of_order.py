"""InMemory Content Fake 与生产 Current freshness 的时序回归。"""

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.content.ingestion import ContentIngestionService, InMemoryContentRepository


def _observation(
    *,
    observed_at: datetime,
    title: str | None = None,
    text: str | None = None,
    observed_fields: list[str],
) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-inmemory-order",
        content_type="image",
        title=title,
        text=text,
        observed_at=observed_at,
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="search_notes",
            provider_attempt_id=f"attempt-{uuid4()}",
            raw_artifact_id=uuid4(),
            source_type="keyword_search",
            source_value="爱玛",
            item_locator=f"audit:{uuid4()}",
            observed_at=observed_at,
        ),
        observed_fields=observed_fields,
    )


def test_inmemory_older_observation_does_not_regress_newer_field() -> None:
    repository = InMemoryContentRepository()
    service = ContentIngestionService(repository)
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    service.ingest_content(
        _observation(
            observed_at=newer_at,
            title="NEW",
            observed_fields=["content_type", "title"],
        )
    )
    service.ingest_content(
        _observation(
            observed_at=older_at,
            title="OLD",
            observed_fields=["content_type", "title"],
        )
    )

    current = repository.get_content("xiaohongshu", "audit-inmemory-order")
    assert current is not None
    assert current.title == "NEW"
    assert current.last_seen_at == newer_at


def test_inmemory_older_sparse_observation_can_fill_never_observed_field() -> None:
    repository = InMemoryContentRepository()
    service = ContentIngestionService(repository)
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    service.ingest_content(
        _observation(
            observed_at=newer_at,
            title="NEW",
            observed_fields=["content_type", "title"],
        )
    )
    service.ingest_content(
        _observation(
            observed_at=older_at,
            text="OLDER DETAIL",
            observed_fields=["content_type", "text"],
        )
    )

    current = repository.get_content("xiaohongshu", "audit-inmemory-order")
    assert current is not None
    assert current.title == "NEW"
    assert current.text == "OLDER DETAIL"
    assert current.last_seen_at == newer_at


def test_inmemory_newer_explicit_null_blocks_older_non_null_value() -> None:
    repository = InMemoryContentRepository()
    service = ContentIngestionService(repository)
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    service.ingest_content(
        _observation(
            observed_at=newer_at,
            text=None,
            observed_fields=["content_type", "text"],
        )
    )
    service.ingest_content(
        _observation(
            observed_at=older_at,
            text="OLD TEXT",
            observed_fields=["content_type", "text"],
        )
    )

    current = repository.get_content("xiaohongshu", "audit-inmemory-order")
    assert current is not None
    assert current.text is None
    assert current.last_seen_at == newer_at

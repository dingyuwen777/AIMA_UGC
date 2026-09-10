"""TikHub Discovery 的 Persistent Canonical 页面边界。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.platform.storage import ArtifactRecord, CanonicalArtifactParent

_NOW = datetime(2026, 9, 11, 4, 30, tzinfo=UTC)


def _content(*, suffix: str = "1") -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=f"note-{suffix}",
        content_type="image",
        title=f"爱玛 {suffix}",
        observed_at=_NOW,
        metrics=CanonicalMetricsV1(comment_count=0),
        source=CanonicalSourceV1(
            provider_name="tikhub",
            provider_request_id=str(uuid4()),
            provider_attempt_id=str(uuid4()),
            raw_artifact_id=uuid4(),
            operation="search_notes",
            item_locator=f"item-{suffix}",
            observed_at=_NOW,
        ),
        observed_fields=["title", "content_type", "metrics.comment_count"],
    )


def _artifact() -> ArtifactRecord:
    artifact_id = uuid4()
    return ArtifactRecord(
        id=artifact_id,
        kind="canonical-content.v1",
        storage_backend="local",
        storage_key=f"canonical-content.v1/{artifact_id}.jsonl.gz",
        content_type="application/x-ndjson",
        encoding="gzip",
        retention_class="canonical",
        storage_status="linked",
        created_at=_NOW,
        stored_at=_NOW,
        linked_at=_NOW,
        sha256="a" * 64,
        byte_size=128,
    )


class _Writer:
    def __init__(self, artifact: ArtifactRecord) -> None:
        self.artifact = artifact
        self.calls: list[tuple[tuple[CanonicalContentV1, ...], CanonicalArtifactParent]] = []

    def write(self, contents, *, parent, retention_class, max_bytes):  # type: ignore[no-untyped-def]
        assert retention_class == "canonical"
        assert max_bytes > 0
        materialized = tuple(contents)
        self.calls.append((materialized, parent))
        return self.artifact


class _Reader:
    def __init__(self, contents: tuple[CanonicalContentV1, ...]) -> None:
        self.contents = contents
        self.calls: list[ArtifactRecord] = []

    def read(self, artifact: ArtifactRecord):  # type: ignore[no-untyped-def]
        self.calls.append(artifact)
        yield from self.contents


def test_filter_inputs_are_written_per_search_attempt_then_read_back() -> None:
    expected = (_content(suffix="1"), _content(suffix="2"))
    artifact = _artifact()
    writer = _Writer(artifact)
    reader = _Reader(expected)
    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._canonical_writer = writer  # type: ignore[attr-defined]
    executor._canonical_reader = reader  # type: ignore[attr-defined]
    executor._canonical_for_attempt = lambda _attempt_id: None  # type: ignore[attr-defined]
    attempt_id = uuid4()

    actual = executor._persistent_filter_inputs(  # type: ignore[attr-defined]
        provider_attempt_id=attempt_id,
        expected=expected,
    )

    assert actual == expected
    assert writer.calls == [
        (expected, CanonicalArtifactParent(provider_attempt_id=attempt_id))
    ]
    assert reader.calls == [artifact]


def test_retry_reuses_linked_page_artifact_and_rejects_mapper_drift() -> None:
    expected = (_content(),)
    artifact = _artifact()
    writer = _Writer(artifact)
    reader = _Reader((_content(suffix="different"),))
    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._canonical_writer = writer  # type: ignore[attr-defined]
    executor._canonical_reader = reader  # type: ignore[attr-defined]
    executor._canonical_for_attempt = lambda _attempt_id: artifact  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="Canonical.*不一致"):
        executor._persistent_filter_inputs(  # type: ignore[attr-defined]
            provider_attempt_id=uuid4(),
            expected=expected,
        )

    assert writer.calls == []
    assert reader.calls == [artifact]

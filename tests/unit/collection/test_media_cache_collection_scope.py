from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.bootstrap.media_cache_collection_scope import (
    MediaCachingTikHubCollectionScopeExecutor,
)
from aima_ugc.modules.collection.collection_run_executor import CollectionScopeExecutionResult
from aima_ugc.platform.jobs.models import LeaseLostError


class _Prefetcher:
    """记录媒体预热调用的测试替身。"""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[UUID] = []
        self.error = error

    def prefetch_content(self, content_id: UUID) -> None:
        self.calls.append(content_id)
        if self.error is not None:
            raise self.error


def _result(status: str) -> CollectionScopeExecutionResult:
    return CollectionScopeExecutionResult(
        status=status,  # type: ignore[arg-type]
        stop_reason=None,
        pagination_state={},
        stats={},
        requested_count=1,
        succeeded_count=1 if status != "failed" else 0,
        failed_count=1 if status == "failed" else 0,
        content_count=1,
        comment_count=3,
    )


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("cache unavailable"),
        LookupError("cache repository unavailable"),
    ],
)
def test_successful_enrichment_prefetch_failure_keeps_original_result(
    monkeypatch,
    error: Exception,
) -> None:
    expected = _result("succeeded")
    monkeypatch.setattr(TikHubCollectionScopeExecutor, "execute", lambda self, **_kwargs: expected)
    prefetcher = _Prefetcher(error=error)
    executor = object.__new__(MediaCachingTikHubCollectionScopeExecutor)
    executor._media_prefetcher = prefetcher
    content_id = uuid4()
    run = SimpleNamespace(id=uuid4())
    scope = SimpleNamespace(
        id=uuid4(),
        platform="xiaohongshu",
        source_type="content",
        operation_group="content_enrichment",
        source_value=str(content_id),
    )

    actual = executor.execute(run=run, scope=scope, context=SimpleNamespace())  # type: ignore[arg-type]

    assert actual is expected
    assert prefetcher.calls == [content_id]


def test_prefetch_lease_loss_is_not_swallowed(monkeypatch) -> None:
    """Job Fencing 失效不是缓存故障，必须继续向 Worker 传播。"""

    expected = _result("succeeded")
    monkeypatch.setattr(TikHubCollectionScopeExecutor, "execute", lambda self, **_kwargs: expected)
    executor = object.__new__(MediaCachingTikHubCollectionScopeExecutor)
    executor._media_prefetcher = _Prefetcher(error=LeaseLostError("lease lost"))
    scope = SimpleNamespace(
        id=uuid4(),
        platform="xiaohongshu",
        source_type="content",
        operation_group="content_enrichment",
        source_value=str(uuid4()),
    )

    with pytest.raises(LeaseLostError):
        executor.execute(
            run=SimpleNamespace(id=uuid4()),  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            context=SimpleNamespace(),  # type: ignore[arg-type]
        )


def test_failed_enrichment_does_not_prefetch(monkeypatch) -> None:
    expected = _result("failed")
    monkeypatch.setattr(TikHubCollectionScopeExecutor, "execute", lambda self, **_kwargs: expected)
    prefetcher = _Prefetcher()
    executor = object.__new__(MediaCachingTikHubCollectionScopeExecutor)
    executor._media_prefetcher = prefetcher
    scope = SimpleNamespace(
        id=uuid4(),
        platform="xiaohongshu",
        source_type="content",
        operation_group="content_enrichment",
        source_value=str(uuid4()),
    )

    actual = executor.execute(
        run=SimpleNamespace(id=uuid4()),  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        context=SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert actual is expected
    assert prefetcher.calls == []

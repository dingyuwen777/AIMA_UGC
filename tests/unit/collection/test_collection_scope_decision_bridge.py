"""Collection Scope 把 Search 缺失字段正确桥接到生产 Decision。"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from aima_ugc.adapters.providers.tikhub.capabilities import BILIBILI_TIKHUB_CAPABILITY
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.collection import PreviousContentStateV1
from aima_ugc.modules.collection.decision import CollectionDecisionService

_NOW = datetime(2026, 8, 18, 2, 0, tzinfo=UTC)


class _StateReader:
    def evaluate(self, _content: CanonicalContentV1) -> SimpleNamespace:
        return SimpleNamespace(
            previous=PreviousContentStateV1(comment_count=5),
            business_changed=False,
        )


class _Writer:
    def ingest_content(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(target_id=uuid4())


class _Context:
    fence = object()

    def cancel_requested(self) -> bool:
        return False


def _content(*, comment_count: int | None, comment_count_observed: bool) -> CanonicalContentV1:
    observed_fields = ["content_type", "metrics.play_count"]
    if comment_count_observed:
        observed_fields.append("metrics.comment_count")
    return CanonicalContentV1(
        platform="bilibili",
        external_content_id="100001",
        content_type="video",
        observed_at=_NOW,
        metrics=CanonicalMetricsV1(play_count=100, comment_count=comment_count),
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="fixture",
            observed_at=_NOW,
        ),
        observed_fields=observed_fields,
    )


def test_bilibili_search_missing_comment_count_fetches_detail_before_incremental_comments() -> None:
    search_content = _content(comment_count=None, comment_count_observed=False)
    detail_content = _content(comment_count=7, comment_count_observed=True)

    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._content_state = _StateReader()  # type: ignore[attr-defined]
    executor._content_writer = _Writer()  # type: ignore[attr-defined]
    executor._decision_service = CollectionDecisionService()  # type: ignore[attr-defined]

    detail_calls: list[str] = []
    comment_actions: list[str] = []

    def fake_fetch_detail(**_kwargs: object) -> CanonicalContentV1:
        detail_calls.append("detail")
        return detail_content

    def fake_fetch_comments(**kwargs: object) -> None:
        comment_actions.append(str(kwargs["comment_action"]))

    executor._fetch_detail = fake_fetch_detail  # type: ignore[method-assign]
    executor._fetch_comments = fake_fetch_comments  # type: ignore[method-assign]
    executor._record_non_fetch_coverage = lambda **_kwargs: None  # type: ignore[method-assign]

    executor._process_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(),  # type: ignore[arg-type]
        content=search_content,
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        context=_Context(),  # type: ignore[arg-type]
        stats=SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert detail_calls == ["detail"]
    assert comment_actions == ["fetch_incremental"]

"""Collection Scope 把 Search 缺失字段正确桥接到 durable Decision Action。"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from aima_ugc.adapters.providers.tikhub.capabilities import BILIBILI_TIKHUB_CAPABILITY
from aima_ugc.bootstrap.collection_scope import (
    TikHubCollectionScopeExecutor,
    _DetailCandidate,
    _ExecutedCall,
)
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.collection import CollectionDecisionPolicyV1, PreviousContentStateV1
from aima_ugc.modules.analysis import RelevanceKeyword, RelevanceService
from aima_ugc.modules.collection.decision import CollectionDecisionService

_NOW = datetime(2026, 8, 18, 2, 0, tzinfo=UTC)


class _StateReader:
    def evaluate(self, _content: CanonicalContentV1) -> SimpleNamespace:
        return SimpleNamespace(
            previous=PreviousContentStateV1(comment_count=5),
            business_changed=False,
        )


class _Writer:
    def __init__(self) -> None:
        self.filtered: list[object] = []
        self.ingested: list[object] = []
        self.target_id = uuid4()

    def ingest_content(self, **kwargs: object) -> SimpleNamespace:
        self.ingested.append(kwargs["candidate_id"])
        return SimpleNamespace(target_id=self.target_id)

    def record_candidate_filtered(self, **kwargs: object) -> None:
        self.filtered.append(kwargs["candidate_id"])


class _Actions:
    def __init__(self) -> None:
        self.action = None
        self.completed_comments = False

    def get(self, **_kwargs: object):  # type: ignore[no-untyped-def]
        return self.action

    def get_or_create(self, **kwargs: object):  # type: ignore[no-untyped-def]
        decision = kwargs["decision"]
        self.action = SimpleNamespace(
            id=uuid4(),
            previous_exists=True,
            previous_comment_count=5,
            initial_business_changed=False,
            decision=decision,
            resolved_comment_count=None,
            detail_completed=False,
            comments_completed=False,
        )
        return self.action

    def complete_detail(self, **kwargs: object):  # type: ignore[no-untyped-def]
        self.action = SimpleNamespace(
            id=self.action.id,
            previous_exists=True,
            previous_comment_count=5,
            initial_business_changed=False,
            decision=kwargs["decision"],
            resolved_comment_count=kwargs["resolved_comment_count"],
            detail_completed=True,
            comments_completed=False,
        )
        return self.action

    def complete_comments(self, **_kwargs: object):  # type: ignore[no-untyped-def]
        self.completed_comments = True
        return self.action


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
    executor._content_actions = _Actions()  # type: ignore[attr-defined]
    executor._decision_service = CollectionDecisionService()  # type: ignore[attr-defined]

    detail_calls: list[str] = []
    comment_actions: list[str] = []

    def fake_fetch_detail(**_kwargs: object) -> CanonicalContentV1:
        detail_calls.append("detail")
        return detail_content

    def fake_fetch_comments(**kwargs: object) -> SimpleNamespace:
        comment_actions.append(str(kwargs["comment_action"]))
        return SimpleNamespace(completed=True, technical_partial=False)

    executor._fetch_detail = fake_fetch_detail  # type: ignore[method-assign]
    executor._fetch_comments = fake_fetch_comments  # type: ignore[method-assign]
    executor._record_non_fetch_coverage = lambda **_kwargs: None  # type: ignore[method-assign]

    executor._process_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(
            id=uuid4(),
            source_type="keyword_search",
            source_value="爱玛",
            platform="bilibili",
        ),  # type: ignore[arg-type]
        content=search_content,
        search_executed=_ExecutedCall(
            request_id=uuid4(),
            attempt_id=uuid4(),
            raw_artifact_id=uuid4(),
            observed_at=_NOW,
            body={},
        ),
        search_candidate_id=uuid4(),
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        context=_Context(),  # type: ignore[arg-type]
        stats=SimpleNamespace(technical_partial_results=0),  # type: ignore[arg-type]
        relevance=SimpleNamespace(  # type: ignore[arg-type]
            evaluate=lambda _content: SimpleNamespace(matched=True)
        ),
    )

    assert detail_calls == ["detail"]
    assert comment_actions == ["fetch_incremental"]
    assert executor._content_actions.completed_comments is True  # type: ignore[attr-defined]


def test_search_and_single_detail_nonmatch_are_filtered_before_content_ingestion() -> None:
    search_content = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"title": "其他品牌"}
    )
    detail_content = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={"text": "仍然无关"}
    )
    executor = object.__new__(TikHubCollectionScopeExecutor)
    writer = _Writer()
    executor._content_writer = writer  # type: ignore[attr-defined]
    detail_candidate_id = uuid4()
    detail_calls: list[str] = []

    def fake_detail(**_kwargs: object) -> tuple[_DetailCandidate, ...]:
        detail_calls.append("detail")
        return (_DetailCandidate(detail_content, detail_candidate_id),)

    executor._fetch_detail_candidates = fake_detail  # type: ignore[method-assign]
    stats = SimpleNamespace(filtered_content_count=0)
    search_candidate_id = uuid4()

    executor._process_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(platform="bilibili"),  # type: ignore[arg-type]
        content=search_content,
        search_executed=SimpleNamespace(),  # type: ignore[arg-type]
        search_candidate_id=search_candidate_id,
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        context=_Context(),  # type: ignore[arg-type]
        stats=stats,  # type: ignore[arg-type]
        relevance=RelevanceService((RelevanceKeyword(text="爱玛", priority=1),)),
    )

    assert detail_calls == ["detail"]
    assert writer.filtered == [search_candidate_id, detail_candidate_id]
    assert stats.filtered_content_count == 1


def test_detail_match_accounts_for_search_and_all_detail_candidates() -> None:
    search_content = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"title": "其他品牌"}
    )
    first_detail = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={"text": "详情补充"}
    )
    final_detail = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={"text": "爱玛最终详情"}
    )
    executor = object.__new__(TikHubCollectionScopeExecutor)
    writer = _Writer()
    executor._content_writer = writer  # type: ignore[attr-defined]
    executor._content_state = _StateReader()  # type: ignore[attr-defined]
    executor._content_actions = _Actions()  # type: ignore[attr-defined]
    executor._decision_service = CollectionDecisionService()  # type: ignore[attr-defined]

    detail_candidate_ids = (uuid4(), uuid4())
    executor._fetch_detail_candidates = lambda **_kwargs: (  # type: ignore[method-assign]
        _DetailCandidate(first_detail, detail_candidate_ids[0]),
        _DetailCandidate(final_detail, detail_candidate_ids[1]),
    )
    executor._fetch_comments = lambda **_kwargs: SimpleNamespace(  # type: ignore[method-assign]
        completed=True,
        technical_partial=False,
    )
    executor._record_non_fetch_coverage = (  # type: ignore[method-assign]
        lambda **_kwargs: None
    )
    search_candidate_id = uuid4()

    executor._process_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(
            id=uuid4(),
            source_type="keyword_search",
            source_value="爱玛",
            platform="bilibili",
        ),  # type: ignore[arg-type]
        content=search_content,
        search_executed=_ExecutedCall(
            request_id=uuid4(),
            attempt_id=uuid4(),
            raw_artifact_id=uuid4(),
            observed_at=_NOW,
            body={},
        ),
        search_candidate_id=search_candidate_id,
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        context=_Context(),  # type: ignore[arg-type]
        stats=SimpleNamespace(technical_partial_results=0, filtered_content_count=0),  # type: ignore[arg-type]
        relevance=RelevanceService((RelevanceKeyword(text="爱玛", priority=1),)),
    )

    assert writer.ingested == [search_candidate_id, *detail_candidate_ids]

"""Collection Scope 把 Search 缺失字段正确桥接到 durable Decision Action。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.tikhub.capabilities import BILIBILI_TIKHUB_CAPABILITY
from aima_ugc.bootstrap.collection_scope import (
    TikHubCollectionScopeExecutor,
    _DetailCandidate,
    _DetailFetchOutcome,
    _ExecutedCall,
    _PreparedSearchContent,
)
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.collection import CollectionDecisionPolicyV1, PreviousContentStateV1
from aima_ugc.modules.collection.decision import CollectionDecisionService
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandAliasRecord,
    BrandRecord,
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolver,
)

_NOW = datetime(2026, 8, 18, 2, 0, tzinfo=UTC)
_BRAND_ID = uuid4()


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
        self.ingested_payloads: list[dict[str, object]] = []
        self.target_id = uuid4()

    def ingest_content(self, **kwargs: object) -> SimpleNamespace:
        self.ingested.append(kwargs["candidate_id"])
        self.ingested_payloads.append(kwargs)
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
            previous_capture_complete=False,
            initial_business_changed=False,
            decision=decision,
            resolved_comment_count=kwargs["resolved_comment_count"],
            detail_completed=False,
            comments_completed=False,
        )
        return self.action

    def complete_detail(self, **kwargs: object):  # type: ignore[no-untyped-def]
        self.action = SimpleNamespace(
            id=self.action.id,
            previous_exists=True,
            previous_comment_count=5,
            previous_capture_complete=False,
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


def _filter_snapshot() -> BrandVehicleFilterSnapshot:
    """构造只选择爱玛品牌的冻结目录。"""

    return BrandVehicleFilterSnapshot(
        search_semantics="keyword_pack",
        catalog=BrandVehicleCatalogSnapshot(
            catalog_version=1,
            filter_scope="selected",
            selected_brand_ids=(_BRAND_ID,),
            brands=(
                BrandRecord(
                    id=_BRAND_ID,
                    code="AIMA",
                    display_name="爱玛",
                    role="owned",
                    status="active",
                    version=1,
                    catalog_version=1,
                    created_at=_NOW,
                    updated_at=_NOW,
                ),
            ),
            brand_aliases=(
                BrandAliasRecord(
                    id=uuid4(),
                    brand_id=_BRAND_ID,
                    text="爱玛",
                    normalized_text="爱玛",
                    created_at=_NOW,
                ),
            ),
            vehicles=(),
            vehicle_aliases=(),
        ),
    )


def test_bilibili_search_missing_comment_count_fetches_detail_before_incremental_comments() -> None:
    search_content = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"title": "爱玛搜索命中", "observed_fields": ["title"]}
    )
    detail_content = _content(comment_count=7, comment_count_observed=True)

    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._brand_vehicle_resolver = BrandVehicleResolver()
    writer = _Writer()
    executor._content_state = _StateReader()  # type: ignore[attr-defined]
    executor._content_writer = writer  # type: ignore[attr-defined]
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
        prepared=_PreparedSearchContent(
            search_content=search_content,
            final_content=search_content,
            search_candidate_id=uuid4(),
        ),
        content=search_content,
        search_executed=_ExecutedCall(
            request_id=uuid4(),
            attempt_id=uuid4(),
            raw_artifact_id=uuid4(),
            observed_at=_NOW,
            body={},
        ),
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        context=_Context(),  # type: ignore[arg-type]
        stats=SimpleNamespace(technical_partial_results=0),  # type: ignore[arg-type]
        filter_snapshot=_filter_snapshot(),
    )

    assert detail_calls == ["detail"]
    assert comment_actions == ["fetch_incremental"]
    assert executor._content_actions.completed_comments is True  # type: ignore[attr-defined]
    assert writer.ingested_payloads[0]["brand_vehicle_resolution"].matched is True  # type: ignore[union-attr]


def test_search_and_single_detail_nonmatch_are_filtered_before_content_ingestion() -> None:
    search_content = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"title": "其他品牌", "observed_fields": ["title"]}
    )
    detail_content = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={"text": "仍然无关", "observed_fields": ["text", "metrics.comment_count"]}
    )
    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._brand_vehicle_resolver = BrandVehicleResolver()
    writer = _Writer()
    executor._content_writer = writer  # type: ignore[attr-defined]
    detail_candidate_id = uuid4()
    detail_calls: list[str] = []

    def fake_detail(**_kwargs: object) -> _DetailFetchOutcome:
        detail_calls.append("detail")
        return _DetailFetchOutcome((_DetailCandidate(detail_content, detail_candidate_id),))

    executor._fetch_detail_candidates = fake_detail  # type: ignore[method-assign]
    stats = SimpleNamespace(filtered_content_count=0)
    search_candidate_id = uuid4()

    prepared = executor._prepare_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(platform="bilibili", source_type="keyword_search"),  # type: ignore[arg-type]
        content=search_content,
        search_candidate_id=search_candidate_id,
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        context=_Context(),  # type: ignore[arg-type]
        stats=stats,  # type: ignore[arg-type]
        filter_snapshot=_filter_snapshot(),
    )
    executor._process_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(platform="bilibili", source_type="keyword_search"),  # type: ignore[arg-type]
        prepared=prepared,
        content=prepared.final_content,
        search_executed=SimpleNamespace(),  # type: ignore[arg-type]
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        context=_Context(),  # type: ignore[arg-type]
        stats=stats,  # type: ignore[arg-type]
        filter_snapshot=_filter_snapshot(),
    )

    assert detail_calls == ["detail"]
    assert writer.filtered == [search_candidate_id, detail_candidate_id]
    assert stats.filtered_content_count == 1


def test_detail_match_accounts_for_search_and_all_detail_candidates() -> None:
    search_content = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"title": "其他品牌", "observed_fields": ["title"]}
    )
    first_detail = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={"text": "详情补充", "observed_fields": ["text", "metrics.comment_count"]}
    )
    final_detail = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={"text": "爱玛最终详情", "observed_fields": ["text", "metrics.comment_count"]}
    )
    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._brand_vehicle_resolver = BrandVehicleResolver()
    writer = _Writer()
    executor._content_writer = writer  # type: ignore[attr-defined]
    executor._content_state = _StateReader()  # type: ignore[attr-defined]
    executor._content_actions = _Actions()  # type: ignore[attr-defined]
    executor._decision_service = CollectionDecisionService()  # type: ignore[attr-defined]

    detail_candidate_ids = (uuid4(), uuid4())
    executor._fetch_detail_candidates = lambda **_kwargs: _DetailFetchOutcome(
        (  # type: ignore[method-assign]
            _DetailCandidate(first_detail, detail_candidate_ids[0]),
            _DetailCandidate(final_detail, detail_candidate_ids[1]),
        )
    )
    executor._fetch_comments = lambda **_kwargs: SimpleNamespace(  # type: ignore[method-assign]
        completed=True,
        technical_partial=False,
    )
    executor._record_non_fetch_coverage = (  # type: ignore[method-assign]
        lambda **_kwargs: None
    )
    search_candidate_id = uuid4()

    prepared = executor._prepare_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(
            id=uuid4(),
            source_type="keyword_search",
            source_value="爱玛",
            platform="bilibili",
        ),  # type: ignore[arg-type]
        content=search_content,
        search_candidate_id=search_candidate_id,
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        context=_Context(),  # type: ignore[arg-type]
        stats=SimpleNamespace(technical_partial_results=0, filtered_content_count=0),  # type: ignore[arg-type]
        filter_snapshot=_filter_snapshot(),
    )
    executor._process_search_content(
        run=SimpleNamespace(),  # type: ignore[arg-type]
        scope=SimpleNamespace(
            id=uuid4(),
            source_type="keyword_search",
            source_value="爱玛",
            platform="bilibili",
        ),  # type: ignore[arg-type]
        prepared=prepared,
        content=prepared.final_content,
        search_executed=_ExecutedCall(
            request_id=uuid4(),
            attempt_id=uuid4(),
            raw_artifact_id=uuid4(),
            observed_at=_NOW,
            body={},
        ),
        provider_config=SimpleNamespace(),  # type: ignore[arg-type]
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        context=_Context(),  # type: ignore[arg-type]
        stats=SimpleNamespace(technical_partial_results=0, filtered_content_count=0),  # type: ignore[arg-type]
        filter_snapshot=_filter_snapshot(),
    )

    assert writer.ingested == [search_candidate_id, *detail_candidate_ids]
    assert writer.ingested_payloads[0]["brand_vehicle_resolution"] is None
    assert writer.ingested_payloads[-1]["brand_vehicle_resolution"].matched is True  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "source_type,matched", [("keyword_search", True), ("account", True), ("account", False)]
)
def test_sparse_followup_keeps_effective_filter_comment_facts_and_every_v2_owner_convergence(
    source_type, matched
) -> None:
    """派生决策不能丢primary字段，也不能把合并字段冒充secondary Raw。"""
    search = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"title": "其他品牌", "observed_fields": ["title"]}
    )
    primary = _content(comment_count=0, comment_count_observed=True).model_copy(
        update={
            "title": "爱玛成功详情" if matched else "没有目录命中的详情",
            "text": "已成功正文",
            "observed_fields": ["title", "text", "metrics.comment_count"],
        }
    )
    sparse = _content(comment_count=None, comment_count_observed=False).model_copy(
        update={"observed_fields": ["media"]}
    )
    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._brand_vehicle_resolver = BrandVehicleResolver()
    writer = _Writer()
    executor._content_writer = writer
    executor._content_state = _StateReader()
    executor._content_actions = _Actions()
    executor._decision_service = CollectionDecisionService()
    ids = (uuid4(), uuid4())
    executor._fetch_detail_candidates = lambda **_: _DetailFetchOutcome(
        (_DetailCandidate(primary, ids[0]), _DetailCandidate(sparse, ids[1]))
    )
    coverage_sources = []
    executor._record_non_fetch_coverage = lambda **kwargs: coverage_sources.append(
        kwargs["content"]
    )
    snapshot = _filter_snapshot()
    snapshot = snapshot.model_copy(
        update={"catalog": replace(snapshot.catalog, resolver_semantics="brand_scoped_vehicle_v2")}
    )
    kwargs = dict(
        run=SimpleNamespace(config_snapshot={}),
        scope=SimpleNamespace(
            id=uuid4(), source_type=source_type, source_value="爱玛", platform="bilibili"
        ),
        provider_config=SimpleNamespace(),
        context=_Context(),
        stats=SimpleNamespace(technical_partial_results=0, filtered_content_count=0),
        filter_snapshot=snapshot,
    )
    prepared = executor._prepare_search_content(
        content=search, search_candidate_id=uuid4(), **kwargs
    )
    executor._process_search_content(
        prepared=prepared,
        content=prepared.final_content,
        search_executed=_ExecutedCall(
            request_id=uuid4(),
            attempt_id=uuid4(),
            raw_artifact_id=uuid4(),
            observed_at=_NOW,
            body={},
        ),
        capability=BILIBILI_TIKHUB_CAPABILITY,
        policy=CollectionDecisionPolicyV1(),
        **kwargs,
    )
    assert not writer.filtered
    assert len(writer.ingested) == 3
    assert [item["canonical"] for item in writer.ingested_payloads] == [search, primary, sparse]
    assert all(
        item["brand_vehicle_snapshot"] is snapshot.catalog for item in writer.ingested_payloads
    )
    assert all(
        item["brand_vehicle_resolution"].matched == matched for item in writer.ingested_payloads
    )
    assert executor._content_actions.action.resolved_comment_count == 0
    assert coverage_sources == [primary]

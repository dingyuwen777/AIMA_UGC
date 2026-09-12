"""补齐评论增量缓存的 unavailable 与失败不推进状态边界。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.adapters.providers.imports_test.comparison_comment_enrichment.enrich_comments import (
    enrich_comparison_comments,
)
from aima_ugc.adapters.providers.imports_test.comparison_comment_enrichment.models import (
    CommentFetchCoverageV1,
    VehiclePairCommentRecordV1,
)
from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehicleModelMention,
    VehicleModelReference,
    VehiclePairRecordV1,
    VehiclePairReference,
)
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from pydantic import SecretStr


class _FailIfCalledTransport:
    """证明历史缓存命中时不会访问 Provider。"""

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        """生产代码一旦发请求就立即让测试失败。"""

        raise AssertionError(f"历史 unavailable 不应再次请求 Provider: {request.path}")


class _RateLimitedTransport:
    """用 429 模拟补采 run 在正式发布前失败。"""

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        """返回运行级失败，验证 cache/state 不会登记未完成 run。"""

        return ProviderTransportResponse(status_code=429, body={})


def _config() -> TikHubTestConfig:
    """构造不接触真实 Secret 的测试 Provider 配置。"""

    return TikHubTestConfig(
        base_url="https://api.tikhub.dev",
        api_key=SecretStr("test-key"),
        timeout_seconds=1,
    )


def _pair_record(external_id: str, *, target_model: str = "元宇宙") -> VehiclePairRecordV1:
    """构造最小合法车型共现帖子。"""

    observed_at = datetime(2026, 9, 12, 0, 0, tzinfo=UTC)
    content = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_id,
        content_type="image",
        title=f"{target_model}实际体验",
        text="Q3也试过",
        observed_at=observed_at,
        observed_fields=["title", "text"],
        source=CanonicalSourceV1(
            provider_name="manual",
            source_type="test",
            source_value="incremental-comment-cache-edge",
            observed_at=observed_at,
        ),
    )
    return VehiclePairRecordV1(
        record=UnifiedContentRecordV1(
            content=content,
            matched_keywords=[target_model, "Q3"],
        ),
        matched_target_models=(target_model,),
        matched_competitor_models=(VehicleModelReference(brand="九号", model="Q3"),),
        matched_pairs=(
            VehiclePairReference(
                target_model=target_model,
                competitor_brand="九号",
                competitor_model="Q3",
            ),
        ),
        model_mentions=(
            VehicleModelMention(
                brand="爱玛",
                model=target_model,
                fields=("title",),
                matched_aliases=(target_model,),
            ),
            VehicleModelMention(
                brand="九号",
                model="Q3",
                fields=("text",),
                matched_aliases=("Q3",),
            ),
        ),
    )


def _write_pair_input(path: Path, record: VehiclePairRecordV1) -> None:
    """写入 Stage 3 真实输入形态。"""

    path.write_text(f"{record.model_dump_json()}\n", encoding="utf-8")


def test_unavailable_history_is_cached_without_provider_request(tmp_path: Path) -> None:
    """旧 unavailable 结果也应默认复用，并使用本次最新 pair metadata。"""

    output_root = tmp_path / "comment-output"
    legacy_run = output_root / "runs" / "legacy-unavailable"
    legacy_run.mkdir(parents=True)
    legacy_record = VehiclePairCommentRecordV1(
        record=_pair_record("cached-unavailable"),
        comments=(),
        comment_fetch=CommentFetchCoverageV1(
            coverage="unavailable",
            root_comment_count=0,
            reply_count=0,
            request_count=1,
            root_stop_reason="legacy-unavailable",
        ),
    )
    legacy_jsonl = legacy_run / "comparison_posts_with_comments.jsonl"
    legacy_jsonl.write_text(f"{legacy_record.model_dump_json()}\n", encoding="utf-8")
    (legacy_run / "run_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "comparison-comment-enrichment-run.v1",
                "run_id": "legacy-unavailable",
                "outputs": {"jsonl": str(legacy_jsonl)},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    input_path = tmp_path / "current-pair.jsonl"
    _write_pair_input(input_path, _pair_record("cached-unavailable", target_model="墩墩"))
    summary = enrich_comparison_comments(
        input_path=input_path,
        output_root=output_root,
        run_id="reuse-unavailable",
        provider_config=_config(),
        transport=_FailIfCalledTransport(),
    )

    assert summary.rows_seen == 1
    assert summary.rows_cached == 1
    assert summary.rows_fetched == 0
    assert summary.rows_unavailable == 1
    assert summary.request_count == 0
    reused = VehiclePairCommentRecordV1.model_validate_json(
        summary.output_jsonl_path.read_text(encoding="utf-8").strip()
    )
    assert reused.record.matched_target_models == ("墩墩",)
    assert reused.comment_fetch.coverage == "unavailable"
    assert reused.comments == ()


def test_provider_failure_does_not_register_unpublished_run_in_state(tmp_path: Path) -> None:
    """Provider 运行级失败不得把未发布 run 写入 indexed_runs/cache。"""

    output_root = tmp_path / "comment-output"
    input_path = tmp_path / "pair.jsonl"
    _write_pair_input(input_path, _pair_record("rate-limited-note"))

    with pytest.raises(RuntimeError, match="HTTP 429"):
        enrich_comparison_comments(
            input_path=input_path,
            output_root=output_root,
            run_id="rate-limited",
            provider_config=_config(),
            transport=_RateLimitedTransport(),
        )

    assert not (output_root / "runs" / "rate-limited").exists()
    assert not (output_root / ".staging-rate-limited").exists()
    state_path = output_root / "state" / "manifest.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["indexed_runs"] == []
    cache_entries = list((output_root / "state" / "cache_index").glob("*.jsonl"))
    assert cache_entries == []

"""评论补采 complete 覆盖声明的数量不变量测试。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
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
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import (
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from pydantic import ValidationError


def _source(observed_at: datetime) -> CanonicalSourceV1:
    return CanonicalSourceV1(
        provider_name="test",
        source_type="test",
        source_value="comment-enrichment-invariant",
        observed_at=observed_at,
    )


def _record(observed_at: datetime) -> VehiclePairRecordV1:
    content = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="note-invariant",
        content_type="image",
        title="元宇宙和Q3",
        text="车型对比",
        observed_at=observed_at,
        observed_fields=["title", "text"],
        source=_source(observed_at),
    )
    return VehiclePairRecordV1(
        record=UnifiedContentRecordV1(content=content),
        matched_target_models=("元宇宙",),
        matched_competitor_models=(VehicleModelReference(brand="九号", model="Q3"),),
        matched_pairs=(
            VehiclePairReference(
                target_model="元宇宙",
                competitor_brand="九号",
                competitor_model="Q3",
            ),
        ),
        model_mentions=(
            VehicleModelMention(
                brand="爱玛",
                model="元宇宙",
                fields=("title",),
                matched_aliases=("元宇宙",),
            ),
            VehicleModelMention(
                brand="九号",
                model="Q3",
                fields=("title",),
                matched_aliases=("Q3",),
            ),
        ),
    )


def _comment(
    *,
    comment_id: str,
    root_comment_id: str,
    reply_count: int | None,
    observed_at: datetime,
) -> CanonicalCommentV1:
    return CanonicalCommentV1(
        platform="xiaohongshu",
        external_content_id="note-invariant",
        external_comment_id=comment_id,
        root_comment_id=root_comment_id,
        parent_comment_id=None,
        text=comment_id,
        observed_at=observed_at,
        metrics=CanonicalMetricsV1(reply_count=reply_count),
        source=_source(observed_at),
        observed_fields=["root_comment_id", "parent_comment_id", "text", "metrics.reply_count"],
    )


def test_complete_rejects_known_reply_shortfall() -> None:
    observed_at = datetime(2026, 9, 12, tzinfo=UTC)
    root = _comment(
        comment_id="root-1",
        root_comment_id="root-1",
        reply_count=2,
        observed_at=observed_at,
    )
    reply = _comment(
        comment_id="reply-1",
        root_comment_id="root-1",
        reply_count=0,
        observed_at=observed_at,
    )

    with pytest.raises(ValidationError, match="已知回复数"):
        VehiclePairCommentRecordV1(
            record=_record(observed_at),
            comments=(root, reply),
            comment_fetch=CommentFetchCoverageV1(
                coverage="complete",
                reported_total=1,
                root_comment_count=1,
                reply_count=1,
                request_count=2,
            ),
        )


def test_complete_rejects_known_root_comment_shortfall() -> None:
    observed_at = datetime(2026, 9, 12, tzinfo=UTC)
    root = _comment(
        comment_id="root-1",
        root_comment_id="root-1",
        reply_count=0,
        observed_at=observed_at,
    )

    with pytest.raises(ValidationError, match="一级评论总数"):
        VehiclePairCommentRecordV1(
            record=_record(observed_at),
            comments=(root,),
            comment_fetch=CommentFetchCoverageV1(
                coverage="complete",
                reported_total=2,
                root_comment_count=1,
                reply_count=0,
                request_count=1,
            ),
        )

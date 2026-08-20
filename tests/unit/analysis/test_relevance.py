from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis.relevance import (
    RelevanceKeyword,
    RelevanceService,
    normalize_keyword_storage_text,
)


def _content(*, title: str | None, text: str | None) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="content-1",
        content_type="note",
        title=title,
        text=text,
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
        observed_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
        observed_fields=["title", "text"],
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="aima-monitoring-excel.v1",
            source_value="input.xlsx",
            observed_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
        ),
    )


def test_storage_identity_trims_nfkc_casefold_but_preserves_internal_connectors() -> None:
    assert normalize_keyword_storage_text("  ＡＩＭＡ- ５００  ") == "aima- 500"
    assert normalize_keyword_storage_text("爱 玛/_·") == "爱 玛/_·"

    with pytest.raises(ValueError, match="规范化后不能为空"):
        normalize_keyword_storage_text("　")


def test_relevance_matches_title_or_text_and_deduplicates_match_equivalent_keywords() -> None:
    service = RelevanceService(
        (
            RelevanceKeyword(text="AIMA-500", priority=10),
            RelevanceKeyword(text=" aima 500 ", priority=20),
            RelevanceKeyword(text="爱玛", priority=30),
        )
    )

    decision = service.evaluate(_content(title="AIMA 500 新品", text="爱玛发布"))

    assert decision.matched is True
    assert decision.matched_keywords == ("AIMA-500", "爱玛")
    assert service.effective_keywords == ("AIMA-500", "爱玛")


def test_relevance_rejects_content_without_matching_text_and_empty_keyword_set() -> None:
    with pytest.raises(ValueError, match="至少需要一个"):
        RelevanceService(())

    decision = RelevanceService((RelevanceKeyword(text="爱玛", priority=10),)).evaluate(
        _content(title=None, text="其他品牌")
    )

    assert decision.matched is False
    assert decision.matched_keywords == ()

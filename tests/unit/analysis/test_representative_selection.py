from __future__ import annotations

from pathlib import Path

import pytest
from aima_ugc.adapters.providers.imports import REAL_USER_VOICE_TYPE, LabeledContent
from aima_ugc.modules.analysis.content_labeling import ContentLabelingLLMResponse
from aima_ugc.modules.analysis.representative_selection import (
    RepresentativeCandidate,
    RepresentativeDecisionModel,
    RepresentativeDecisionOutcome,
    RepresentativeSelectionService,
    build_candidate_pool,
    choose_representative_contents,
    validate_group_selection,
)


class _FakeLLM:
    provider_name = "fake"
    model_name = "fake-representative-v1"

    def __init__(self, group_response: str | None = None) -> None:
        self.group_response = group_response
        self.calls = []

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        if "selected_item_nos" in request.prompt:
            if self.group_response is None:
                raise RuntimeError("group selector unavailable")
            return ContentLabelingLLMResponse(raw_text=self.group_response)
        raise AssertionError("不应发起逐条重新打标请求")


def _content(
    content_id: str,
    *,
    platform: str = "抖音",
    voice_type: str = "真实用户发声",
    title: str = "标题",
    text: str = "用户具体描述了实际使用体验",
    author: str = "普通用户",
    sentiment_label: str = "正面",
) -> LabeledContent:
    return LabeledContent(
        row_number=2,
        platform=platform,
        content_id=content_id,
        title=title,
        text=text,
        author=author,
        published_at="2026-09-01 10:00:00",
        content_url=f"https://example.test/{content_id}",
        voice_type=voice_type,
        sentiment_label=sentiment_label,
    )


def test_candidate_pool_only_keeps_target_real_user_records() -> None:
    pool = build_candidate_pool(
        (
            _content("1"),
            _content("2", platform="微博"),
            _content("3", voice_type="营销推广发声"),
            _content("4", author="", text=""),
            _content("5", sentiment_label="中性"),
        ),
        real_user_voice_type=REAL_USER_VOICE_TYPE,
    )

    assert [candidate.content.content_id for candidate in pool.candidates] == ["1"]
    assert pool.summary.target_platform_rows == 4
    assert pool.summary.real_user_rows == 3
    assert pool.summary.excluded_non_target == 1
    assert pool.summary.excluded_non_user == 1
    assert pool.summary.excluded_non_sentiment == 1
    assert pool.summary.excluded_missing_evidence == 1


def test_group_protocol_fails_closed() -> None:
    with pytest.raises(ValueError, match="group_selection_duplicate_item_no"):
        validate_group_selection(
            '{"selected_item_nos": [1, 1]}',
            expected_item_nos=(1, 2),
            max_per_group=10,
        )


def test_service_uses_existing_labels_and_only_model_selects_within_groups(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("只在已有标签分组内选择代表性内容，不重新打标", encoding="utf-8")
    fake = _FakeLLM(group_response='{"selected_item_nos":[1]}')
    candidates = (
        RepresentativeCandidate(
            item_no=1,
            content=_content("1", sentiment_label="负面"),
        ),
    )

    result = RepresentativeSelectionService(
        prompt_path=prompt,
        llm=fake,
    ).run(candidates)

    assert result.outcomes[0].status == "succeeded"
    assert result.outcomes[0].attempts == 0
    assert result.outcomes[0].decision is not None
    assert result.outcomes[0].decision.sentiment == "负面"
    assert result.outcomes[0].decision.theme == ""
    assert result.outcomes[0].decision.reason == ""
    assert result.outcomes[0].decision.score == 0
    assert [item.candidate.content.content_id for item in result.selected] == ["1"]
    assert result.group_audits[0].used_model is False
    assert result.group_audits[1].used_model is True
    assert len(fake.calls) == 1


def test_local_fallback_covers_themes_and_does_not_fill_missing_groups() -> None:
    candidates = [RepresentativeCandidate(item_no=i, content=_content(str(i))) for i in range(1, 4)]
    outcomes = [
        RepresentativeDecisionOutcome(
            candidate=candidate,
            decision=RepresentativeDecisionModel(
                item_no=candidate.item_no,
                eligible=True,
                sentiment="正面",
                theme=theme,
                score=5,
            ),
            status="succeeded",
            attempts=0,
        )
        for candidate, theme in zip(candidates, ("续航表现", "续航表现", "外观设计"), strict=True)
    ]

    selected = choose_representative_contents(outcomes, max_per_group=2)

    assert [item.candidate.item_no for item in selected] == [1, 3]
    assert all(item.decision.sentiment == "正面" for item in selected)

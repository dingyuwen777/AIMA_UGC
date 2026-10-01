"""正式报告必须使用模型筛选并传递真实影响力指标。"""

from dataclasses import replace
from pathlib import Path

import pytest
from aima_ugc.modules.analysis.content_labeling import ContentLabelingLLMResponse
from aima_ugc.modules.analysis.representative_selection import (
    LabeledContent,
    RepresentativeCandidate,
    RepresentativeSelectionService,
)


class FakeLLM:
    provider_name = "fake"
    model_name = "fake"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests = []

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("overloaded")
        return ContentLabelingLLMResponse(raw_text='{"selected_item_nos":[1]}')


def candidate() -> RepresentativeCandidate:
    return RepresentativeCandidate(
        item_no=1,
        content=LabeledContent(
            row_number=2,
            platform="抖音",
            content_id="one",
            title="骑行感受",
            text="续航稳定",
            author="用户",
            published_at="2026-09-30",
            content_url="https://example.test/one",
            voice_type="真实用户发声",
            sentiment_label="正面",
        ),
    )


def test_formal_report_fails_closed(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("已有标签，优先影响力", encoding="utf-8")
    with pytest.raises(RuntimeError, match="overloaded"):
        RepresentativeSelectionService(
            prompt_path=prompt,
            llm=FakeLLM(fail=True),
            fail_closed=True,
        ).run((candidate(),))


def test_follower_and_interaction_counts_reach_model(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("优先粉丝数", encoding="utf-8")
    item = candidate()
    item = replace(
        item,
        content=replace(
            item.content,
            author_follower_count=50000,
            like_count=120,
            comment_count=30,
            share_count=9,
        ),
    )
    llm = FakeLLM()
    RepresentativeSelectionService(prompt_path=prompt, llm=llm, fail_closed=True).run((item,))
    body = llm.requests[0].items[0].text
    for value in ("50000", "120", "30", "9"):
        assert value in body

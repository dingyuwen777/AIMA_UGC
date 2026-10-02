"""工作台深链接的多选筛选必须贯穿声音广场冻结查询。"""

import pytest
from aima_ugc.contracts.http import ContentFilterSnapshot
from pydantic import ValidationError


def test_content_filters_preserve_plural_sentiment_and_voice_with_legacy_inputs() -> None:
    filters = ContentFilterSnapshot(
        sentiments=("正面", "负面"),
        voice_types=("真实用户发声", "品牌官方发声"),
        sentiment="正面",
        voice_type="真实用户发声",
    )
    assert filters.sentiments == ("正面", "负面")
    assert filters.voice_types == ("真实用户发声", "品牌官方发声")
    assert filters.sentiment == "正面"
    assert filters.voice_type == "真实用户发声"


@pytest.mark.parametrize("field", ["sentiments", "voice_types"])
def test_content_plural_filters_reject_duplicates(field: str) -> None:
    with pytest.raises(ValidationError):
        ContentFilterSnapshot(**{field: ("正面", "正面")})

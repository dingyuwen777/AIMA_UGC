"""工作台 Contract 与核心时间口径。"""

from datetime import date

import pytest
from aima_ugc.bootstrap.workbench_http import _previous_period
from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.contracts.workbench import (
    WorkbenchLayoutModule,
    WorkbenchLayoutUpdateRequest,
    WorkbenchQuery,
    WorkbenchStreamQuery,
)
from pydantic import ValidationError


def test_workbench_query_rejects_reversed_period_and_duplicate_filter_values() -> None:
    """公共查询必须阻止反向日期与同维度重复值，避免聚合身份不稳定。"""

    with pytest.raises(ValidationError):
        WorkbenchQuery(date_from=date(2026, 9, 10), date_to=date(2026, 9, 1))
    with pytest.raises(ValidationError):
        WorkbenchQuery(sentiments=("正面", "正面"))


def test_workbench_stream_query_has_bounded_cursor_page() -> None:
    """声音流必须用有限页和不透明游标遍历范围，不能靠固定最新 30 条循环。"""

    query = WorkbenchStreamQuery(limit=100, cursor="signed-cursor")

    assert query.limit == 100
    assert query.cursor == "signed-cursor"
    with pytest.raises(ValidationError):
        WorkbenchStreamQuery(limit=501)


def test_workbench_layout_requires_complete_unique_module_set() -> None:
    """保存布局必须一次提交三个模块，不能让部分 PATCH 制造未知默认值。"""

    modules = (
        WorkbenchLayoutModule(
            module_id="sound-stream",
            order=0,
            column_span=6,
            row_units=48,
        ),
        WorkbenchLayoutModule(
            module_id="brand-mind",
            order=1,
            column_span=6,
            row_units=48,
        ),
        WorkbenchLayoutModule(
            module_id="ugc-trend",
            order=2,
            column_span=6,
            row_units=48,
        ),
    )
    request = WorkbenchLayoutUpdateRequest(revision=0, modules=modules)
    assert [item.module_id for item in request.modules] == [
        "sound-stream",
        "brand-mind",
        "ugc-trend",
    ]

    with pytest.raises(ValidationError):
        WorkbenchLayoutUpdateRequest(
            revision=0,
            modules=(modules[0], modules[1], modules[1]),
        )


def test_analysis_scheme_requires_positive_sentiment_for_workbench_rate() -> None:
    """正向率依赖 active Taxonomy 的“正面”，管理员不能发布缺少该语义的 Scheme。"""

    with pytest.raises(ValidationError, match="正面"):
        AnalysisSchemeDefinitionRequest(
            prompt_template="规则\n{{AIMA_TAXONOMY_JSON}}",
            sentiments=("中性", "无法判断"),
            voice_types=("真实用户发声", "无法判断"),
            labels={
                "产品体验": ("续航表现",),
                "无法分类": ("无法判断",),
            },
        )


def test_previous_period_is_adjacent_equal_length_beijing_calendar_range() -> None:
    """“上期”固定为当前自然日范围之前的紧邻等长区间。"""

    previous_from, previous_to, start_at, end_at = _previous_period(
        date(2026, 9, 21),
        date(2026, 9, 27),
    )

    assert previous_from == date(2026, 9, 14)
    assert previous_to == date(2026, 9, 20)
    assert start_at.isoformat() == "2026-09-14T00:00:00+08:00"
    assert end_at.isoformat() == "2026-09-21T00:00:00+08:00"

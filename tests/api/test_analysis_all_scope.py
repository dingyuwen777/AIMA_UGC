"""AI Analysis Run 全量目标 Contract 回归。"""

from uuid import uuid4

import pytest
from aima_ugc.contracts.http import AnalysisRunTargetSelection
from pydantic import ValidationError


def test_analysis_run_all_scope_carries_no_content_ids() -> None:
    """全部数据 Scope 不向 HTTP Payload 搬运 Content ID。"""

    targets = AnalysisRunTargetSelection(scope="all")

    assert targets.scope == "all"
    assert targets.content_ids == ()


def test_analysis_run_all_scope_rejects_explicit_content_ids() -> None:
    """全部数据与显式选择互斥，避免产生含糊目标语义。"""

    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(scope="all", content_ids=(uuid4(),))


def test_analysis_run_selected_scope_keeps_existing_bounds() -> None:
    """已选内容模式继续要求 1—1000 条且去重，不因新增 all 放宽。"""

    content_id = uuid4()
    targets = AnalysisRunTargetSelection(scope="selected", content_ids=(content_id,))
    assert targets.content_ids == (content_id,)

    max_selected = tuple(uuid4() for _ in range(1000))
    assert (
        AnalysisRunTargetSelection(scope="selected", content_ids=max_selected).content_ids
        == max_selected
    )

    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(scope="selected", content_ids=())
    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(scope="selected", content_ids=(content_id, content_id))
    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(
            scope="selected",
            content_ids=tuple(uuid4() for _ in range(1001)),
        )

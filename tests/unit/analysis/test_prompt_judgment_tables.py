"""锁定 AI Prompt 的中文发声类型与判断标准可维护结构。"""

from aima_ugc.modules.analysis.content_labeling import (
    CONTENT_LABELING_PROMPT_PATH,
    PromptTaxonomyLoader,
)

_EXPECTED_VOICE_TYPES = (
    "真实用户发声",
    "品牌官方发声",
    "门店经销商发声",
    "营销推广发声",
    "行业从业发声",
    "媒体机构发声",
    "无法判断",
)


def _assert_markers_in_order(prompt: str, *markers: str) -> None:
    """要求同一判断标准内的表格、边界和示例按可维护顺序出现。"""

    positions = [prompt.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_prompt_uses_chinese_voice_type_values_as_final_business_values() -> None:
    """voice_type 合法值应直接等于最终中文业务展示值。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    assert taxonomy.voice_types == _EXPECTED_VOICE_TYPES
    assert len(taxonomy.primary_labels) == 9
    assert len(taxonomy.all_secondary_labels) == 39

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    for legacy_value in (
        "user_voice",
        "creator_marketing",
        "brand_official",
        "dealer_promotion",
        "media_information",
        "other_organization",
        "unknown",
    ):
        assert f'"{legacy_value}"' not in prompt


def test_prompt_judgment_standards_use_tables_with_examples_and_boundaries() -> None:
    """所有人工判断标准都应采用表格，并在表格后保留专属边界或示例。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    _assert_markers_in_order(
        prompt,
        "## 语义相关性判断标准",
        "| 判定结果 | 核心定义 | 说明 |",
        "### 相关性高混淆场景与示例",
        "## 发声类型判断标准",
    )
    _assert_markers_in_order(
        prompt,
        "## 发声类型判断标准",
        "| 推荐名称 | 核心定义 | 说明 |",
        "### 先组合两层证据，再分类",
        "### 七类边界与高混淆场景",
        "### 发声类型示例",
        "## 情感判断标准",
    )
    _assert_markers_in_order(
        prompt,
        "## 情感判断标准",
        "| 情感 | 核心定义 | 说明 |",
        "### 情感高混淆场景与示例",
        "## 一级/二级标签判断标准",
    )
    _assert_markers_in_order(
        prompt,
        "## 一级/二级标签判断标准",
        "| 一级标签 | 二级标签 | 覆盖内容与判断标准 | 典型表达仅作辅助 |",
        "## 多主题与边界冲突优先级",
        "## 示例",
        "## 返回前自检",
    )

    assert "爱玛骑遇团" in prompt
    assert "二手车" in prompt
    assert "行业从业发声" in prompt
    assert "媒体机构发声" in prompt
    assert "爱玛官方旗舰店" in prompt
    assert "AAA电动车批发王总" in prompt

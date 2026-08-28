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
    """主要判断标准应使用表格，并保留模型学习所需边界和示例。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    assert "| 判定结果 | 核心定义 | 说明 |" in prompt
    assert "| 推荐名称 | 核心定义 | 说明 |" in prompt
    assert "| 情感 | 核心定义 | 说明 |" in prompt
    assert "| 一级标签 | 二级标签 | 覆盖内容与判断标准 | 典型表达仅作辅助 |" in prompt

    assert "### 相关性高混淆场景与示例" in prompt
    assert "### 七类边界与高混淆场景" in prompt
    assert "### 发声类型示例" in prompt
    assert "### 情感高混淆场景与示例" in prompt
    assert "## 多主题与边界冲突优先级" in prompt
    assert "## 示例" in prompt

    assert "爱玛骑遇团" in prompt
    assert "二手车" in prompt
    assert "行业从业发声" in prompt
    assert "媒体机构发声" in prompt
    assert "爱玛官方旗舰店" in prompt
    assert "AAA电动车批发王总" in prompt

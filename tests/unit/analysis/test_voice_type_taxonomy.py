"""voice_type 与 sentiment/labels 共享 Prompt Taxonomy 运行时事实源。"""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3, ContentLabelPairV2
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.contracts.export import UnifiedDataExcelAnalysisV1
from aima_ugc.modules.analysis.content_labeling import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomyError,
    PromptTaxonomyLoader,
)

OBSERVED_AT = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
CURRENT_VOICE_TYPES = (
    "真实用户发声",
    "品牌官方发声",
    "门店经销商发声",
    "营销推广发声",
    "行业从业发声",
    "媒体机构发声",
    "无法判断",
)


def _content() -> CanonicalContentV1:
    """构造只覆盖正式 Analysis 最小输入边界的内容。"""

    return CanonicalContentV1(
        observed_fields=["title", "text"],
        platform="xiaohongshu",
        external_content_id="voice-type-taxonomy-test",
        content_type="note",
        title="爱玛通勤体验",
        text="骑了一年，日常通勤够用。",
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _mutated_prompt(tmp_path: Path, mutate: Any) -> Path:
    """只替换 Prompt 中机器 Taxonomy JSON，保留全部自然语言判断规则。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"(<!-- AIMA_TAXONOMY_START -->\s*```json\s*)(.*?)(\s*```\s*<!-- AIMA_TAXONOMY_END -->)",
        prompt,
        flags=re.DOTALL,
    )
    assert match is not None
    payload: dict[str, Any] = json.loads(match.group(2))
    mutate(payload)
    replacement = json.dumps(payload, ensure_ascii=False, indent=2)
    path = tmp_path / "content_labeling_voice_type_test.md"
    path.write_text(
        prompt[: match.start(2)] + replacement + prompt[match.end(2) :], encoding="utf-8"
    )
    return path


def _response(*, voice_type: str, sentiment: str, primary: str, secondary: str) -> str:
    """生成一个固定结构的单 item 模型响应。"""

    return json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": "relevant",
                    "voice_type": voice_type,
                    "sentiment": sentiment,
                    "labels": [
                        {
                            "primary_label": primary,
                            "secondary_label": secondary,
                        }
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )


def test_prompt_uses_business_defined_voice_type_taxonomy() -> None:
    """当前 Prompt 必须使用本轮确认的七类发声类型机器集合。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    assert taxonomy.voice_types == CURRENT_VOICE_TYPES
    assert "other_organization" not in taxonomy.voice_types
    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    for legacy_value in (
        "user_voice",
        "brand_official",
        "dealer_promotion",
        "creator_marketing",
        "industry_professional",
        "media_information",
        "other_organization",
    ):
        assert legacy_value not in prompt


def test_prompt_judgment_sections_use_tables_with_examples_and_confusion_cases() -> None:
    """各判断维度应统一为表格定义，并在表格后保留示例或高混淆场景。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    assert "## 语义相关性判断标准" in prompt
    assert "| 判断结果 | 核心定义 | 判断说明 |" in prompt
    assert "### 语义相关性高混淆场景" in prompt
    assert "### 语义相关性示例" in prompt

    assert "## 内容发声类型判断标准" in prompt
    assert "| 发声类型 | 核心定义 | 说明 |" in prompt
    assert "### 先组合两层证据，再分类" in prompt
    assert "### 发声类型高混淆场景" in prompt
    assert "### 发声类型示例" in prompt

    assert "## 情感判断标准" in prompt
    assert "| 情感 | 核心定义 | 判断说明 |" in prompt
    assert "### 情感高混淆场景" in prompt
    assert "### 情感判断示例" in prompt

    assert "## 一级/二级标签判断标准" in prompt
    assert "| 一级标签 | 二级标签 | 覆盖内容与判断标准 | 典型表达仅作辅助 |" in prompt
    assert "### 一级/二级标签高混淆场景" in prompt
    assert "### 一级/二级标签示例" in prompt


def test_prompt_retains_voice_type_business_boundaries_and_learning_examples() -> None:
    """表格化不能删掉业务给定的发声类型边界、已知主体和高混淆学习信号。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    assert "真实用户发声" in prompt
    assert "品牌官方发声" in prompt
    assert "门店经销商发声" in prompt
    assert "营销推广发声" in prompt
    assert "行业从业发声" in prompt
    assert "媒体机构发声" in prompt
    assert "无法判断" in prompt
    assert "爱玛骑遇团" in prompt
    assert "二手车" in prompt
    assert "爱玛官方旗舰店" in prompt
    assert "爱玛科学实验室" in prompt
    assert "修车" in prompt
    assert "雅迪" in prompt
    assert "作者“通勤小林”" in prompt
    assert "作者和正文都极少" in prompt


def test_prompt_voice_type_changes_are_runtime_driven_without_python_changes(
    tmp_path: Path,
) -> None:
    """Prompt 新增 voice type 后，正式 Service 应无需新增 Python Literal 即可接受。"""

    future_voice_type = "社区活动发声"

    def add_future_voice_type(payload: dict[str, Any]) -> None:
        payload["schema_version"] = "aima-content-taxonomy.v2"
        payload["voice_types"] = ["无法判断", future_voice_type]

    loader = PromptTaxonomyLoader(_mutated_prompt(tmp_path, add_future_voice_type))
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    fake = FakeContentLabelingLLM(
        responses=[
            _response(
                voice_type=future_voice_type,
                sentiment=taxonomy.sentiments[0],
                primary=primary,
                secondary=taxonomy.labels[primary][0],
            )
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    assert taxonomy.voice_types == ("无法判断", future_voice_type)
    assert result.items[0].analysis_status == "succeeded"
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.voice_type == future_voice_type


def test_unknown_voice_type_uses_taxonomy_validation_retry() -> None:
    """结构合法但不在当前 Taxonomy 的 voice_type 必须以稳定错误码触发 Validation Retry。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    valid_voice_type = taxonomy.voice_types[0]
    fake = FakeContentLabelingLLM(
        responses=[
            _response(
                voice_type="not_defined_in_prompt",
                sentiment=taxonomy.sentiments[0],
                primary=primary,
                secondary=taxonomy.labels[primary][0],
            ),
            _response(
                voice_type=valid_voice_type,
                sentiment=taxonomy.sentiments[0],
                primary=primary,
                secondary=taxonomy.labels[primary][0],
            ),
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert len(fake.calls) == 2
    assert "unknown_voice_type" in result.attempts[0].validation_error_codes
    assert "unknown_voice_type" in fake.calls[1].previous_validation_error_codes


def test_analysis_contract_keeps_structure_but_does_not_copy_voice_type_taxonomy() -> None:
    """Analysis Contract 只约束字符串结构，具体 voice type 由 RuntimeTaxonomyValidator 负责。"""

    analysis = ContentLabelAnalysisV3(
        relevance="relevant",
        voice_type="future_prompt_voice_type",
        sentiment="中性",
        labels=(ContentLabelPairV2(primary_label="测试一级", secondary_label="测试二级"),),
        prompt_version="content-labeling.v3",
        prompt_sha256="a" * 64,
        taxonomy_sha256="b" * 64,
        model_provider="fake",
        model="fake",
        input_hash="c" * 64,
        analyzed_at=OBSERVED_AT,
    )

    assert analysis.voice_type == "future_prompt_voice_type"


def test_excel_analysis_does_not_invent_voice_type_default() -> None:
    """导出兼容省略 voice_type，但不得用具体业务类别充当默认值。"""

    field = UnifiedDataExcelAnalysisV1.model_fields["voice_type"]

    assert not field.is_required()
    assert field.default is None


def test_duplicate_voice_type_in_prompt_taxonomy_fails_closed_before_llm(
    tmp_path: Path,
) -> None:
    """机器 Taxonomy 的 voice_types 必须与 sentiments 一样拒绝重复值。"""

    def duplicate_voice_type(payload: dict[str, Any]) -> None:
        payload["schema_version"] = "aima-content-taxonomy.v2"
        payload["voice_types"] = ["无法判断", "无法判断"]

    loader = PromptTaxonomyLoader(_mutated_prompt(tmp_path, duplicate_voice_type))
    fake = FakeContentLabelingLLM(responses=["{}"])

    with pytest.raises(PromptTaxonomyError):
        ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
            [_content()],
            max_validation_retries=0,
        )

    assert fake.calls == []


def test_production_python_does_not_copy_concrete_voice_type_values() -> None:
    """当前 Prompt voice type 机器值不得再复制到 Analysis 生产 Python。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    root = Path(__file__).resolve().parents[3] / "backend" / "src" / "aima_ugc"
    python_files = [
        *sorted((root / "contracts" / "analysis").rglob("*.py")),
        *sorted((root / "modules" / "analysis").rglob("*.py")),
    ]

    for path in python_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        string_literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        copied = [
            voice_type for voice_type in taxonomy.voice_types if voice_type in string_literals
        ]
        assert copied == [], f"{path} 不得硬编码具体 voice_type: {copied}"

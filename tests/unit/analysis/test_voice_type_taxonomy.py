"""voice_type 与 sentiment/labels 共享当前 Prompt Taxonomy 运行时事实源。"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

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
CURRENT_VOICE_TYPES = ("品牌官方发声", "真实用户发声", "营销推广发声")
LEGACY_V4_PROMPT_PATH = CONTENT_LABELING_PROMPT_PATH.with_name("content_labeling_v4.md")


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


def _mutated_v46_prompt(tmp_path: Path, *, old: str, new: str) -> Path:
    """只在测试副本中修改 V4.6 原文，验证 Parser 的 fail-closed 边界。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    assert prompt.count(old) >= 1
    path = tmp_path / "content_labeling_v4.6_test.md"
    path.write_text(prompt.replace(old, new, 1), encoding="utf-8")
    return path


def _response(
    *,
    voice_type: str,
    sentiment: str,
    primary: str,
    secondary: str,
) -> str:
    """生成固定结构的 V4.6 单 item 响应。"""

    return json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": "relevant",
                    "relevance_evidence": ["爱玛"],
                    "source_type": "ordinary_consumer",
                    "content_intent": "organic_inquiry",
                    "voice_type": voice_type,
                    "voice_evidence": ["骑了一年"],
                    "sentiment": sentiment,
                    "sentiment_evidence": ["通勤够用"],
                    "labels": [
                        {
                            "primary_label": primary,
                            "secondary_label": secondary,
                            "evidence": ["骑了一年"],
                        }
                    ],
                    "decision_status": "clear",
                }
            ]
        },
        ensure_ascii=False,
    )


def test_prompt_uses_v46_three_class_voice_type_taxonomy() -> None:
    """当前 Prompt 只暴露业务确认的 V4.6 三类发声类型。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    assert taxonomy.voice_types == CURRENT_VOICE_TYPES
    assert "个人交易发声" not in taxonomy.voice_types
    assert "门店经销商发声" not in taxonomy.voice_types
    assert "行业从业发声" not in taxonomy.voice_types
    assert "媒体机构发声" not in taxonomy.voice_types
    assert "无法判断" not in taxonomy.voice_types


def test_prompt_retains_v46_voice_boundaries_and_official_whitelists() -> None:
    """V4.6 原文必须保留三分类公式、严格真实用户准入和各平台官号白名单。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    assert "官号白名单命中 = 品牌官方发声" in prompt
    assert "A-F全部通过 = 真实用户发声" in prompt
    assert "其他一切 = 营销推广发声" in prompt
    assert "爱玛官方旗舰店" in prompt
    assert "爱玛科学实验室" in prompt
    assert "爱玛骑遇团" in prompt
    assert "真实到场 ≠ 真实用户发声" in prompt


def test_prompt_voice_type_addition_is_runtime_driven_without_python_contract_change(
    tmp_path: Path,
) -> None:
    """Prompt 闭集扩展仍由 RuntimeTaxonomyValidator 决定，不需要 Python Literal。"""

    future_voice_type = "社区活动发声"
    loader = PromptTaxonomyLoader(
        _mutated_v46_prompt(
            tmp_path,
            old="   - `营销推广发声`\n",
            new="   - `营销推广发声`\n   - `社区活动发声`\n",
        )
    )
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

    assert taxonomy.voice_types == (*CURRENT_VOICE_TYPES, future_voice_type)
    assert result.items[0].analysis_status == "succeeded"
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.voice_type == future_voice_type


def test_unknown_voice_type_uses_taxonomy_validation_retry() -> None:
    """结构合法但不在当前 Taxonomy 的 voice_type 必须触发 Validation Retry。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    fake = FakeContentLabelingLLM(
        responses=[
            _response(
                voice_type="not_defined_in_prompt",
                sentiment=taxonomy.sentiments[0],
                primary=primary,
                secondary=taxonomy.labels[primary][0],
            ),
            _response(
                voice_type="营销推广发声",
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


def test_duplicate_voice_type_in_v46_prompt_fails_closed_before_llm(
    tmp_path: Path,
) -> None:
    """V4.6 voice_type 闭集与其它 Taxonomy 一样拒绝重复值。"""

    loader = PromptTaxonomyLoader(
        _mutated_v46_prompt(
            tmp_path,
            old="   - `营销推广发声`\n",
            new="   - `营销推广发声`\n   - `营销推广发声`\n",
        )
    )
    fake = FakeContentLabelingLLM(responses=["{}"])

    with pytest.raises(PromptTaxonomyError):
        ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
            [_content()],
            max_validation_retries=0,
        )

    assert fake.calls == []


def test_legacy_v4_voice_taxonomy_remains_loadable() -> None:
    """代码升级后既有 V4 Scheme 的八类发声 Taxonomy 仍可恢复。"""

    taxonomy = PromptTaxonomyLoader(LEGACY_V4_PROMPT_PATH).load()

    assert taxonomy.output_protocol_version == "content-labeling.v4"
    assert "个人交易发声" in taxonomy.voice_types
    assert "无法判断" in taxonomy.voice_types


def test_analysis_contract_keeps_structure_but_does_not_copy_voice_type_taxonomy() -> None:
    """Analysis Contract 只约束字符串结构，具体 voice type 由 Runtime Taxonomy 负责。"""

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


def test_production_python_does_not_copy_concrete_voice_type_values() -> None:
    """当前 Prompt voice type 机器值不得复制到 Analysis 生产 Python。"""

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

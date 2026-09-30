"""可读表格 Prompt 的编译、版本冻结和模型校验回归。"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingService,
    FakeContentLabelingLLM,
)
from aima_ugc.modules.analysis.prompt_snapshot import FrozenPromptTaxonomyLoader
from aima_ugc.modules.analysis.prompt_taxonomy import (
    CONTENT_LABELING_PROMPT_PATH,
    PromptTaxonomyError,
    PromptTaxonomyLoader,
)
from aima_ugc.modules.analysis.schemes import (
    AnalysisSchemeVersionRecord,
    bootstrap_definition_from_prompt,
    compile_analysis_scheme,
    prompt_taxonomy_from_version,
)


def test_current_prompt_is_a_clean_markdown_source() -> None:
    """业务文档不再要求人工维护机器 JSON，并明确平台与单条请求。"""
    text = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    assert "## 机器可读" not in text
    assert "统计用途" not in text
    assert '"platform"' in text
    assert "## 发声类型判断标准" in text
    assert "一条内容一个请求" in text
    assert "## 文档维护边界（维护者必读）" in text
    assert "固定模板" in text
    assert "可编辑规则" in text
    assert "联动校验" in text
    taxonomy = PromptTaxonomyLoader.load_text(text)
    assert taxonomy.voice_types == ("品牌官方发声", "真实用户发声", "营销推广发声")
    assert len(taxonomy.all_secondary_labels) == 39


def test_markdown_content_revision_does_not_change_output_protocol() -> None:
    """修订内容编号不能改变结构协议，避免每次编辑规则都升级程序。"""
    text = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    original = PromptTaxonomyLoader.load_text(text)
    edited = PromptTaxonomyLoader.load_text(
        text.replace(original.prompt_version, "content-labeling.v99.1")
    )
    assert edited.output_protocol_version == original.output_protocol_version
    assert edited.taxonomy_sha256 == original.taxonomy_sha256
    assert edited.prompt_sha256 != original.prompt_sha256


def test_duplicate_label_table_row_reports_line() -> None:
    """表格错误应定位到源文件行，不能自动丢弃判断指南。"""
    text = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| 品牌评价 | 口碑与信任 |"))
    with pytest.raises(PromptTaxonomyError, match="行.*重复"):
        PromptTaxonomyLoader.load_text(text.replace(row, row + "\n" + row, 1))


def _text() -> str:
    return CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")


def _response(**updates: object) -> str:
    item = {
        "item_no": 1,
        "relevance": "relevant",
        "relevance_evidence": ["爱玛"],
        "source_type": "ordinary_consumer",
        "content_intent": "organic_experience",
        "real_user_qualified": True,
        "voice_type": "真实用户发声",
        "voice_evidence": ["骑了一年"],
        "sentiment": "正面",
        "sentiment_evidence": ["骑着舒服"],
        "labels": [
            {"primary_label": "骑行性能", "secondary_label": "舒适性", "evidence": ["骑着舒服"]}
        ],
        "decision_status": "clear",
    }
    item.update(updates)
    return json.dumps({"items": [item]}, ensure_ascii=False)


def _content() -> CanonicalContentV1:
    now = datetime(2026, 9, 30, tzinfo=UTC)
    return CanonicalContentV1(
        platform="douyin",
        external_content_id="md-scheme-acceptance",
        title="爱玛通勤体验",
        text="爱玛骑了一年，骑着舒服。",
        content_type="video",
        observed_at=now,
        observed_fields=["title", "text"],
        source=CanonicalSourceV1(
            provider_name="imports", operation="excel_import", observed_at=now
        ),
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("真实用户发声", "消费者体验"),
        ("正面", "好评"),
        ("骑行性能", "骑行体验"),
        ("舒适性", "乘坐舒适"),
    ],
)
def test_markdown_rename_applies_to_runtime_without_parallel_lists(old: str, new: str) -> None:
    compiled = compile_analysis_scheme(
        AnalysisSchemeDefinitionRequest(
            prompt_template=_text().replace(old, new),
            sentiments=("伪造旧镜像",),
            voice_types=("伪造旧镜像",),
            labels={"伪造": ("旧镜像",)},
        )
    )
    taxonomy = compiled.to_prompt_taxonomy()
    response = _response().replace(old, new)
    fake = FakeContentLabelingLLM(responses=[response])
    result = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy), llm=fake
    ).label_contents([_content()], max_validation_retries=0)
    analysis = result.items[0].analysis
    assert analysis is not None
    assert result.items[0].analysis_status == "succeeded"
    expected = json.loads(response)["items"][0]
    assert analysis.voice_type == expected["voice_type"]
    assert analysis.sentiment == expected["sentiment"]
    assert [(item.primary_label, item.secondary_label) for item in analysis.labels] == [
        (expected["labels"][0]["primary_label"], expected["labels"][0]["secondary_label"])
    ]
    assert "伪造旧镜像" not in taxonomy.voice_types
    assert fake.calls[0].prompt == compiled.prompt_text
    assert fake.calls[0].model_payload()[0]["platform"] == "douyin"
    assert len(fake.calls[0].items) == 1


def test_add_and_remove_classifications_use_table_and_rule_references() -> None:
    text = (
        _text()
        .replace(
            "<!-- /AIMA_TABLE -->",
            "| 媒体专题发声 | 媒体专题内容 | 与其他发声类型独立区分 |\n<!-- /AIMA_TABLE -->",
            1,
        )
        .replace(
            "| media_org | 任意 | 任意 | 营销推广发声 |",
            "| media_org | 任意 | 任意 | 媒体专题发声 |",
        )
    )
    added = PromptTaxonomyLoader.load_text(text)
    assert "媒体专题发声" in added.voice_types
    restored = text.replace(
        "| 媒体专题发声 | 媒体专题内容 | 与其他发声类型独立区分 |\n", ""
    ).replace(
        "| media_org | 任意 | 任意 | 媒体专题发声 |",
        "| media_org | 任意 | 任意 | 营销推广发声 |",
    )
    assert (
        PromptTaxonomyLoader.load_text(restored).taxonomy_sha256
        == PromptTaxonomyLoader.load_text(_text()).taxonomy_sha256
    )


@pytest.mark.parametrize(
    ("before", "after", "error"),
    [
        ("| media_org | 任意 | 任意 | 营销推广发声 |\n", "", "唯一覆盖"),
        (
            "| media_org | 任意 | 任意 | 营销推广发声 |",
            "| 未定义主体 | 任意 | 任意 | 营销推广发声 |",
            "行.*未定义主体",
        ),
        ("<!-- AIMA_TABLE: labels -->", "<!-- AIMA_TABLE: 未闭合 -->", "成对"),
        ("| 舒适性 |", "| 新名称 |", "JSON 示例"),
    ],
)
def test_invalid_markdown_fails_before_model_request(before: str, after: str, error: str) -> None:
    text = _text()
    assert before in text
    with pytest.raises(PromptTaxonomyError, match=error):
        compile_analysis_scheme(
            AnalysisSchemeDefinitionRequest(prompt_template=text.replace(before, after))
        )


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"real_user_qualified": False}, "inconsistent_voice_type"),
        ({"real_user_qualified": None}, "missing_real_user_qualification"),
        ({"source_type": "dealer_store"}, "inconsistent_voice_type"),
        ({"content_intent": "personal_transaction"}, "inconsistent_voice_type"),
        ({"voice_evidence": ["不存在的经历"]}, "fabricated_evidence"),
    ],
)
def test_semantic_conflict_and_fabricated_evidence_are_retried(
    updates: dict[str, object], code: str
) -> None:
    fake = FakeContentLabelingLLM(responses=[_response(**updates), _response()])
    result = ContentLabelingService(prompt_loader=PromptTaxonomyLoader(), llm=fake).label_contents(
        [_content()], max_validation_retries=1
    )
    assert result.items[0].analysis_status == "succeeded"
    assert code in result.attempts[0].validation_error_codes
    assert len(fake.calls) == 2


def _version(text: str) -> AnalysisSchemeVersionRecord:
    compiled = compile_analysis_scheme(bootstrap_definition_from_prompt(text))
    return AnalysisSchemeVersionRecord(
        id=uuid4(),
        scheme_id=uuid4(),
        version=1,
        status="published",
        description="冻结验收",
        definition=compiled.definition,
        compiled_prompt=compiled.prompt_text,
        prompt_sha256=compiled.prompt_sha256,
        taxonomy_sha256=compiled.taxonomy_sha256,
        created_by="test",
        created_at=datetime(2026, 9, 30, tzinfo=UTC),
        published_at=None,
    )


def test_published_version_restores_snapshot_without_recompiling_latest_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = _version(_text())
    import aima_ugc.modules.analysis.schemes as schemes

    monkeypatch.setattr(
        schemes, "compile_analysis_scheme", lambda *_args: pytest.fail("旧版本不能重新编译")
    )
    taxonomy = prompt_taxonomy_from_version(version)
    assert taxonomy.taxonomy_sha256 == version.taxonomy_sha256
    assert taxonomy.prompt_text == version.compiled_prompt
    with pytest.raises(ValueError, match="不一致"):
        prompt_taxonomy_from_version(
            replace(version, compiled_prompt=version.compiled_prompt + "改变")
        )


def test_legacy_published_version_can_restore_after_markdown_format_changes() -> None:
    legacy = Path(__file__).resolve().parents[2] / "fixtures/analysis/content_labeling_legacy_v3.md"
    version = _version(legacy.read_text(encoding="utf-8"))
    taxonomy = prompt_taxonomy_from_version(version)
    assert taxonomy.source_format == "legacy.v3.0"
    assert taxonomy.output_protocol_version == "content-labeling.v3.0"


def test_sentiment_name_change_changes_identity_without_relabeling_history() -> None:
    old = _version(_text())
    revised = _version(_text().replace("正面", "积极"))
    assert old.taxonomy_sha256 != revised.taxonomy_sha256
    assert "正面" in prompt_taxonomy_from_version(old).sentiments
    assert "积极" in prompt_taxonomy_from_version(revised).sentiments


def test_jsonb_key_reordering_preserves_primary_label_display_order() -> None:
    version = _version(_text())
    definition = AnalysisSchemeDefinitionRequest.model_validate(
        json.loads(json.dumps(version.definition.model_dump(mode="json"), sort_keys=True))
    )
    restored = prompt_taxonomy_from_version(replace(version, definition=definition))
    original = prompt_taxonomy_from_version(version)
    assert restored.primary_labels == original.primary_labels
    assert restored.taxonomy_sha256 == original.taxonomy_sha256

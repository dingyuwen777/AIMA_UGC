"""Prompt V4.6 首次正式打标基线的协议与运行时回归。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis.content_labeling import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomy,
    PromptTaxonomyLoader,
    content_labeling_input_hash,
)
from aima_ugc.modules.analysis.schemes import (
    AnalysisSchemeVersionRecord,
    bootstrap_definition_from_prompt,
    compile_analysis_scheme,
    prompt_taxonomy_from_version,
)

OBSERVED_AT = datetime(2026, 9, 29, 11, 26, tzinfo=UTC)
EXPECTED_PROMPT_SHA256 = "9a8fa7e98680ee707871f0303d4154dfbae4e900c0be90535edd8b5793ab02cb"


def _content(
    *,
    platform: str = "xiaohongshu",
    title: str | None = "爱玛B21怎么解码",
    text: str | None = "有人知道这个怎么才能解码提速吗",
) -> CanonicalContentV1:
    """构造 V4.6 模型输入；不添加与协议无关的业务字段。"""

    return CanonicalContentV1(
        observed_fields=["title", "text"],
        platform=platform,  # type: ignore[arg-type]
        external_content_id=f"v46-{platform}",
        content_type="note",
        title=title,
        text=text,
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _inquiry_item(
    taxonomy: PromptTaxonomy,
    *,
    voice_evidence: list[str] | None = None,
) -> dict[str, object]:
    """生成 V4.6 普通咨询的合法营销兜底响应。"""

    primary = "智能化与电子功能"
    secondary = "智能辅助功能"
    assert secondary in taxonomy.labels[primary]
    return {
        "item_no": 1,
        "relevance": "relevant",
        "relevance_evidence": ["爱玛B21"],
        "source_type": "ordinary_consumer",
        "content_intent": "organic_inquiry",
        "voice_type": "营销推广发声",
        "voice_evidence": ["怎么解码"] if voice_evidence is None else voice_evidence,
        "sentiment": "中性",
        "sentiment_evidence": ["怎么才能解码提速"],
        "labels": [
            {
                "primary_label": primary,
                "secondary_label": secondary,
                "evidence": ["解码提速"],
            }
        ],
        "decision_status": "clear",
    }


def _response(item: dict[str, object]) -> str:
    """序列化单条模型响应。"""

    return json.dumps({"items": [item]}, ensure_ascii=False)


def test_v46_prompt_asset_matches_the_uploaded_source_exactly() -> None:
    """正式 Prompt 文件必须与用户上传原文保持相同 LF 规范化文本身份。"""

    payload = CONTENT_LABELING_PROMPT_PATH.read_bytes()

    assert CONTENT_LABELING_PROMPT_PATH.name == "content_labeling_v4.6.md"
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_PROMPT_SHA256
    prompt = payload.decode("utf-8")
    assert len(prompt) == 11157
    assert prompt.count("\n") == 1047
    assert prompt.endswith("\n")


def test_v46_taxonomy_and_semantic_closed_sets_are_parsed_without_rule_bullets() -> None:
    """V4.6 Markdown 闭集必须形成唯一运行时 Taxonomy，规则项目不能混入标签。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    rules = taxonomy.semantic_rules

    assert taxonomy.prompt_version == "content-labeling.v4.6"
    assert taxonomy.output_protocol_version == "content-labeling.v4.6"
    assert taxonomy.voice_types == ("品牌官方发声", "真实用户发声", "营销推广发声")
    assert taxonomy.sentiments == ("正面", "中性", "负面", "混合")
    assert taxonomy.primary_labels == (
        "品牌评价",
        "外观设计",
        "骑行性能",
        "电池、续航与充电",
        "智能化与电子功能",
        "耐用性与质量",
        "价格与价值",
        "销售与购买体验",
        "售后服务",
    )
    assert len(taxonomy.all_secondary_labels) == 39
    assert "标签规则" not in taxonomy.labels
    assert "标签名称必须严格从上面选择。" not in taxonomy.all_secondary_labels
    assert rules is not None
    assert rules.source_types == (
        "ordinary_consumer",
        "brand_official",
        "dealer_store",
        "industry_practitioner",
        "media_org",
    )
    assert rules.content_intents == (
        "organic_experience",
        "organic_inquiry",
        "organic_complaint",
        "organic_recommendation",
        "personal_transaction",
        "commercial_sales",
        "organized_campaign",
        "news_information",
    )


def test_v46_scheme_bootstrap_compiles_back_to_the_exact_original_prompt() -> None:
    """结构化 Scheme 必须保留管理员能力，但首次编译不能改写模型实际 Prompt。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    definition = bootstrap_definition_from_prompt(prompt)
    compiled = compile_analysis_scheme(definition)

    assert compiled.prompt_text == prompt
    assert compiled.prompt_sha256 == EXPECTED_PROMPT_SHA256
    assert definition.voice_types == ("品牌官方发声", "真实用户发声", "营销推广发声")
    assert "无法判断" not in definition.sentiments
    assert "无法分类" not in definition.labels


def test_v46_scheme_round_trip_uses_declared_protocol_with_database_runtime_identity() -> None:
    """数据库 Scheme ID 只改变审计身份，不能让 V4.6 回落到旧 JSON Parser。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    definition = bootstrap_definition_from_prompt(prompt)
    compiled = compile_analysis_scheme(definition)
    scheme_id = uuid4()
    version_id = uuid4()
    record = AnalysisSchemeVersionRecord(
        id=version_id,
        scheme_id=scheme_id,
        version=1,
        status="published",
        description="test",
        definition=definition,
        compiled_prompt=compiled.prompt_text,
        prompt_sha256=compiled.prompt_sha256,
        taxonomy_sha256=compiled.taxonomy_sha256,
        created_by="test",
        created_at=OBSERVED_AT,
        published_at=OBSERVED_AT,
    )

    taxonomy = prompt_taxonomy_from_version(record)

    assert taxonomy.prompt_version == f"analysis-scheme:{version_id}"
    assert taxonomy.output_protocol_version == "content-labeling.v4.6"
    assert taxonomy.prompt_text == prompt


def test_v46_model_payload_and_input_hash_include_platform() -> None:
    """平台参与官号白名单判断，因此必须进入模型输入与幂等身份。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    fake = FakeContentLabelingLLM(responses=[_response(_inquiry_item(taxonomy))])
    xiaohongshu_content = _content(platform="xiaohongshu")

    result = ContentLabelingService(prompt_loader=PromptTaxonomyLoader(), llm=fake).label_contents(
        [xiaohongshu_content],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "succeeded"
    payload = fake.calls[0].model_payload()[0]
    assert payload["platform"] == "xiaohongshu"
    assert set(payload) == {"item_no", "platform", "title", "text", "author"}
    douyin = xiaohongshu_content.model_copy(
        update={"platform": "douyin", "external_content_id": "v46-douyin"}
    )
    assert content_labeling_input_hash(xiaohongshu_content) != content_labeling_input_hash(douyin)


def test_v46_marketing_voice_requires_nonempty_original_evidence() -> None:
    """营销推广是汇总兜底类别，但 voice_evidence 仍必须非空。"""

    taxonomy = PromptTaxonomyLoader().load()
    item = _inquiry_item(taxonomy, voice_evidence=[])
    fake = FakeContentLabelingLLM(responses=[_response(item)])

    result = ContentLabelingService(prompt_loader=PromptTaxonomyLoader(), llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "failed"
    assert "missing_evidence" in result.items[0].validation_error_codes


def test_v46_irrelevant_requires_empty_sentiment_evidence() -> None:
    """irrelevant 的 null/[] 是固定协议值，不能携带情感证据。"""

    taxonomy = PromptTaxonomyLoader().load()
    item = _inquiry_item(taxonomy)
    item.update(
        relevance="irrelevant",
        sentiment=None,
        sentiment_evidence=["怎么解码"],
        labels=[],
    )
    fake = FakeContentLabelingLLM(responses=[_response(item)])

    result = ContentLabelingService(prompt_loader=PromptTaxonomyLoader(), llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "failed"
    assert "irrelevant_has_sentiment_evidence" in result.items[0].validation_error_codes


def test_v46_empty_input_accepts_only_the_protocol_sentinel() -> None:
    """五个文本字段全空时仅允许 Prompt 明确批准的 EMPTY_INPUT evidence。"""

    item = {
        "item_no": 1,
        "relevance": "irrelevant",
        "relevance_evidence": ["[EMPTY_INPUT]"],
        "source_type": "ordinary_consumer",
        "content_intent": "organic_experience",
        "voice_type": "营销推广发声",
        "voice_evidence": ["[EMPTY_INPUT]"],
        "sentiment": None,
        "sentiment_evidence": [],
        "labels": [],
        "decision_status": "clear",
    }
    fake = FakeContentLabelingLLM(responses=[_response(item)])

    result = ContentLabelingService(prompt_loader=PromptTaxonomyLoader(), llm=fake).label_contents(
        [_content(title=None, text=None)],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.relevance == "irrelevant"

    nonempty = dict(item)
    nonempty["relevance_evidence"] = ["[EMPTY_INPUT]"]
    fake_bad = FakeContentLabelingLLM(responses=[_response(nonempty)])
    bad_result = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(),
        llm=fake_bad,
    ).label_contents([_content()], max_validation_retries=0)
    assert bad_result.items[0].analysis_status == "failed"
    assert "fabricated_evidence" in bad_result.items[0].validation_error_codes


def test_v46_excel_mode_does_not_fabricate_a_business_result_after_validation_failure() -> None:
    """V4.6 即使从离线入口执行，重试耗尽也必须保留失败事实。"""

    fake = FakeContentLabelingLLM(responses=["not-json"])
    result = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(),
        llm=fake,
        force_excel_complete=True,
    ).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "failed"
    assert result.items[0].analysis is None
    assert result.items[0].validation_error_codes == ("invalid_json",)


def test_v46_excel_mode_does_not_swallow_terminal_provider_errors() -> None:
    """V4.6 Provider 终态错误必须向上暴露，不能被本地分类兜底掩盖。"""

    fake = FakeContentLabelingLLM(responses=[])
    service = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(),
        llm=fake,
        force_excel_complete=True,
    )

    with pytest.raises(RuntimeError, match="没有剩余响应"):
        service.label_contents([_content()], max_validation_retries=0)

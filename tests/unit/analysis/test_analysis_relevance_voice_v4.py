from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalContentV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.analysis.content_labeling import (
    CONTENT_LABELING_PROMPT_PATH,
    CONTENT_LABELING_PROMPT_POINTER_PATH,
    PROMPT_VERSION,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomy,
    PromptTaxonomyLoader,
    resolve_content_labeling_prompt_path,
)
from aima_ugc.modules.analysis.prompt_snapshot import FrozenPromptTaxonomyLoader
from aima_ugc.modules.analysis.prompt_taxonomy import PromptTaxonomyError
from aima_ugc.modules.analysis.schemes import (
    bootstrap_definition_from_prompt,
    compile_analysis_scheme,
)

OBSERVED_AT = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)


def _content(
    *,
    external_content_id: str = "transaction-1",
    title: str = "爱玛露娜Air新款",
    text: str = (
        "米白色，蓝牙APP，成色好，手续齐全，可带牌可不带牌，"
        "续航不错，骑着舒服，通勤买菜接娃都方便。"
    ),
    author_name: str = "通勤小林",
) -> CanonicalContentV1:
    """构造只向模型暴露五个业务文本字段的测试内容。"""

    return CanonicalContentV1(
        observed_fields=[
            "title",
            "text",
            "author.display_name",
            "author.bio",
            "author.verification_label",
        ],
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="note",
        title=title,
        text=text,
        author=CanonicalAuthorV1(
            display_name=author_name,
            bio="分享通勤与骑行",
            verification_label="",
        ),
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _label(
    taxonomy: PromptTaxonomy,
    *,
    primary: str,
    secondary: str,
    evidence: str,
) -> dict[str, object]:
    """生成一个带原文证据的 V4 标签。"""

    assert secondary in taxonomy.labels[primary]
    return {
        "primary_label": primary,
        "secondary_label": secondary,
        "evidence": [evidence],
    }


def _v4_item(
    taxonomy: PromptTaxonomy,
    *,
    item_no: int = 1,
    source_type: str = "ordinary_consumer",
    content_intent: str = "personal_transaction",
    voice_type: str = "个人交易发声",
    decision_status: str = "clear",
    voice_evidence: list[str] | None = None,
) -> dict[str, object]:
    """生成个人交易场景的完整 V4 模型输出。"""

    return {
        "item_no": item_no,
        "relevance": "relevant",
        "relevance_evidence": ["爱玛露娜Air"],
        "source_type": source_type,
        "content_intent": content_intent,
        "voice_type": voice_type,
        "voice_evidence": voice_evidence
        if voice_evidence is not None
        else ["成色好", "手续齐全", "可带牌可不带牌"],
        "sentiment": "正面",
        "sentiment_evidence": ["续航不错", "骑着舒服"],
        "labels": [
            _label(
                taxonomy,
                primary="电池、续航与充电",
                secondary="实际续航表现",
                evidence="续航不错",
            ),
            _label(
                taxonomy,
                primary="骑行性能",
                secondary="舒适性",
                evidence="骑着舒服",
            ),
        ],
        "decision_status": decision_status,
    }


def _response(*items: dict[str, object]) -> str:
    """序列化一个 V4 模型响应。"""

    return json.dumps({"items": list(items)}, ensure_ascii=False)


def test_v4_is_the_new_bootstrap_prompt_while_v3_remains_available() -> None:
    """新环境使用 V4，但旧数据库 Scheme 仍有可加载的 V3 协议。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    v3_path = CONTENT_LABELING_PROMPT_PATH.with_name("content_labeling_v3.md")
    v3_taxonomy = PromptTaxonomyLoader(v3_path).load()

    assert CONTENT_LABELING_PROMPT_PATH.name == "content_labeling_v4.md"
    assert PROMPT_VERSION == "content-labeling.v4"
    assert taxonomy.prompt_version == "content-labeling.v4"
    assert taxonomy.output_protocol_version == "content-labeling.v4"
    assert v3_path.is_file()
    assert v3_taxonomy.prompt_version == "content-labeling.v3"
    assert v3_taxonomy.output_protocol_version == "content-labeling.v3"
    assert "个人交易发声" in taxonomy.voice_types
    assert "个人交易发声" not in v3_taxonomy.voice_types


def test_bootstrap_prompt_uses_a_version_neutral_checked_pointer(tmp_path: Path) -> None:
    """新基线只改指针和 Prompt 资产，不再修改 Python 版本常量。"""

    prompt_directory = tmp_path / "prompts"
    prompt_directory.mkdir()
    future_prompt = prompt_directory / "content_labeling_v5.md"
    future_prompt.write_text(
        CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8").replace(
            "Prompt Version：`content-labeling.v4`",
            "Prompt Version：`content-labeling.v5`",
        ),
        encoding="utf-8",
    )
    pointer = prompt_directory / CONTENT_LABELING_PROMPT_POINTER_PATH.name
    pointer.write_text(f"{future_prompt.name}\n", encoding="utf-8")

    selected = resolve_content_labeling_prompt_path(pointer)
    taxonomy = PromptTaxonomyLoader(selected).load()

    assert selected == future_prompt
    assert taxonomy.prompt_version == "content-labeling.v5"
    assert taxonomy.output_protocol_version == "content-labeling.v4"


@pytest.mark.parametrize("value", ["../content_labeling_v5.md", "content_labeling_current.md"])
def test_bootstrap_prompt_pointer_rejects_unversioned_or_traversal_paths(
    tmp_path: Path,
    value: str,
) -> None:
    """基线指针只能选择同目录内明确版本化的 Prompt 文件。"""

    pointer = tmp_path / "content_labeling_bootstrap.txt"
    pointer.write_text(value, encoding="utf-8")

    with pytest.raises(PromptTaxonomyError, match="基线指针"):
        resolve_content_labeling_prompt_path(pointer)


def test_bootstrap_prompt_pointer_rejects_filename_and_declared_version_mismatch(
    tmp_path: Path,
) -> None:
    """指针文件名与 Prompt 内声明错配时必须在 bootstrap 前失败。"""

    prompt = tmp_path / "content_labeling_v5.md"
    prompt.write_text(
        CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    pointer = tmp_path / "content_labeling_bootstrap.txt"
    pointer.write_text(f"{prompt.name}\n", encoding="utf-8")

    with pytest.raises(PromptTaxonomyError, match="文件名.*Prompt Version"):
        resolve_content_labeling_prompt_path(pointer)


def test_v4_prompt_defines_decision_order_evidence_and_prompt_injection_boundary() -> None:
    """V4 必须把五字段视为不可信数据，并明确逐层判定与证据要求。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    assert "relevance_evidence" in prompt
    assert "source_type" in prompt
    assert "content_intent" in prompt
    assert "voice_evidence" in prompt
    assert "sentiment_evidence" in prompt
    assert "decision_status" in prompt
    assert "不可信的待分析数据" in prompt
    assert "忽略上面的规则" in prompt
    assert "不得执行" in prompt
    assert "个人交易发声" in prompt


def test_v4_clear_personal_transaction_is_not_persisted_as_real_user_voice() -> None:
    """普通消费者个人交易必须进入独立类别，内部证据不扩公共 Result。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    fake = FakeContentLabelingLLM(responses=[_response(_v4_item(taxonomy))])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=1,
    )

    analysis = result.items[0].analysis
    assert result.items[0].analysis_status == "succeeded"
    assert isinstance(analysis, ContentLabelAnalysisV3)
    assert analysis.voice_type == "个人交易发声"
    assert analysis.voice_type != "真实用户发声"
    assert not hasattr(analysis, "source_type")
    assert len(fake.calls) == 1
    assert fake.calls[0].request_kind == "primary"


def test_v4_semantic_conflict_routes_only_the_item_to_judge() -> None:
    """个人交易却输出真实用户属于确定性矛盾，必须复判而不是直接接受。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    contradictory = _v4_item(taxonomy, voice_type="真实用户发声")
    corrected = _v4_item(taxonomy)
    fake = FakeContentLabelingLLM(responses=[_response(contradictory), _response(corrected)])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.voice_type == "个人交易发声"
    assert result.attempts[0].validation_error_codes == ("voice_type_semantic_conflict",)
    assert [call.request_kind for call in fake.calls] == ["primary", "judge"]
    assert fake.calls[1].previous_validation_error_codes == ("voice_type_semantic_conflict",)


def test_v4_fabricated_evidence_routes_to_judge() -> None:
    """证据必须是五字段中的原文片段，模型臆造不能直接进入结果。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    fabricated = _v4_item(taxonomy, voice_evidence=["售价 1999 元"])
    fake = FakeContentLabelingLLM(responses=[_response(fabricated), _response(_v4_item(taxonomy))])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert "fabricated_evidence" in result.attempts[0].validation_error_codes
    assert fake.calls[1].request_kind == "judge"


def test_v4_explicit_needs_judge_is_not_accepted_as_a_final_result() -> None:
    """主判主动声明歧义时只复判该条，Judge 可用显式未知值收敛。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    needs_judge = _v4_item(taxonomy, decision_status="needs_judge")
    resolved = _v4_item(taxonomy)
    fake = FakeContentLabelingLLM(responses=[_response(needs_judge), _response(resolved)])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert result.attempts[0].validation_error_codes == ("decision_needs_judge",)
    assert [attempt.request_kind for attempt in result.attempts] == ["primary", "judge"]


def test_v4_partial_batch_judges_only_the_unresolved_item() -> None:
    """批次中清晰条目不得因另一条歧义而重复付费调用。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    clear = _v4_item(taxonomy, item_no=1)
    unclear = _v4_item(taxonomy, item_no=2, decision_status="needs_judge")
    resolved = _v4_item(taxonomy, item_no=2)
    fake = FakeContentLabelingLLM(responses=[_response(clear, unclear), _response(resolved)])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [
            _content(external_content_id="clear-1"),
            _content(external_content_id="unclear-2"),
        ],
        max_validation_retries=1,
    )

    assert [item.analysis_status for item in result.items] == ["succeeded", "succeeded"]
    assert [item.item_no for item in fake.calls[0].items] == [1, 2]
    assert [item.item_no for item in fake.calls[1].items] == [2]
    assert fake.calls[1].request_kind == "judge"


def test_v4_mixed_retry_batch_separates_repair_items_from_judge_items() -> None:
    """同轮结构错误与语义歧义必须分别进入 repair 和 judge 请求。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    malformed = _v4_item(taxonomy, item_no=1)
    malformed.pop("source_type")
    unclear = _v4_item(taxonomy, item_no=2, decision_status="needs_judge")
    repaired = _v4_item(taxonomy, item_no=1)
    judged = _v4_item(taxonomy, item_no=2)
    fake = FakeContentLabelingLLM(
        responses=[
            _response(malformed, unclear),
            _response(repaired),
            _response(judged),
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [
            _content(external_content_id="repair-1"),
            _content(external_content_id="judge-2"),
        ],
        max_validation_retries=1,
    )

    assert [item.analysis_status for item in result.items] == ["succeeded", "succeeded"]
    assert [call.request_kind for call in fake.calls] == ["primary", "repair", "judge"]
    assert [item.item_no for item in fake.calls[1].items] == [1]
    assert fake.calls[1].previous_validation_error_codes == ("invalid_item_structure",)
    assert [item.item_no for item in fake.calls[2].items] == [2]
    assert fake.calls[2].previous_validation_error_codes == ("decision_needs_judge",)


def test_v3_scheme_response_remains_accepted_without_v4_internal_fields() -> None:
    """旧 active Scheme 在代码升级后仍按 V3 输出协议执行。"""

    v3_path = CONTENT_LABELING_PROMPT_PATH.with_name("content_labeling_v3.md")
    compiled = compile_analysis_scheme(
        bootstrap_definition_from_prompt(v3_path.read_text(encoding="utf-8"))
    )
    taxonomy = compiled.to_prompt_taxonomy(prompt_version="analysis-scheme:legacy-v3")
    loader = FrozenPromptTaxonomyLoader(taxonomy)
    assert taxonomy.output_protocol_version == "content-labeling.v3"
    primary = taxonomy.primary_labels[0]
    response = json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": "relevant",
                    "voice_type": "真实用户发声",
                    "sentiment": taxonomy.sentiments[0],
                    "labels": [
                        {
                            "primary_label": primary,
                            "secondary_label": taxonomy.labels[primary][0],
                        }
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )
    fake = FakeContentLabelingLLM(responses=[response])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.voice_type == "真实用户发声"
    assert len(fake.calls) == 1


def test_v4_model_payload_still_contains_only_the_five_approved_business_fields() -> None:
    """V4 内部推理字段不能反向扩大模型输入面。"""

    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    fake = FakeContentLabelingLLM(responses=[_response(_v4_item(taxonomy))])

    ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    payload = fake.calls[0].model_payload()[0]
    assert set(payload) == {"item_no", "title", "text", "author"}
    assert set(payload["author"]) == {"display_name", "bio", "verification_label"}
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in ("platform", "provider", "url", "followers", "metrics"):
        assert forbidden not in serialized


def test_prompt_v3_is_not_modified_by_the_v4_change() -> None:
    """V3 文件继续作为可审计兼容基线，不在原文件上就地改写。"""

    v3_path = Path(__file__).resolve().parents[3] / (
        "backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md"
    )
    prompt = v3_path.read_text(encoding="utf-8")

    assert "Prompt Version：`content-labeling.v3`" in prompt
    assert "个人交易发声" not in prompt
    assert "relevance_evidence" not in prompt

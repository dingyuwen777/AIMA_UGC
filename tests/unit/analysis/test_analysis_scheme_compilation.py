"""Analysis Scheme 当前 Prompt 编译与镜像一致性回归。"""

import pytest
from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH
from aima_ugc.modules.analysis.prompt_taxonomy import PromptTaxonomyLoader
from aima_ugc.modules.analysis.schemes import (
    bootstrap_definition_from_prompt,
    compile_analysis_scheme,
)


def _current_definition() -> AnalysisSchemeDefinitionRequest:
    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    return bootstrap_definition_from_prompt(prompt)


def test_compile_analysis_scheme_is_stable_across_jsonb_object_key_order() -> None:
    """JSONB 不保留对象键顺序，编译结果不能依赖 labels 的插入顺序。"""

    original = _current_definition()
    jsonb_round_trip = AnalysisSchemeDefinitionRequest(
        prompt_template=original.prompt_template,
        sentiments=original.sentiments,
        voice_types=original.voice_types,
        labels=dict(reversed(tuple(original.labels.items()))),
    )

    compiled_original = compile_analysis_scheme(original)
    compiled_round_trip = compile_analysis_scheme(jsonb_round_trip)

    assert compiled_original.prompt_text == compiled_round_trip.prompt_text
    assert compiled_original.prompt_sha256 == compiled_round_trip.prompt_sha256
    assert compiled_original.taxonomy_sha256 == compiled_round_trip.taxonomy_sha256


def test_compile_analysis_scheme_updates_human_and_machine_taxonomy_together() -> None:
    """结构化编辑必须同时更新模型可读正文和机器校验镜像。"""

    current = _current_definition()
    edited = AnalysisSchemeDefinitionRequest(
        prompt_template=current.prompt_template,
        sentiments=tuple(reversed(current.sentiments)),
        voice_types=tuple(reversed(current.voice_types)),
        labels={"自定义一级": ("自定义二级",)},
    )

    compiled = compile_analysis_scheme(edited)
    taxonomy = compiled.to_prompt_taxonomy()
    human_labels = compiled.prompt_text.split("## 9. 标签 Taxonomy", 1)[1].split("### 标签规则", 1)[
        0
    ]

    assert "2. `voice_type` 最终只允许：\n   - `营销推广发声`" in compiled.prompt_text
    assert "只允许：\n\n- `混合`\n- `负面`\n- `中性`\n- `正面`" in compiled.prompt_text
    assert "### 自定义一级\n\n- 自定义二级" in human_labels
    assert "### 品牌评价" not in human_labels
    assert taxonomy.sentiments == edited.sentiments
    assert taxonomy.voice_types == edited.voice_types
    assert dict(taxonomy.labels) == dict(edited.labels)
    assert "AIMA_LABEL_GUIDE_START" not in compiled.prompt_text
    assert "AIMA_LABEL_GUIDE_START" not in compiled.definition.prompt_template


def test_git_markdown_label_edit_auto_normalizes_machine_taxonomy() -> None:
    """直接修改 Git Markdown 标签区时自动生成一致的运行时机器 Taxonomy。"""

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    edited_prompt = prompt.replace(
        "### 品牌评价\n\n- 口碑与信任\n",
        "### 品牌评价\n\n- Git直改标签\n",
        1,
    )
    assert edited_prompt != prompt

    taxonomy = PromptTaxonomyLoader.load_text(edited_prompt)

    assert taxonomy.labels["品牌评价"][0] == "Git直改标签"
    assert '"Git直改标签"' in taxonomy.prompt_text
    assert "AIMA_LABEL_GUIDE_START" not in taxonomy.prompt_text

    definition = bootstrap_definition_from_prompt(edited_prompt)
    compiled = compile_analysis_scheme(definition)

    assert compiled.definition.labels["品牌评价"][0] == "Git直改标签"
    assert compiled.to_prompt_taxonomy().labels["品牌评价"][0] == "Git直改标签"
    assert '"Git直改标签"' in compiled.prompt_text
    assert "AIMA_LABEL_GUIDE_START" not in compiled.prompt_text


def test_current_bootstrap_label_guide_matches_all_current_label_pairs() -> None:
    """默认 Git Prompt 的详细标签指南必须与当前人类可读闭集完全一致。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    assert len(taxonomy.primary_labels) == 9
    assert len(taxonomy.all_secondary_labels) == 39
    assert "AIMA_LABEL_GUIDE_START" in taxonomy.prompt_text
    assert "AIMA_LABEL_GUIDE_END" in taxonomy.prompt_text


def test_compile_analysis_scheme_rejects_noncurrent_prompt_template() -> None:
    """Compiler 不为旧版本或无版本模板保留隐式兼容入口。"""

    current = _current_definition()
    definition = AnalysisSchemeDefinitionRequest(
        prompt_template=current.prompt_template.replace(
            "content-labeling.v3.0", "content-labeling.v4.6"
        ),
        sentiments=current.sentiments,
        voice_types=current.voice_types,
        labels=dict(current.labels),
    )

    with pytest.raises(ValueError, match="只接受当前 content-labeling.v3.0"):
        compile_analysis_scheme(definition)

"""Analysis Scheme 结构化定义编译与数据库快照模型。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis.prompt_taxonomy import (
    PROMPT_VERSION,
    PromptTaxonomy,
    PromptTaxonomyLoader,
)

TAXONOMY_PLACEHOLDER = "{{AIMA_TAXONOMY_JSON}}"
_TAXONOMY_START = "<!-- AIMA_TAXONOMY_START -->"
_TAXONOMY_END = "<!-- AIMA_TAXONOMY_END -->"
_BLOCK_PATTERN = re.compile(
    re.escape(_TAXONOMY_START) + r".*?" + re.escape(_TAXONOMY_END),
    flags=re.DOTALL,
)
_CURRENT_VERSION_DECLARATION = f"Prompt Version：`{PROMPT_VERSION}`"
_VOICE_TYPES_PATTERN = re.compile(r"(?m)(^2\. `voice_type` 最终只允许：\n)(?:   - `[^`\n]+`\n)+")
_SENTIMENTS_PATTERN = re.compile(
    r"(?ms)(^## 8\. 情感判断[^\n]*\n.*?^只允许：[^\S\n]*\n\n)"
    r"(?:- `[^`\n]+`\n)+"
)
_LABELS_PATTERN = re.compile(
    r"(?ms)(^## 9\. 标签 Taxonomy[^\n]*\n\n相关内容至少返回一个标签对。\n\n)"
    r"(?P<labels>.*?)(?=^### 标签规则[^\n]*$)"
)


def _ordered_label_names(definition: AnalysisSchemeDefinitionRequest) -> list[str]:
    """按人类可读标题固定标签顺序，避免 JSONB 对象键顺序影响编译结果。"""

    heading_order = re.findall(r"(?m)^### (?P<primary>.+?)\s*$", definition.prompt_template)
    ordered = list(dict.fromkeys(name for name in heading_order if name in definition.labels))
    ordered.extend(sorted(set(definition.labels) - set(ordered)))
    return ordered


def _render_current_prompt(definition: AnalysisSchemeDefinitionRequest) -> str:
    """把结构化闭集同步写入当前 v3.0 Prompt 的人类文本和机器镜像。"""

    if definition.prompt_template.count(_CURRENT_VERSION_DECLARATION) != 1:
        raise ValueError("Analysis Scheme 只接受当前 content-labeling.v3.0 模板")
    if definition.prompt_template.count(TAXONOMY_PLACEHOLDER) != 1:
        raise ValueError("Analysis Scheme 模板必须且只能包含一个 Taxonomy 占位符")

    prompt_text = definition.prompt_template
    voice_lines = "".join(f"   - `{value}`\n" for value in definition.voice_types)
    prompt_text, voice_substitutions = _VOICE_TYPES_PATTERN.subn(
        lambda match: match.group(1) + voice_lines,
        prompt_text,
    )

    sentiment_lines = "".join(f"- `{value}`\n" for value in definition.sentiments)
    prompt_text, sentiment_substitutions = _SENTIMENTS_PATTERN.subn(
        lambda match: match.group(1) + sentiment_lines,
        prompt_text,
    )

    label_sections = "\n\n".join(
        f"### {primary}\n\n"
        + "\n".join(f"- {secondary}" for secondary in definition.labels[primary])
        for primary in _ordered_label_names(definition)
    )
    prompt_text, label_substitutions = _LABELS_PATTERN.subn(
        lambda match: match.group(1) + label_sections + "\n\n",
        prompt_text,
    )
    if (voice_substitutions, sentiment_substitutions, label_substitutions) != (1, 1, 1):
        raise ValueError("当前 Prompt 必须包含唯一的发声类型、情感和标签人类可读闭集")

    taxonomy_payload = {
        "schema_version": "aima-content-taxonomy.v2",
        "sentiments": list(definition.sentiments),
        "voice_types": list(definition.voice_types),
        "labels": {key: list(definition.labels[key]) for key in _ordered_label_names(definition)},
    }
    readable_json = json.dumps(taxonomy_payload, ensure_ascii=False, indent=2)
    block = f"{_TAXONOMY_START}\n```json\n{readable_json}\n```\n{_TAXONOMY_END}"
    return prompt_text.replace(TAXONOMY_PLACEHOLDER, block)


@dataclass(frozen=True, slots=True)
class CompiledAnalysisScheme:
    """校验并编译后的 Prompt/Taxonomy 原子快照。"""

    definition: AnalysisSchemeDefinitionRequest
    prompt_text: str
    prompt_sha256: str
    taxonomy_sha256: str

    def to_prompt_taxonomy(self, *, prompt_version: str = PROMPT_VERSION) -> PromptTaxonomy:
        """构造 ContentLabelingService 可直接消费的冻结 Taxonomy。"""

        taxonomy = PromptTaxonomyLoader.load_text(
            self.prompt_text,
            prompt_version=prompt_version,
        )
        if (
            taxonomy.sentiments != self.definition.sentiments
            or taxonomy.voice_types != self.definition.voice_types
            or dict(taxonomy.labels) != dict(self.definition.labels)
            or taxonomy.taxonomy_sha256 != self.taxonomy_sha256
            or taxonomy.prompt_sha256 != self.prompt_sha256
        ):
            raise ValueError("Analysis Scheme 编译后的 Prompt Taxonomy 不一致")
        return taxonomy


@dataclass(frozen=True, slots=True)
class AnalysisSchemeVersionRecord:
    """数据库中一个 Scheme Version 的完整快照。"""

    id: UUID
    scheme_id: UUID
    version: int
    status: str
    description: str
    definition: AnalysisSchemeDefinitionRequest
    compiled_prompt: str
    prompt_sha256: str
    taxonomy_sha256: str
    created_by: str
    created_at: datetime
    published_at: datetime | None


def compile_analysis_scheme(
    definition: AnalysisSchemeDefinitionRequest,
) -> CompiledAnalysisScheme:
    """把结构化 Taxonomy 编译为唯一运行时 Prompt，并核对同源 Taxonomy。"""

    rendered_prompt = _render_current_prompt(definition)
    taxonomy = PromptTaxonomyLoader.load_text(rendered_prompt)
    if (
        taxonomy.sentiments != definition.sentiments
        or taxonomy.voice_types != definition.voice_types
        or dict(taxonomy.labels) != dict(definition.labels)
    ):
        raise ValueError("Analysis Scheme 编译后的 Prompt 闭集与结构化定义不一致")

    normalized_template, substitutions = _BLOCK_PATTERN.subn(
        TAXONOMY_PLACEHOLDER,
        taxonomy.prompt_text,
    )
    if substitutions != 1:
        raise ValueError("编译后的 Prompt 必须且只能包含一个 Taxonomy 区块")
    normalized_definition = AnalysisSchemeDefinitionRequest(
        prompt_template=normalized_template,
        sentiments=taxonomy.sentiments,
        voice_types=taxonomy.voice_types,
        labels=dict(taxonomy.labels),
    )

    return CompiledAnalysisScheme(
        definition=normalized_definition,
        prompt_text=taxonomy.prompt_text,
        prompt_sha256=taxonomy.prompt_sha256,
        taxonomy_sha256=taxonomy.taxonomy_sha256,
    )


def prompt_taxonomy_from_version(version: AnalysisSchemeVersionRecord) -> PromptTaxonomy:
    """把数据库 Version 恢复为运行时不可变 Taxonomy，并核对编译 Hash。"""

    compiled = compile_analysis_scheme(version.definition)
    if (
        compiled.prompt_text != version.compiled_prompt
        or compiled.prompt_sha256 != version.prompt_sha256
        or compiled.taxonomy_sha256 != version.taxonomy_sha256
    ):
        raise ValueError("Analysis Scheme Version 编译快照不一致")
    return compiled.to_prompt_taxonomy(prompt_version=f"analysis-scheme:{version.id}")


def bootstrap_definition_from_prompt(prompt_text: str) -> AnalysisSchemeDefinitionRequest:
    """把 Git Prompt 转为一次性 bootstrap 模板，避免数据库与文件双写。"""

    taxonomy = PromptTaxonomyLoader.load_text(prompt_text)
    template, substitutions = _BLOCK_PATTERN.subn(
        TAXONOMY_PLACEHOLDER,
        taxonomy.prompt_text,
    )
    if substitutions != 1:
        raise ValueError("Bootstrap Prompt 必须且只能包含一个 Taxonomy 区块")

    return AnalysisSchemeDefinitionRequest(
        prompt_template=template,
        sentiments=taxonomy.sentiments,
        voice_types=taxonomy.voice_types,
        labels=dict(taxonomy.labels),
    )


__all__ = [
    "AnalysisSchemeVersionRecord",
    "CompiledAnalysisScheme",
    "TAXONOMY_PLACEHOLDER",
    "bootstrap_definition_from_prompt",
    "compile_analysis_scheme",
    "prompt_taxonomy_from_version",
]

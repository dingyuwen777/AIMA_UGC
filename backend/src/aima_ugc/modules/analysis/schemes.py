"""Analysis Scheme 结构化定义编译与数据库快照模型。"""

from __future__ import annotations

import hashlib
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
_V46_VERSION = "content-labeling.v4.6"
_V46_VERSION_DECLARATION = f"Prompt Version：`{_V46_VERSION}`"
_V46_VOICE_PATTERN = re.compile(
    r"(?m)(^2\. `voice_type` 最终只允许：\n)(?:   - `[^`\n]+`\n)+"
)
_V46_SENTIMENT_PATTERN = re.compile(
    r"(?ms)(^# 8\. 情感判断\s*$.*?^只允许：\s*$\n\n)(?:- `[^`\n]+`\n)+"
)
_V46_LABELS_PATTERN = re.compile(
    r"(?ms)(^# 9\. 标签 Taxonomy\s*$\n\n相关内容至少返回一个标签对。\n\n)"
    r"(?P<labels>.*?)(?=^### 标签规则\s*$)"
)


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


def _render_v46_prompt(definition: AnalysisSchemeDefinitionRequest) -> str:
    """把 V4.6 结构化 Taxonomy 写回原 Markdown 闭集，保持其余业务原文不变。"""

    prompt_text = definition.prompt_template.replace(TAXONOMY_PLACEHOLDER, "")

    voice_lines = "".join(f"   - `{value}`\n" for value in definition.voice_types)
    prompt_text, voice_substitutions = _V46_VOICE_PATTERN.subn(
        lambda match: match.group(1) + voice_lines,
        prompt_text,
    )

    sentiment_lines = "".join(f"- `{value}`\n" for value in definition.sentiments)
    prompt_text, sentiment_substitutions = _V46_SENTIMENT_PATTERN.subn(
        lambda match: match.group(1) + sentiment_lines,
        prompt_text,
    )

    label_match = _V46_LABELS_PATTERN.search(prompt_text)
    if label_match is None:
        raise ValueError("V4.6 Prompt 缺少唯一标签 Taxonomy 区块")
    template_primary_order = re.findall(
        r"(?m)^## (?P<primary>.+?)\s*$",
        label_match.group("labels"),
    )
    ordered_primaries = [
        primary for primary in template_primary_order if primary in definition.labels
    ]
    ordered_primaries.extend(
        sorted(set(definition.labels) - set(ordered_primaries))
    )
    label_sections = "\n\n".join(
        f"## {primary}\n\n"
        + "\n".join(f"- {secondary}" for secondary in definition.labels[primary])
        for primary in ordered_primaries
    )
    prompt_text, label_substitutions = _V46_LABELS_PATTERN.subn(
        lambda match: match.group(1) + label_sections + "\n\n",
        prompt_text,
    )

    if (voice_substitutions, sentiment_substitutions, label_substitutions) != (1, 1, 1):
        raise ValueError("V4.6 Prompt 必须包含唯一的发声类型、情感和标签 Taxonomy 区块")
    return prompt_text


def compile_analysis_scheme(
    definition: AnalysisSchemeDefinitionRequest,
) -> CompiledAnalysisScheme:
    """把结构化 Taxonomy 编译为唯一运行时 Prompt，并核对同源 Taxonomy。"""

    if _V46_VERSION_DECLARATION in definition.prompt_template:
        prompt_text = _render_v46_prompt(definition)
    else:
        taxonomy_payload = {
            "schema_version": "aima-content-taxonomy.v2",
            "sentiments": list(definition.sentiments),
            "voice_types": list(definition.voice_types),
            # PostgreSQL JSONB 不保留对象键插入顺序，旧版 Prompt 继续显式规范化。
            "labels": {key: list(definition.labels[key]) for key in sorted(definition.labels)},
        }
        readable_json = json.dumps(taxonomy_payload, ensure_ascii=False, indent=2)
        block = f"{_TAXONOMY_START}\n```json\n{readable_json}\n```\n{_TAXONOMY_END}"
        prompt_text = definition.prompt_template.replace(TAXONOMY_PLACEHOLDER, block)

    taxonomy = PromptTaxonomyLoader.load_text(prompt_text)
    if (
        taxonomy.sentiments != definition.sentiments
        or taxonomy.voice_types != definition.voice_types
        or dict(taxonomy.labels) != dict(definition.labels)
    ):
        raise ValueError("Analysis Scheme 编译后的 Prompt Taxonomy 与结构化定义不一致")

    return CompiledAnalysisScheme(
        definition=definition,
        prompt_text=prompt_text,
        prompt_sha256=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
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
    if taxonomy.output_protocol_version == _V46_VERSION:
        if prompt_text.count(_V46_VERSION_DECLARATION) != 1:
            raise ValueError("V4.6 Bootstrap Prompt 必须声明唯一 Prompt Version")
        template = prompt_text.replace(
            _V46_VERSION_DECLARATION,
            _V46_VERSION_DECLARATION + TAXONOMY_PLACEHOLDER,
            1,
        )
    else:
        template, substitutions = _BLOCK_PATTERN.subn(TAXONOMY_PLACEHOLDER, prompt_text)
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

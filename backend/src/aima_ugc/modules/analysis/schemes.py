"""Analysis Scheme 结构化定义编译与数据库快照模型。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis.prompt_taxonomy import (
    PROMPT_VERSION,
    PromptTaxonomy,
)

TAXONOMY_PLACEHOLDER = "{{AIMA_TAXONOMY_JSON}}"
_TAXONOMY_START = "<!-- AIMA_TAXONOMY_START -->"
_TAXONOMY_END = "<!-- AIMA_TAXONOMY_END -->"
_BLOCK_PATTERN = re.compile(
    re.escape(_TAXONOMY_START) + r".*?" + re.escape(_TAXONOMY_END),
    flags=re.DOTALL,
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

        return PromptTaxonomy(
            prompt_version=prompt_version,
            prompt_text=self.prompt_text,
            schema_version="aima-content-taxonomy.v2",
            sentiments=self.definition.sentiments,
            voice_types=self.definition.voice_types,
            labels=MappingProxyType(dict(self.definition.labels)),
            taxonomy_sha256=self.taxonomy_sha256,
            prompt_sha256=self.prompt_sha256,
        )


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
    """把结构化 Taxonomy 注入唯一受控占位符并计算稳定 Hash。"""

    taxonomy_payload = {
        "schema_version": "aima-content-taxonomy.v2",
        "sentiments": list(definition.sentiments),
        "voice_types": list(definition.voice_types),
        # PostgreSQL JSONB 不保留对象键插入顺序，Prompt 编译必须显式规范化。
        "labels": {key: list(definition.labels[key]) for key in sorted(definition.labels)},
    }
    readable_json = json.dumps(taxonomy_payload, ensure_ascii=False, indent=2)
    normalized_json = json.dumps(
        taxonomy_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    block = f"{_TAXONOMY_START}\n```json\n{readable_json}\n```\n{_TAXONOMY_END}"
    prompt_text = definition.prompt_template.replace(TAXONOMY_PLACEHOLDER, block)
    return CompiledAnalysisScheme(
        definition=definition,
        prompt_text=prompt_text,
        prompt_sha256=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        taxonomy_sha256=hashlib.sha256(normalized_json).hexdigest(),
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

    from aima_ugc.modules.analysis.prompt_taxonomy import PromptTaxonomyLoader

    taxonomy = PromptTaxonomyLoader().load()
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

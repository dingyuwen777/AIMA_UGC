"""Prompt Markdown 中机器可读 Taxonomy 的唯一运行时加载器。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

_TAXONOMY_START = "<!-- AIMA_TAXONOMY_START -->"
_TAXONOMY_END = "<!-- AIMA_TAXONOMY_END -->"
_SEMANTIC_RULES_START = "<!-- AIMA_SEMANTIC_RULES_START -->"
_SEMANTIC_RULES_END = "<!-- AIMA_SEMANTIC_RULES_END -->"
_TAXONOMY_SCHEMA_VERSION = "aima-content-taxonomy.v2"
_SEMANTIC_RULES_SCHEMA_VERSION = "aima-content-semantic-rules.v1"
_SUPPORTED_OUTPUT_PROTOCOLS = frozenset({"content-labeling.v3", "content-labeling.v4"})
_PROMPT_VERSION_PATTERN = re.compile(r"Prompt Version：`(?P<version>content-labeling\.v\d+)`")
_OUTPUT_PROTOCOL_PATTERN = re.compile(
    r"<!-- AIMA_OUTPUT_PROTOCOL: (?P<version>content-labeling\.v\d+) -->"
)
_PROMPT_FILENAME_PATTERN = re.compile(r"content_labeling_v(?P<version>\d+)\.md")
_PROMPT_DIRECTORY = Path(__file__).with_name("prompts")
CONTENT_LABELING_PROMPT_POINTER_PATH = _PROMPT_DIRECTORY / "content_labeling_bootstrap.txt"


class PromptTaxonomyError(ValueError):
    """Prompt 或其机器 Taxonomy 不满足 P1E fail-closed 约束。"""


def resolve_content_labeling_prompt_path(pointer_path: Path) -> Path:
    """从受限指针解析新空库使用的版本化 Prompt 资产。"""

    pointer = Path(pointer_path)
    try:
        filename = pointer.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PromptTaxonomyError(f"无法读取 Prompt 基线指针: {pointer}") from exc
    filename_match = _PROMPT_FILENAME_PATTERN.fullmatch(filename)
    if filename_match is None:
        raise PromptTaxonomyError("Prompt 基线指针必须引用同目录内的版本化 Prompt 文件")

    prompt_path = pointer.parent / filename
    if not prompt_path.is_file():
        raise PromptTaxonomyError(f"Prompt 基线指针引用的文件不存在: {filename}")
    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptTaxonomyError(f"无法读取 Prompt 基线文件: {filename}") from exc
    declared_versions = _PROMPT_VERSION_PATTERN.findall(prompt_text)
    expected_version = f"content-labeling.v{filename_match.group('version')}"
    if declared_versions != [expected_version]:
        raise PromptTaxonomyError("Prompt 基线文件名与内部 Prompt Version 声明必须一致")
    return prompt_path


CONTENT_LABELING_PROMPT_PATH = resolve_content_labeling_prompt_path(
    CONTENT_LABELING_PROMPT_POINTER_PATH
)
_PROMPT_FILENAME_MATCH = _PROMPT_FILENAME_PATTERN.fullmatch(CONTENT_LABELING_PROMPT_PATH.name)
assert _PROMPT_FILENAME_MATCH is not None
PROMPT_VERSION = f"content-labeling.v{_PROMPT_FILENAME_MATCH.group('version')}"


@dataclass(frozen=True, slots=True)
class PromptSemanticRules:
    """V4 Output Protocol 内部主体/意图到发声类型的不可变映射。"""

    source_types: tuple[str, ...]
    content_intents: tuple[str, ...]
    organic_intents: tuple[str, ...]
    source_voice_types: Mapping[str, str]
    ordinary_consumer_organic_voice_type: str
    personal_transaction_voice_type: str
    campaign_voice_type: str
    unknown_voice_type: str

    def derive_voice_type(self, *, source_type: str, content_intent: str) -> str:
        """按 Prompt 声明的优先级确定最终发声类型，不复制业务枚举。"""

        source_voice_type = self.source_voice_types.get(source_type)
        if source_voice_type is not None:
            return source_voice_type
        if content_intent == "personal_transaction":
            return self.personal_transaction_voice_type
        if content_intent in {"commercial_sales", "organized_campaign"}:
            return self.campaign_voice_type
        if source_type == "ordinary_consumer" and content_intent in self.organic_intents:
            return self.ordinary_consumer_organic_voice_type
        return self.unknown_voice_type


@dataclass(frozen=True, slots=True)
class PromptTaxonomy:
    """从同一 Markdown Prompt 解析出的不可变运行时 Taxonomy。"""

    prompt_version: str
    output_protocol_version: str
    prompt_text: str
    schema_version: str
    sentiments: tuple[str, ...]
    voice_types: tuple[str, ...]
    labels: Mapping[str, tuple[str, ...]]
    semantic_rules: PromptSemanticRules | None
    taxonomy_sha256: str
    prompt_sha256: str

    @property
    def primary_labels(self) -> tuple[str, ...]:
        """按 Prompt JSON 原始顺序返回一级标签。"""

        return tuple(self.labels)

    @property
    def all_secondary_labels(self) -> tuple[str, ...]:
        """按一级标签顺序展开所有二级标签。"""

        return tuple(
            secondary for primary in self.primary_labels for secondary in self.labels[primary]
        )


class PromptTaxonomyLoader:
    """从唯一 Markdown Prompt 严格解析、校验并计算版本 Hash。"""

    def __init__(self, prompt_path: Path = CONTENT_LABELING_PROMPT_PATH) -> None:
        self._prompt_path = Path(prompt_path)

    @property
    def prompt_path(self) -> Path:
        """返回当前 Loader 使用的 Prompt 文件。"""

        return self._prompt_path

    def load(self) -> PromptTaxonomy:
        """读取完整 Prompt，并在任何模型调用前 fail closed。"""

        try:
            prompt_text = self._prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptTaxonomyError(f"无法读取 Prompt: {self._prompt_path}") from exc

        return self.load_text(prompt_text)

    @staticmethod
    def load_text(
        prompt_text: str,
        *,
        prompt_version: str | None = None,
    ) -> PromptTaxonomy:
        """从已给定的完整 Prompt 文本恢复运行时协议与 Taxonomy。"""

        taxonomy_json = _extract_marked_json(
            prompt_text,
            start_marker=_TAXONOMY_START,
            end_marker=_TAXONOMY_END,
            block_name="Taxonomy",
        )
        try:
            payload = json.loads(taxonomy_json, object_pairs_hook=_reject_duplicate_object_keys)
        except (json.JSONDecodeError, PromptTaxonomyError) as exc:
            raise PromptTaxonomyError("Prompt Taxonomy JSON 不合法") from exc

        if not isinstance(payload, dict):
            raise PromptTaxonomyError("Prompt Taxonomy 根节点必须是 JSON object")
        expected_keys = {"schema_version", "sentiments", "voice_types", "labels"}
        if set(payload) != expected_keys:
            raise PromptTaxonomyError(
                "Prompt Taxonomy 根节点字段必须严格为 schema_version/sentiments/voice_types/labels"
            )

        schema_version = payload["schema_version"]
        if schema_version != _TAXONOMY_SCHEMA_VERSION:
            raise PromptTaxonomyError(
                f"Prompt Taxonomy schema_version 必须为 {_TAXONOMY_SCHEMA_VERSION}"
            )

        sentiments = _clean_string_list(payload["sentiments"], field_name="sentiments")
        voice_types = _clean_string_list(payload["voice_types"], field_name="voice_types")
        raw_labels = payload["labels"]
        if not isinstance(raw_labels, dict) or not raw_labels:
            raise PromptTaxonomyError("labels 必须是非空 JSON object")

        labels: dict[str, tuple[str, ...]] = {}
        all_secondaries: set[str] = set()
        for raw_primary, raw_secondaries in raw_labels.items():
            if not isinstance(raw_primary, str):
                raise PromptTaxonomyError("一级标签必须是字符串")
            primary = raw_primary.strip()
            if not primary or primary != raw_primary:
                raise PromptTaxonomyError("一级标签必须是非空且无首尾空白的字符串")
            if primary in labels:
                raise PromptTaxonomyError(f"一级标签重复: {primary}")
            secondaries = _clean_string_list(
                raw_secondaries,
                field_name=f"labels.{primary}",
            )
            for secondary in secondaries:
                if secondary in all_secondaries:
                    raise PromptTaxonomyError(f"二级标签在不同一级标签下重复: {secondary}")
                all_secondaries.add(secondary)
            labels[primary] = secondaries

        normalized_taxonomy = json.dumps(
            {
                "schema_version": schema_version,
                "sentiments": list(sentiments),
                "voice_types": list(voice_types),
                "labels": {primary: list(secondaries) for primary, secondaries in labels.items()},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        resolved_prompt_version = prompt_version or _prompt_version_from_text(prompt_text)
        output_protocol_version = _output_protocol_from_text(prompt_text)
        semantic_rules = _parse_semantic_rules(
            prompt_text,
            output_protocol_version=output_protocol_version,
            voice_types=voice_types,
        )

        return PromptTaxonomy(
            prompt_version=resolved_prompt_version,
            output_protocol_version=output_protocol_version,
            prompt_text=prompt_text,
            schema_version=schema_version,
            sentiments=sentiments,
            voice_types=voice_types,
            labels=MappingProxyType(labels),
            semantic_rules=semantic_rules,
            taxonomy_sha256=hashlib.sha256(normalized_taxonomy).hexdigest(),
            prompt_sha256=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        )


def _extract_marked_json(
    prompt_text: str,
    *,
    start_marker: str,
    end_marker: str,
    block_name: str,
) -> str:
    if prompt_text.count(start_marker) != 1 or prompt_text.count(end_marker) != 1:
        raise PromptTaxonomyError(f"Prompt 必须且只能包含一组 {block_name} 标记")

    start_index = prompt_text.index(start_marker) + len(start_marker)
    end_index = prompt_text.index(end_marker)
    if end_index <= start_index:
        raise PromptTaxonomyError(f"Prompt {block_name} 标记顺序不合法")

    between = prompt_text[start_index:end_index].strip()
    match = re.fullmatch(r"```json\s*\n(?P<payload>.*?)\n```", between, flags=re.DOTALL)
    if match is None:
        raise PromptTaxonomyError(f"{block_name} 标记之间必须且只能包含一个 ```json 代码块")
    return str(match.group("payload"))


def _prompt_version_from_text(prompt_text: str) -> str:
    matches = _PROMPT_VERSION_PATTERN.findall(prompt_text)
    if len(matches) != 1:
        raise PromptTaxonomyError("Prompt 必须声明一个合法的 Prompt Version")
    return str(matches[0])


def _output_protocol_from_text(prompt_text: str) -> str:
    matches = _OUTPUT_PROTOCOL_PATTERN.findall(prompt_text)
    if len(matches) > 1:
        raise PromptTaxonomyError("Prompt 最多声明一个 Output Protocol")
    declared_prompt_version = _prompt_version_from_text(prompt_text)
    version = matches[0] if matches else declared_prompt_version
    if version not in _SUPPORTED_OUTPUT_PROTOCOLS:
        raise PromptTaxonomyError("Prompt Output Protocol 不受支持")
    return version


def _parse_semantic_rules(
    prompt_text: str,
    *,
    output_protocol_version: str,
    voice_types: tuple[str, ...],
) -> PromptSemanticRules | None:
    if output_protocol_version == "content-labeling.v3":
        if _SEMANTIC_RULES_START in prompt_text or _SEMANTIC_RULES_END in prompt_text:
            raise PromptTaxonomyError("V3 Prompt 不能声明 V4 Semantic Rules")
        return None

    raw_json = _extract_marked_json(
        prompt_text,
        start_marker=_SEMANTIC_RULES_START,
        end_marker=_SEMANTIC_RULES_END,
        block_name="Semantic Rules",
    )
    try:
        payload = json.loads(raw_json, object_pairs_hook=_reject_duplicate_object_keys)
    except (json.JSONDecodeError, PromptTaxonomyError) as exc:
        raise PromptTaxonomyError("Prompt Semantic Rules JSON 不合法") from exc
    if not isinstance(payload, dict):
        raise PromptTaxonomyError("Prompt Semantic Rules 根节点必须是 JSON object")

    expected_keys = {
        "schema_version",
        "source_types",
        "content_intents",
        "organic_intents",
        "source_voice_types",
        "ordinary_consumer_organic_voice_type",
        "personal_transaction_voice_type",
        "campaign_voice_type",
        "unknown_voice_type",
    }
    if set(payload) != expected_keys:
        raise PromptTaxonomyError("Prompt Semantic Rules 根节点字段不完整或存在额外字段")
    if payload["schema_version"] != _SEMANTIC_RULES_SCHEMA_VERSION:
        raise PromptTaxonomyError(
            f"Prompt Semantic Rules schema_version 必须为 {_SEMANTIC_RULES_SCHEMA_VERSION}"
        )

    source_types = _clean_string_list(payload["source_types"], field_name="source_types")
    content_intents = _clean_string_list(
        payload["content_intents"],
        field_name="content_intents",
    )
    organic_intents = _clean_string_list(
        payload["organic_intents"],
        field_name="organic_intents",
    )
    required_sources = {"ordinary_consumer", "unknown"}
    required_intents = {
        "personal_transaction",
        "commercial_sales",
        "organized_campaign",
        "unknown",
    }
    if not required_sources.issubset(source_types):
        raise PromptTaxonomyError("Semantic Rules 缺少必要 source_type")
    if not required_intents.issubset(content_intents):
        raise PromptTaxonomyError("Semantic Rules 缺少必要 content_intent")
    if not set(organic_intents).issubset(content_intents):
        raise PromptTaxonomyError("organic_intents 必须属于 content_intents")

    raw_source_voice_types = payload["source_voice_types"]
    if not isinstance(raw_source_voice_types, dict) or not raw_source_voice_types:
        raise PromptTaxonomyError("source_voice_types 必须是非空 JSON object")
    source_voice_types: dict[str, str] = {}
    for source_type, voice_type in raw_source_voice_types.items():
        if source_type not in source_types or source_type in required_sources:
            raise PromptTaxonomyError("source_voice_types 包含非法 source_type")
        if not isinstance(voice_type, str) or voice_type not in voice_types:
            raise PromptTaxonomyError("source_voice_types 包含非法 voice_type")
        source_voice_types[source_type] = voice_type
    if set(source_voice_types) != set(source_types) - required_sources:
        raise PromptTaxonomyError("每个非普通、非未知 source_type 都必须声明 voice_type 映射")

    voice_fields = (
        "ordinary_consumer_organic_voice_type",
        "personal_transaction_voice_type",
        "campaign_voice_type",
        "unknown_voice_type",
    )
    resolved_voice_types: dict[str, str] = {}
    for field_name in voice_fields:
        value = payload[field_name]
        if not isinstance(value, str) or value not in voice_types:
            raise PromptTaxonomyError(f"{field_name} 必须属于 voice_types")
        resolved_voice_types[field_name] = value
    if (
        resolved_voice_types["personal_transaction_voice_type"]
        == resolved_voice_types["ordinary_consumer_organic_voice_type"]
    ):
        raise PromptTaxonomyError("个人交易与普通消费者自然发声必须使用不同 voice_type")

    return PromptSemanticRules(
        source_types=source_types,
        content_intents=content_intents,
        organic_intents=organic_intents,
        source_voice_types=MappingProxyType(source_voice_types),
        ordinary_consumer_organic_voice_type=resolved_voice_types[
            "ordinary_consumer_organic_voice_type"
        ],
        personal_transaction_voice_type=resolved_voice_types["personal_transaction_voice_type"],
        campaign_voice_type=resolved_voice_types["campaign_voice_type"],
        unknown_voice_type=resolved_voice_types["unknown_voice_type"],
    )


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PromptTaxonomyError(f"Prompt Taxonomy JSON object 字段重复: {key}")
        result[key] = value
    return result


def _clean_string_list(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PromptTaxonomyError(f"{field_name} 必须是非空字符串数组")

    result: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        if not isinstance(raw_item, str):
            raise PromptTaxonomyError(f"{field_name} 只能包含字符串")
        item = raw_item.strip()
        if not item or item != raw_item:
            raise PromptTaxonomyError(f"{field_name} 不能包含空字符串或首尾空白")
        if item in seen:
            raise PromptTaxonomyError(f"{field_name} 包含重复值: {item}")
        seen.add(item)
        result.append(item)
    return tuple(result)

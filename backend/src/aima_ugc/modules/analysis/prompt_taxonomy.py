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
_TAXONOMY_SCHEMA_VERSION = "aima-content-taxonomy.v1"
PROMPT_VERSION = "content-labeling.v3"
CONTENT_LABELING_PROMPT_PATH = Path(__file__).with_name("prompts") / "content_labeling_v3.md"


class PromptTaxonomyError(ValueError):
    """Prompt 或其机器 Taxonomy 不满足 P1E fail-closed 约束。"""


@dataclass(frozen=True, slots=True)
class PromptTaxonomy:
    """从同一 Markdown Prompt 解析出的不可变运行时 Taxonomy。"""

    prompt_version: str
    prompt_text: str
    schema_version: str
    sentiments: tuple[str, ...]
    labels: Mapping[str, tuple[str, ...]]
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

        taxonomy_json = _extract_taxonomy_json(prompt_text)
        try:
            payload = json.loads(taxonomy_json, object_pairs_hook=_reject_duplicate_object_keys)
        except (json.JSONDecodeError, PromptTaxonomyError) as exc:
            raise PromptTaxonomyError("Prompt Taxonomy JSON 不合法") from exc

        if not isinstance(payload, dict):
            raise PromptTaxonomyError("Prompt Taxonomy 根节点必须是 JSON object")
        expected_keys = {"schema_version", "sentiments", "labels"}
        if set(payload) != expected_keys:
            raise PromptTaxonomyError(
                "Prompt Taxonomy 根节点字段必须严格为 schema_version/sentiments/labels"
            )

        schema_version = payload["schema_version"]
        if schema_version != _TAXONOMY_SCHEMA_VERSION:
            raise PromptTaxonomyError(
                f"Prompt Taxonomy schema_version 必须为 {_TAXONOMY_SCHEMA_VERSION}"
            )

        sentiments = _clean_string_list(payload["sentiments"], field_name="sentiments")
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
                "labels": {primary: list(secondaries) for primary, secondaries in labels.items()},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return PromptTaxonomy(
            prompt_version=PROMPT_VERSION,
            prompt_text=prompt_text,
            schema_version=schema_version,
            sentiments=sentiments,
            labels=MappingProxyType(labels),
            taxonomy_sha256=hashlib.sha256(normalized_taxonomy).hexdigest(),
            prompt_sha256=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        )


def _extract_taxonomy_json(prompt_text: str) -> str:
    if prompt_text.count(_TAXONOMY_START) != 1 or prompt_text.count(_TAXONOMY_END) != 1:
        raise PromptTaxonomyError("Prompt 必须且只能包含一组 Taxonomy 标记")

    start_index = prompt_text.index(_TAXONOMY_START) + len(_TAXONOMY_START)
    end_index = prompt_text.index(_TAXONOMY_END)
    if end_index <= start_index:
        raise PromptTaxonomyError("Prompt Taxonomy 标记顺序不合法")

    between = prompt_text[start_index:end_index].strip()
    match = re.fullmatch(r"```json\s*\n(?P<payload>.*?)\n```", between, flags=re.DOTALL)
    if match is None:
        raise PromptTaxonomyError("Taxonomy 标记之间必须且只能包含一个 ```json 代码块")
    return match.group("payload")


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

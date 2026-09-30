"""从可读 Markdown 定义表编译不可变分类与组合规则。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .prompt_taxonomy import (
    PromptSemanticRules,
    PromptTaxonomy,
    PromptTaxonomyError,
    _prompt_version_from_text,
)

SOURCE_FORMAT = "markdown-tables.v1"
OUTPUT_PROTOCOL = "content-labeling.tables.v1"


class _CompiledMarkdownSnapshot(BaseModel):
    """受支持的持久化编译格式，与文档修订号独立。"""

    model_config = ConfigDict(extra="forbid")
    source_format: str
    output_protocol: str
    sentiments: tuple[str, ...] = Field(min_length=1, max_length=50)
    voice_types: tuple[str, ...] = Field(min_length=1, max_length=50)
    labels: dict[str, tuple[str, ...]] = Field(min_length=1, max_length=100)
    primary_order: tuple[str, ...] = Field(min_length=1, max_length=100)
    source_types: tuple[str, ...] = Field(min_length=1, max_length=50)
    content_intents: tuple[str, ...] = Field(min_length=1, max_length=50)
    voice_rules: tuple[tuple[str, str, str, str], ...] = Field(min_length=1)


_TABLE = re.compile(
    r"<!-- AIMA_TABLE: (?P<name>[a-z_]+) -->\s*\n(?P<body>.*?)<!-- /AIMA_TABLE -->",
    re.DOTALL,
)
_HEADERS = {
    "voice_types": ("发声类型", "核心定义", "判断边界"),
    "sentiments": ("情感", "核心定义", "判断说明"),
    "source_types": ("值", "含义", "主要证据"),
    "content_intents": ("值", "含义"),
    "voice_rules": ("主体", "内容意图", "真实用户准入", "发声类型"),
    "labels": ("一级标签", "二级标签", "覆盖内容与判断标准", "典型表达仅作辅助"),
}


def _plain(cell: str) -> str:
    """去掉展示标记，保留规范分类原名。"""
    return cell.strip().strip("`*").strip()


def _cells(line: str) -> list[str]:
    """识别未转义的列分隔符，允许说明中使用转义竖线。"""
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", line.strip()[1:-1])]


def _tables(text: str) -> dict[str, list[tuple[int, list[str]]]]:
    """解析唯一的正式定义表，并把错误定位到 Markdown 行。"""
    tables: dict[str, list[tuple[int, list[str]]]] = {}
    for match in _TABLE.finditer(text):
        name = match["name"]
        base_line = text[: match.start("body")].count("\n") + 1
        if name not in _HEADERS or name in tables:
            raise PromptTaxonomyError(f"行 {base_line}：未知或重复定义表 {name}")
        rows: list[tuple[int, list[str]]] = []
        for offset, raw in enumerate(match["body"].splitlines()):
            line = raw.strip()
            if not line:
                continue
            number = base_line + offset
            if not line.startswith("|") or not line.endswith("|"):
                raise PromptTaxonomyError(f"行 {number}：定义表必须使用完整 Markdown 表格行")
            cells = _cells(line)
            if len(cells) != len(_HEADERS[name]):
                raise PromptTaxonomyError(f"行 {number}：{name} 列数不正确")
            if tuple(map(_plain, cells)) == _HEADERS[name] or all(
                re.fullmatch(r":?-{3,}:?", cell) for cell in cells
            ):
                continue
            if any(not cell for cell in cells):
                raise PromptTaxonomyError(f"行 {number}：定义表不能有空单元格")
            rows.append((number, cells))
        if not rows:
            raise PromptTaxonomyError(f"行 {base_line}：{name} 定义表不能为空")
        header = next((line.strip() for line in match["body"].splitlines() if line.strip()), "")
        if tuple(map(_plain, _cells(header))) != _HEADERS[name]:
            raise PromptTaxonomyError(f"行 {base_line}：{name} 表头不正确")
        tables[name] = rows
    if (
        set(tables) != set(_HEADERS)
        or text.count("<!-- /AIMA_TABLE -->") != len(tables)
        or text.count("<!-- AIMA_TABLE:") != len(tables)
    ):
        raise PromptTaxonomyError("正式定义表必须成对、唯一且包含：" + "、".join(_HEADERS))
    return tables


def _unique(rows: list[tuple[int, list[str]]], *, name: str) -> tuple[str, ...]:
    """校验分类规范名称，防止重复值和隐式别名。"""
    values: list[str] = []
    for number, cells in rows:
        value = _plain(cells[0])
        if not value or value in values or value in {"unknown", "无法判断", "无法分类"}:
            raise PromptTaxonomyError(f"行 {number}：{name} 分类重复、为空或为禁止值：{value}")
        values.append(value)
        if len(value) > 128 or len(values) > 50:
            raise PromptTaxonomyError(f"行 {number}：{name} 超过分类名称或数量限制")
    return tuple(values)


def _machine_payload(
    *,
    sentiments: tuple[str, ...],
    voices: tuple[str, ...],
    labels: Mapping[str, tuple[str, ...]],
    sources: tuple[str, ...],
    intents: tuple[str, ...],
    rules: tuple[tuple[str, str, str, str], ...],
) -> dict[str, Any]:
    """构造与自然语言修订号无关、可持久化且可核验的机器快照。"""
    return {
        "source_format": SOURCE_FORMAT,
        "output_protocol": OUTPUT_PROTOCOL,
        "sentiments": list(sentiments),
        "voice_types": list(voices),
        "labels": {name: list(values) for name, values in labels.items()},
        "primary_order": list(labels),
        "source_types": list(sources),
        "content_intents": list(intents),
        "voice_rules": [list(rule) for rule in rules],
    }


def _digest(payload: dict[str, Any]) -> str:
    """对机器语义统一编码，忽略 JSONB 对象键顺序。"""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _from_payload(text: str, payload: dict[str, Any], *, version: str | None) -> PromptTaxonomy:
    """恢复该格式的冻结产物；不重新解释历史 Markdown。"""
    snapshot = _CompiledMarkdownSnapshot.model_validate(payload)
    voices = snapshot.voice_types
    if set(snapshot.primary_order) != set(snapshot.labels) or len(
        set(snapshot.primary_order)
    ) != len(snapshot.primary_order):
        raise ValueError("冻结一级标签顺序与标签集合不一致")
    labels = {key: snapshot.labels[key] for key in snapshot.primary_order}
    source_types = tuple(payload["source_types"])
    content_intents = tuple(payload["content_intents"])
    rules = snapshot.voice_rules
    qualified_rules = tuple(rule for rule in rules if rule[2] == "通过")
    personal_source = qualified_rules[0][0] if qualified_rules else ""
    organic = tuple(dict.fromkeys(rule[1] for rule in qualified_rules))
    unqualified_voice = (
        matching_voice_types(rules, personal_source, organic[0], False)[0] if organic else ""
    )
    semantics = PromptSemanticRules(
        source_types=source_types,
        content_intents=content_intents,
        organic_intents=organic,
        source_voice_types=MappingProxyType(
            {
                source: voice
                for source, intent, gate, voice in rules
                if intent == "任意" and gate == "任意"
            }
        ),
        ordinary_consumer_organic_voice_type_when_real_user_qualified=qualified_rules[0][3]
        if qualified_rules
        else "",
        ordinary_consumer_organic_voice_type_when_not_qualified=unqualified_voice,
        ordinary_consumer_nonorganic_voice_type=next(
            (
                voice
                for source, intent, gate, voice in rules
                if source == personal_source and gate == "任意"
            ),
            "",
        ),
        real_user_gate="A-F_all_required",
        official_whitelist_priority=True,
        irrelevant_nonofficial_voice_type=unqualified_voice,
        voice_rules=rules,
    )
    return PromptTaxonomy(
        prompt_version=version or _prompt_version_from_text(text),
        output_protocol_version=OUTPUT_PROTOCOL,
        prompt_text=text,
        schema_version="aima-content-taxonomy.v3",
        sentiments=tuple(payload["sentiments"]),
        voice_types=voices,
        labels=MappingProxyType(labels),
        semantic_rules=semantics,
        taxonomy_sha256=_digest(payload),
        prompt_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_format=SOURCE_FORMAT,
    )


def compile_markdown_prompt(text: str, *, prompt_version: str | None = None) -> PromptTaxonomy:
    """从唯一可读源生成分类和规则；定义冲突在模型调用前失败关闭。"""
    _prompt_version_from_text(text)
    tables = _tables(text)
    voices = _unique(tables["voice_types"], name="发声类型")
    sentiments = _unique(tables["sentiments"], name="情感")
    sources = _unique(tables["source_types"], name="主体")
    intents = _unique(tables["content_intents"], name="意图")
    labels: dict[str, tuple[str, ...]] = {}
    secondaries: set[str] = set()
    for number, cells in tables["labels"]:
        primary, secondary = map(_plain, cells[:2])
        if (
            not primary
            or not secondary
            or max(len(primary), len(secondary)) > 256
            or primary in {"无法分类", "无法判断"}
            or secondary in {"无法分类", "无法判断"}
        ):
            raise PromptTaxonomyError(f"行 {number}：标签名称非法或超过长度限制")
        if secondary in secondaries:
            raise PromptTaxonomyError(f"行 {number}：二级标签重复：{secondary}")
        secondaries.add(secondary)
        labels[primary] = (*labels.get(primary, ()), secondary)
    rules_list: list[tuple[str, str, str, str]] = []
    for number, cells in tables["voice_rules"]:
        source, intent, gate, voice = map(_plain, cells)
        if source not in sources and source != "任意":
            raise PromptTaxonomyError(f"行 {number}：映射引用未定义主体：{source}")
        if intent not in intents and intent != "任意":
            raise PromptTaxonomyError(f"行 {number}：映射引用未定义意图：{intent}")
        if gate not in {"通过", "未通过", "任意"} or voice not in voices:
            raise PromptTaxonomyError(f"行 {number}：非法准入条件或发声类型：{voice}")
        rules_list.append((source, intent, gate, voice))
    rules = tuple(rules_list)
    unused_voices = set(voices) - {rule[3] for rule in rules}
    if unused_voices:
        raise PromptTaxonomyError(
            "发声类型缺少可到达的组合规则：" + "、".join(sorted(unused_voices))
        )
    for source in sources:
        for intent in intents:
            for qualified in (False, True):
                matching = matching_voice_types(rules, source, intent, qualified)
                if len(matching) != 1:
                    raise PromptTaxonomyError(
                        f"发声映射必须唯一覆盖组合：{source}/{intent}/{qualified}"
                    )
    payload = _machine_payload(
        sentiments=sentiments,
        voices=voices,
        labels=labels,
        sources=sources,
        intents=intents,
        rules=rules,
    )
    _validate_examples(text, payload)
    return _from_payload(text, payload, version=prompt_version)


def _validate_examples(text: str, payload: dict[str, Any]) -> None:
    """JSON 示例不能继续引用已删除分类或违反固定输出协议。"""
    for match in re.finditer(r"```json\s*\n(.*?)\n```", text, re.DOTALL):
        number = text[: match.start()].count("\n") + 1
        try:
            example = json.loads(match[1])
            if not isinstance(example, dict) or not isinstance(example.get("items"), list):
                continue
            for item in example["items"]:
                if "voice_type" not in item:
                    continue
                if (
                    item["voice_type"] not in payload["voice_types"]
                    or item["source_type"] not in payload["source_types"]
                    or item["content_intent"] not in payload["content_intents"]
                    or type(item["real_user_qualified"]) is not bool
                ):
                    raise ValueError("分类或准入字段不合法")
                if item["sentiment"] is not None and item["sentiment"] not in payload["sentiments"]:
                    raise ValueError("情感引用已删除分类")
                for pair in item["labels"]:
                    if pair["secondary_label"] not in payload["labels"].get(
                        pair["primary_label"], ()
                    ):
                        raise ValueError("标签示例引用已删除的父子关系")
                rules = tuple(tuple(rule) for rule in payload["voice_rules"])
                if matching_voice_types(
                    rules, item["source_type"], item["content_intent"], item["real_user_qualified"]
                ) != [item["voice_type"]]:
                    raise ValueError("发声示例与组合规则不一致")
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            raise PromptTaxonomyError(f"行 {number}：JSON 示例与定义不一致：{exc}") from exc


def matching_voice_types(
    rules: tuple[tuple[str, str, str, str], ...],
    source: str,
    intent: str,
    qualified: bool,
) -> list[str]:
    """按明确组合匹配，不猜测主体、意图或消费者身份。"""
    gate = "通过" if qualified else "未通过"
    return [
        voice
        for rule_source, rule_intent, rule_gate, voice in rules
        if rule_source in {source, "任意"}
        and rule_intent in {intent, "任意"}
        and rule_gate in {gate, "任意"}
    ]


def snapshot_payload(taxonomy: PromptTaxonomy) -> dict[str, Any]:
    """从已编译对象导出数据库快照，派生数据不作为独立编辑源。"""
    return _machine_payload(
        sentiments=taxonomy.sentiments,
        voices=taxonomy.voice_types,
        labels=taxonomy.labels,
        sources=taxonomy.semantic_rules.source_types,
        intents=taxonomy.semantic_rules.content_intents,
        rules=taxonomy.semantic_rules.voice_rules,
    )


def restore_snapshot(text: str, payload: dict[str, Any], *, version: str) -> PromptTaxonomy:
    """仅恢复受支持的快照格式，完整性由版本保存的双 Hash 检查。"""
    if (
        payload.get("source_format") != SOURCE_FORMAT
        or payload.get("output_protocol") != OUTPUT_PROTOCOL
    ):
        raise PromptTaxonomyError("Scheme 编译快照格式不受支持")
    try:
        return _from_payload(text, payload, version=version)
    except (KeyError, TypeError, ValueError) as exc:
        raise PromptTaxonomyError("Scheme 编译快照结构不合法") from exc

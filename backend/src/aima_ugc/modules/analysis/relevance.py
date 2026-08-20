"""面向所有采集来源的相关性准入规则。"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from aima_ugc.contracts.canonical import CanonicalContentV1

_IGNORED_MATCH_CONNECTORS = frozenset({"-", "_", "·"})


def normalize_keyword_storage_text(value: str) -> str:
    """生成数据库唯一性使用的关键词身份，保留内部空白和连接符。"""

    normalized = unicodedata.normalize("NFKC", value.strip()).casefold()
    if not normalized:
        raise ValueError("关键词规范化后不能为空")
    return normalized


def normalize_keyword_match_text(value: str) -> str:
    """生成相关性匹配身份；仅匹配时忽略空白和已批准的连接符。"""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace() and character not in _IGNORED_MATCH_CONNECTORS
    )


@dataclass(frozen=True, slots=True)
class RelevanceKeyword:
    """带稳定优先级的相关性关键词。"""

    text: str
    priority: int

    def __post_init__(self) -> None:
        display_text = self.text.strip()
        if not display_text:
            raise ValueError("关键词规范化后不能为空")
        if not normalize_keyword_match_text(display_text):
            raise ValueError("关键词匹配身份不能为空")
        object.__setattr__(self, "text", display_text)


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    """一条 Canonical Content 的相关性准入结论。"""

    matched: bool
    matched_keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PreparedKeyword:
    display_text: str
    match_text: str


class RelevanceService:
    """按冻结关键词快照过滤 Canonical Content，不访问数据库或 Provider。"""

    def __init__(self, keywords: tuple[RelevanceKeyword, ...]) -> None:
        prepared: list[_PreparedKeyword] = []
        seen_match_texts: set[str] = set()
        ordered = sorted(enumerate(keywords), key=lambda item: (item[1].priority, item[0]))
        for _, keyword in ordered:
            match_text = normalize_keyword_match_text(keyword.text)
            if match_text in seen_match_texts:
                continue
            prepared.append(_PreparedKeyword(keyword.text, match_text))
            seen_match_texts.add(match_text)
        if not prepared:
            raise ValueError("相关性过滤至少需要一个非空关键词")
        self._keywords = tuple(prepared)

    @property
    def effective_keywords(self) -> tuple[str, ...]:
        return tuple(keyword.display_text for keyword in self._keywords)

    def evaluate(self, content: CanonicalContentV1) -> RelevanceDecision:
        searchable_fields = (
            normalize_keyword_match_text(content.title or ""),
            normalize_keyword_match_text(content.text or ""),
        )
        matched_keywords = tuple(
            keyword.display_text
            for keyword in self._keywords
            if any(keyword.match_text in field for field in searchable_fields)
        )
        return RelevanceDecision(
            matched=bool(matched_keywords),
            matched_keywords=matched_keywords,
        )


__all__ = [
    "RelevanceDecision",
    "RelevanceKeyword",
    "RelevanceService",
    "normalize_keyword_match_text",
    "normalize_keyword_storage_text",
]

"""imports_test 本地关键词包加载器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aima_ugc.modules.analysis.offline_content import normalize_keyword_match_text


@dataclass(frozen=True, slots=True)
class LocalKeywordPack:
    """本地词包加载结果；保留源行数与规范化后的有效匹配词。"""

    path: Path
    source_keyword_count: int
    keywords: tuple[str, ...]

    @property
    def effective_keyword_count(self) -> int:
        return len(self.keywords)


def load_keyword_pack(path: Path) -> LocalKeywordPack:
    """读取 UTF-8 文本词包；忽略空行/注释，并按匹配规范化身份保留首个标准词。"""

    source_path = Path(path)
    raw_keywords: list[str] = []
    for raw_line in source_path.read_text(encoding="utf-8-sig").splitlines():
        keyword = raw_line.strip()
        if not keyword or keyword.startswith("#"):
            continue
        raw_keywords.append(keyword)

    if not raw_keywords:
        raise ValueError(f"关键词包至少需要一个非空关键词: {source_path}")

    effective_keywords: list[str] = []
    seen_match_texts: set[str] = set()
    for keyword in raw_keywords:
        match_text = normalize_keyword_match_text(keyword)
        if not match_text:
            raise ValueError(f"关键词规范化后不能为空: {keyword!r}")
        if match_text in seen_match_texts:
            continue
        effective_keywords.append(keyword)
        seen_match_texts.add(match_text)

    return LocalKeywordPack(
        path=source_path,
        source_keyword_count=len(raw_keywords),
        keywords=tuple(effective_keywords),
    )

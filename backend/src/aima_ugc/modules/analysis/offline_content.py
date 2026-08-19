"""P1 Provider-neutral JSONL 关键词过滤与去重。"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from pydantic import ValidationError

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1

_IGNORED_KEYWORD_CONNECTORS = frozenset({"-", "_", "·"})


@dataclass(frozen=True, slots=True)
class ContentFilterSummary:
    """关键词过滤结果摘要。"""

    input_path: Path
    output_path: Path
    rows_seen: int
    rows_written: int
    rows_filtered_out: int


@dataclass(frozen=True, slots=True)
class ContentDeduplicationSummary:
    """内容去重结果摘要。"""

    input_path: Path
    output_path: Path
    conflict_path: Path
    rows_seen: int
    rows_written: int
    duplicates_removed: int
    conflicts: int


class ContentDeduplicationConflictError(ValueError):
    """兼容旧版调用方保留的异常；当前去重流程不再因字段差异抛出。"""

    def __init__(self, summary: ContentDeduplicationSummary) -> None:
        self.summary = summary
        super().__init__(f"发现 {summary.conflicts} 个非等价重复记录；详见 {summary.conflict_path}")


@dataclass(frozen=True, slots=True)
class _SeenIdentity:
    fingerprint: str
    line_number: int
    byte_offset: int


@dataclass(frozen=True, slots=True)
class _PreparedKeyword:
    display_text: str
    match_text: str


def normalize_keyword_match_text(value: str) -> str:
    """把关键词或待匹配文本归一化为仅用于相关性清洗的匹配文本。"""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace() and character not in _IGNORED_KEYWORD_CONNECTORS
    )


def filter_canonical_content_jsonl(
    *,
    input_path: Path,
    output_path: Path,
    keywords: Iterable[str],
) -> ContentFilterSummary:
    """按规范化后的 title/text 包含关系过滤 Canonical JSONL，并写统一内容记录。"""

    source_path = Path(input_path)
    target_path = Path(output_path)
    prepared_keywords = _prepare_keywords(keywords)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    target_path.unlink(missing_ok=True)

    rows_seen = 0
    rows_written = 0
    try:
        with (
            source_path.open("rb") as input_file,
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
        ):
            for line_number, raw_line in enumerate(input_file, start=1):
                rows_seen += 1
                content = _parse_canonical_line(raw_line, source_path, line_number)
                searchable_fields = (
                    normalize_keyword_match_text(content.title or ""),
                    normalize_keyword_match_text(content.text or ""),
                )
                matched_keywords = [
                    keyword.display_text
                    for keyword in prepared_keywords
                    if any(keyword.match_text in field for field in searchable_fields)
                ]
                if not matched_keywords:
                    continue
                record = UnifiedContentRecordV1(
                    content=content,
                    matched_keywords=matched_keywords,
                )
                _write_model(output_file, record)
                rows_written += 1
            _flush_and_sync(output_file)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    temp_path.replace(target_path)
    return ContentFilterSummary(
        input_path=source_path,
        output_path=target_path,
        rows_seen=rows_seen,
        rows_written=rows_written,
        rows_filtered_out=rows_seen - rows_written,
    )


def deduplicate_content_jsonl(
    *,
    input_path: Path,
    output_path: Path,
) -> ContentDeduplicationSummary:
    """按 (platform, external_content_id) 去重，保留首次记录并审计字段差异。"""

    source_path = Path(input_path)
    target_path = Path(output_path)
    conflict_path = target_path.with_name("deduplication_conflicts.jsonl")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_conflict_path = conflict_path.with_name(f".{conflict_path.name}.tmp")
    for path in (temp_path, temp_conflict_path, target_path, conflict_path):
        path.unlink(missing_ok=True)

    rows_seen = 0
    rows_written = 0
    duplicates_removed = 0
    conflicts = 0
    seen: dict[tuple[str, str], _SeenIdentity] = {}
    try:
        with (
            source_path.open("rb") as input_file,
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
            temp_conflict_path.open("w", encoding="utf-8", newline="\n") as conflict_file,
        ):
            line_number = 0
            while True:
                byte_offset = input_file.tell()
                raw_line = input_file.readline()
                if not raw_line:
                    break
                line_number += 1
                rows_seen += 1
                record = _parse_unified_line(raw_line, source_path, line_number)
                identity = (record.content.platform, record.content.external_content_id)
                fingerprint = _business_fingerprint(record)
                previous = seen.get(identity)
                if previous is None:
                    seen[identity] = _SeenIdentity(
                        fingerprint=fingerprint,
                        line_number=line_number,
                        byte_offset=byte_offset,
                    )
                    _write_model(output_file, record)
                    rows_written += 1
                    continue
                if previous.fingerprint == fingerprint:
                    duplicates_removed += 1
                    continue

                duplicates_removed += 1
                conflicts += 1
                first_record = _read_record_at(
                    input_file,
                    source_path,
                    previous.byte_offset,
                    previous.line_number,
                )
                _write_conflict(
                    conflict_file,
                    first_record=first_record,
                    duplicate_record=record,
                    first_line=previous.line_number,
                    duplicate_line=line_number,
                )

            _flush_and_sync(output_file)
            _flush_and_sync(conflict_file)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        temp_conflict_path.unlink(missing_ok=True)
        raise

    summary = ContentDeduplicationSummary(
        input_path=source_path,
        output_path=target_path,
        conflict_path=conflict_path,
        rows_seen=rows_seen,
        rows_written=rows_written,
        duplicates_removed=duplicates_removed,
        conflicts=conflicts,
    )
    temp_conflict_path.replace(conflict_path)
    temp_path.replace(target_path)
    return summary


def _prepare_keywords(keywords: Iterable[str]) -> tuple[_PreparedKeyword, ...]:
    prepared: list[_PreparedKeyword] = []
    seen_match_texts: set[str] = set()
    for raw_keyword in keywords:
        display_text = raw_keyword.strip()
        if not display_text:
            raise ValueError("keywords 不能包含空字符串")
        match_text = normalize_keyword_match_text(display_text)
        if not match_text:
            raise ValueError("keywords 规范化后不能为空")
        if match_text in seen_match_texts:
            continue
        prepared.append(
            _PreparedKeyword(
                display_text=display_text,
                match_text=match_text,
            )
        )
        seen_match_texts.add(match_text)
    if not prepared:
        raise ValueError("keywords 至少需要一个非空关键词")
    return tuple(prepared)


def _parse_canonical_line(raw_line: bytes, path: Path, line_number: int) -> CanonicalContentV1:
    if not raw_line.strip():
        raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝继续处理")
    try:
        return CanonicalContentV1.model_validate_json(raw_line)
    except ValidationError as exc:
        raise ValueError(f"{path}: 第 {line_number} 行不是合法 CanonicalContentV1") from exc


def _parse_unified_line(raw_line: bytes, path: Path, line_number: int) -> UnifiedContentRecordV1:
    if not raw_line.strip():
        raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝继续处理")
    try:
        return UnifiedContentRecordV1.model_validate_json(raw_line)
    except ValidationError as exc:
        raise ValueError(f"{path}: 第 {line_number} 行不是合法 UnifiedContentRecordV1") from exc


def _read_record_at(
    input_file: BinaryIO,
    path: Path,
    byte_offset: int,
    line_number: int,
) -> UnifiedContentRecordV1:
    resume_offset = input_file.tell()
    input_file.seek(byte_offset)
    raw_line = input_file.readline()
    input_file.seek(resume_offset)
    return _parse_unified_line(raw_line, path, line_number)


def _business_payload(record: UnifiedContentRecordV1) -> dict[str, Any]:
    payload: dict[str, Any] = record.model_dump(mode="json")
    content = payload["content"]
    source = content["source"]
    source.pop("item_locator", None)
    return payload


def _business_fingerprint(record: UnifiedContentRecordV1) -> str:
    payload = _business_payload(record)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _different_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[str] = []
        for key in sorted(set(left) | set(right)):
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                differences.append(child_path)
                continue
            differences.extend(_different_paths(left[key], right[key], child_path))
        return differences
    if isinstance(left, list) and isinstance(right, list):
        return [] if left == right else [prefix]
    return [] if left == right else [prefix]


def _write_conflict(
    conflict_file: TextIO,
    *,
    first_record: UnifiedContentRecordV1,
    duplicate_record: UnifiedContentRecordV1,
    first_line: int,
    duplicate_line: int,
) -> None:
    payload = {
        "platform": duplicate_record.content.platform,
        "external_content_id": duplicate_record.content.external_content_id,
        "first_line": first_line,
        "duplicate_line": duplicate_line,
        "different_fields": _different_paths(
            _business_payload(first_record),
            _business_payload(duplicate_record),
        ),
    }
    conflict_file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    conflict_file.write("\n")


def _write_model(output_file: TextIO, record: UnifiedContentRecordV1) -> None:
    output_file.write(record.model_dump_json())
    output_file.write("\n")


def _flush_and_sync(output_file: TextIO) -> None:
    output_file.flush()
    os.fsync(output_file.fileno())

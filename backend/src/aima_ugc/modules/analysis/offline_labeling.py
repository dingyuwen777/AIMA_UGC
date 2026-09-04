"""离线 JSONL 打标的文件预检、checkpoint 持久化、原子回写与恢复。"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import TextIO

from pydantic import TypeAdapter, ValidationError

from aima_ugc.contracts.analysis import (
    ContentLabelAnalysis,
    ContentLabelAnalysisV3,
    UnifiedContentRecordV1,
)

from .content_labeling import (
    ContentLabelingAttempt,
    ContentLabelingBatchResult,
    ContentLabelingService,
    _input_hash,
    _to_model_item,
)
from .prompt_taxonomy import PromptTaxonomy

DEFAULT_OFFLINE_LLM_CONCURRENCY = 250


@dataclass(frozen=True, slots=True)
class OfflineContentLabelingSummary:
    """一次离线 JSONL 打标的可审计摘要。"""

    input_path: Path
    analysis_dir: Path
    rows_seen: int
    rows_already_labeled: int
    rows_recovered: int
    rows_succeeded: int
    rows_failed: int
    llm_attempts: int
    rows_irrelevant_removed: int = 0
    peak_in_flight: int = 0
    llm_http_requests: int = 0
    transport_retries: int = 0
    llm_request_audit_path: Path | None = None
    llm_calculated_http_requests: int = 0
    llm_uncalculated_http_requests: int = 0
    llm_input_tokens: int = 0
    llm_input_cache_hit_tokens: int = 0
    llm_input_cache_miss_tokens: int = 0
    llm_output_tokens: int = 0
    llm_total_cost_amount: Decimal | None = None
    llm_cost_currency: str | None = None


@dataclass(frozen=True, slots=True)
class _SourceRow:
    line_number: int
    record: UnifiedContentRecordV1
    input_hash: str


@dataclass(frozen=True, slots=True)
class _ItemOutcome:
    source: _SourceRow
    result: ContentLabelingBatchResult


_CheckpointKey = tuple[str, str, str]
_StableContentKey = tuple[str, str]
_ANALYSIS_ADAPTER: TypeAdapter[ContentLabelAnalysis] = TypeAdapter(ContentLabelAnalysis)


def _validate_max_concurrency(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("并发数必须是大于 0 的整数")


def _preflight_source(
    source_path: Path,
    *,
    checkpoint_index: dict[_CheckpointKey, ContentLabelAnalysis],
) -> tuple[int, int, int, int]:
    """付费调用前完整验证输入，并计算本次待处理集合。"""

    rows_seen = 0
    rows_already_labeled = 0
    rows_recovered = 0
    pending_count = 0
    stable_identities: set[_StableContentKey] = set()

    with source_path.open("rb") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            rows_seen += 1
            record = _parse_record(raw_line, source_path, line_number)
            identity = (record.content.platform, record.content.external_content_id)
            if identity in stable_identities:
                raise ValueError(
                    f"{source_path}: 第 {line_number} 行出现重复稳定内容身份 "
                    f"({identity[0]}, {identity[1]})，拒绝在付费模型调用前继续"
                )
            stable_identities.add(identity)
            if record.analysis is not None:
                rows_already_labeled += 1
                continue
            input_hash = _content_input_hash(record)
            if _checkpoint_key(record, input_hash) in checkpoint_index:
                rows_recovered += 1
            else:
                pending_count += 1

    return rows_seen, rows_already_labeled, rows_recovered, pending_count


def _iter_pending_rows(
    source_path: Path,
    *,
    checkpoint_index: dict[_CheckpointKey, ContentLabelAnalysis],
) -> Iterator[_SourceRow]:
    with source_path.open("rb") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            record = _parse_record(raw_line, source_path, line_number)
            if record.analysis is not None:
                continue
            input_hash = _content_input_hash(record)
            if _checkpoint_key(record, input_hash) in checkpoint_index:
                continue
            yield _SourceRow(
                line_number=line_number,
                record=record,
                input_hash=input_hash,
            )


def _label_one(
    source: _SourceRow,
    *,
    service: ContentLabelingService,
    max_validation_retries: int,
    stop_event: Event | None = None,
) -> _ItemOutcome:
    result = service.label_contents(
        [source.record.content],
        max_validation_retries=max_validation_retries,
        stop_event=stop_event,
    )
    if len(result.items) != 1 or result.items[0].item_no != 1:
        raise RuntimeError("单条 ContentLabelingService 调用必须且只能返回 item_no=1")
    if result.items[0].input_hash != source.input_hash:
        raise RuntimeError("ContentLabelingService 单条结果 input_hash 与预检不一致")
    return _ItemOutcome(source=source, result=result)


def _persist_outcomes(
    outcomes: Iterable[_ItemOutcome],
    *,
    checkpoint_file: TextIO,
    attempt_file: TextIO,
    failed_file: TextIO,
    checkpoint_index: dict[_CheckpointKey, ContentLabelAnalysis],
) -> tuple[int, int, int]:
    rows_succeeded = 0
    rows_failed = 0
    llm_attempts = 0
    wrote_checkpoint = False

    for outcome in outcomes:
        source = outcome.source
        result = outcome.result
        item_result = result.items[0]
        _write_attempts_for_single_item(
            attempt_file,
            source=source,
            result=result,
        )
        llm_attempts += len(result.attempts)

        if item_result.analysis_status == "succeeded":
            analysis = item_result.analysis
            if analysis is None:
                raise RuntimeError("ContentLabelingService 成功 item 缺少 analysis")
            if analysis.input_hash != item_result.input_hash:
                raise RuntimeError("ContentLabelingService analysis/input_hash 不一致")
            key = _checkpoint_key(source.record, item_result.input_hash)
            previous = checkpoint_index.get(key)
            if previous is not None:
                if previous != analysis:
                    raise RuntimeError("同一 checkpoint 身份产生冲突的 Analysis")
                continue
            _write_json_line(
                checkpoint_file,
                {
                    "schema_version": "content-label-checkpoint.v1",
                    "line_number": source.line_number,
                    "platform": source.record.content.platform,
                    "external_content_id": source.record.content.external_content_id,
                    "input_hash": item_result.input_hash,
                    "analysis": analysis.model_dump(mode="json"),
                },
            )
            checkpoint_index[key] = analysis
            rows_succeeded += 1
            wrote_checkpoint = True
            continue

        if item_result.analysis is not None:
            raise RuntimeError("ContentLabelingService 失败 item 不得带 analysis")
        _write_json_line(
            failed_file,
            {
                "schema_version": "content-label-failure.v1",
                "line_number": source.line_number,
                "platform": source.record.content.platform,
                "external_content_id": source.record.content.external_content_id,
                "input_hash": item_result.input_hash,
                "analysis_status": "failed",
                "validation_error_codes": list(item_result.validation_error_codes),
            },
        )
        rows_failed += 1

    # checkpoint 是恢复事实源，新成功结果先 durable。
    # attempts/failed 只 flush，正常或 Fatal 收尾再统一 fsync。
    if wrote_checkpoint:
        _flush_and_sync(checkpoint_file)
    attempt_file.flush()
    failed_file.flush()
    return rows_succeeded, rows_failed, llm_attempts


def _write_attempts_for_single_item(
    output_file: TextIO,
    *,
    source: _SourceRow,
    result: ContentLabelingBatchResult,
) -> None:
    for attempt in result.attempts:
        if attempt.item_nos != (1,):
            raise RuntimeError("单条离线打标 attempt 必须只包含 item_no=1")
        _write_json_line(
            output_file,
            _attempt_payload(
                attempt,
                source=source,
            ),
        )


def _attempt_payload(
    attempt: ContentLabelingAttempt,
    *,
    source: _SourceRow,
) -> dict[str, object]:
    return {
        "schema_version": "content-label-attempt.v2",
        "batch_no": source.line_number,
        "attempt_no": attempt.attempt_no,
        "item_nos": [1],
        "items": [
            {
                "item_no": 1,
                "line_number": source.line_number,
                "platform": source.record.content.platform,
                "external_content_id": source.record.content.external_content_id,
                "input_hash": source.input_hash,
            }
        ],
        "validation_error_codes": list(attempt.validation_error_codes),
        "model_provider": attempt.model_provider,
        "model": attempt.model,
        "prompt_sha256": attempt.prompt_sha256,
        "taxonomy_sha256": attempt.taxonomy_sha256,
        "started_at": attempt.started_at.isoformat(),
        "completed_at": attempt.completed_at.isoformat(),
        "logical_request_id": attempt.logical_request_id,
        "input_tokens": attempt.input_tokens,
        "output_tokens": attempt.output_tokens,
        "input_cache_hit_tokens": attempt.input_cache_hit_tokens,
        "input_cache_miss_tokens": attempt.input_cache_miss_tokens,
        "cost_amount": str(attempt.cost_amount) if attempt.cost_amount is not None else None,
        "cost_currency": attempt.cost_currency,
        "pricing_snapshot_sha256": attempt.pricing_snapshot_sha256,
        "pricing_source_url": attempt.pricing_source_url,
    }


def _rewrite_source_in_original_order(
    source_path: Path,
    *,
    checkpoint_index: dict[_CheckpointKey, ContentLabelAnalysis],
) -> int:
    temp_path = source_path.with_name(f".{source_path.name}.labeling.tmp")
    temp_path.unlink(missing_ok=True)
    removed = 0
    try:
        with (
            source_path.open("rb") as input_file,
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
        ):
            for line_number, raw_line in enumerate(input_file, start=1):
                record = _parse_record(raw_line, source_path, line_number)
                if record.analysis is None:
                    input_hash = _content_input_hash(record)
                    analysis = checkpoint_index.get(_checkpoint_key(record, input_hash))
                    if analysis is not None:
                        record = _rewrite_record(record, analysis)
                if (
                    isinstance(record.analysis, ContentLabelAnalysisV3)
                    and not record.analysis.is_relevant
                ):
                    removed += 1
                    continue
                output_file.write(record.model_dump_json())
                output_file.write("\n")
            _flush_and_sync(output_file)
        os.replace(temp_path, source_path)
        return removed
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _load_checkpoint_index(
    path: Path,
    *,
    recovery_taxonomy: PromptTaxonomy | None,
    recovery_model_provider: str,
    recovery_model: str,
) -> dict[_CheckpointKey, ContentLabelAnalysis]:
    if not path.exists() or recovery_taxonomy is None:
        return {}

    index: dict[_CheckpointKey, ContentLabelAnalysis] = {}
    with path.open("rb") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            if not raw_line.strip():
                raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝恢复 checkpoint")
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: 第 {line_number} 行不是合法 checkpoint JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint 顶层必须是 object")
            if payload.get("schema_version") != "content-label-checkpoint.v1":
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint schema_version 不支持")
            platform = payload.get("platform")
            external_content_id = payload.get("external_content_id")
            input_hash = payload.get("input_hash")
            if not isinstance(platform, str) or not platform:
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint 身份字段不合法")
            if not isinstance(external_content_id, str) or not external_content_id:
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint 身份字段不合法")
            if not isinstance(input_hash, str) or not input_hash:
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint 身份字段不合法")
            try:
                analysis = _ANALYSIS_ADAPTER.validate_python(payload.get("analysis"))
            except ValidationError as exc:
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint analysis 不合法") from exc
            if analysis.input_hash != input_hash:
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint input_hash 不一致")
            if (
                analysis.prompt_sha256 != recovery_taxonomy.prompt_sha256
                or analysis.taxonomy_sha256 != recovery_taxonomy.taxonomy_sha256
                or analysis.model_provider != recovery_model_provider
                or analysis.model != recovery_model
            ):
                continue
            key = (platform, external_content_id, input_hash)
            previous = index.get(key)
            if previous is not None and previous != analysis:
                raise ValueError(f"{path}: 第 {line_number} 行 checkpoint 与既有成功结果冲突")
            index[key] = analysis
    return index


def _content_input_hash(record: UnifiedContentRecordV1) -> str:
    return _input_hash(_to_model_item(record.content, item_no=1))


def _checkpoint_key(record: UnifiedContentRecordV1, input_hash: str) -> _CheckpointKey:
    return (record.content.platform, record.content.external_content_id, input_hash)


def _rewrite_record(
    record: UnifiedContentRecordV1,
    analysis: ContentLabelAnalysis,
) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=record.content,
        matched_keywords=list(record.matched_keywords),
        analysis=analysis,
    )


def _parse_record(raw_line: bytes, path: Path, line_number: int) -> UnifiedContentRecordV1:
    if not raw_line.strip():
        raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝继续打标")
    try:
        return UnifiedContentRecordV1.model_validate_json(raw_line)
    except ValidationError as exc:
        raise ValueError(f"{path}: 第 {line_number} 行不是合法 UnifiedContentRecordV1") from exc


def _write_json_line(output_file: TextIO, payload: dict[str, object]) -> None:
    output_file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    output_file.write("\n")


def _flush_and_sync(output_file: TextIO) -> None:
    output_file.flush()
    os.fsync(output_file.fileno())


__all__ = [
    "DEFAULT_OFFLINE_LLM_CONCURRENCY",
    "OfflineContentLabelingSummary",
]

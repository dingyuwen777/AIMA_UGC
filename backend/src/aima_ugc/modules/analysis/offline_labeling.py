"""P1F 离线 JSONL 舆情打标编排；成功 checkpoint 后原子发布同一业务 JSONL。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from aima_ugc.contracts.analysis import ContentLabelAnalysisV1, UnifiedContentRecordV1

from .content_labeling import (
    ContentLabelingAttempt,
    ContentLabelingBatchResult,
    ContentLabelingService,
)


@dataclass(frozen=True, slots=True)
class OfflineContentLabelingSummary:
    """一次离线 JSONL 打标的可审计摘要。"""

    input_path: Path
    analysis_dir: Path
    rows_seen: int
    rows_already_labeled: int
    rows_succeeded: int
    rows_failed: int
    llm_attempts: int


@dataclass(frozen=True, slots=True)
class _SourceRow:
    line_number: int
    record: UnifiedContentRecordV1


@dataclass(frozen=True, slots=True)
class _PendingRow:
    item_no: int
    source: _SourceRow


@dataclass(frozen=True, slots=True)
class _BatchOutcome:
    rows: tuple[UnifiedContentRecordV1, ...]
    rows_already_labeled: int
    rows_succeeded: int
    rows_failed: int
    llm_attempts: int


def label_unified_content_jsonl(
    *,
    input_path: Path,
    analysis_dir: Path,
    service: ContentLabelingService,
    max_validation_retries: int,
    batch_size: int = 20,
) -> OfflineContentLabelingSummary:
    """读取统一内容 JSONL，记录模型审计并原子回写已校验 Analysis。"""

    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size 必须是大于 0 的整数")

    source_path = Path(input_path)
    audit_dir = Path(analysis_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = audit_dir / "checkpoints.jsonl"
    attempt_path = audit_dir / "attempts.jsonl"
    failed_path = audit_dir / "failed.jsonl"
    temp_path = source_path.with_name(f".{source_path.name}.labeling.tmp")
    temp_path.unlink(missing_ok=True)

    rows_seen = 0
    rows_already_labeled = 0
    rows_succeeded = 0
    rows_failed = 0
    llm_attempts = 0
    batch_no = 0
    published_changes = False

    try:
        with (
            source_path.open("rb") as input_file,
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
            checkpoint_path.open("a", encoding="utf-8", newline="\n") as checkpoint_file,
            attempt_path.open("a", encoding="utf-8", newline="\n") as attempt_file,
            failed_path.open("a", encoding="utf-8", newline="\n") as failed_file,
        ):
            source_batch: list[_SourceRow] = []
            for line_number, raw_line in enumerate(input_file, start=1):
                rows_seen += 1
                source_batch.append(
                    _SourceRow(
                        line_number=line_number,
                        record=_parse_record(raw_line, source_path, line_number),
                    )
                )
                if len(source_batch) < batch_size:
                    continue

                batch_no += 1
                outcome = _process_batch(
                    batch=source_batch,
                    batch_no=batch_no,
                    service=service,
                    max_validation_retries=max_validation_retries,
                    checkpoint_file=checkpoint_file,
                    attempt_file=attempt_file,
                    failed_file=failed_file,
                )
                _write_records(output_file, outcome.rows)
                rows_already_labeled += outcome.rows_already_labeled
                rows_succeeded += outcome.rows_succeeded
                rows_failed += outcome.rows_failed
                llm_attempts += outcome.llm_attempts
                published_changes = published_changes or outcome.rows_succeeded > 0
                source_batch.clear()

            if source_batch:
                batch_no += 1
                outcome = _process_batch(
                    batch=source_batch,
                    batch_no=batch_no,
                    service=service,
                    max_validation_retries=max_validation_retries,
                    checkpoint_file=checkpoint_file,
                    attempt_file=attempt_file,
                    failed_file=failed_file,
                )
                _write_records(output_file, outcome.rows)
                rows_already_labeled += outcome.rows_already_labeled
                rows_succeeded += outcome.rows_succeeded
                rows_failed += outcome.rows_failed
                llm_attempts += outcome.llm_attempts
                published_changes = published_changes or outcome.rows_succeeded > 0

            _flush_and_sync(output_file)

        if published_changes:
            os.replace(temp_path, source_path)
        else:
            temp_path.unlink(missing_ok=True)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return OfflineContentLabelingSummary(
        input_path=source_path,
        analysis_dir=audit_dir,
        rows_seen=rows_seen,
        rows_already_labeled=rows_already_labeled,
        rows_succeeded=rows_succeeded,
        rows_failed=rows_failed,
        llm_attempts=llm_attempts,
    )


def _process_batch(
    *,
    batch: list[_SourceRow],
    batch_no: int,
    service: ContentLabelingService,
    max_validation_retries: int,
    checkpoint_file: TextIO,
    attempt_file: TextIO,
    failed_file: TextIO,
) -> _BatchOutcome:
    pending_sources = [source for source in batch if source.record.analysis is None]
    if not pending_sources:
        return _BatchOutcome(
            rows=tuple(source.record for source in batch),
            rows_already_labeled=len(batch),
            rows_succeeded=0,
            rows_failed=0,
            llm_attempts=0,
        )

    pending = tuple(
        _PendingRow(item_no=item_no, source=source)
        for item_no, source in enumerate(pending_sources, start=1)
    )
    result = service.label_contents(
        [item.source.record.content for item in pending],
        max_validation_retries=max_validation_retries,
    )
    if len(result.items) != len(pending):
        raise RuntimeError("ContentLabelingService 返回 item 数量与输入不一致")

    pending_by_item_no = {item.item_no: item for item in pending}
    item_hashes = {item.item_no: item.input_hash for item in result.items}
    _write_attempts(
        attempt_file,
        batch_no=batch_no,
        result=result,
        pending_by_item_no=pending_by_item_no,
        item_hashes=item_hashes,
    )

    analyses: dict[int, ContentLabelAnalysisV1] = {}
    failed_count = 0
    for item_result in result.items:
        pending_item = pending_by_item_no.get(item_result.item_no)
        if pending_item is None:
            raise RuntimeError("ContentLabelingService 返回未知 item_no")
        source = pending_item.source
        if item_result.analysis_status == "succeeded":
            analysis = item_result.analysis
            if analysis is None:
                raise RuntimeError("ContentLabelingService 成功 item 缺少 analysis")
            if analysis.input_hash != item_result.input_hash:
                raise RuntimeError("ContentLabelingService analysis/input_hash 不一致")
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
            analyses[source.line_number] = analysis
            continue

        if item_result.analysis is not None:
            raise RuntimeError("ContentLabelingService 失败 item 不得带 analysis")
        failed_count += 1
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

    # 成功 checkpoint 必须先持久化，之后才允许把 Analysis 写入业务 JSONL 临时文件。
    _flush_and_sync(checkpoint_file)
    _flush_and_sync(attempt_file)
    _flush_and_sync(failed_file)

    rewritten: list[UnifiedContentRecordV1] = []
    for source in batch:
        analysis = analyses.get(source.line_number)
        if analysis is None:
            rewritten.append(source.record)
            continue
        rewritten.append(
            UnifiedContentRecordV1(
                content=source.record.content,
                matched_keywords=list(source.record.matched_keywords),
                analysis=analysis,
            )
        )

    return _BatchOutcome(
        rows=tuple(rewritten),
        rows_already_labeled=len(batch) - len(pending),
        rows_succeeded=len(analyses),
        rows_failed=failed_count,
        llm_attempts=len(result.attempts),
    )


def _write_attempts(
    output_file: TextIO,
    *,
    batch_no: int,
    result: ContentLabelingBatchResult,
    pending_by_item_no: dict[int, _PendingRow],
    item_hashes: dict[int, str],
) -> None:
    for attempt in result.attempts:
        _write_json_line(
            output_file,
            _attempt_payload(
                attempt,
                batch_no=batch_no,
                pending_by_item_no=pending_by_item_no,
                item_hashes=item_hashes,
            ),
        )


def _attempt_payload(
    attempt: ContentLabelingAttempt,
    *,
    batch_no: int,
    pending_by_item_no: dict[int, _PendingRow],
    item_hashes: dict[int, str],
) -> dict[str, object]:
    identities: list[dict[str, object]] = []
    for item_no in attempt.item_nos:
        pending = pending_by_item_no.get(item_no)
        if pending is None:
            raise RuntimeError("ContentLabelingAttempt 包含未知 item_no")
        input_hash = item_hashes.get(item_no)
        if input_hash is None:
            raise RuntimeError("ContentLabelingAttempt 缺少 item input_hash")
        identities.append(
            {
                "item_no": item_no,
                "line_number": pending.source.line_number,
                "platform": pending.source.record.content.platform,
                "external_content_id": pending.source.record.content.external_content_id,
                "input_hash": input_hash,
            }
        )

    return {
        "schema_version": "content-label-attempt.v1",
        "batch_no": batch_no,
        "attempt_no": attempt.attempt_no,
        "item_nos": list(attempt.item_nos),
        "items": identities,
        "validation_error_codes": list(attempt.validation_error_codes),
        "model_provider": attempt.model_provider,
        "model": attempt.model,
        "prompt_sha256": attempt.prompt_sha256,
        "taxonomy_sha256": attempt.taxonomy_sha256,
        "started_at": attempt.started_at.isoformat(),
        "completed_at": attempt.completed_at.isoformat(),
        "input_tokens": attempt.input_tokens,
        "output_tokens": attempt.output_tokens,
        "cost_amount": str(attempt.cost_amount) if attempt.cost_amount is not None else None,
        "cost_currency": attempt.cost_currency,
    }


def _parse_record(raw_line: bytes, path: Path, line_number: int) -> UnifiedContentRecordV1:
    if not raw_line.strip():
        raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝继续打标")
    try:
        return UnifiedContentRecordV1.model_validate_json(raw_line)
    except ValidationError as exc:
        raise ValueError(f"{path}: 第 {line_number} 行不是合法 UnifiedContentRecordV1") from exc


def _write_records(output_file: TextIO, records: tuple[UnifiedContentRecordV1, ...]) -> None:
    for record in records:
        output_file.write(record.model_dump_json())
        output_file.write("\n")


def _write_json_line(output_file: TextIO, payload: dict[str, object]) -> None:
    output_file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    output_file.write("\n")


def _flush_and_sync(output_file: TextIO) -> None:
    output_file.flush()
    os.fsync(output_file.fileno())


__all__ = [
    "OfflineContentLabelingSummary",
    "label_unified_content_jsonl",
]

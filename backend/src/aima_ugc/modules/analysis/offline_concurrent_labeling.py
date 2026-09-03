"""复用公共 bounded executor 的离线 JSONL Analysis 编排。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .concurrent_labeling import ConcurrentTaskOutcome, run_bounded_concurrently
from .content_labeling import ContentLabelingService
from .offline_labeling import (
    DEFAULT_OFFLINE_LLM_CONCURRENCY,
    OfflineContentLabelingSummary,
    _ItemOutcome,
    _SourceRow,
    _flush_and_sync,
    _iter_pending_rows,
    _label_one,
    _load_checkpoint_index,
    _persist_outcomes,
    _preflight_source,
    _resolve_concurrency,
    _rewrite_source_in_original_order,
)
from .prompt_taxonomy import PromptTaxonomy


def label_unified_content_jsonl(
    *,
    input_path: Path,
    analysis_dir: Path,
    service: ContentLabelingService,
    max_validation_retries: int,
    max_concurrency: int = DEFAULT_OFFLINE_LLM_CONCURRENCY,
    recovery_taxonomy: PromptTaxonomy | None = None,
    batch_size: int | None = None,
) -> OfflineContentLabelingSummary:
    """以公共 bounded executor 执行离线单内容请求，同时保持原 checkpoint/恢复语义。"""

    actual_concurrency = _resolve_concurrency(
        max_concurrency=max_concurrency,
        legacy_batch_size=batch_size,
    )
    source_path = Path(input_path)
    audit_dir = Path(analysis_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = audit_dir / "checkpoints.jsonl"
    attempt_path = audit_dir / "attempts.jsonl"
    failed_path = audit_dir / "failed.jsonl"
    checkpoint_index = _load_checkpoint_index(
        checkpoint_path,
        recovery_taxonomy=recovery_taxonomy,
        recovery_model_provider=service.provider_name,
        recovery_model=service.model_name,
    )

    rows_seen, rows_already_labeled, rows_recovered, pending_count = _preflight_source(
        source_path,
        checkpoint_index=checkpoint_index,
    )
    rows_succeeded = 0
    rows_failed = 0
    llm_attempts = 0
    peak_in_flight = 0

    if pending_count:
        with (
            checkpoint_path.open("a", encoding="utf-8", newline="\n") as checkpoint_file,
            attempt_path.open("a", encoding="utf-8", newline="\n") as attempt_file,
            failed_path.open("a", encoding="utf-8", newline="\n") as failed_file,
        ):

            def task(source: _SourceRow) -> _ItemOutcome:
                """调用既有单条模型函数，确保输入 Hash 和单 item 结果校验完全不变。"""

                return _label_one(
                    source,
                    service=service,
                    max_validation_retries=max_validation_retries,
                )

            def persist_completed(
                outcomes: Sequence[ConcurrentTaskOutcome[_SourceRow, _ItemOutcome]],
            ) -> None:
                """沿用既有 checkpoint/attempt/failed 持久化，并只处理已成功返回的任务。"""

                nonlocal rows_succeeded, rows_failed, llm_attempts
                item_outcomes = tuple(
                    outcome.result for outcome in outcomes if outcome.result is not None
                )
                if not item_outcomes:
                    return
                succeeded, failed, attempts = _persist_outcomes(
                    item_outcomes,
                    checkpoint_file=checkpoint_file,
                    attempt_file=attempt_file,
                    failed_file=failed_file,
                    checkpoint_index=checkpoint_index,
                )
                rows_succeeded += succeeded
                rows_failed += failed
                llm_attempts += attempts

            concurrency_summary = run_bounded_concurrently(
                _iter_pending_rows(source_path, checkpoint_index=checkpoint_index),
                task=task,
                max_concurrency=actual_concurrency,
                on_completed=persist_completed,
                canary=True,
                fail_fast=True,
            )
            peak_in_flight = concurrency_summary.peak_in_flight

            # attempts/failed 不是恢复事实源，正常收尾时一次 durable，避免每条额外 fsync。
            _flush_and_sync(attempt_file)
            _flush_and_sync(failed_file)

    rows_irrelevant_removed = (
        _rewrite_source_in_original_order(
            source_path,
            checkpoint_index=checkpoint_index,
        )
        if rows_seen
        else 0
    )

    return OfflineContentLabelingSummary(
        input_path=source_path,
        analysis_dir=audit_dir,
        rows_seen=rows_seen,
        rows_already_labeled=rows_already_labeled,
        rows_recovered=rows_recovered,
        rows_succeeded=rows_succeeded,
        rows_failed=rows_failed,
        llm_attempts=llm_attempts,
        rows_irrelevant_removed=rows_irrelevant_removed,
        peak_in_flight=peak_in_flight,
    )


__all__ = ["label_unified_content_jsonl"]

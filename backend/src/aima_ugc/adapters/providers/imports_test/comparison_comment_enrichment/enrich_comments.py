"""直接从车型共现 JSONL 为五个平台逐帖补采全部评论并导出 Excel。"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import zipfile
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TextIO

from pydantic import ValidationError

from aima_ugc.adapters.providers.imports_test.comparison_comment_enrichment.models import (
    CommentFetchCoverageV1,
    CommentFetchFailureV1,
    CommentIdentityMismatchV1,
    CommentReplyShortfallV1,
    VehiclePairCommentRecordV1,
)
from aima_ugc.adapters.providers.imports_test.incremental_state import (
    AppendOnlyShardIndex,
    atomic_write_json,
    content_identity_key,
    iter_completed_run_dirs,
    load_json_object,
    resolve_summary_output,
    sha256_file,
    shard_name,
    state_lock,
)
from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehiclePairRecordV1,
)
from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import RawOutputRecord, RunOutputStore
from aima_ugc.contracts.canonical import CanonicalCommentV1
from aima_ugc.contracts.export import UnifiedDataExcelCommentV1, UnifiedDataExcelV1
from aima_ugc.contracts.platform import PLATFORM_NAMES, PlatformName
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransport,
    ProviderTransportFailure,
)
from aima_ugc.platform.export import (
    export_unified_data_excel,
    project_canonical_comment,
    project_canonical_content,
)
from aima_ugc.platform.time import beijing_now

INPUT_JSONL = Path(
    r"E:\work\03_Aima\code\AIMA_UGC\backend\src\aima_ugc\adapters\providers"
    r"\imports_test\vehicle_pair_filter\output\runs\20260912T190531.644615+0800"
    r"\comparison_posts.jsonl"
)
OUTPUT_ROOT = Path(__file__).with_name("output")
RESUME_RUN_ID: str | None = None

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")
_FATAL_HTTP_STATUSES = frozenset({401, 403, 408, 425, 429})
_STATE_SCHEMA = "comparison-comment-enrichment-state.v1"
_RUN_SCHEMA = "comparison-comment-enrichment-run.v2"
_CACHE_POLICY = "reuse-any-committed-result.v1"
_RUN_SCHEMAS = frozenset({"comparison-comment-enrichment-run.v1", _RUN_SCHEMA})
_RESUME_SCHEMA = "comparison-comment-enrichment-resume.v1"
_PUBLISH_RETRY_DELAYS_SECONDS = (0.1, 0.25, 0.5, 1.0)


@dataclass(frozen=True, slots=True)
class CommentEnrichmentRunSummary:
    """记录一次五平台逐帖评论补采的正式输出与统计。"""

    run_id: str
    run_dir: Path
    input_path: Path
    output_jsonl_path: Path
    workbook_path: Path
    current_jsonl_path: Path
    current_workbook_path: Path
    run_summary_path: Path
    rows_seen: int
    rows_cached: int
    rows_fetched: int
    rows_complete: int
    rows_partial: int
    rows_unavailable: int
    platform_counts: dict[PlatformName, int]
    root_comment_count: int
    reply_count: int
    request_count: int
    failure_count: int


@dataclass(frozen=True, slots=True)
class _FetchResult:
    """内部保存单帖补采后的评论与覆盖信息。"""

    comments: tuple[CanonicalCommentV1, ...]
    coverage: CommentFetchCoverageV1


@dataclass(frozen=True, slots=True)
class _SendResult:
    """一次确定 Provider 响应的正文、Raw 定位或永久失败。"""

    body: dict[str, Any] | None
    raw_record: RawOutputRecord
    raw_locator: str
    failure: CommentFetchFailureV1 | None


class _TikHubCommentFetcher:
    """用生产 TikHub Runtime 为已知内容身份补采全部评论与回复。"""

    def __init__(
        self,
        *,
        provider_config: TikHubTestConfig,
        transport: ProviderTransport,
        staging_dir: Path,
    ) -> None:
        self.provider_config = provider_config
        self.transport = transport
        self.staging_dir = staging_dir
        self._stores: dict[PlatformName, RunOutputStore] = {}
        self._platform_request_counts: Counter[PlatformName] = Counter()
        self.request_count = 0
        self._restore_request_counters()

    def _restore_request_counters(self) -> None:
        """续跑时从既有 Raw 文件号恢复计数，保证审计文件永不覆盖。"""

        for platform in PLATFORM_NAMES:
            raw_dir = self.staging_dir / "provider" / platform / "runs" / "comments" / "raw"
            request_no = 0
            for path in raw_dir.glob("*.json"):
                prefix, _, _ = path.name.partition("_")
                if prefix.isdecimal():
                    request_no = max(request_no, int(prefix))
            if request_no:
                self._platform_request_counts[platform] = request_no
                self.request_count += request_no

    def fetch(self, record: VehiclePairRecordV1) -> _FetchResult:
        """对一篇已筛选帖子分页抓完一级评论及其全部二级回复。"""

        content = record.record.content
        reported_total = content.metrics.comment_count
        unsupported_reason = _unsupported_comment_identity_reason(
            platform=content.platform,
            external_content_id=content.external_content_id,
            alternate_ids=content.alternate_ids,
        )
        if unsupported_reason is not None:
            return _FetchResult(
                comments=(),
                coverage=CommentFetchCoverageV1(
                    coverage="unavailable",
                    reported_total=reported_total,
                    root_comment_count=0,
                    reply_count=0,
                    request_count=0,
                    root_stop_reason=unsupported_reason,
                ),
            )
        request_count_before = self.request_count
        comments: list[CanonicalCommentV1] = []
        seen_comment_ids: set[str] = set()
        failures: list[CommentFetchFailureV1] = []
        reply_shortfalls: list[CommentReplyShortfallV1] = []
        identity_mismatches: list[CommentIdentityMismatchV1] = []
        root_count = 0
        reply_count = 0
        state: dict[str, object] | None = None
        page_no = 0
        root_stop_reason: str | None = None

        while True:
            page_no += 1
            call = tikhub_runtime.build_comments_call(
                platform=content.platform,
                external_content_id=content.external_content_id,
                alternate_ids=content.alternate_ids,
                state=state,
            )
            sent = self._send(
                platform=content.platform,
                call=call,
                stage="comments",
                root_comment_id=None,
            )
            if sent.failure is not None:
                failures.append(sent.failure)
                root_stop_reason = sent.failure.code
                break
            assert sent.body is not None

            mapped_roots: list[CanonicalCommentV1] = []
            for item_index, raw_item in enumerate(
                tikhub_runtime.extract_comment_items(content.platform, sent.body)
            ):
                item_locator = f"{sent.raw_locator}#comments.page[{page_no}].items[{item_index}]"
                comment = tikhub_runtime.map_comment(
                    platform=content.platform,
                    raw=raw_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=sent.raw_record.request_id,
                        provider_attempt_id=sent.raw_record.attempt_id,
                        raw_artifact_id=sent.raw_record.artifact_id,
                        operation=call.operation,
                        source_type="content",
                        source_value=content.external_content_id,
                        observed_at=sent.raw_record.observed_at,
                        external_content_id=content.external_content_id,
                    ),
                    item_locator=item_locator,
                    is_root=True,
                )
                if comment.external_content_id != content.external_content_id:
                    identity_mismatches.append(
                        _identity_mismatch(
                            stage="comments",
                            comment=comment,
                            expected_external_content_id=content.external_content_id,
                            raw_locator=item_locator,
                        )
                    )
                    continue
                if comment.external_comment_id in seen_comment_ids:
                    continue
                seen_comment_ids.add(comment.external_comment_id)
                comments.append(comment)
                mapped_roots.append(comment)
                root_count += 1
                self._store(content.platform).append_canonical("comments", comment)

            for root in mapped_roots:
                if root.metrics.reply_count == 0:
                    continue
                replies, reply_failures, reply_mismatches, reply_shortfall = self._fetch_replies(
                    content_platform=content.platform,
                    external_content_id=content.external_content_id,
                    alternate_ids=content.alternate_ids,
                    root=root,
                    seen_comment_ids=seen_comment_ids,
                )
                comments.extend(replies)
                reply_count += len(replies)
                failures.extend(reply_failures)
                identity_mismatches.extend(reply_mismatches)
                if reply_shortfall is not None:
                    reply_shortfalls.append(reply_shortfall)

            advance = tikhub_runtime.advance_comments(
                platform=content.platform,
                state=state,
                body=sent.body,
            )
            if not advance.should_continue:
                root_stop_reason = advance.stop_reason or "provider_exhausted"
                break
            state = dict(advance.next_state or {})

        request_count = self.request_count - request_count_before
        coverage: Literal["complete", "partial", "unavailable"]
        if failures or reply_shortfalls or identity_mismatches:
            coverage = "partial" if comments else "unavailable"
        elif reported_total is not None and root_count < reported_total:
            coverage = "partial"
            root_stop_reason = (
                f"{root_stop_reason or 'provider_stopped'}; observed_lt_reported_total"
            )
        else:
            coverage = "complete"
        return _FetchResult(
            comments=tuple(comments),
            coverage=CommentFetchCoverageV1(
                coverage=coverage,
                reported_total=reported_total,
                root_comment_count=root_count,
                reply_count=reply_count,
                request_count=request_count,
                root_stop_reason=root_stop_reason,
                failures=tuple(failures),
                reply_shortfalls=tuple(reply_shortfalls),
                identity_mismatches=tuple(identity_mismatches),
            ),
        )

    def _fetch_replies(
        self,
        *,
        content_platform: PlatformName,
        external_content_id: str,
        alternate_ids: dict[str, str],
        root: CanonicalCommentV1,
        seen_comment_ids: set[str],
    ) -> tuple[
        list[CanonicalCommentV1],
        list[CommentFetchFailureV1],
        list[CommentIdentityMismatchV1],
        CommentReplyShortfallV1 | None,
    ]:
        """对一个一级评论分页抓完全部二级回复，不使用采样数量上限。"""

        replies: list[CanonicalCommentV1] = []
        failures: list[CommentFetchFailureV1] = []
        identity_mismatches: list[CommentIdentityMismatchV1] = []
        state: dict[str, object] | None = None
        page_no = 0
        while True:
            page_no += 1
            call = tikhub_runtime.build_sub_comments_call(
                platform=content_platform,
                external_content_id=external_content_id,
                root_comment_id=root.external_comment_id,
                alternate_ids=alternate_ids,
                state=state,
            )
            sent = self._send(
                platform=content_platform,
                call=call,
                stage="replies",
                root_comment_id=root.external_comment_id,
            )
            if sent.failure is not None:
                failures.append(sent.failure)
                break
            assert sent.body is not None

            for item_index, raw_item in enumerate(
                tikhub_runtime.extract_sub_comment_items(content_platform, sent.body)
            ):
                item_locator = f"{sent.raw_locator}#replies.page[{page_no}].items[{item_index}]"
                comment = tikhub_runtime.map_comment(
                    platform=content_platform,
                    raw=raw_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=sent.raw_record.request_id,
                        provider_attempt_id=sent.raw_record.attempt_id,
                        raw_artifact_id=sent.raw_record.artifact_id,
                        operation=call.operation,
                        source_type="comment",
                        source_value=root.external_comment_id,
                        observed_at=sent.raw_record.observed_at,
                        external_content_id=external_content_id,
                        root_comment_id=root.external_comment_id,
                    ),
                    item_locator=item_locator,
                    is_root=False,
                )
                if comment.external_content_id != external_content_id:
                    identity_mismatches.append(
                        _identity_mismatch(
                            stage="replies",
                            comment=comment,
                            expected_external_content_id=external_content_id,
                            raw_locator=item_locator,
                        )
                    )
                    continue
                if comment.external_comment_id in seen_comment_ids:
                    continue
                seen_comment_ids.add(comment.external_comment_id)
                replies.append(comment)
                self._store(content_platform).append_canonical("comments", comment)

            advance = tikhub_runtime.advance_sub_comments(
                platform=content_platform,
                state=state,
                body=sent.body,
            )
            if not advance.should_continue:
                break
            state = dict(advance.next_state or {})
        reported_count = root.metrics.reply_count
        reply_shortfall = None
        if reported_count is not None and len(replies) < reported_count:
            reply_shortfall = CommentReplyShortfallV1(
                root_comment_id=root.external_comment_id,
                reported_count=reported_count,
                observed_count=len(replies),
            )
        return replies, failures, identity_mismatches, reply_shortfall

    def _send(
        self,
        *,
        platform: PlatformName,
        call: tikhub_runtime.TikHubOperationCall,
        stage: str,
        root_comment_id: str | None,
    ) -> _SendResult:
        """发送一次请求并先保存确定响应 Raw，再分类永久或运行级失败。"""

        self.request_count += 1
        self._platform_request_counts[platform] += 1
        request_no = self._platform_request_counts[platform]
        try:
            response = self.transport.send(call.transport_request(self.provider_config.api_key))
        except ProviderTransportFailure as exc:
            raise RuntimeError(
                f"TikHub {platform} Transport 失败: {exc.code}: {exc.safe_summary}"
            ) from exc

        raw_record = self._store(platform).save_raw(
            operation=call.operation,
            body=response.body,
            request_no=request_no,
            status_code=response.status_code,
            external_request_id=response.external_request_id,
        )
        raw_locator = raw_record.path.relative_to(self.staging_dir).as_posix()
        status_code = response.status_code
        if status_code is None:
            raise RuntimeError(f"TikHub {platform} HTTP 响应缺少 status_code")
        if status_code >= 500 or status_code in _FATAL_HTTP_STATUSES:
            raise RuntimeError(
                f"TikHub {platform} 返回运行级失败 HTTP {status_code}: {raw_locator}"
            )
        if status_code >= 400:
            failure = CommentFetchFailureV1(
                stage="comments" if stage == "comments" else "replies",
                root_comment_id=root_comment_id,
                status_code=status_code,
                code=f"http_{status_code}",
                safe_summary=f"TikHub 返回不可重试 HTTP {status_code}",
                raw_locator=raw_locator,
            )
            return _SendResult(None, raw_record, raw_locator, failure)
        if status_code >= 300:
            raise RuntimeError(f"TikHub {platform} 返回未支持的 HTTP {status_code}: {raw_locator}")
        if not isinstance(response.body, dict):
            raise ValueError(f"TikHub {platform} 成功响应必须为 JSON Object: {raw_locator}")
        return _SendResult(dict(response.body), raw_record, raw_locator, None)

    def _store(self, platform: PlatformName) -> RunOutputStore:
        """为每个平台惰性创建独立 Raw/Canonical 审计目录。"""

        store = self._stores.get(platform)
        if store is not None:
            return store
        store = RunOutputStore.create(
            output_root=self.staging_dir / "provider",
            platform=platform,
            run_id="comments",
        )
        self._stores[platform] = store
        return store


def _identity_mismatch(
    *,
    stage: Literal["comments", "replies"],
    comment: CanonicalCommentV1,
    expected_external_content_id: str,
    raw_locator: str,
) -> CommentIdentityMismatchV1:
    """把串帖评论转成安全诊断，不让错误归属进入正式评论集合。"""

    return CommentIdentityMismatchV1(
        stage=stage,
        external_comment_id=comment.external_comment_id,
        expected_external_content_id=expected_external_content_id,
        observed_external_content_id=comment.external_content_id,
        raw_locator=raw_locator,
    )


def _unsupported_comment_identity_reason(
    *,
    platform: PlatformName,
    external_content_id: str,
    alternate_ids: dict[str, str],
) -> str | None:
    """阻止把微博文章哈希等非 status_id 身份误发给评论接口。"""

    if platform != "weibo":
        return None
    status_id = alternate_ids.get("status_id", external_content_id).strip()
    if status_id.isdecimal():
        return None
    return "unsupported_weibo_comment_identity"


def enrich_comparison_comments(
    *,
    input_path: Path,
    output_root: Path,
    run_id: str | None = None,
    env_file: str | Path | None = None,
    provider_config: TikHubTestConfig | None = None,
    transport: ProviderTransport | None = None,
) -> CommentEnrichmentRunSummary:
    """自动接管本机旧评论 run；有缓存的帖子直接复用，只为真正缺失帖子请求 Provider。"""

    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    _validate_input_jsonl(source_path)

    if provider_config is not None and env_file is not None:
        raise ValueError("provider_config 与 env_file 不能同时提供")
    config = provider_config or TikHubTestConfig.load(env_file)
    if transport is not None:
        return _run_enrichment(
            input_path=source_path,
            output_root=Path(output_root),
            run_id=run_id,
            provider_config=config,
            transport=transport,
        )

    with TikHubHttpTransport(
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    ) as actual_transport:
        return _run_enrichment(
            input_path=source_path,
            output_root=Path(output_root),
            run_id=run_id,
            provider_config=config,
            transport=actual_transport,
        )


def _run_enrichment(
    *,
    input_path: Path,
    output_root: Path,
    run_id: str | None,
    provider_config: TikHubTestConfig,
    transport: ProviderTransport,
) -> CommentEnrichmentRunSummary:
    """在文件化 cache/state 保护下按原输入顺序增量补采，并维护累计 current。"""

    with state_lock(output_root):
        _recover_completed_staging_runs(output_root)
        state, cache_index = _load_and_reconcile_state(output_root)
        actual_run_id = _resolve_run_id(run_id)
        runs_root = output_root / "runs"
        final_run_dir = runs_root / actual_run_id
        staging_dir = output_root / f".staging-{actual_run_id}"
        if final_run_dir.exists():
            raise FileExistsError(f"目标 run 已存在: {final_run_dir}")
        runs_root.mkdir(parents=True, exist_ok=True)
        is_resuming = staging_dir.exists()
        if is_resuming and not staging_dir.is_dir():
            raise FileExistsError(f"staging 路径不是目录: {staging_dir}")
        if not is_resuming:
            staging_dir.mkdir(parents=True, exist_ok=False)
            try:
                _write_json(
                    staging_dir / "resume_manifest.json",
                    {
                        "schema_version": _RESUME_SCHEMA,
                        "run_id": actual_run_id,
                        "input_sha256": sha256_file(input_path),
                    },
                )
            except BaseException:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise

        staging_jsonl = staging_dir / "comparison_posts_with_comments.jsonl"
        staging_workbook = staging_dir / "comparison_posts_with_comments.xlsx"
        final_jsonl = final_run_dir / staging_jsonl.name
        final_workbook = final_run_dir / staging_workbook.name
        final_summary = final_run_dir / "run_summary.json"
        current_jsonl = output_root / "current" / "comparison_posts_with_comments.jsonl"
        current_workbook = output_root / "current" / "comparison_posts_with_comments.xlsx"
        resumed_records = _load_resumable_records(staging_jsonl) if is_resuming else []
        if is_resuming:
            _validate_resume_manifest(
                staging_dir=staging_dir,
                run_id=actual_run_id,
                input_path=input_path,
                has_resumed_records=bool(resumed_records),
            )
        if resumed_records:
            _validate_resume_prefix(input_path=input_path, resumed_records=resumed_records)

        rows_seen = 0
        rows_cached = 0
        rows_fetched = 0
        coverage_counts: Counter[str] = Counter()
        platform_counts: Counter[PlatformName] = Counter()
        root_comment_count = 0
        reply_count = 0
        failure_count = 0
        fetcher = _TikHubCommentFetcher(
            provider_config=provider_config,
            transport=transport,
            staging_dir=staging_dir,
        )
        loaded_cache_shards: dict[str, dict[str, dict[str, Any]]] = {}

        completed_staging = False
        try:
            output_mode = "a" if is_resuming else "w"
            with staging_jsonl.open(output_mode, encoding="utf-8", newline="\n") as output_file:
                for record in _iter_input_records(input_path):
                    rows_seen += 1
                    content = record.record.content
                    platform_counts[content.platform] += 1
                    should_append = rows_seen > len(resumed_records)
                    if not should_append:
                        enriched = resumed_records[rows_seen - 1]
                        rows_cached += 1
                    else:
                        key = content_identity_key(content.platform, content.external_content_id)
                        shard = shard_name(key)
                        cached_entries = loaded_cache_shards.get(shard)
                        if cached_entries is None:
                            cached_entries = cache_index.load_shard(shard)
                            loaded_cache_shards[shard] = cached_entries
                        cached_entry = cached_entries.get(key)
                        if cached_entry is not None:
                            cached = _read_cached_record(output_root, cached_entry)
                            enriched = VehiclePairCommentRecordV1(
                                record=record,
                                comments=cached.comments,
                                comment_fetch=cached.comment_fetch,
                            )
                            rows_cached += 1
                        else:
                            fetched = fetcher.fetch(record)
                            enriched = VehiclePairCommentRecordV1(
                                record=record,
                                comments=fetched.comments,
                                comment_fetch=fetched.coverage,
                            )
                            rows_fetched += 1

                    if should_append:
                        output_file.write(enriched.model_dump_json())
                        output_file.write("\n")
                    coverage = enriched.comment_fetch
                    coverage_counts[coverage.coverage] += 1
                    root_comment_count += coverage.root_comment_count
                    reply_count += coverage.reply_count
                    failure_count += len(coverage.failures)
                output_file.flush()
                os.fsync(output_file.fileno())

            excel_summary = export_unified_data_excel(
                _iter_excel_records(staging_jsonl),
                staging_workbook,
                include_analysis=False,
            )
            if excel_summary.content_rows != rows_seen:
                raise RuntimeError("Excel 内容行数与评论补采 JSONL 帖子数不一致")
            if excel_summary.comment_rows != root_comment_count + reply_count:
                raise RuntimeError("Excel 评论行数与评论补采 JSONL 评论数不一致")

            _write_json(
                staging_dir / "run_summary.json",
                _run_summary_payload(
                    run_id=actual_run_id,
                    input_path=input_path,
                    rows_seen=rows_seen,
                    rows_cached=rows_cached,
                    rows_fetched=rows_fetched,
                    coverage_counts=coverage_counts,
                    platform_counts=platform_counts,
                    root_comment_count=root_comment_count,
                    reply_count=reply_count,
                    request_count=fetcher.request_count,
                    failure_count=failure_count,
                    jsonl_path=final_jsonl,
                    workbook_path=final_workbook,
                    current_jsonl_path=current_jsonl,
                    current_workbook_path=current_workbook,
                ),
            )
            completed_staging = True
            _publish_run_directory(staging_dir, final_run_dir)
        except BaseException:
            if not completed_staging and not _has_resumable_data(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        # final run 已发布后再推进 cache；即使 current 生成中断，下次也会从该 run 自动恢复且不重抓。
        _index_comment_run(
            output_root=output_root,
            run_id=actual_run_id,
            jsonl_path=final_jsonl,
            cache_index=cache_index,
        )
        indexed_runs = set(_string_list(state.get("indexed_runs")))
        indexed_runs.add(actual_run_id)
        state["indexed_runs"] = sorted(indexed_runs)
        atomic_write_json(output_root / "state" / "manifest.json", state)
        _materialize_current(
            output_root=output_root,
            cache_index=cache_index,
            output_path=current_jsonl,
            workbook_path=current_workbook,
        )
        _write_json(
            final_summary,
            _run_summary_payload(
                run_id=actual_run_id,
                input_path=input_path,
                rows_seen=rows_seen,
                rows_cached=rows_cached,
                rows_fetched=rows_fetched,
                coverage_counts=coverage_counts,
                platform_counts=platform_counts,
                root_comment_count=root_comment_count,
                reply_count=reply_count,
                request_count=fetcher.request_count,
                failure_count=failure_count,
                jsonl_path=final_jsonl,
                workbook_path=final_workbook,
                current_jsonl_path=current_jsonl,
                current_workbook_path=current_workbook,
            ),
        )

        return CommentEnrichmentRunSummary(
            run_id=actual_run_id,
            run_dir=final_run_dir,
            input_path=input_path,
            output_jsonl_path=final_jsonl,
            workbook_path=final_workbook,
            current_jsonl_path=current_jsonl,
            current_workbook_path=current_workbook,
            run_summary_path=final_summary,
            rows_seen=rows_seen,
            rows_cached=rows_cached,
            rows_fetched=rows_fetched,
            rows_complete=coverage_counts["complete"],
            rows_partial=coverage_counts["partial"],
            rows_unavailable=coverage_counts["unavailable"],
            platform_counts={platform: platform_counts[platform] for platform in PLATFORM_NAMES},
            root_comment_count=root_comment_count,
            reply_count=reply_count,
            request_count=fetcher.request_count,
            failure_count=failure_count,
        )


def _load_resumable_records(path: Path) -> list[VehiclePairCommentRecordV1]:
    """读取未完成 run 已提交到 JSONL 的整行结果。"""

    if not path.is_file():
        raise ValueError(f"续跑 staging 缺少评论 JSONL: {path}")
    records: list[VehiclePairCommentRecordV1] = []
    with path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            try:
                records.append(VehiclePairCommentRecordV1.model_validate_json(raw_line))
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"续跑评论 JSONL 第 {line_number} 行非法: {path}") from exc
    return records


def _validate_resume_manifest(
    *,
    staging_dir: Path,
    run_id: str,
    input_path: Path,
    has_resumed_records: bool,
) -> None:
    """核对断点的输入身份；旧 staging 至少要有可严格比对的完成行。"""

    manifest_path = staging_dir / "resume_manifest.json"
    manifest = load_json_object(manifest_path)
    if not manifest:
        if has_resumed_records:
            return
        raise ValueError(f"续跑 staging 缺少输入清单且没有已完成记录: {staging_dir}")
    if manifest.get("schema_version") != _RESUME_SCHEMA:
        raise ValueError(f"不支持的评论续跑清单版本: {manifest_path}")
    if manifest.get("run_id") != run_id:
        raise ValueError(f"评论续跑清单的 run_id 与目录不一致: {manifest_path}")
    if manifest.get("input_sha256") != sha256_file(input_path):
        raise ValueError(f"续跑输入文件已变化: {input_path}")


def _validate_resume_prefix(
    *,
    input_path: Path,
    resumed_records: list[VehiclePairCommentRecordV1],
) -> None:
    """续跑前严格核对输入前缀，避免把旧结果拼接到另一批输入。"""

    input_records = _iter_input_records(input_path)
    for line_number, resumed in enumerate(resumed_records, start=1):
        current = next(input_records, None)
        if current is None or current != resumed.record:
            raise ValueError(f"续跑输入与 staging 第 {line_number} 行不一致")


def _has_resumable_data(staging_dir: Path) -> bool:
    """判断失败 staging 是否含已落盘结果或 Provider Raw 审计证据。"""

    jsonl_path = staging_dir / "comparison_posts_with_comments.jsonl"
    if jsonl_path.is_file() and jsonl_path.stat().st_size > 0:
        return True
    provider_root = staging_dir / "provider"
    return provider_root.is_dir() and any(provider_root.rglob("raw/*.json"))


def _recover_completed_staging_runs(output_root: Path) -> None:
    """发布上次已写完摘要的 staging；只做本地校验和改名，不调用 Provider。"""

    runs_root = output_root / "runs"
    for staging_dir in sorted(output_root.glob(".staging-*")):
        if not staging_dir.is_dir():
            continue
        summary_path = staging_dir / "run_summary.json"
        if not summary_path.is_file():
            continue
        run_id = staging_dir.name.removeprefix(".staging-")
        final_run_dir = runs_root / run_id
        if final_run_dir.exists():
            continue
        _validate_completed_staging(staging_dir=staging_dir, run_id=run_id)
        runs_root.mkdir(parents=True, exist_ok=True)
        _publish_run_directory(staging_dir, final_run_dir)


def _validate_completed_staging(*, staging_dir: Path, run_id: str) -> None:
    """以摘要和完整 JSONL 为提交标记，拒绝接管不完整或不兼容 staging。"""

    summary_path = staging_dir / "run_summary.json"
    summary = load_json_object(summary_path)
    if summary.get("schema_version") not in _RUN_SCHEMAS:
        raise ValueError(f"不支持的评论 staging 版本: {summary_path}")
    if summary.get("run_id") != run_id:
        raise ValueError(f"评论 staging 的 run_id 与目录不一致: {summary_path}")

    jsonl_path = staging_dir / "comparison_posts_with_comments.jsonl"
    workbook_path = staging_dir / "comparison_posts_with_comments.xlsx"
    if not jsonl_path.is_file() or not workbook_path.is_file() or workbook_path.stat().st_size == 0:
        raise ValueError(f"评论 staging 缺少完整输出: {staging_dir}")
    if not zipfile.is_zipfile(workbook_path):
        raise ValueError(f"评论 staging Excel 不是有效的 XLSX: {workbook_path}")
    with zipfile.ZipFile(workbook_path) as workbook_archive:
        damaged_member = workbook_archive.testzip()
    if damaged_member is not None:
        raise ValueError(f"评论 staging Excel 成员损坏: {workbook_path}: {damaged_member}")

    observed: Counter[str] = Counter()
    with jsonl_path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            try:
                enriched = VehiclePairCommentRecordV1.model_validate_json(raw_line)
            except (ValidationError, ValueError) as exc:
                raise ValueError(
                    f"评论 staging JSONL 非法: {jsonl_path}: 第 {line_number} 行"
                ) from exc
            observed["rows_seen"] += 1
            observed[f"rows_{enriched.comment_fetch.coverage}"] += 1
            observed["root_comment_count"] += enriched.comment_fetch.root_comment_count
            observed["reply_count"] += enriched.comment_fetch.reply_count
            observed["failure_count"] += len(enriched.comment_fetch.failures)

    for field in (
        "rows_seen",
        "rows_complete",
        "rows_partial",
        "rows_unavailable",
        "root_comment_count",
        "reply_count",
        "failure_count",
    ):
        expected = summary.get(field)
        if (
            isinstance(expected, int)
            and not isinstance(expected, bool)
            and expected != observed[field]
        ):
            raise ValueError(f"评论 staging 摘要字段 {field} 与 JSONL 不一致: {summary_path}")


def _publish_run_directory(staging_dir: Path, final_run_dir: Path) -> None:
    """短暂文件占用时有界重试最终改名；失败后由调用方保留完整 staging。"""

    for attempt in range(len(_PUBLISH_RETRY_DELAYS_SECONDS) + 1):
        try:
            os.replace(staging_dir, final_run_dir)
            return
        except PermissionError:
            if attempt == len(_PUBLISH_RETRY_DELAYS_SECONDS):
                raise
            time.sleep(_PUBLISH_RETRY_DELAYS_SECONDS[attempt])


def _load_and_reconcile_state(
    output_root: Path,
) -> tuple[dict[str, Any], AppendOnlyShardIndex]:
    """首次升级扫描本机旧评论 runs 建 cache；以后自动补索引但绝不触发 Provider。"""

    manifest_path = output_root / "state" / "manifest.json"
    state = load_json_object(manifest_path)
    if state:
        if state.get("schema_version") != _STATE_SCHEMA:
            raise ValueError(f"不支持的评论增量状态版本: {manifest_path}")
        if state.get("cache_policy") != _CACHE_POLICY:
            raise ValueError(f"评论缓存策略不兼容: {manifest_path}")
    else:
        state = {
            "schema_version": _STATE_SCHEMA,
            "cache_policy": _CACHE_POLICY,
            "indexed_runs": [],
        }

    cache_index = AppendOnlyShardIndex(output_root / "state" / "cache_index")
    indexed_runs = set(_string_list(state.get("indexed_runs")))
    for run_dir in iter_completed_run_dirs(output_root):
        if run_dir.name in indexed_runs:
            continue
        summary = load_json_object(run_dir / "run_summary.json")
        if summary.get("schema_version") not in _RUN_SCHEMAS:
            continue
        jsonl_path = resolve_summary_output(
            run_dir=run_dir,
            summary=summary,
            output_key="jsonl",
            fallback_relative="comparison_posts_with_comments.jsonl",
        )
        if not jsonl_path.is_file():
            continue
        _index_comment_run(
            output_root=output_root,
            run_id=run_dir.name,
            jsonl_path=jsonl_path,
            cache_index=cache_index,
        )
        indexed_runs.add(run_dir.name)
        state["indexed_runs"] = sorted(indexed_runs)
        atomic_write_json(manifest_path, state)
    state["indexed_runs"] = sorted(indexed_runs)
    atomic_write_json(manifest_path, state)
    return state, cache_index


def _index_comment_run(
    *,
    output_root: Path,
    run_id: str,
    jsonl_path: Path,
    cache_index: AppendOnlyShardIndex,
) -> None:
    """只读一个已完成 run，保存 content identity → JSONL byte offset locator。"""

    delta_root = output_root / "state" / ".reconcile" / run_id / "cache_index"
    shutil.rmtree(delta_root, ignore_errors=True)
    delta_root.mkdir(parents=True, exist_ok=False)
    writers: dict[str, TextIO] = {}
    try:
        with ExitStack() as stack, jsonl_path.open("rb") as source_file:
            line_number = 0
            while True:
                byte_offset = source_file.tell()
                raw_line = source_file.readline()
                if not raw_line:
                    break
                line_number += 1
                if not raw_line.strip():
                    continue
                try:
                    enriched = VehiclePairCommentRecordV1.model_validate_json(raw_line)
                except (ValidationError, ValueError) as exc:
                    raise ValueError(
                        f"历史评论 JSONL 非法: {jsonl_path}: 第 {line_number} 行"
                    ) from exc
                content = enriched.record.record.content
                key = content_identity_key(content.platform, content.external_content_id)
                shard = shard_name(key)
                writer = writers.get(shard)
                if writer is None:
                    writer = stack.enter_context(
                        (delta_root / f"{shard}.jsonl").open(
                            "w",
                            encoding="utf-8",
                            newline="\n",
                        )
                    )
                    writers[shard] = writer
                entry = {
                    "key": key,
                    "run_id": run_id,
                    "path": _relative_or_absolute(output_root, jsonl_path),
                    "offset": byte_offset,
                    "coverage": enriched.comment_fetch.coverage,
                }
                writer.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
                writer.write("\n")
            for writer in writers.values():
                writer.flush()
                os.fsync(writer.fileno())
        cache_index.append_delta_dir(delta_root)
    finally:
        shutil.rmtree(delta_root.parent.parent, ignore_errors=True)


def _partition_input(input_path: Path, partition_root: Path) -> None:
    """保留给大批量离线诊断的按 identity 分片工具；主补采链按输入顺序处理。"""

    partition_root.mkdir(parents=True, exist_ok=False)
    writers: dict[str, TextIO] = {}
    with ExitStack() as stack, input_path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            record = _parse_input_record(
                raw_line,
                input_path=input_path,
                line_number=line_number,
            )
            content = record.record.content
            key = content_identity_key(content.platform, content.external_content_id)
            shard = shard_name(key)
            writer = writers.get(shard)
            if writer is None:
                writer = stack.enter_context(
                    (partition_root / f"{shard}.jsonl").open(
                        "w",
                        encoding="utf-8",
                        newline="\n",
                    )
                )
                writers[shard] = writer
            writer.write(record.model_dump_json())
            writer.write("\n")
        for writer in writers.values():
            writer.flush()
            os.fsync(writer.fileno())


def _read_cached_record(
    output_root: Path,
    entry: dict[str, Any],
) -> VehiclePairCommentRecordV1:
    """按 state locator 从历史不可变 run 随机读取完整帖子+评论，不复制评论到 state。"""

    path_value = entry.get("path")
    offset = entry.get("offset")
    if not isinstance(path_value, str) or not isinstance(offset, int) or offset < 0:
        raise ValueError("评论 cache locator 非法")
    path = Path(path_value)
    if not path.is_absolute():
        path = output_root / path
    if not path.is_file():
        raise FileNotFoundError(f"评论 cache 指向的历史 run 已丢失: {path}")
    with path.open("rb") as source_file:
        source_file.seek(offset)
        raw_line = source_file.readline()
    try:
        return VehiclePairCommentRecordV1.model_validate_json(raw_line)
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"评论 cache 指向的历史记录已损坏: {path}@{offset}") from exc


def _materialize_current(
    *,
    output_root: Path,
    cache_index: AppendOnlyShardIndex,
    output_path: Path,
    workbook_path: Path,
) -> None:
    """从 cache 最新 locator 生成累计全量 JSONL/Excel；该步骤只有本地 I/O，不请求 TikHub。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_name(f".{output_path.name}.tmp")
    temp.unlink(missing_ok=True)
    content_rows = 0
    comment_rows = 0
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as output_file:
            for entry in cache_index.iter_latest_entries():
                enriched = _read_cached_record(output_root, entry)
                output_file.write(enriched.model_dump_json())
                output_file.write("\n")
                content_rows += 1
                comment_rows += len(enriched.comments)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp, output_path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise

    excel_summary = export_unified_data_excel(
        _iter_excel_records(output_path),
        workbook_path,
        include_analysis=False,
    )
    if excel_summary.content_rows != content_rows:
        raise RuntimeError("累计评论 Excel 内容行数与 current JSONL 不一致")
    if excel_summary.comment_rows != comment_rows:
        raise RuntimeError("累计评论 Excel 评论行数与 current JSONL 不一致")


def _run_summary_payload(
    *,
    run_id: str,
    input_path: Path,
    rows_seen: int,
    rows_cached: int,
    rows_fetched: int,
    coverage_counts: Counter[str],
    platform_counts: Counter[PlatformName],
    root_comment_count: int,
    reply_count: int,
    request_count: int,
    failure_count: int,
    jsonl_path: Path,
    workbook_path: Path,
    current_jsonl_path: Path,
    current_workbook_path: Path,
) -> dict[str, object]:
    """统一构造评论增量 run 摘要，显式区分 cached 与真正网络 fetch。"""

    return {
        "schema_version": _RUN_SCHEMA,
        "run_id": run_id,
        "input": str(input_path),
        "cache_policy": _CACHE_POLICY,
        "rows_seen": rows_seen,
        "rows_cached": rows_cached,
        "rows_fetched": rows_fetched,
        "rows_complete": coverage_counts["complete"],
        "rows_partial": coverage_counts["partial"],
        "rows_unavailable": coverage_counts["unavailable"],
        "platform_counts": {platform: platform_counts[platform] for platform in PLATFORM_NAMES},
        "root_comment_count": root_comment_count,
        "reply_count": reply_count,
        "request_count": request_count,
        "failure_count": failure_count,
        "outputs": {
            "jsonl": str(jsonl_path),
            "xlsx": str(workbook_path),
            "current_jsonl": str(current_jsonl_path),
            "current_xlsx": str(current_workbook_path),
        },
    }


def _relative_or_absolute(output_root: Path, path: Path) -> str:
    """优先保存 output_root 相对 locator，跨机器复制目录时仍可恢复。"""

    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return str(path)


def _validate_input_jsonl(path: Path) -> None:
    """网络请求前先完整校验输入 JSONL，避免格式错误发生在已产生 Provider 费用之后。"""

    with path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            _parse_input_record(raw_line, input_path=path, line_number=line_number)


def _iter_input_records(path: Path) -> Iterator[VehiclePairRecordV1]:
    """第二遍流式读取已校验的车型共现记录。"""

    with path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            yield _parse_input_record(raw_line, input_path=path, line_number=line_number)


def _parse_input_record(
    raw_line: bytes,
    *,
    input_path: Path,
    line_number: int,
) -> VehiclePairRecordV1:
    """按第二阶段正式输出模型校验一行输入并保留行号定位。"""

    try:
        return VehiclePairRecordV1.model_validate_json(raw_line)
    except (ValidationError, ValueError) as exc:
        raise ValueError(
            f"输入 JSONL 第 {line_number} 行不符合 VehiclePairRecordV1: {input_path}"
        ) from exc


def _iter_excel_records(path: Path) -> Iterator[UnifiedDataExcelV1]:
    """把补采 JSONL 流式投影为现有 Provider-neutral Excel Contract。"""

    with path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            try:
                enriched = VehiclePairCommentRecordV1.model_validate_json(raw_line)
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"补采 JSONL 第 {line_number} 行无法导出 Excel") from exc
            pair_record = enriched.record
            content = pair_record.record.content
            coverage = enriched.comment_fetch
            excel_content = project_canonical_content(
                content,
                matched_keywords=pair_record.record.matched_keywords,
                coverage=(
                    f"{coverage.coverage}; roots={coverage.root_comment_count}; "
                    f"replies={coverage.reply_count}"
                ),
            )
            target_models = set(pair_record.matched_target_models)
            brands: list[str] = []
            roles: list[str] = []
            vehicles: list[str] = []
            for mention in pair_record.model_mentions:
                if mention.brand not in brands:
                    brands.append(mention.brand)
                    roles.append("owned" if mention.model in target_models else "competitor")
                if mention.model not in vehicles:
                    vehicles.append(mention.model)
            excel_content = excel_content.model_copy(
                update={
                    "brands": tuple(brands),
                    "brand_roles": tuple(roles),
                    "competition_scope": "mixed",
                    "vehicles": tuple(vehicles),
                }
            )
            excel_comments: list[UnifiedDataExcelCommentV1] = []
            for comment in enriched.comments:
                excel_comments.append(
                    project_canonical_comment(
                        comment,
                        level="一级" if _is_root_comment(comment) else "二级",
                    )
                )
            yield UnifiedDataExcelV1(
                content=excel_content,
                comments=tuple(excel_comments),
            )


def _is_root_comment(comment: CanonicalCommentV1) -> bool:
    """按 Canonical root/parent 身份判断 Excel 展示层级。"""

    return (
        comment.root_comment_id == comment.external_comment_id and comment.parent_comment_id is None
    )


def _write_json(path: Path, value: object) -> None:
    """原子 run 发布前把摘要写入 staging 并刷盘。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.unlink(missing_ok=True)
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _string_list(value: object) -> list[str]:
    """读取状态中的字符串列表。"""

    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _resolve_run_id(run_id: str | None) -> str:
    """生成或校验文件系统安全的 run ID。"""

    value = run_id or beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def main() -> None:
    """使用文件顶部人工配置执行五平台增量评论补采。"""

    summary = enrich_comparison_comments(
        input_path=INPUT_JSONL,
        output_root=OUTPUT_ROOT,
        run_id=RESUME_RUN_ID,
    )
    counts = ", ".join(
        f"{platform}={summary.platform_counts[platform]}" for platform in PLATFORM_NAMES
    )
    print(
        "车型共现帖子评论增量补采完成: "
        f"run_id={summary.run_id}, rows={summary.rows_seen}, "
        f"cached={summary.rows_cached}, fetched={summary.rows_fetched}, "
        f"complete={summary.rows_complete}, partial={summary.rows_partial}, "
        f"unavailable={summary.rows_unavailable}, roots={summary.root_comment_count}, "
        f"replies={summary.reply_count}, requests={summary.request_count}, "
        f"{counts}, current={summary.current_jsonl_path}"
    )


if __name__ == "__main__":
    main()

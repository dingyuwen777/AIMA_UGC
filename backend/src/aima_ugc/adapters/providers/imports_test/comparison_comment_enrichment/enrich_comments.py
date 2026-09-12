"""直接从车型共现 JSONL 为五个平台逐帖补采全部评论并导出 Excel。"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from aima_ugc.adapters.providers.imports_test.comparison_comment_enrichment.models import (
    CommentFetchCoverageV1,
    CommentFetchFailureV1,
    VehiclePairCommentRecordV1,
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
    r"E:\AIMA_UGC_data\vehicle_pair_filter\output\runs\<run_id>\comparison_posts.jsonl"
)
OUTPUT_ROOT = Path(__file__).with_name("output")

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")
_FATAL_HTTP_STATUSES = frozenset({401, 403, 408, 425, 429})


@dataclass(frozen=True, slots=True)
class CommentEnrichmentRunSummary:
    """记录一次五平台逐帖评论补采的正式输出与统计。"""

    run_id: str
    run_dir: Path
    input_path: Path
    output_jsonl_path: Path
    workbook_path: Path
    run_summary_path: Path
    rows_seen: int
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

    def fetch(self, record: VehiclePairRecordV1) -> _FetchResult:
        """对一篇已筛选帖子分页抓完一级评论及其全部二级回复。"""

        content = record.record.content
        request_count_before = self.request_count
        comments: list[CanonicalCommentV1] = []
        seen_comment_ids: set[str] = set()
        failures: list[CommentFetchFailureV1] = []
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
                replies, reply_failures = self._fetch_replies(
                    content_platform=content.platform,
                    external_content_id=content.external_content_id,
                    alternate_ids=content.alternate_ids,
                    root=root,
                    seen_comment_ids=seen_comment_ids,
                )
                comments.extend(replies)
                reply_count += len(replies)
                failures.extend(reply_failures)

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
        if failures:
            coverage = "partial" if comments else "unavailable"
        else:
            coverage = "complete"
        return _FetchResult(
            comments=tuple(comments),
            coverage=CommentFetchCoverageV1(
                coverage=coverage,
                reported_total=content.metrics.comment_count,
                root_comment_count=root_count,
                reply_count=reply_count,
                request_count=request_count,
                root_stop_reason=root_stop_reason,
                failures=tuple(failures),
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
    ) -> tuple[list[CanonicalCommentV1], list[CommentFetchFailureV1]]:
        """对一个一级评论分页抓完全部二级回复，不使用采样数量上限。"""

        replies: list[CanonicalCommentV1] = []
        failures: list[CommentFetchFailureV1] = []
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
        return replies, failures

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


def enrich_comparison_comments(
    *,
    input_path: Path,
    output_root: Path,
    run_id: str | None = None,
    env_file: str | Path | None = None,
    provider_config: TikHubTestConfig | None = None,
    transport: ProviderTransport | None = None,
) -> CommentEnrichmentRunSummary:
    """直接遍历车型共现 JSONL，为五个平台逐帖补采全部评论并导出 Excel。"""

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
    """在一个原子 run 中执行网络补采、统一 JSONL、Excel 与摘要写出。"""

    actual_run_id = _resolve_run_id(run_id)
    runs_root = output_root / "runs"
    final_run_dir = runs_root / actual_run_id
    staging_dir = output_root / f".staging-{actual_run_id}"
    if final_run_dir.exists():
        raise FileExistsError(f"目标 run 已存在: {final_run_dir}")
    if staging_dir.exists():
        raise FileExistsError(f"staging run 已存在，请先人工确认后清理: {staging_dir}")
    runs_root.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=False)

    staging_jsonl = staging_dir / "comparison_posts_with_comments.jsonl"
    staging_workbook = staging_dir / "comparison_posts_with_comments.xlsx"
    final_jsonl = final_run_dir / staging_jsonl.name
    final_workbook = final_run_dir / staging_workbook.name
    final_summary = final_run_dir / "run_summary.json"

    rows_seen = 0
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

    try:
        with staging_jsonl.open("w", encoding="utf-8", newline="\n") as output_file:
            for record in _iter_input_records(input_path):
                rows_seen += 1
                platform_counts[record.record.content.platform] += 1
                fetched = fetcher.fetch(record)
                enriched = VehiclePairCommentRecordV1(
                    record=record,
                    comments=fetched.comments,
                    comment_fetch=fetched.coverage,
                )
                output_file.write(enriched.model_dump_json())
                output_file.write("\n")
                coverage_counts[fetched.coverage.coverage] += 1
                root_comment_count += fetched.coverage.root_comment_count
                reply_count += fetched.coverage.reply_count
                failure_count += len(fetched.coverage.failures)
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

        summary_payload: dict[str, object] = {
            "schema_version": "comparison-comment-enrichment-run.v1",
            "run_id": actual_run_id,
            "input": str(input_path),
            "rows_seen": rows_seen,
            "rows_complete": coverage_counts["complete"],
            "rows_partial": coverage_counts["partial"],
            "rows_unavailable": coverage_counts["unavailable"],
            "platform_counts": {platform: platform_counts[platform] for platform in PLATFORM_NAMES},
            "root_comment_count": root_comment_count,
            "reply_count": reply_count,
            "request_count": fetcher.request_count,
            "failure_count": failure_count,
            "outputs": {
                "jsonl": str(final_jsonl),
                "xlsx": str(final_workbook),
            },
        }
        _write_json(staging_dir / "run_summary.json", summary_payload)
        os.replace(staging_dir, final_run_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return CommentEnrichmentRunSummary(
        run_id=actual_run_id,
        run_dir=final_run_dir,
        input_path=input_path,
        output_jsonl_path=final_jsonl,
        workbook_path=final_workbook,
        run_summary_path=final_summary,
        rows_seen=rows_seen,
        rows_complete=coverage_counts["complete"],
        rows_partial=coverage_counts["partial"],
        rows_unavailable=coverage_counts["unavailable"],
        platform_counts={platform: platform_counts[platform] for platform in PLATFORM_NAMES},
        root_comment_count=root_comment_count,
        reply_count=reply_count,
        request_count=fetcher.request_count,
        failure_count=failure_count,
    )


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

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _resolve_run_id(run_id: str | None) -> str:
    """生成或校验文件系统安全的 run ID。"""

    value = run_id or beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def main() -> None:
    """使用文件顶部人工配置执行五平台车型共现帖子评论补采。"""

    summary = enrich_comparison_comments(
        input_path=INPUT_JSONL,
        output_root=OUTPUT_ROOT,
    )
    counts = ", ".join(
        f"{platform}={summary.platform_counts[platform]}" for platform in PLATFORM_NAMES
    )
    print(
        "车型共现帖子评论补采完成: "
        f"run_id={summary.run_id}, rows={summary.rows_seen}, complete={summary.rows_complete}, "
        f"partial={summary.rows_partial}, unavailable={summary.rows_unavailable}, "
        f"roots={summary.root_comment_count}, replies={summary.reply_count}, "
        f"requests={summary.request_count}, {counts}, output={summary.run_dir}"
    )


if __name__ == "__main__":
    main()

"""Excel 离线导入人工入口；配置参数并调用生产实现。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import SecretStr

from aima_ugc.adapters.llm import (
    DEFAULT_LLM_TRANSPORT_MAX_RETRIES,
    DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS,
    LLMRequestAuditWriter,
    OpenAICompatibleContentLabelingLLM,
    RetryingContentLabelingLLM,
    load_llm_pricing,
    recalculate_llm_request_costs,
)
from aima_ugc.adapters.providers.imports import (
    ExcelBatchConversionSummary,
    ExcelConversionSummary,
    convert_excel_files_to_canonical_jsonl,
    convert_excel_to_canonical_jsonl,
)
from aima_ugc.adapters.providers.imports_test.keyword_pack import load_keyword_pack
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentDeduplicationSummary,
    ContentFilterSummary,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    OfflineContentLabelingSummary,
    PromptTaxonomyLoader,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
    label_unified_content_jsonl,
)
from aima_ugc.platform.export import (
    ExcelExportSummary,
    export_unified_content_jsonl_to_excel,
)
from aima_ugc.platform.reporting import ReportGenerationSummary, generate_excel_report

os.environ.pop("SSLKEYLOGFILE", None)

# 配置一个 Path 走单文件转换；配置多个 Path 的有序元组合并到同一个 run。
INPUT_XLSX_FILES: Path | tuple[Path, ...] = (
    Path(r"E:\Desktop\08_18数据\惠科data(0813-0816).xlsx"),
    Path(r"E:\Desktop\08_18数据\惠科data(0817-0819).xlsx"),
)
OUTPUT_ROOT = Path(__file__).with_name("output")
KEYWORD_PACK_FILE = Path(__file__).with_name("keyword_pack.txt")

# None 表示自动扫描工作簿；如需强制指定某页，改成对应 Sheet 名。
SHEET_NAME: str | None = None
PROFILE = "aima-monitoring-excel.v1"
WRITE_TO_DATABASE = False

# 只限制报告统计，不影响转换、关键词过滤、去重、AI 打标或最终 Excel 全量数据。
# None 表示报告使用 Excel 内全部日期；日期范围包含开始日和结束日。
REPORT_DATE_RANGE: tuple[date, date] | None = (
    date(2026, 8, 13),
    date(2026, 8, 19),
)

# 最终 Excel 的“内容”Sheet 展示列；顺序就是导出顺序。
EXCEL_CONTENT_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "命中关键词",
    "发声类型",
    "是否用户真实发声",
    "情感标签",
    "一级标签",
    "二级标签",
)

# 最终 Excel 的“标签明细”Sheet 展示列；顺序就是导出顺序。
EXCEL_LABEL_DETAIL_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "命中关键词",
    "发声类型",
    "是否用户真实发声",
    "情感标签",
    "一级标签",
    "二级标签",
)

# 最终 Excel 的“评论”Sheet 展示列；顺序就是导出顺序。
EXCEL_COMMENT_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "评论内容",
    "作者",
    "评论时间",
    "评论点赞",
    "回复数",
    "评论层级",
    "评论ID",
    "根评论ID",
    "父评论ID",
)

ENABLE_REAL_LLM = True
# 一条内容一次独立 LLM 请求；同时最多 250 个请求在飞。
LLM_CONCURRENCY = 250
MAX_VALIDATION_RETRIES = 2
MAX_TRANSPORT_RETRIES = DEFAULT_LLM_TRANSPORT_MAX_RETRIES

ENV_FILE = Path(__file__).with_name(".env")

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")
_BEIJING = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class P1RunSummary:
    """一次人工全链路运行的交付摘要。"""

    run_id: str
    run_dir: Path
    run_summary_path: Path
    labeled_excel_path: Path
    report_markdown_path: Path
    report_word_path: Path


def prepare_run_dir(*, run_id: str | None = None) -> Path:
    """创建一次独立人工运行目录；显式 run_id 不允许覆盖既有目录。"""

    actual_run_id = _resolve_run_id(run_id)
    run_dir = OUTPUT_ROOT / "runs" / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _stage_run_dir(run_dir: Path | None) -> Path:
    if run_dir is None:
        return prepare_run_dir()
    actual = Path(run_dir)
    if not actual.is_dir():
        raise FileNotFoundError(f"imports_test run_dir 不存在: {actual}")
    return actual


def convert(
    *,
    run_dir: Path | None = None,
) -> ExcelConversionSummary | ExcelBatchConversionSummary:
    """执行 XLSX → Canonical JSONL。"""

    actual_run_dir = _stage_run_dir(run_dir)
    input_paths = _input_xlsx_files()
    if len(input_paths) > 1:
        summary: ExcelConversionSummary | ExcelBatchConversionSummary = (
            convert_excel_files_to_canonical_jsonl(
                input_paths=input_paths,
                output_path=actual_run_dir / "canonical" / "contents.jsonl",
                profile_name=PROFILE,
                sheet_name=SHEET_NAME,
            )
        )
    else:
        summary = convert_excel_to_canonical_jsonl(
            input_path=input_paths[0],
            output_path=actual_run_dir / "canonical" / "contents.jsonl",
            profile_name=PROFILE,
            sheet_name=SHEET_NAME,
        )
    _write_conversion_manifest(actual_run_dir, _source_rows(summary))
    return summary


def filter_keywords(*, run_dir: Path | None = None) -> ContentFilterSummary:
    """执行 Canonical JSONL → 关键词命中过滤后的统一内容记录。"""

    actual_run_dir = _stage_run_dir(run_dir)
    keyword_pack = load_keyword_pack(KEYWORD_PACK_FILE)
    return filter_canonical_content_jsonl(
        input_path=actual_run_dir / "canonical" / "contents.jsonl",
        output_path=actual_run_dir / "filtered" / "contents.jsonl",
        keywords=keyword_pack.keywords,
    )


def deduplicate(*, run_dir: Path | None = None) -> ContentDeduplicationSummary:
    """执行 filtered JSONL → 稳定身份去重后的统一内容记录。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return deduplicate_content_jsonl(
        input_path=actual_run_dir / "filtered" / "contents.jsonl",
        output_path=actual_run_dir / "deduplicated" / "contents.jsonl",
    )


def ingest_database(
    *,
    run_dir: Path | None = None,
    rows_seen: int | None = None,
    source_rows: tuple[tuple[Path, int], ...] | None = None,
) -> object:
    """显式数据库阶段；默认主链不调用，且本入口不管理 Docker/Migration。"""

    actual_run_dir = _stage_run_dir(run_dir)
    canonical_path = actual_run_dir / "canonical" / "contents.jsonl"
    deduplicated_path = actual_run_dir / "deduplicated" / "contents.jsonl"
    resolved_rows_seen = rows_seen if rows_seen is not None else _count_jsonl_rows(canonical_path)

    resolved_source_rows = source_rows or _load_conversion_source_rows(actual_run_dir)
    if resolved_source_rows is None:
        input_paths = _input_xlsx_files()
        resolved_source_rows = ((input_paths[0], resolved_rows_seen),)

    # 延迟导入保证默认 file-only 模式不装配数据库 Runtime。
    from aima_ugc.bootstrap.manual_ingestion import (
        ingest_excel_files_run_to_postgres,
        ingest_excel_run_to_postgres,
    )

    if len(resolved_source_rows) > 1:
        return ingest_excel_files_run_to_postgres(
            source_rows=resolved_source_rows,
            unified_content_path=deduplicated_path,
            rows_rejected=0,
        )

    return ingest_excel_run_to_postgres(
        input_path=resolved_source_rows[0][0],
        unified_content_path=deduplicated_path,
        rows_seen=resolved_source_rows[0][1],
        rows_rejected=0,
    )


def export_raw_excel(*, run_dir: Path | None = None) -> ExcelExportSummary:
    """可选导出当前 run 的未填分析标签人工审阅视图。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return export_unified_content_jsonl_to_excel(
        input_path=actual_run_dir / "deduplicated" / "contents.jsonl",
        output_path=actual_run_dir / "raw_data.xlsx",
        include_analysis=False,
        content_columns=EXCEL_CONTENT_COLUMNS,
        label_detail_columns=EXCEL_LABEL_DETAIL_COLUMNS,
        comment_columns=EXCEL_COMMENT_COLUMNS,
    )


def label_sentiment(*, run_dir: Path | None = None) -> OfflineContentLabelingSummary:
    """使用真实 LLM，以单条请求和有界并发打标当前 run。"""

    if not ENABLE_REAL_LLM:
        raise RuntimeError("真实 LLM 未启用；如需打标请将 ENABLE_REAL_LLM 设为 True")

    actual_run_dir = _stage_run_dir(run_dir)
    env = _load_env_file(ENV_FILE)
    timeout_seconds = _parse_positive_float(
        env.get(
            "AIMA_LLM_TIMEOUT_SECONDS",
            str(DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS),
        ),
        name="AIMA_LLM_TIMEOUT_SECONDS",
    )

    # 一次 run 只读取/解析一次 Prompt，所有 250 个并发请求共享同一个不可变口径。
    recovery_taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    prompt_loader = FrozenPromptTaxonomyLoader(recovery_taxonomy)
    request_audit_path = actual_run_dir / "analysis" / "llm_requests.jsonl"
    audit_writer = LLMRequestAuditWriter(request_audit_path)
    with audit_writer:
        with OpenAICompatibleContentLabelingLLM(
            base_url=_require_env(env, "AIMA_LLM_BASE_URL"),
            api_key=SecretStr(_require_env(env, "AIMA_LLM_API_KEY")),
            model=_require_env(env, "AIMA_LLM_MODEL"),
            timeout_seconds=timeout_seconds,
            max_connections=LLM_CONCURRENCY,
            pricing_catalog=load_llm_pricing(),
            request_audit=audit_writer.record,
        ) as base_llm:
            llm = RetryingContentLabelingLLM(
                inner=base_llm,
                max_retries=MAX_TRANSPORT_RETRIES,
            )
            service = ContentLabelingService(
                prompt_loader=prompt_loader,
                llm=llm,
            )
            summary = label_unified_content_jsonl(
                input_path=actual_run_dir / "deduplicated" / "contents.jsonl",
                analysis_dir=actual_run_dir / "analysis",
                service=service,
                max_validation_retries=MAX_VALIDATION_RETRIES,
                max_concurrency=LLM_CONCURRENCY,
                recovery_taxonomy=recovery_taxonomy,
            )
            llm_http_requests = llm.total_requests
            transport_retries = llm.total_retries

    cost_summary = audit_writer.summary
    if audit_writer.session_request_count != llm_http_requests:
        raise RuntimeError("LLM HTTP 请求数与费用审计记录数不一致")
    return replace(
        summary,
        llm_http_requests=llm_http_requests,
        transport_retries=transport_retries,
        llm_request_audit_path=request_audit_path,
        llm_calculated_http_requests=cost_summary.calculated_request_count,
        llm_uncalculated_http_requests=cost_summary.uncalculated_request_count,
        llm_input_tokens=cost_summary.input_tokens,
        llm_input_cache_hit_tokens=cost_summary.input_cache_hit_tokens,
        llm_input_cache_miss_tokens=cost_summary.input_cache_miss_tokens,
        llm_output_tokens=cost_summary.output_tokens,
        llm_total_cost_amount=cost_summary.total_cost_amount,
        llm_cost_currency=cost_summary.cost_currency,
    )


def recalculate_cost(*, run_dir: Path | None = None) -> object:
    """按当前价格目录生成派生费用报告，不覆盖原请求审计。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return recalculate_llm_request_costs(
        input_path=actual_run_dir / "analysis" / "llm_requests.jsonl",
        output_path=actual_run_dir / "analysis" / "cost_recalculation.json",
        pricing_catalog=load_llm_pricing(),
    )


def export_labeled_excel(
    *,
    run_dir: Path | None = None,
    run_id: str | None = None,
) -> ExcelExportSummary:
    """从当前 run 回写后的 deduplicated JSONL 导出最终带 Analysis 的 Excel。"""

    actual_run_dir = prepare_run_dir(run_id=run_id) if run_dir is None else _stage_run_dir(run_dir)
    return export_unified_content_jsonl_to_excel(
        input_path=actual_run_dir / "deduplicated" / "contents.jsonl",
        output_path=_labeled_output_path(actual_run_dir),
        include_analysis=True,
        content_columns=EXCEL_CONTENT_COLUMNS,
        label_detail_columns=EXCEL_LABEL_DETAIL_COLUMNS,
        comment_columns=EXCEL_COMMENT_COLUMNS,
    )


def generate_report(
    *,
    excel_path: Path | None = None,
    run_dir: Path | None = None,
    output_dir: Path | None = None,
    report_date_range: tuple[date, date] | None = None,
) -> ReportGenerationSummary:
    """从最终统一 Excel 独立生成 Markdown/Word 报告。"""

    if excel_path is not None and run_dir is not None:
        raise ValueError("excel_path 与 run_dir 只能指定一个")
    if excel_path is None and run_dir is None:
        raise ValueError("必须指定 excel_path 或既有 run_dir")

    if excel_path is not None:
        source_path = Path(excel_path)
        target_dir = Path(output_dir) if output_dir is not None else source_path.parent / "reports"
    else:
        assert run_dir is not None
        actual_run_dir = _stage_run_dir(run_dir)
        source_path = _labeled_output_path(actual_run_dir)
        target_dir = Path(output_dir) if output_dir is not None else actual_run_dir / "reports"

    return generate_excel_report(
        input_path=source_path,
        output_dir=target_dir,
        report_date_range=report_date_range,
    )


def run_all(
    *,
    run_id: str | None = None,
    write_to_database: bool = WRITE_TO_DATABASE,
    report_excel_path: Path | None = None,
) -> P1RunSummary:
    """创建一次独立 run，最终 Excel 完成后生成同一份 Markdown/Word 报告。"""

    actual_run_id = _resolve_run_id(run_id)
    run_dir = prepare_run_dir(run_id=actual_run_id)
    stages: list[dict[str, object]] = []

    conversion = convert(run_dir=run_dir)
    stages.append(_stage_payload("convert", conversion))

    filtering = filter_keywords(run_dir=run_dir)
    stages.append(_stage_payload("filter_keywords", filtering))

    deduplication = deduplicate(run_dir=run_dir)
    stages.append(_stage_payload("deduplicate", deduplication))

    if write_to_database:
        source_rows = _source_rows(conversion)
        database_ingestion = ingest_database(
            run_dir=run_dir,
            rows_seen=conversion.rows_seen,
            source_rows=source_rows,
        )
        stages.append(_stage_payload("database_ingestion", database_ingestion))

    labeling = label_sentiment(run_dir=run_dir)
    stages.append(_stage_payload("label_sentiment", labeling))

    labeled_export = export_labeled_excel(run_dir=run_dir)
    stages.append(_stage_payload("export_labeled_excel", labeled_export))

    run_summary_path = run_dir / "run_summary.json"
    labeled_excel_path = _labeled_output_path(run_dir)
    report_input_path = (
        Path(report_excel_path) if report_excel_path is not None else labeled_excel_path
    )
    if not report_input_path.is_file():
        raise FileNotFoundError(f"报告 Excel 不存在: {report_input_path}")
    report = generate_report(
        excel_path=report_input_path,
        output_dir=run_dir / "reports",
        report_date_range=REPORT_DATE_RANGE,
    )
    stages.append(_stage_payload("generate_report", report))

    input_paths = _input_xlsx_files()
    run_payload: dict[str, object] = {
        "schema_version": "p1-run-summary.v2",
        "run_id": actual_run_id,
        "source_xlsx_files": [str(path) for path in input_paths],
        "output_root": str(OUTPUT_ROOT),
        "run_dir": str(run_dir),
        "keyword_pack_file": str(KEYWORD_PACK_FILE),
        "labeled_excel": str(labeled_excel_path),
        "report_input_excel": str(report_input_path),
        "report_markdown": str(report.markdown_path),
        "report_word": str(report.word_path),
        "report_date_range": (
            [day.isoformat() for day in REPORT_DATE_RANGE]
            if REPORT_DATE_RANGE is not None
            else None
        ),
        "stages": stages,
    }
    if len(input_paths) == 1:
        run_payload["source_xlsx"] = str(input_paths[0])
    _atomic_write_json(run_summary_path, run_payload)
    return P1RunSummary(
        run_id=actual_run_id,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        labeled_excel_path=labeled_excel_path,
        report_markdown_path=report.markdown_path,
        report_word_path=report.word_path,
    )


def _count_jsonl_rows(path: Path) -> int:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def _input_xlsx_files() -> tuple[Path, ...]:
    configured = INPUT_XLSX_FILES
    if isinstance(configured, Path):
        return (configured,)
    if not isinstance(configured, tuple):
        raise TypeError("INPUT_XLSX_FILES 必须配置为一个 Path 或 Path 元组")
    input_paths = tuple(Path(path) for path in configured)
    if not input_paths:
        raise ValueError("INPUT_XLSX_FILES 至少需要配置一个 Excel")
    return input_paths


def _source_rows(
    summary: ExcelConversionSummary | ExcelBatchConversionSummary,
) -> tuple[tuple[Path, int], ...]:
    if isinstance(summary, ExcelBatchConversionSummary):
        return tuple((item.input_path, item.rows_seen) for item in summary.files)
    return ((summary.input_path, summary.rows_seen),)


def _write_conversion_manifest(
    run_dir: Path,
    source_rows: tuple[tuple[Path, int], ...],
) -> None:
    _atomic_write_json(
        Path(run_dir) / "canonical" / "conversion_summary.json",
        {
            "schema_version": "excel-conversion-run.v1",
            "sources": [
                {"input_path": str(input_path), "rows_seen": rows_seen}
                for input_path, rows_seen in source_rows
            ],
        },
    )


def _load_conversion_source_rows(
    run_dir: Path,
) -> tuple[tuple[Path, int], ...] | None:
    manifest_path = Path(run_dir) / "canonical" / "conversion_summary.json"
    if not manifest_path.is_file():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "excel-conversion-run.v1":
        raise ValueError(f"转换清单格式不支持: {manifest_path}")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"转换清单缺少 sources: {manifest_path}")
    parsed: list[tuple[Path, int]] = []
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError(f"转换清单 source 不是 object: {manifest_path}")
        input_path = item.get("input_path")
        rows_seen = item.get("rows_seen")
        if not isinstance(input_path, str) or not input_path:
            raise ValueError(f"转换清单 input_path 不合法: {manifest_path}")
        if isinstance(rows_seen, bool) or not isinstance(rows_seen, int) or rows_seen < 0:
            raise ValueError(f"转换清单 rows_seen 不合法: {manifest_path}")
        parsed.append((Path(input_path), rows_seen))
    return tuple(parsed)


def _resolve_run_id(run_id: str | None) -> str:
    value = run_id or datetime.now(UTC).astimezone(_BEIJING).strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def _labeled_output_path(run_dir: Path) -> Path:
    return Path(run_dir) / "labeled_data.xlsx"


def _stage_payload(stage: str, summary: object) -> dict[str, object]:
    return {
        "stage": stage,
        "summary": _jsonable_summary(summary),
    }


def _jsonable_summary(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable_value(asdict(value))
    if isinstance(value, dict):
        return _jsonable_value(value)
    return _jsonable_value(value)


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"LLM 配置文件不存在: {path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            raise ValueError(f"{path}: 第 {line_number} 行不是 KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise ValueError(f"{path}: 第 {line_number} 行变量名为空或重复")
        values[key] = _strip_optional_quotes(raw_value.strip())
    return values


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _require_env(values: dict[str, str], name: str) -> str:
    value = values.get(name, "")
    if not value or value != value.strip():
        raise ValueError(f"{name} 必须在 ENV_FILE 中配置为非空且已清洗的值")
    return value


def _parse_positive_float(value: str, *, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if parsed <= 0:
        raise ValueError(f"{name} 必须大于 0")
    return parsed


if __name__ == "__main__":
    result = run_all()
    print(
        "run_all 完成: "
        f"run_id={result.run_id}, "
        f"labeled_excel={result.labeled_excel_path}, "
        f"report_markdown={result.report_markdown_path}, "
        f"report_word={result.report_word_path}, "
        f"run_summary={result.run_summary_path}"
    )

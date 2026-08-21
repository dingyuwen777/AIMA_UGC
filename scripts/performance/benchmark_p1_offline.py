"""离线 Excel 主链性能基准；只编排生产实现，不复制业务规则。"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.imports import convert_excel_to_canonical_jsonl
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomy,
    PromptTaxonomyLoader,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
    label_unified_content_jsonl,
)
from aima_ugc.platform.export import export_unified_content_jsonl_to_excel
from openpyxl import Workbook

PERFORMANCE_SCHEMA_VERSION = "p1-offline-performance.v1"
_PROFILE = "aima-monitoring-excel.v1"
_SHEET_NAME = "文章"
_KEYWORDS = ("爱玛",)
_HEADERS = (
    "序号",
    "监测项名称",
    "文章编号",
    "标题",
    "内文",
    "媒体名称（中文）",
    "版面",
    "出版日期",
    "媒体类型",
    "作者",
    "全文情感",
    "原文链接",
    "粉丝数",
)
_PLATFORMS = ("小红书", "抖音", "微博", "B站", "快手")


class _TaxonomyBenchmarkLLM:
    """由当前 PromptTaxonomy 动态生成合法响应的无网络性能 Fake。"""

    provider_name = "p1-performance-fake"
    model_name = "taxonomy-derived-fake"

    def __init__(self, taxonomy: PromptTaxonomy) -> None:
        self._sentiment = taxonomy.sentiments[0]
        self._primary = taxonomy.primary_labels[0]
        self._secondary = taxonomy.labels[self._primary][0]

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        payload = {
            "items": [
                {
                    "item_no": item.item_no,
                    "relevance": "relevant",
                    "voice_type": "user_voice",
                    "sentiment": self._sentiment,
                    "labels": [
                        {
                            "primary_label": self._primary,
                            "secondary_label": self._secondary,
                        }
                    ],
                }
                for item in request.items
            ]
        }
        return ContentLabelingLLMResponse(
            raw_text=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )


def run_benchmark(
    *,
    work_dir: Path,
    row_count: int = 90_000,
    label_concurrency: int = 250,
) -> dict[str, Any]:
    """生成 13 列相似结构 Fixture，并对离线生产主链做无网络性能测量。"""

    _require_positive_int(row_count, name="row_count")
    _require_positive_int(label_concurrency, name="label_concurrency")
    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    _require_empty_work_dir(root)

    source_xlsx = root / "source_90000.xlsx"
    canonical_jsonl = root / "canonical" / "contents.jsonl"
    filtered_jsonl = root / "filtered" / "contents.jsonl"
    deduplicated_jsonl = root / "deduplicated" / "contents.jsonl"
    analysis_dir = root / "analysis"
    labeled_xlsx = root / "labeled_data.xlsx"
    report_path = root / "performance_report.json"

    fixture_started = time.perf_counter()
    _write_fixture(source_xlsx, row_count=row_count)
    fixture_elapsed = time.perf_counter() - fixture_started

    stages: dict[str, dict[str, int | float]] = {}

    conversion, stages["convert"] = _measure_stage(
        row_count=row_count,
        operation=lambda: convert_excel_to_canonical_jsonl(
            input_path=source_xlsx,
            output_path=canonical_jsonl,
            profile_name=_PROFILE,
            sheet_name=_SHEET_NAME,
        ),
    )
    if conversion.rows_written != row_count or conversion.rows_rejected != 0:
        raise RuntimeError("性能 Fixture 转换后行数不一致")

    filtering, stages["filter_keywords"] = _measure_stage(
        row_count=row_count,
        operation=lambda: filter_canonical_content_jsonl(
            input_path=canonical_jsonl,
            output_path=filtered_jsonl,
            keywords=_KEYWORDS,
        ),
    )
    if filtering.rows_written != row_count or filtering.rows_filtered_out != 0:
        raise RuntimeError("性能 Fixture 关键词过滤后行数不一致")

    deduplication, stages["deduplicate"] = _measure_stage(
        row_count=row_count,
        operation=lambda: deduplicate_content_jsonl(
            input_path=filtered_jsonl,
            output_path=deduplicated_jsonl,
        ),
    )
    if (
        deduplication.rows_written != row_count
        or deduplication.duplicates_removed != 0
        or deduplication.conflicts != 0
    ):
        raise RuntimeError("性能 Fixture 去重后行数不一致")

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=_TaxonomyBenchmarkLLM(taxonomy),
    )
    labeling, stages["analysis_writeback"] = _measure_stage(
        row_count=row_count,
        operation=lambda: label_unified_content_jsonl(
            input_path=deduplicated_jsonl,
            analysis_dir=analysis_dir,
            service=service,
            max_validation_retries=0,
            max_concurrency=label_concurrency,
            recovery_taxonomy=taxonomy,
        ),
    )
    if labeling.rows_succeeded != row_count or labeling.rows_failed != 0:
        raise RuntimeError("性能 Fixture Analysis 回写后成功行数不一致")
    stages["analysis_writeback"]["llm_attempts"] = labeling.llm_attempts
    stages["analysis_writeback"]["peak_in_flight"] = labeling.peak_in_flight

    exported, stages["export_labeled_excel"] = _measure_stage(
        row_count=row_count,
        operation=lambda: export_unified_content_jsonl_to_excel(
            input_path=deduplicated_jsonl,
            output_path=labeled_xlsx,
            include_analysis=True,
        ),
    )
    if exported.content_rows != row_count:
        raise RuntimeError("性能 Fixture 最终 Excel 行数不一致")

    pipeline_elapsed = sum(float(stage["elapsed_seconds"]) for stage in stages.values())
    report: dict[str, Any] = {
        "schema_version": PERFORMANCE_SCHEMA_VERSION,
        "row_count": row_count,
        "column_count": len(_HEADERS),
        "label_concurrency": label_concurrency,
        "fixture_generation_seconds": fixture_elapsed,
        "pipeline_elapsed_seconds": pipeline_elapsed,
        "pipeline_rows_per_second": row_count / pipeline_elapsed,
        "peak_rss_bytes": max(int(stage["peak_rss_bytes"]) for stage in stages.values()),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "os_name": os.name,
        },
        "prompt_sha256": taxonomy.prompt_sha256,
        "taxonomy_sha256": taxonomy.taxonomy_sha256,
        "stages": stages,
        "artifacts": {
            "source_xlsx": _artifact(source_xlsx),
            "canonical_jsonl": _artifact(canonical_jsonl),
            "filtered_jsonl": _artifact(filtered_jsonl),
            "deduplicated_jsonl": _artifact(deduplicated_jsonl),
            "attempts_jsonl": _artifact(analysis_dir / "attempts.jsonl"),
            "checkpoints_jsonl": _artifact(analysis_dir / "checkpoints.jsonl"),
            "labeled_xlsx": _artifact(labeled_xlsx),
            "report_json": {"path": str(report_path.resolve())},
        },
    }
    _atomic_write_json(report_path, report)
    return report


def _write_fixture(path: Path, *, row_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(_SHEET_NAME)
    sheet.append(_HEADERS)
    published_at = datetime(2026, 8, 18, 10, 0, 0)
    for index in range(1, row_count + 1):
        sheet.append(
            (
                index,
                "爱玛监测",
                f"AIMA-P1H-{index:06d}",
                f"爱玛产品体验样本 {index}",
                f"这是用于性能测量的爱玛公开内容结构样本 {index}。",
                _PLATFORMS[(index - 1) % len(_PLATFORMS)],
                "客户端",
                published_at,
                "社交媒体",
                f"样本作者{index % 1000}",
                "源情感仅供原文件审阅",
                f"https://example.com/aima/{index}",
                index % 100_000,
            )
        )
    workbook.save(path)


def _measure_stage(*, row_count: int, operation: Any) -> tuple[Any, dict[str, int | float]]:
    started = time.perf_counter()
    result = operation()
    elapsed = time.perf_counter() - started
    if elapsed <= 0:
        raise RuntimeError("性能测量时钟未前进")
    return (
        result,
        {
            "rows": row_count,
            "elapsed_seconds": elapsed,
            "rows_per_second": row_count / elapsed,
            "peak_rss_bytes": _peak_rss_bytes(),
        },
    )


def _peak_rss_bytes() -> int:
    if os.name == "nt":
        return _windows_peak_rss_bytes()

    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    multiplier = 1 if sys.platform == "darwin" else 1024
    peak = int(usage * multiplier)
    if peak <= 0:
        raise RuntimeError("无法取得进程峰值 RSS")
    return peak


def _windows_peak_rss_bytes() -> int:
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    get_process_memory_info = psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_process_memory_info.restype = ctypes.c_int

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not get_process_memory_info(
        get_current_process(),
        ctypes.byref(counters),
        ctypes.sizeof(counters),
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo 失败")
    peak = int(counters.PeakWorkingSetSize)
    if peak <= 0:
        raise RuntimeError("Windows 未返回有效峰值 RSS")
    return peak


def _artifact(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {"path": str(resolved), "bytes": resolved.stat().st_size}


def _require_empty_work_dir(path: Path) -> None:
    if any(path.iterdir()):
        raise ValueError(f"性能 work_dir 必须为空目录: {path}")


def _require_positive_int(value: int, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} 必须是大于 0 的整数")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行离线 Excel 生产主链性能基准")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=90_000)
    parser.add_argument("--label-concurrency", type=int, default=250)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_benchmark(
        work_dir=args.work_dir,
        row_count=args.rows,
        label_concurrency=args.label_concurrency,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

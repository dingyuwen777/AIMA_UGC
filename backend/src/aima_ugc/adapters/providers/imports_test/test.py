"""P1 Excel 离线导入人工入口；只配置参数并调用生产实现。"""

from pathlib import Path

from aima_ugc.adapters.providers.imports import (
    ExcelConversionSummary,
    convert_excel_to_canonical_jsonl,
)

INPUT_XLSX = Path(r"E:\path\to\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")

KEYWORDS = ("爱玛",)

SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

ENABLE_REAL_LLM = False
MAX_VALIDATION_RETRIES = 2

ENV_FILE = Path(__file__).with_name(".env")


def convert() -> ExcelConversionSummary:
    """执行 P1B 的 XLSX → Canonical JSONL；不做筛选、去重或 AI。"""

    return convert_excel_to_canonical_jsonl(
        input_path=INPUT_XLSX,
        output_path=OUTPUT_ROOT / "canonical" / "contents.jsonl",
        profile_name=PROFILE,
        sheet_name=SHEET_NAME,
    )


if __name__ == "__main__":
    result = convert()
    print(
        "convert 完成: "
        f"rows_seen={result.rows_seen}, "
        f"rows_written={result.rows_written}, "
        f"rows_rejected={result.rows_rejected}, "
        f"output={result.output_path}"
    )

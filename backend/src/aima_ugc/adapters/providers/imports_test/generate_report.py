from datetime import date
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import generate_report

OUTPUT_ROOT = Path(__file__).with_name("output")
INPUT_EXCEL = OUTPUT_ROOT / "runs" / "20260820T140218.951531+0800" / "labeled_data.xlsx"
# 只影响本次报告，日期范围包含开始日和结束日；改为 None 表示统计全部日期。
REPORT_DATE_RANGE = (date(2026, 8, 13), date(2026, 8, 19))
REPORT_OUTPUT_DIR = (
    OUTPUT_ROOT
    / "reports"
    / (
        "all"
        if REPORT_DATE_RANGE is None
        else f"{REPORT_DATE_RANGE[0]:%Y%m%d}-{REPORT_DATE_RANGE[1]:%Y%m%d}"
    )
)


def main() -> None:
    result = generate_report(
        excel_path=INPUT_EXCEL,
        output_dir=REPORT_OUTPUT_DIR,
        report_date_range=REPORT_DATE_RANGE,
    )

    print(result.markdown_path)
    print(result.word_path)


if __name__ == "__main__":
    main()

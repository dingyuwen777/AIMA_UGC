from datetime import date
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import (
    generate_report,
    load_feishu_publication_config,
    publish_generated_report_to_feishu,
)

OUTPUT_ROOT = Path(__file__).with_name("output")
# 本期报告输入；每次换本期 run 时同步更新下面的上一期输入。
INPUT_EXCEL = OUTPUT_ROOT / "runs" / "20260910T092503.286116+0800" / "labeled_data.xlsx"
# 本期 2026-09-01 的等长紧邻上期 2026-08-31；只用于 1.3 环比，不改变本期统计输入。
PREVIOUS_INPUT_EXCEL = OUTPUT_ROOT / "runs" / "20260903T122420.816753+0800" / "labeled_data.xlsx"
# 只影响本次报告，日期范围包含开始日和结束日；改为 None 表示统计全部日期。
REPORT_DATE_RANGE = (date(2026, 9, 3), date(2026, 9, 9))
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
    feishu_config = load_feishu_publication_config()
    result = generate_report(
        excel_path=INPUT_EXCEL,
        output_dir=REPORT_OUTPUT_DIR,
        report_date_range=REPORT_DATE_RANGE,
        previous_excel_path=PREVIOUS_INPUT_EXCEL,
        prepare_feishu_publication=feishu_config is not None,
    )

    print(result.markdown_path)
    print(result.word_path)
    if feishu_config is not None:
        publication = publish_generated_report_to_feishu(result, config=feishu_config)
        print(publication.native_document_url)
        if publication.editable_chart_sheet_url is not None:
            print(publication.editable_chart_sheet_url)


if __name__ == "__main__":
    main()

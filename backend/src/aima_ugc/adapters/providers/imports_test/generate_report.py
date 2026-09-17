import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import (
    generate_report,
    load_feishu_publication_config,
    publish_generated_report_to_feishu,
)
from aima_ugc.bootstrap.representative_report_pipeline import (
    prepare_representative_report,
)
from aima_ugc.bootstrap.representative_selection_publication import (
    publish_selected_representatives_to_feishu,
)
from aima_ugc.entrypoints.representative_selection_main import (
    DEFAULT_ENV_FILE,
    _load_entrypoint_settings,
)

OUTPUT_ROOT = Path(__file__).with_name("output")
INPUT_EXCEL = OUTPUT_ROOT / "runs" / "20260917T093549.030465+0800" / "labeled_data.xlsx"
PREVIOUS_INPUT_EXCEL = OUTPUT_ROOT / "runs" / "20260910T092503.286116+0800" / "labeled_data.xlsx"
REPORT_DATE_RANGE = (date(2026, 9, 10), date(2026, 9, 16))
REPORT_OUTPUT_DIR = (
    OUTPUT_ROOT
    / "reports"
    / (
        "all"
        if REPORT_DATE_RANGE is None
        else f"{REPORT_DATE_RANGE[0]:%Y%m%d}-{REPORT_DATE_RANGE[1]:%Y%m%d}"
    )
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成报告并可选发布代表性评论与飞书报告")
    parser.add_argument("--input-xlsx", type=Path, default=INPUT_EXCEL)
    parser.add_argument("--previous-input-xlsx", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--report-start", type=date.fromisoformat, default=REPORT_DATE_RANGE[0])
    parser.add_argument("--report-end", type=date.fromisoformat, default=REPORT_DATE_RANGE[1])
    parser.add_argument("--prompt", type=Path, help="代表性筛选 Prompt")
    parser.add_argument("--max-per-group", type=int, default=10)
    parser.add_argument("--selector-pool-size", type=int, default=50)
    parser.add_argument("--screenshots-dir", type=Path, help="预先准备的 PNG 截图目录")
    parser.add_argument("--no-screenshots", action="store_true", help="跳过自动截图尝试")
    parser.add_argument(
        "--publish-all",
        action="store_true",
        help="本地报告生成后，同时发布飞书在线报告和代表性评论多维表",
    )
    parser.add_argument(
        "--publish-report",
        action="store_true",
        help="只发布报告，不发布代表性评论多维表",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    if arguments.max_per_group <= 0 or arguments.selector_pool_size <= 0:
        raise SystemExit("--max-per-group 和 --selector-pool-size 必须大于 0")
    if arguments.report_start > arguments.report_end:
        raise SystemExit("--report-start 不能晚于 --report-end")
    if arguments.publish_all and arguments.publish_report:
        raise SystemExit("--publish-all 与 --publish-report 不能同时使用")

    settings, environment = _load_entrypoint_settings(arguments.env_file)
    publish_report = arguments.publish_all or arguments.publish_report
    feishu_config = None
    if publish_report:
        feishu_config = load_feishu_publication_config(environ=environment)
        if feishu_config is None:
            raise SystemExit("发布报告前必须启用并配置 AIMA_FEISHU_REPORT_ENABLED")
    if arguments.publish_all and (not settings.feishu_app_id or not settings.feishu_table_id):
        raise SystemExit("--publish-all 缺少飞书多维表配置")

    input_excel = arguments.input_xlsx.resolve()
    previous_excel = (
        arguments.previous_input_xlsx.resolve()
        if arguments.previous_input_xlsx is not None
        else (
            PREVIOUS_INPUT_EXCEL.resolve()
            if input_excel == INPUT_EXCEL.resolve()
            else None
        )
    )
    output_dir = (
        arguments.output_dir.resolve()
        if arguments.output_dir is not None
        else (
            REPORT_OUTPUT_DIR.resolve()
            if input_excel == INPUT_EXCEL.resolve()
            else input_excel.parent
            / "reports"
            / f"{arguments.report_start:%Y%m%d}-{arguments.report_end:%Y%m%d}"
        )
    )
    preparation = prepare_representative_report(
        input_path=input_excel,
        output_dir=output_dir / "representative_selection",
        settings=settings,
        environment=environment,
        prompt_path=(arguments.prompt or _default_prompt()).resolve(),
        max_per_group=arguments.max_per_group,
        selector_pool_size=arguments.selector_pool_size,
        screenshots_dir=(
            None if arguments.screenshots_dir is None else arguments.screenshots_dir.resolve()
        ),
        capture_screenshots=not arguments.no_screenshots,
    )
    result = generate_report(
        excel_path=input_excel,
        output_dir=output_dir,
        report_date_range=(arguments.report_start, arguments.report_end),
        previous_excel_path=previous_excel,
        prepare_feishu_publication=publish_report,
        representative_rows=preparation.rows,
    )

    print(result.markdown_path)
    print(result.word_path)
    status: dict[str, object] = {
        "report_markdown": str(result.markdown_path),
        "report_word": str(result.word_path),
        "representative_count": len(preparation.rows),
        "warnings": list(preparation.warnings),
    }
    if feishu_config is not None:
        publication = publish_generated_report_to_feishu(result, config=feishu_config)
        status["report_feishu"] = asdict(publication)
        print(publication.native_document_url)
        if publication.editable_chart_sheet_url is not None:
            print(publication.editable_chart_sheet_url)
    if arguments.publish_all:
        sync_summary = publish_selected_representatives_to_feishu(
            selected=preparation.selection_run.selected,
            output_dir=output_dir / "representative_selection",
            settings=settings,
        )
        status["representative_feishu"] = sync_summary.as_dict()
        print(json.dumps(sync_summary.as_dict(), ensure_ascii=False))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "publication_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return 0


def _default_prompt() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "modules"
        / "analysis"
        / "prompts"
        / "zhengfu_shaixuan.md"
    )


if __name__ == "__main__":
    raise SystemExit(main())

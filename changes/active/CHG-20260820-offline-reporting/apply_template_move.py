from pathlib import Path


def replace_required(path: str, old: str, new: str, count: int = 1) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual < count:
        raise RuntimeError(
            f"{path}: expected at least {count} occurrences, found {actual}: {old!r}"
        )
    file_path.write_text(text.replace(old, new, count), encoding="utf-8")


excel_report = "backend/src/aima_ugc/platform/reporting/excel_report.py"
replace_required(
    excel_report,
    'from .markdown_word import WordConversionSummary, convert_markdown_to_docx\n\n_BEIJING = ZoneInfo("Asia/Shanghai")\n',
    'from .markdown_word import WordConversionSummary, convert_markdown_to_docx\n\nDEFAULT_REPORT_TEMPLATE_PATH = Path(__file__).with_name("report_template.md")\n\n_BEIJING = ZoneInfo("Asia/Shanghai")\n',
)
replace_required(
    excel_report,
    "    template_path: Path,\n",
    "    template_path: Path | None = None,\n",
)
replace_required(
    excel_report,
    "    template = Path(template_path)\n",
    "    template = DEFAULT_REPORT_TEMPLATE_PATH if template_path is None else Path(template_path)\n",
)

init_path = "backend/src/aima_ugc/platform/reporting/__init__.py"
replace_required(
    init_path,
    "from .excel_report import ReportGenerationSummary, generate_excel_report\n",
    "from .excel_report import (\n    DEFAULT_REPORT_TEMPLATE_PATH,\n    ReportGenerationSummary,\n    generate_excel_report,\n)\n",
)
replace_required(
    init_path,
    '__all__ = [\n    "ReportGenerationSummary",\n',
    '__all__ = [\n    "DEFAULT_REPORT_TEMPLATE_PATH",\n    "ReportGenerationSummary",\n',
)

imports_entry = "backend/src/aima_ugc/adapters/providers/imports_test/test.py"
replace_required(
    imports_entry,
    'REPORT_TEMPLATE_FILE = Path(__file__).with_name("report_template.md")\n',
    "",
)
replace_required(
    imports_entry,
    "    return generate_excel_report(\n        input_path=source_path,\n        output_dir=target_dir,\n        template_path=REPORT_TEMPLATE_FILE,\n    )\n",
    "    return generate_excel_report(\n        input_path=source_path,\n        output_dir=target_dir,\n    )\n",
)

test_path = "tests/unit/platform/test_imports_test_reporting.py"
replace_required(
    test_path,
    "from aima_ugc.platform.reporting import ReportGenerationSummary\n",
    "from aima_ugc.platform.reporting import (\n    DEFAULT_REPORT_TEMPLATE_PATH,\n    ReportGenerationSummary,\n)\n",
)
replace_required(
    test_path,
    "        template_path=imports_entry.REPORT_TEMPLATE_FILE,\n",
    "        template_path=DEFAULT_REPORT_TEMPLATE_PATH,\n",
)
replace_required(
    test_path,
    "        template_path: Path,\n",
    "        template_path: Path | None = None,\n",
)
replace_required(
    test_path,
    '        captured["template_path"] = template_path\n',
    "        assert template_path is None\n",
)
replace_required(
    test_path,
    '        "output_dir": output_dir,\n        "template_path": imports_entry.REPORT_TEMPLATE_FILE,\n',
    '        "output_dir": output_dir,\n',
)

imports_readme = "backend/src/aima_ugc/adapters/providers/imports_test/README.md"
replace_required(
    imports_readme,
    'REPORT_TEMPLATE_FILE = Path(__file__).with_name("report_template.md")\n',
    "",
)
replace_required(
    imports_readme,
    "Excel 输入只有 `INPUT_XLSX_FILES` 一个配置入口。它接受一个 `Path` 或非空的\n",
    "报告默认模板由 `aima_ugc.platform.reporting` 统一维护在\n"
    "`backend/src/aima_ugc/platform/reporting/report_template.md`，人工入口不再维护第二份模板路径。\n\n"
    "Excel 输入只有 `INPUT_XLSX_FILES` 一个配置入口。它接受一个 `Path` 或非空的\n",
)

reporting_readme = "backend/src/aima_ugc/platform/reporting/README.md"
replace_required(
    reporting_readme,
    '    template_path=Path("report_template.md"),\n',
    "",
)
replace_required(
    reporting_readme,
    "`generate_excel_report()` 只读输入 Workbook，不调用 LLM、不写 PostgreSQL，也不保存或二次格式化输入 Excel。\n",
    "`generate_excel_report()` 默认使用本目录的 `report_template.md`；调用方也可显式传入 `template_path=` 覆盖模板。函数只读输入 Workbook，不调用 LLM、不写 PostgreSQL，也不保存或二次格式化输入 Excel。\n",
)
replace_required(
    reporting_readme,
    "`imports_test/report_template.md` 是当前人工入口的默认报告模板，不属于数据库或 HTTP Contract。\n",
    "默认报告模板固定由本模块维护在 `backend/src/aima_ugc/platform/reporting/report_template.md`；`imports_test` 只复用该默认模板，不拥有第二份模板事实源。\n",
)

blueprint = "docs/blueprint/13-统一数据Excel导出与调试复用.md"
replace_required(
    blueprint,
    "它不是 `imports_test` 私有统计脚本。`imports_test` 只提供默认 Markdown 模板和人工调用入口；统计、Markdown 渲染、Word 转换和图表嵌入属于 Provider-neutral 平台能力。\n",
    "它不是 `imports_test` 私有统计脚本。默认 Markdown 模板、统计、Markdown 渲染、Word 转换和图表嵌入都属于 Provider-neutral 平台能力；`imports_test` 只提供人工调用入口。\n",
)
replace_required(
    blueprint,
    "具体人工入口模板当前为：\n\n```text\nbackend/src/aima_ugc/adapters/providers/imports_test/report_template.md\n```\n",
    "默认共享模板当前为：\n\n```text\nbackend/src/aima_ugc/platform/reporting/report_template.md\n```\n\n"
    "`generate_excel_report()` 默认使用该模板；需要特定展示时允许调用方显式传入 `template_path=`，"
    "但不能复制一套平台私有 Report Renderer。\n",
)
replace_required(
    blueprint,
    "不得把 `imports_test` 的路径、run 目录或本地模板位置提升为正式 HTTP/数据库 Contract。\n",
    "不得把 `imports_test` 的路径或 run 目录提升为正式 HTTP/数据库 Contract；共享默认模板属于 Report Renderer 自身资源。\n",
)

for obsolete in (
    "backend/src/aima_ugc/adapters/providers/imports_test/report_template.md",
    "changes/active/CHG-20260820-offline-reporting/template_red_evidence.json",
    "changes/active/CHG-20260820-offline-reporting/template_move_trigger.txt",
):
    Path(obsolete).unlink(missing_ok=True)

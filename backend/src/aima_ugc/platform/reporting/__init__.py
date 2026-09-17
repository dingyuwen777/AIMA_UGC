"""Provider-neutral 报告生成与 Markdown/Word/飞书转换。"""

from .chart_spec import ChartSpec
from .chart_workbook import ChartWorkbookSummary, build_editable_chart_workbook
from .excel_report import (
    DEFAULT_REPORT_TEMPLATE_PATH,
    ReportGenerationSummary,
    generate_excel_report,
)
from .feishu_native_document import (
    FeishuNativeBlock,
    FeishuNativeDocument,
    build_feishu_native_document,
)
from .markdown_word import (
    WordConversionSummary,
    convert_markdown_to_docx,
    extract_chart_specs,
)
from .representative_section import (
    REPRESENTATIVE_GROUP_ORDER,
    REPRESENTATIVE_TABLE_HEADERS,
    RepresentativeReportRow,
    build_representative_section,
    format_representative_labels,
    normalize_representative_content_url,
)

__all__ = [
    "DEFAULT_REPORT_TEMPLATE_PATH",
    "ChartSpec",
    "ChartWorkbookSummary",
    "FeishuNativeBlock",
    "FeishuNativeDocument",
    "ReportGenerationSummary",
    "RepresentativeReportRow",
    "REPRESENTATIVE_GROUP_ORDER",
    "REPRESENTATIVE_TABLE_HEADERS",
    "WordConversionSummary",
    "build_editable_chart_workbook",
    "build_feishu_native_document",
    "convert_markdown_to_docx",
    "extract_chart_specs",
    "generate_excel_report",
    "build_representative_section",
    "format_representative_labels",
    "normalize_representative_content_url",
]

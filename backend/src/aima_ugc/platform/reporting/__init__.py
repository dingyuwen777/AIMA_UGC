"""Provider-neutral 报告生成与 Markdown/Word 转换。"""

from .excel_report import (
    DEFAULT_REPORT_TEMPLATE_PATH,
    ReportGenerationSummary,
    generate_excel_report,
)
from .markdown_word import WordConversionSummary, convert_markdown_to_docx

__all__ = [
    "DEFAULT_REPORT_TEMPLATE_PATH",
    "ReportGenerationSummary",
    "WordConversionSummary",
    "convert_markdown_to_docx",
    "generate_excel_report",
]

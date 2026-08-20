# Provider-neutral 离线报告

本目录实现从**处理完成的统一数据 Excel**生成 Markdown / Word 报告的只读派生能力。

它不负责 Provider Raw、Canonical、Analysis 打标、数据库写入或 Excel 导出本身。

## 生产入口

```python
from pathlib import Path

from aima_ugc.platform.reporting import generate_excel_report

summary = generate_excel_report(
    input_path=Path("labeled_data.xlsx"),
    output_dir=Path("reports"),
    template_path=Path("report_template.md"),
)
```

输出：

```text
reports/report.md
reports/report.docx
```

`generate_excel_report()` 只读输入 Workbook，不调用 LLM、不写 PostgreSQL，也不保存或二次格式化输入 Excel。

## 输入约束

输入必须是当前统一 Workbook 结构：

```text
内容
标签明细
评论
```

报告当前最低读取列：

```text
内容：平台 / 发布时间 / 命中关键词 / 情感标签 / 一级标签 / 二级标签
标签明细：平台 / 情感标签 / 一级标签 / 二级标签
评论：平台
```

这些是 Report Renderer 的读取要求，不是新的 `UnifiedDataExcelV1` Contract。统一 Excel 的正式字段和共享 Exporter 仍由 `aima_ugc.platform.export` 与 Blueprint 13 维护。

## 统计口径

```text
内容总量、平台、情感、关键词、每日趋势
→ 内容 Sheet

一级/二级标签总体频次、一级→二级标签对
→ 标签明细 Sheet

评论总量、各平台评论量
→ 评论 Sheet
```

Markdown 表格保存完整统计。为了避免折线过多，部分图表只展示总体数量最高的 Top N 标签，但完整标签和每日非零明细不会被裁掉。

## Markdown 与 Word

报告正文只维护 Markdown 模板：

```text
Markdown 模板
→ 统计占位符替换
→ report.md
→ convert_markdown_to_docx()
→ report.docx
```

Word 不维护第二套正文。

Markdown 图表使用 Mermaid：

```text
pie
xychart
```

Word 转换器解析本报告使用的上述子集，并生成内嵌 PNG。未支持的 Mermaid 类型直接失败，不能静默丢图。

DOCX 生成后会重新打开并检查：

- ZIP CRC；
- 必需 OOXML 文件；
- 关键 XML 可解析；
- 内嵌图表媒体数量。

运行时不依赖 Pandoc、LibreOffice、Matplotlib、pandas、在线 Mermaid 服务或额外 Word Python 库。

## `imports_test` 如何复用

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

当前人工调试版 `run_all()` 保留最新仓库事实：AI 打标和 `labeled_data.xlsx` 导出暂时被注释，不会为了报告而静默恢复。因此报告接线按“实际文件存在才生成”处理：

```text
run_all(report_excel_path=<已处理 Excel>)
→ 使用显式 Excel 生成 reports/report.md + report.docx

run_all()
→ 如果本 run 已经存在 labeled_data.xlsx，则生成报告
→ 如果不存在，则在 run_summary.json 中把 generate_report 记为 skipped
```

也可以完全绕过 `run_all()`，只指定一个已经处理好的 Excel：

```python
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import generate_report

result = generate_report(
    excel_path=Path(r"E:\path\to\labeled_data.xlsx"),
    output_dir=Path(r"E:\path\to\reports"),
)
```

`imports_test/report_template.md` 是当前人工入口的默认报告模板，不属于数据库或 HTTP Contract。

## 自动化测试

核心报告行为：

```bash
uv run pytest tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_docx_package_structure.py -q
```

`imports_test` 接线：

```bash
uv run pytest tests/unit/platform/test_imports_test_reporting.py tests/unit/collection/test_p1g_imports_run_all.py -q
```

测试应证明：

- 统计口径正确；
- 输入 Excel Hash 在报告前后不变；
- 模板文字同时进入 Markdown 和 Word；
- DOCX ZIP/关键 OOXML/图表媒体结构可校验；
- Word 换行节点使用合法 `w:r > w:br` 层级；
- 未支持 Mermaid 类型关闭失败；
- 显式 `report_excel_path` 能生成报告，同时不恢复当前已禁用的 AI/Excel 阶段；
- 默认没有最终 Excel 时明确记录报告跳过；
- 既有多 Excel、数据库来源和 LLM 费用审计语义保持不变。

测试和当前 CI 结果才是验证事实，本 README 不替代测试断言。

## 当前限制

- 当前是离线文件报告，不是正式网页报告中心；
- 不生成新的 AI 结论，只统计已有结构化数据；
- Word 转换不是通用 Markdown/Mermaid 引擎，只支持当前报告需要的子集；
- 当前人工 `run_all()` 是否能自动获得最终 Excel，取决于调用前是否已有 `labeled_data.xlsx` 或是否显式传入 `report_excel_path`；
- 正式 Report Job、Artifact 权限/API、PostgreSQL Read Model 或 Web 页面如后续需要，必须作为对应阶段独立演进。

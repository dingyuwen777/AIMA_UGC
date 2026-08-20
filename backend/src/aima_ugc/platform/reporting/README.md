# Provider-neutral 离线报告

本目录实现从**处理完成的统一数据 Excel**生成 Markdown / Word 舆情报告的只读派生能力。

默认报告面向营销管理层和领导汇报：先给管理摘要、核心指标和风险关注，再展开平台、情感、议题、关键词与趋势，完整统计明细保留在后半部分。生成正文不暴露 Excel/Sheet/模板/转换器等实现术语，可以直接作为业务报告阅读和展示。

本模块不负责 Provider Raw、Canonical、Analysis 打标、数据库写入或 Excel 导出本身，也不调用 LLM 生成新的主观结论；管理摘要和风险摘要均由既有结构化统计确定性计算。

## 生产入口

```python
from datetime import date
from pathlib import Path

from aima_ugc.platform.reporting import generate_excel_report

summary = generate_excel_report(
    input_path=Path("labeled_data.xlsx"),
    output_dir=Path("reports"),
    report_date_range=(date(2026, 8, 13), date(2026, 8, 19)),
)
```

输出：

```text
reports/report.md
reports/report.docx
```

`report_date_range` 是可选的北京时间自然日闭区间，只限制报告统计；传 `None` 时使用 Excel
全部日期。`generate_excel_report()` 默认使用本目录的 `report_template.md`；调用方也可显式
传入 `template_path=` 覆盖模板。函数只读输入 Workbook，不调用 LLM、不写 PostgreSQL，
也不保存或二次格式化输入 Excel。

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

指定 `report_date_range` 时还要求：

```text
内容：按“发布时间”筛选
标签明细：优先按“发布时间”筛选；没有该列时要求内容页和标签明细页同时包含“内容ID”
评论：存在评论记录时按“评论时间”筛选
```

周期范围包含开始日和结束日。筛选所需日期缺失或无法解析时直接失败，不会把无法归属周期的
记录静默计入或排除。周期内“内容”和“标签明细”的记录数、平台、情感、一级/二级标签及
标签对会交叉核对，不一致时拒绝生成报告。

这些是 Report Renderer 的读取要求，不是新的 `UnifiedDataExcelV1` Contract。统一 Excel 的正式字段和共享 Exporter 仍由 `aima_ugc.platform.export` 与 Blueprint 13 维护。

## 默认管理层报告内容

默认报告至少覆盖：

```text
管理摘要
├─ 内容/评论声量
├─ 覆盖平台
├─ 负面内容量与占比
├─ 声量峰值
├─ 主要平台
├─ 首要一级/二级议题
└─ 热点关键词

舆情风险关注
├─ 负面内容平台分布
├─ 负面一级议题
└─ 负面二级议题

平台与情感
├─ 平台声量/评论量
├─ 平台 × 情感交叉对比
└─ 平台每日趋势

整体情感
├─ 情感结构
└─ 情感每日趋势

核心议题
├─ 一级议题
├─ 二级议题
├─ 一级→二级关系
└─ 每日趋势

热点关键词
完整统计明细
数据质量说明
```

完整表格保存全部平台、标签、标签对、关键词和每日非零数据。为了保持图表可读性，部分图表只展示总体数量最高的 Top N 序列，但不会裁剪完整统计表。

## Markdown 与 Word

报告正文只维护 Markdown 模板：

```text
Markdown 模板
→ 统计占位符替换
→ report.md
→ convert_markdown_to_docx()
→ report.docx
```

Word 不维护第二套正文。因此修改 `report_template.md` 的标题、正文、章节顺序或普通说明后，下次生成的 Markdown 和 Word 会一起变化；无需再单独维护一份 Word 正文代码。

Markdown 图表继续使用本报告支持的 Mermaid 子集：

```text
pie
xychart
```

### Word 图表可编辑

Word 不再把这些图表转换成静态 PNG。当前转换器会把图表写成 Office 原生 Chart，并为每张图内嵌对应的 XLSX 数据：

```text
word/charts/chartN.xml
word/embeddings/chartN.xlsx
```

因此在支持 Office Chart 编辑的 Word 中，可以选中图表并使用“编辑数据”修改分类、系列和数值；图表仍由 Office 原生引擎显示，可继续调整标题、图例、样式和布局。

Markdown 仍保留 Mermaid 源码，Word 只负责把当前支持的 pie/bar/line 语义转换为可编辑 Office Chart。未支持的 Mermaid 类型必须直接失败，不能静默丢图。

DOCX 生成后会重新打开并检查：

- ZIP CRC；
- 必需 OOXML 文件；
- 关键 XML 可解析；
- Office Chart 数量；
- 每张 Chart 的 Relationship；
- 每张图内嵌 XLSX 数据包可正常打开。

运行时不依赖 Pandoc、LibreOffice、Matplotlib、pandas、在线 Mermaid 服务或额外 Word Python 库；内嵌图表数据复用仓库已锁定的 openpyxl。

不同 Office/LibreOffice 版本对主题颜色、字体和分页可能存在轻微视觉差异，因此交付前仍应按目标办公软件做最终视觉抽查；结构测试不能替代所有桌面端渲染差异。

## `imports_test` 如何复用

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

当前 `run_all()` 完整人工链路为：

```text
convert
→ filter_keywords
→ deduplicate
→ 可选 database_ingestion
→ label_sentiment
→ export_labeled_excel
→ generate_report
```

默认报告读取本次 run 的：

```text
labeled_data.xlsx
```

并生成：

```text
reports/report.md
reports/report.docx
```

`run_all(report_excel_path=...)` 可以显式覆盖报告输入 Excel；但如果只是对一个已经处理好的 Excel 出报告，更直接的方式是绕过前序处理：

```python
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import generate_report

result = generate_report(
    excel_path=Path(r"E:\path\to\labeled_data.xlsx"),
    output_dir=Path(r"E:\path\to\reports"),
    report_date_range=(date(2026, 8, 13), date(2026, 8, 19)),
)
```

默认报告模板固定由本模块维护在 `backend/src/aima_ugc/platform/reporting/report_template.md`；`imports_test` 只复用该默认模板，不拥有第二份模板事实源。

## 自动化测试

核心报告行为：

```bash
uv run pytest tests/unit/platform/test_offline_reporting.py tests/unit/platform/test_docx_package_structure.py tests/unit/platform/test_reporting_default_template.py -q
```

`imports_test` 接线：

```bash
uv run pytest tests/unit/platform/test_imports_test_reporting.py tests/unit/collection/test_p1g_imports_run_all.py -q
```

测试应证明：

- 默认正文适合管理层直接阅读，不泄漏实现术语；
- 管理摘要、平台×情感与负面风险统计正确；
- 输入 Excel Hash 在报告前后不变；
- 模板文字同时进入 Markdown 和 Word；
- DOCX ZIP/关键 OOXML/Office Chart/内嵌 XLSX 结构可校验；
- 图表系列名称和数值进入内嵌数据工作簿；
- Word 换行节点使用合法 `w:r > w:br` 层级；
- 未支持 Mermaid 类型关闭失败；
- `run_all()` 在最终 Excel 后追加报告阶段；
- 显式 `report_excel_path` 能覆盖报告输入；
- 既有多 Excel、数据库来源和 LLM 费用审计语义保持不变。

测试和当前 CI 结果才是验证事实，本 README 不替代测试断言。

## 当前限制

- 当前是离线文件报告，不是正式网页报告中心；
- 不生成新的 AI 结论，只统计已有结构化数据；
- Word 转换不是通用 Markdown/Mermaid/Office Chart 引擎，只支持当前报告需要的子集；
- 正式 Report Job、Artifact 权限/API、PostgreSQL Read Model 或 Web 页面如后续需要，必须作为对应阶段独立演进。

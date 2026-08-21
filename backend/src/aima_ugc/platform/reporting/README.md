# Provider-neutral 离线报告

本目录实现从**处理完成的统一数据 Excel**生成 Markdown / Word 舆情报告的只读派生能力。

默认报告面向营销管理层和领导汇报：先给管理摘要、核心指标和正负面舆情重点关注，再展开平台、情感、议题、关键词与趋势，完整统计明细保留在后半部分。生成正文不暴露 Excel/Sheet/模板/转换器等实现术语，可以直接作为业务报告阅读和展示。

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
reports/assets/primary_topics_wordcloud.png
reports/assets/keyword_wordcloud.png
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
├─ 正面/中性/负面内容量与占比
├─ 声量峰值
├─ 主要平台
├─ 首要一级/二级议题
└─ 热点关键词

舆情重点关注
├─ 客观情感概览
├─ 正面内容平台/一级议题/二级议题
└─ 负面内容平台/一级议题/二级议题

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

报告读取到已知平台 ID 时统一使用中文展示名：`xiaohongshu`、`douyin`、`weibo`、
`bilibili`、`kuaishou` 分别展示为“小红书”“抖音”“微博”“哔哩哔哩”“快手”。
输入已经是中文时保持中文；未知平台保持原值，避免新平台在展示映射更新前丢失。该投影只影响
Markdown、Word 表格和图表文字，不修改输入 Excel 或底层稳定平台 ID。

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
xychart-beta
```

生成器使用 `xychart-beta`，以兼容当前目标 Markdown 阅读器；Word 转换器同时接受
`xychart-beta` 和历史 `xychart` 输入，因此已有报告仍可继续转换。

### Word 图表可编辑

Word 不再把这些图表转换成静态 PNG。当前转换器会把图表写成 Office 原生 Chart，并为每张图内嵌对应的 XLSX 数据：

```text
word/charts/chartN.xml
word/embeddings/chartN.xlsx
```

因此在支持 Office Chart 编辑的 Word 中，可以选中图表并使用“编辑数据”修改分类、系列和数值；图表仍由 Office 原生引擎显示，可继续调整标题、图例、样式和布局。

当前 Word 使用 A4 横向页面和约 15 mm 页边距。普通数据表保持白底、浅表头、轻横向分隔、
数值右对齐和重复表头；面向领导阅读的 Top 统计不再把全部条目逐项拉成长进度条，而是使用
“Top 重点 Ranking + 对应图表/词云 + 其余完整紧凑明细”的两层表达。Top Ranking 的排名、
标签、数量、占比和细比例条都是 Word 原生 OOXML，可继续编辑；其余完整条目采用双列紧凑
明细，数据没有裁剪。

一级议题使用一个横向组合区域：上方是标签对总量、一级议题数和 Top1 占比三个克制 KPI，
下方左侧是一级议题 Ranking，右侧是词云。这里不加入图标、奖牌、星标或逐行小饼图/圆环图；
Top1 只通过字重和主强调蓝轻度突出。平台分布和情感结构这类窄表可以与对应 Office Chart
并排；平台 × 情感等宽矩阵仍使用完整横向表格后接图表，避免把多列数据硬塞进半页宽度。

柱状图/折线图继续使用 Office 原生 Chart + 内嵌 XLSX，并显示数据标签；长分类使用横向条形图。
多系列每日趋势按可读性分层：情感趋势继续拆为正面/中性主趋势和负面/混合低量级趋势；平台、
一级议题和二级议题趋势在系列较多时把最高声量主序列单独展示，其余每组最多四个系列，避免
单张图中几十个数值标签重叠。所有分层图仍来自同一统计结果、使用绝对数量，不使用双 Y 轴，
并保持内嵌 XLSX 可编辑能力。

完整每日明细在 `report.md` 中仍保留日期/维度/数量长表，Word 展示层利用横向 A4 宽度把它们
透视为按日期为行、维度为列的紧凑矩阵；维度过多时每组最多五列分块展示。因此 Markdown 的
完整数据语义不变，Word 只优化信息密度和扫读效率。

Markdown 仍保留 Mermaid 源码，Word 只负责把当前支持的 pie/bar/line 语义转换为可编辑 Office Chart。未支持的 Mermaid 类型必须直接失败，不能静默丢图。

DOCX 生成后会重新打开并检查：

- ZIP CRC；
- 必需 OOXML 文件；
- 关键 XML 可解析；
- Office Chart 数量；
- 每张 Chart 的 Relationship；
- 每张图内嵌 XLSX 数据包可正常打开；
- PNG 图片可重新打开且 Relationship 不悬空。

词云继续直接消费同一份报告 Counter，不建立第二套统计。当前实现采用 Pillow 自定义
Editorial Word Cloud，而不是默认随机词云：最多取 36 个词，使用 sqrt 频次权重并进一步温和
压缩字号差异；所有词保持水平，第一名可使用系统 CJK 粗体，主体使用海军蓝、主蓝、青绿、柔紫
和蓝灰，只有少数次级词使用低饱和赭色点缀。布局从视觉中心向外寻找最近空位，完成后再按实际
字形边界裁切并受限放大回 1600×900 画布，所以只有 4–9 个词时也不会缩成中央的一小团，词很多
时又保留必要的呼吸感。布局完全确定性，不使用图形 mask、随机旋转、阴影、图标或彩虹配色。

词云以约 300 DPI PNG 打包到 `word/media/`，因此 Word 中不可通过“编辑数据”重新布局词云；
精确数量仍由旁边的原生 Ranking 保留，下一次重新生成报告时词云会根据新的 Counter 自动更新。
运行环境必须提供可用 CJK 字体：Windows 优先微软雅黑，Linux 优先 Noto Sans CJK /
Source Han Sans，也可通过 `AIMA_REPORT_CJK_FONT` 指向现有字体；缺失时明确失败。当前实现不依赖
Pandoc、LibreOffice、Matplotlib、pandas、`wordcloud` 库、在线 Mermaid 服务或 `python-docx`；
内嵌图表数据继续复用 openpyxl。

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
reports/assets/primary_topics_wordcloud.png
reports/assets/keyword_wordcloud.png
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
- 管理摘要、平台×情感与正负面重点关注统计正确；
- 输入 Excel Hash 在报告前后不变；
- 模板文字同时进入 Markdown 和 Word；
- DOCX ZIP/关键 OOXML/Office Chart/内嵌 XLSX 结构可校验；
- 图表系列名称和数值进入内嵌数据工作簿；
- 已知英文平台 ID 在 Excel、Markdown、Word 和图表中统一显示中文，未知平台保持原值；
- Word 为 A4 横向，Editorial Table、KPI、Top Ranking、紧凑完整明细和组合布局分层明确；
- bar/line 有数据标签，长分类为横向条形图，分层趋势仍保持 Office Chart + 内嵌 XLSX；
- Markdown 完整每日长表与 Word 紧凑矩阵包含相同的日期、维度和数值；
- 一级议题与热点关键词词云来自对应统计 Counter，稀疏/稠密样例均保持确定性、合理视觉密度，PNG 可重开且正确打包到 `word/media/`；
- Word 换行节点使用合法 `w:r > w:br` 层级；
- 未支持 Mermaid / AIMA 展示元数据关闭失败；
- `run_all()` 在最终 Excel 后追加报告阶段；
- 显式 `report_excel_path` 能覆盖报告输入；
- 既有多 Excel、数据库来源和 LLM 费用审计语义保持不变。

测试和当前 CI 结果才是验证事实，本 README 不替代测试断言。

## 当前限制

- 当前是离线文件报告，不是正式网页报告中心；
- 不生成新的 AI 结论，只统计已有结构化数据；
- Word 转换不是通用 Markdown/Mermaid/Office Chart 引擎，只支持当前报告需要的子集；
- 正式 Report Job、Artifact 权限/API、PostgreSQL Read Model 或 Web 页面如后续需要，必须作为对应阶段独立演进。

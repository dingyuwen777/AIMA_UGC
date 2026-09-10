# Provider-neutral 离线舆情报告

本目录实现从**处理完成的统一数据 Excel**生成 Markdown / Word 舆情报告的只读派生能力。

它和 `modules/reporting/` 的正式 PostgreSQL Excel Export 不是同一件事：

```text
modules/reporting/
→ 正式 data export HTTP / Job / PostgreSQL
→ 产出统一数据明细 XLSX

platform/reporting/
→ 读取已经生成好的统一 XLSX
→ 计算报告统计
→ 生成 report.md
→ 生成模板式纵向 A4 report.docx
```

详细专题说明见：

[`../../../../../docs/appendix/10_Word舆情报告生成与排版实现.md`](../../../../../docs/appendix/10_Word舆情报告生成与排版实现.md)

统一数据 Excel 规则见：

[`../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md`](../../../../../docs/appendix/06_Excel统一数据导出与离线调试.md)

---

## 1. 先看代码地图

| 文件 | 当前职责 | 想改什么时先看 |
| --- | --- | --- |
| `excel_report.py` | 读取统一 Workbook、筛选日期、统计平台/情感/议题/关键词、构造 Report Context | 统计口径、报告数据来源、日期筛选 |
| `report_template.md` | Markdown 正文唯一模板 | 标题、章节顺序、说明文字 |
| `markdown_word.py` | 解析当前支持的 Markdown/展示元数据并驱动 Word | Markdown → DOCX 转换规则 |
| `visual_docx.py` | A4 纵向页面、Ranking、表格、组合布局、词云等视觉组件 | Word 排版、页面密度、字号/间距 |
| `chart_spec.py` | 从 Mermaid/报告数据形成 Office Chart 规格 | bar/line/pie 语义、系列分组 |
| `chart_png.py` | 需要静态位图的确定性视觉资产 | 词云/飞书图表 PNG 生成边界 |
| `feishu_native_document.py` | 把当前报告 Markdown 投影为顺序化的正文、原生表格、图表和图片块 | 飞书正文/表格/图表的内容位置 |
| `docx_package.py` | OOXML Chart、关系、内嵌 XLSX、ZIP 包装与结构校验 | Office Chart/OOXML/嵌入工作簿 |
| `__init__.py` | 对外导出 `generate_excel_report` 等稳定入口 | 调用方入口 |

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/generate_report.py
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

如果只是改 Word 视觉，通常不应该修改 Canonical、Content Ingestion、AI Prompt 或 PostgreSQL Schema。

---

## 2. 生产入口

```python
from datetime import date
from pathlib import Path

from aima_ugc.platform.reporting import generate_excel_report

summary = generate_excel_report(
    input_path=Path("labeled_data.xlsx"),
    output_dir=Path("reports"),
    report_date_range=(date(2026, 8, 13), date(2026, 8, 19)),
    previous_input_path=Path("previous_labeled_data.xlsx"),
)
```

输出：

```text
reports/report.md
reports/report.docx
reports/assets/primary_topics_wordcloud.png
reports/assets/keyword_wordcloud.png
```

`report_date_range` 是可选的北京时间自然日闭区间，只限制报告统计；传 `None` 时使用 Excel 全部日期。传入 `previous_input_path` 时必须同时指定本期 `report_date_range`：报告会从上期 Workbook 读取与本期等长、紧邻本期的上一周期，并自动生成 1.3 的结论和“指标 / 本期 / 上期 / 变化情况”表。未传上期输入时，1.3 会明确标识暂无可比数据。`generate_excel_report()` 默认使用本目录的 `report_template.md`；调用方也可显式传入 `template_path=` 覆盖模板。

该函数：

- 只读输入 Workbook；
- 不调用 LLM；
- 不写 PostgreSQL；
- 不反向修改输入 Excel；
- 不创建第二套 Content/Analysis 事实。

---

## 3. 输入约束

输入必须是当前统一 Workbook：

```text
内容
标签明细
评论
```

当前报告最低读取列：

```text
内容：平台 / 发布时间 / 命中关键词 / 情感标签 / 一级标签 / 二级标签
标签明细：平台 / 情感标签 / 一级标签 / 二级标签
评论：平台
```

指定 `report_date_range` 时还要求：

```text
内容：按“发布时间”筛选
标签明细：优先按“发布时间”筛选；没有该列时要求内容页和标签明细页同时有“内容ID”
评论：存在评论记录时按“评论时间”筛选
```

周期包含开始日和结束日。筛选所需日期缺失或无法解析时直接失败，不会把无法归属周期的记录静默计入或排除。

周期内“内容”和“标签明细”的记录数、平台、情感、一级/二级标签及标签对会交叉核对，不一致时拒绝生成报告。

这些是 Report Renderer 的读取要求，不是新的 `UnifiedDataExcelV1` Contract；统一 Excel 的机器/共享实现仍看：

```text
backend/src/aima_ugc/contracts/export.py
backend/src/aima_ugc/platform/export/excel.py
```

---

## 4. 数据如何变成报告

完整链路：

```text
统一 Excel
→ excel_report.py
   ├─ 读取 3 个 Sheet
   ├─ 日期筛选
   ├─ 数据一致性校验
   ├─ 平台统计
   ├─ 情感统计
   ├─ 一级/二级标签统计
   ├─ 标签对统计
   ├─ 关键词统计
   └─ 日趋势统计
→ Report Context
→ report_template.md 占位符替换
→ report.md
→ markdown_word.py
→ visual_docx.py / chart_spec.py / docx_package.py
→ report.docx
```

词云直接消费同一 Report Context Counter；不会重新扫描 Excel 建第二套统计。

---

## 5. 默认管理层报告内容

默认报告至少覆盖：

```text
总体概况
├─ 内容声量、覆盖平台、正面/中性/负面内容量与占比
├─ 平台每日明细
├─ 每日舆情声量走势
└─ 与上周期对比的自动结论与指标对比表（提供上期统一 Excel 时）

平台声量与情感结构
├─ 平台声量/评论量
├─ 平台 × 情感纵向分组柱状图
└─ 平台每日趋势（抖音单图、其他平台合图）

情感表现
├─ 情感结构
├─ 情感每日趋势（正面/中性、负面/混合分图）
├─ 正面一级/二级议题横向排名图
└─ 负面一级/二级议题横向排名图

核心议题
├─ 一级议题
├─ 二级议题
├─ 一级议题词云
└─ 二级议题词云

热点关键词
```

报告中的情感统计（正面、中性、负面及混合）只纳入“发声类型”为“真实用户发声”的内容；内容总量、平台声量、关键词和整体议题统计仍保留全部内容。情感占比以周期内真实用户发声内容为分母。

提供 `previous_input_path` 后，“与上周期对比”会比较总声量、正面率、负面率、五个平台声量和正/负面 TOP1 一级议题，并输出自动结论和固定对比表。上期范围始终是与本期等长且紧邻的自然日区间；未提供上期输入时，不猜测历史数据。模板中的示例数字和批注不进入报告。图表与词云继续只消费同一 Report Context，不重新统计输入 Excel。

已知平台 ID 的中文投影：

```text
xiaohongshu → 小红书
douyin      → 抖音
weibo       → 微博
bilibili    → 哔哩哔哩
kuaishou    → 快手
```

输入已经是中文时保持中文；未知平台保留原值。这个映射只影响展示，不修改输入数据身份。

---

## 6. Markdown 为什么是正文唯一模板

```text
report_template.md
→ 统计占位符替换
→ report.md
→ convert_markdown_to_docx()
→ report.docx
```

Word 不维护第二套正文。

因此如果要改：

- 章节标题；
- 说明文字；
- 章节顺序；
- 管理摘要措辞；

优先改：

```text
report_template.md
```

而不是在 `visual_docx.py` 再写一套正文字符串。

---

## 7. Markdown 图表与 Word Office Chart

Markdown 当前使用支持子集：

```text
pie
xychart-beta
```

Word 转换器还兼容历史 `xychart` 输入。

Word 不把柱状图/折线图/饼图都转成 PNG，而是写 Office 原生 Chart，并为每张图嵌入对应 XLSX：

```text
word/charts/chartN.xml
word/embeddings/chartN.xlsx
```

因此在支持 Office Chart 编辑的 Word 中可以继续：

- 编辑数据；
- 调整标题；
- 调整图例；
- 修改样式/布局。

精确 OOXML 打包实现：

```text
docx_package.py
```

图表规格：

```text
chart_spec.py
```

未支持的 Mermaid 类型必须直接失败，不能静默丢图。

---

## 8. 当前 Word 版式

当前 Word 是：

```text
A4 纵向
上下约 20 mm、左右约 25 mm 页边距
```

普通数据表：

- 白底；
- 浅表头；
- 轻横向分隔；
- 数值右对齐；
- 重复表头。

纵向页中的一级、二级议题和关键词 Top 数据采用左右并排的紧凑表达：

```text
Top 重点 Ranking
+ 对应图表/词云
```

不是把几十个条目全部拉成长进度条。

平台分布、情感结构等短表与图表并排；一级、二级议题和关键词采用左侧紧凑 Top Ranking、右侧词云，不显示进度条。正面/负面一级、二级议题不再配套表格，均为单张带数据标签的横向 Office 排名图：类别标签包含排名和占比，柱端显示数量，并从上到下按数量递减。Word 通过反转图表内嵌工作簿中的横向排名行序保持原生类别轴，避免反转坐标轴造成标签错位；因此类别、条形和柱端数值逐行对齐，数值横轴固定在图底部。

这些视觉实现主要在：

```text
visual_docx.py
```

---

## 9. 每日趋势为何按固定组别分图

模板要求每日走势按固定可读组别呈现：

- 平台：`抖音平台每日内容量` 与 `其他平台每日内容量`；
- 情感：`正面、中性每日趋势` 与 `负面、混合每日趋势`；
- 每图使用对应组内的绝对数量；
- 显示具体数据标签；
- 不使用双 Y 轴；
- 每张图都保留可编辑的 Office Chart 与内嵌 XLSX。

平台、情感趋势和议题排名都继续消费同一 Report Context，不会因拆图另建统计口径。

---

## 10. 词云如何生成

词云直接消费报告 Counter，不建立第二套统计。

当前实现是确定性的 Pillow Editorial Word Cloud：

- 最多 36 个词；
- `sqrt` 频次权重；
- 进一步压缩字号差异；
- 所有词水平；
- 从视觉中心向外寻找最近空位；
- 按真实字形边界碰撞；
- 最终裁切并放大回 1600×900；
- 约 300 DPI PNG；
- 不使用随机旋转、图形 mask、阴影、图标和彩虹配色。

4–9 个词的稀疏场景也会重新利用画布，不缩成中央很小一团。

运行环境必须有 CJK 字体：

```text
Windows：优先微软雅黑
Linux：优先 Noto Sans CJK / Source Han Sans
```

也可以通过：

```text
AIMA_REPORT_CJK_FONT
```

指定现有字体路径。缺失时明确失败。

---

## 11. DOCX 生成后怎样自检

生成后不是只看文件是否存在，还会重新打开并检查：

- ZIP CRC；
- 必需 OOXML 文件；
- 关键 XML 可解析；
- Office Chart 数量；
- Chart Relationship；
- 每张图内嵌 XLSX 能打开；
- PNG 能重新打开；
- 图片 Relationship 不悬空。

结构验证主要由：

```text
docx_package.py
相关 unit tests
```

完成。

但不同 Office/LibreOffice 版本仍可能出现字体、主题色、分页细节差异，所以正式视觉交付需要目标办公软件抽查；结构测试不能替代所有渲染差异。

---

## 12. `imports_test` 如何复用

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

当前 `run_all()` 人工链：

```text
convert
→ filter_keywords
→ deduplicate
→ 可选 database_ingestion
→ label_sentiment
→ export_labeled_excel
→ generate_report
```

默认报告读取：

```text
labeled_data.xlsx
```

生成：

```text
reports/report.md
reports/report.docx
reports/assets/primary_topics_wordcloud.png
reports/assets/keyword_wordcloud.png
```

只对已经处理好的 Excel 出报告时，直接调用：

```python
from datetime import date
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.test import generate_report

result = generate_report(
    excel_path=Path(r"E:\path\to\labeled_data.xlsx"),
    output_dir=Path(r"E:\path\to\reports"),
    report_date_range=(date(2026, 8, 13), date(2026, 8, 19)),
)
```

`imports_test` 不拥有第二份 Report Template。

---

## 13. 修改不同问题应该改哪里

### 改统计口径

```text
excel_report.py
→ 对应统计 unit test
→ report_template.md（如果展示字段变化）
```

不要先改 Word OOXML。

### 改报告正文

```text
report_template.md
→ default template test
→ Markdown / Word 一致性 test
```

### 改页面布局/Ranking/KPI

```text
visual_docx.py
→ reporting/docx layout tests
→ 真实 DOCX 视觉抽查
```

### 改 Office Chart

```text
chart_spec.py
→ docx_package.py
→ chart structure tests
→ 内嵌 XLSX 校验
```

### 改词云

```text
chart_png.py / 对应词云实现
→ 稀疏/稠密 fixture test
→ PNG reopen
→ DOCX media relationship test
```

### 改 Excel 输入字段

先判断是不是统一 Excel Contract 变化：

```text
backend/src/aima_ugc/contracts/export.py
backend/src/aima_ugc/platform/export/excel.py
```

如果是，只改 Report Reader 会造成正式 Export 和 Report 语义分叉。

---

## 14. 自动化测试

核心：

```bash
uv run pytest \
  tests/unit/platform/test_offline_reporting.py \
  tests/unit/platform/test_docx_package_structure.py \
  tests/unit/platform/test_reporting_default_template.py -q
```

`imports_test` 接线：

```bash
uv run pytest \
  tests/unit/platform/test_imports_test_reporting.py \
  tests/unit/collection/test_p1g_imports_run_all.py -q
```

测试重点包括：

- 总体概况/平台×情感/正负面议题统计正确；
- 输入 Excel Hash 不变化；
- 模板文字同时进入 Markdown 与 Word；
- DOCX ZIP/OOXML/Office Chart/嵌入 XLSX 正确；
- 平台中文映射一致；
- A4 纵向、上期对比区、Ranking 与词云/图表组合布局；
- 图表系列和数据标签；
- Markdown 与 Word 保持模板章节、统计数据和图表语义一致；
- 稀疏/稠密词云确定性和可打开；
- 不支持的 Mermaid/展示元数据关闭失败；
- `run_all()` 接线不破坏既有 Excel/数据库/LLM 语义。

---

## 15. 当前限制

- 当前是离线文件报告，不是正式网页报告中心；
- 不生成新的 AI 结论，只统计已有结构化数据；
- Word 转换只支持当前报告需要的 Markdown/Mermaid/Office Chart 子集，不是通用转换引擎；
- 当前没有正式 Report Job、Report PostgreSQL Read Model 或 Report Web 页面；
- 正式 Excel Data Export 由 `modules/reporting/` 负责，不应和本目录混为一个 Owner。

---

## 16. 飞书双产物发布

飞书接入不改变本目录的正文与统计 Owner。发布时不再导入 DOCX 来生成在线文档，而是直接用飞书原生块重建正文和表格：

```text
统一 Excel
→ report.md（内部正文结构源，不交给用户）
→ report.docx（原始下载件，Office Chart 保持不变）
→ adapters/feishu/report_publisher.py
   ├─ 上传原始 DOCX：飞书文件夹内下载
   ├─ 创建空白飞书原生文档
   ├─ report.md → 正文块 / 标题块 / 原生表格单元格 / 图片块
   └─ ChartSpec → 高清静态 PNG 图表
```

`feishu_native_document.py` 只消费 `report.md`、本地图片资产和已有 `ChartSpec`，也不重新读取 Excel。标记为
`table-style=compact-daily` 的三列日期/维度/数量明细会按 Word 相同的首见顺序透视为“日期 × 维度”原生表格；每张表最多五个维度，避免在线文档列过窄。
飞书文档保持 Markdown 中的章节、表格和图表顺序；Word 的并排版式在飞书中会顺序展示为“表格后接图”，不承诺像素级分页一致。

报告图表和词云在飞书文档中是高清 PNG。启用飞书发布时，会用本地临时生成的 `report-charts.xlsx` 导入飞书原生“可编辑图表”Sheet，并在每张图下提供对应的数据编辑入口；用户改完 Sheet 后截图并手动替换在线报告中的图片。当前不生成同步清单、不同步按钮，也不会影响原始 Word。该 XLSX 仅作导入输入，不是用户交付物。

发布器上传原始 DOCX 时直接使用本地文件字节并记录 SHA-256；原始 Word 不会被飞书文档修改覆盖。默认报告生成始终只产生 Markdown 和 Word；显式开启飞书发布时才生成并在发布成功后清理本地临时图表 XLSX，同时发起飞书发布请求。

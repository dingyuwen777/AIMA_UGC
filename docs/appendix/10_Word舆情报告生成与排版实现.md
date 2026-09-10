# Word 舆情报告生成与排版实现

本文用于真正理解和修改当前离线报告链：一份已经处理完成的统一 Excel 怎样经过统计、Markdown 模板、Office Chart、词云和 OOXML 打包，最终生成 `report.md + report.docx`。

先区分两个 Reporting 能力：

```text
正式数据库 Excel Export
→ backend/src/aima_ugc/modules/reporting/
→ PostgreSQL + Job
→ 产出统一数据明细 XLSX

本文的离线 Word Report
→ backend/src/aima_ugc/platform/reporting/
→ 读取统一 XLSX
→ 产出 Markdown + DOCX
```

当前 Word Report **不直接查 PostgreSQL、不创建正式 Job、不再次调用 LLM**。

---

# 1. 一张图看懂当前实现

```text
统一数据 Excel
├─ 内容
├─ 标签明细
└─ 评论
        │
        ▼
excel_report.py
├─ 日期范围过滤
├─ 输入一致性校验
├─ 平台统计
├─ 情感统计
├─ 一级/二级议题统计
├─ 标签对统计
├─ 关键词统计
└─ 每日趋势统计
        │
        ▼
Report Context
   ├───────────────┐
   │               │
   ▼               ▼
report_template.md  词云/图表规格
   │               │
   ▼               │
report.md           │
   │               │
   └──────┬────────┘
          ▼
markdown_word.py
→ visual_docx.py
→ chart_spec.py
→ chart_png.py
→ docx_package.py
          │
          ▼
report.docx
```

核心原则：

> Markdown、Word、图表、KPI、词云都消费同一份统计上下文；不能各自重新算一遍数据。

---

# 2. 代码地图：想改什么先打开哪个文件

| 你想改的东西 | 主要文件 | 不应该先改哪里 |
| --- | --- | --- |
| 平台/情感/标签/关键词统计口径 | `excel_report.py` | `visual_docx.py` |
| 报告章节、标题、正文说明 | `report_template.md` | Python 里硬编码第二套正文 |
| Markdown → Word 解析规则 | `markdown_word.py` | 数据库/AI |
| A4 纵向、Ranking、表格、组合布局 | `visual_docx.py` | Excel Reader |
| 图表语义/系列规格 | `chart_spec.py` | TikHub Mapper |
| 词云/静态 PNG | `chart_png.py` | Office Chart XML |
| Office Chart、关系、嵌入 XLSX、OOXML ZIP | `docx_package.py` | 报告统计逻辑 |
| 人工执行入口 | `adapters/providers/imports_test/generate_report.py` | 新写一套 Renderer |

目录：

```text
backend/src/aima_ugc/platform/reporting/
```

模块 README：

[`../../backend/src/aima_ugc/platform/reporting/README.md`](../../backend/src/aima_ugc/platform/reporting/README.md)

---

# 3. 当前生产函数怎样调用

对外入口由：

```text
backend/src/aima_ugc/platform/reporting/__init__.py
```

导出。

典型调用：

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

默认产物：

```text
reports/
├─ report.md
├─ report.docx
└─ assets/
   ├─ primary_topics_wordcloud.png
   └─ keyword_wordcloud.png
```

如果不传 `report_date_range`：

```text
使用输入 Excel 全部可解析数据
```

如果传入：

```text
(start_date, end_date)
```

按 `Asia/Shanghai` 自然日闭区间统计。

---

# 4. 输入 Excel 必须是什么

报告消费当前统一 Workbook：

```text
内容
标签明细
评论
```

统一 Excel 具体定义：

[`06_Excel统一数据导出与离线调试.md`](06_Excel统一数据导出与离线调试.md)

机器实现：

```text
backend/src/aima_ugc/contracts/export/models.py
backend/src/aima_ugc/platform/export/excel.py
```

报告最低需要的业务信息包括：

```text
内容
→ 平台
→ 发布时间
→ 命中关键词
→ 情感标签
→ 一级标签
→ 二级标签

标签明细
→ 平台
→ 情感标签
→ 一级标签
→ 二级标签

评论
→ 平台
```

日期范围筛选时还需要可可靠定位日期：

```text
内容 → 发布时间
评论 → 评论时间
标签明细 → 优先自己的发布时间；否则通过内容ID关联到内容日期
```

如果无法可靠判断某条数据是否属于报告周期，当前逻辑 fail closed，不偷偷把它算进去或丢掉。

---

# 5. 为什么会做跨 Sheet 一致性校验

统一 Workbook 三张 Sheet 表达的是同一批业务事实的不同视图。

如果：

```text
内容 Sheet：100 条
标签明细：只对应 90 条内容
```

或者平台/情感/标签关系对不上，继续生成报告会导致：

```text
KPI 一套数字
图表另一套数字
明细又第三套数字
```

所以 `excel_report.py` 会在统计前做一致性校验。

这类失败不是“Word Renderer 太严格”，而是输入派生视图已经不一致，应先修上游 Export/数据。

---

# 6. 统计事实在哪里形成

统计集中在：

```text
excel_report.py
```

报告 Context 会集中形成：

```text
内容总量
评论总量
平台分布
情感分布
平台 × 情感
一级议题
二级议题
一级→二级标签对
关键词
每日平台趋势
每日情感趋势
每日议题趋势
正面/负面重点
```

Word 不应该重新打开 Excel 再算一次。

词云也不应该自己重新遍历 Workbook；它只消费 Context 中已经计算好的 Counter。

这样可以保证：

```text
管理摘要 = 120
表格 = 120
图表 = 120
词云频次来源 = 同一份统计
```

---

# 7. Markdown 为什么是正文结构事实源

默认模板：

```text
backend/src/aima_ugc/platform/reporting/report_template.md
```

流程：

```text
统计 Context
→ 替换模板占位符
→ report.md
→ Word 转换
```

如果要改：

- 报告标题；
- 章节顺序；
- 总体概况和上期对比区文案；
- 某个图表或词云的章节位置；
- 某个章节解释文字；

优先修改：

```text
report_template.md
```

为什么不把正文写死在 Python：

- 文案和视觉逻辑分离；
- 维护章节结构不需要碰 OOXML；
- `report.md` 和 `report.docx` 不会各有一套正文。

Python Renderer 只负责把 Markdown 中的结构转成专业 Word 展示，并插入 Markdown 本身不擅长表达的 Office Chart/Ranking/词云。

---

# 8. `report.md` 和 `report.docx` 是否必须一模一样

**统计事实必须一致，视觉投影可以不同。**

例如正面二级议题：

```text
report.md / report.docx
→ 仅输出一张 Top 8 横向排名图
→ 类别标签显示排名、议题和占比
→ 柱端数据标签显示数量
→ 从上到下按数量递减
```

允许：

- Word 把 Top N 重点视觉化；
- Word 按模板指定的组别拆分平台和情感趋势图。

不允许：

- Word 和 Markdown 用不同统计逻辑；
- 图表只画“看起来好看的数字”而非 Context。

---

# 9. Word 当前为什么使用模板式 A4 纵向

当前报告目标：

```text
领导阅读
模板式纵向阅读
飞书上传预览
正式汇报
单页的重点摘要和图表
```

因此 Word 使用：

```text
A4 纵向
上下约 20 mm、左右约 25 mm 页边距
```

真实页面设置实现：

```text
visual_docx.py
```

纵向布局通过更紧凑的两列组合满足：

- 核心指标和平台每日明细；
- 平台 × 情感矩阵；
- 左 Ranking + 右词云；
- 抖音/其他平台、正面中性/负面混合的固定分组趋势；
- 重点 Top 分布。

模板中的“与上周期对比”在提供 `previous_input_path` 时消费上期统一 Excel：它按本期日期范围计算等长、紧邻的上一周期，输出结论和“指标 / 本期 / 上期 / 变化情况”表。未提供上期输入时明确显示暂无可比数据，不猜测历史结果。模板批注、示例数值和“缺失”说明不出现在最终报告。

---

# 10. KPI / Ranking 为什么不是默认 Excel 风格

领导阅读需要先看到：

```text
发生了多少？
最主要的是什么？
正负面结构怎样？
哪天峰值？
```

所以当前 Word 有：

- KPI 数字；
- Top Ranking；
- 简洁统计表；
- 重点图表；
- 词云。

不是所有数据都做成彩色卡片，也不是每行做一个小饼图。

`visual_docx.py` 负责这些组件。

典型一级议题页：

```text
上方
→ 总量 / 一级议题数 / Top1 占比 KPI

下方左
→ 一级议题 Ranking

下方右
→ 一级议题词云
```

正面/负面一级、二级议题则直接使用单张横向排名图，不再在报告中输出配套表格或“完整明细”区域；横向图按数量从上到下递减。为避免 Word 在反转类别坐标轴时将类别文字错位、横轴移到图顶，渲染器仅在横向排名图的内嵌工作簿与 Chart XML 中反转行序，仍使用 Word 原生类别轴：类别文字、条形和柱端数量逐行对齐，数值横轴固定在图底部。一级、二级议题与关键词的 Ranking/词云组合只保留紧凑的文字排名，不附加进度条；原始统计仍由同一 Excel Report Context 计算。

---

# 11. 为什么平台和情感趋势按固定组别分图

用户已确认以下固定分图方式，因此当前渲染器：

- 抖音单独生成 `抖音平台每日内容量`，其余平台生成 `其他平台每日内容量`；
- 正面、中性生成 `正面、中性每日趋势`，负面、混合生成 `负面、混合每日趋势`；
- 显示数值标签；
- 每个组使用绝对数量和单一 Y 轴；
- 每张图保留一个可编辑 Office Chart 与内嵌 XLSX。

平台和情感趋势都继续消费同一个 Context；分图不另建统计口径。

当前不用双 Y 轴去制造复杂比例。

图表规格入口：

```text
chart_spec.py
markdown_word.py
```

---

# 12. 为什么柱状图/折线图/饼图要用 Office Chart

Word 中主要统计图不是 PNG 截图，而是原生 Office Chart。

生成后 DOCX 包中会有：

```text
word/charts/chartN.xml
word/embeddings/chartN.xlsx
```

优势：

- Word 中仍可编辑；
- 图表数据随文档一起保存；
- 可以验证图表数据是否和报告一致；
- 不需要为每个图重复生成静态图片。

当前支持的 Markdown 图表输入主要包括：

```text
pie
xychart-beta
```

转换器也保留当前需要的兼容解析。

不支持的图表类型应该明确失败，不能悄悄把图丢掉继续产出“成功 Word”。

OOXML 打包：

```text
docx_package.py
```

图表规格：

```text
chart_spec.py
```

---

# 13. Office Chart 的内嵌 XLSX 从哪里来

Office Chart 需要自己的数据工作簿。

正确：

```text
Report Context / Chart Spec
→ 生成 chartN.xlsx
→ 放进 DOCX embeddings
```

错误：

```text
修改用户输入 Excel
→ 新增隐藏 Sheet
→ Word Chart 引用原文件
```

当前输入 Workbook 只读，Chart 自己的 XLSX 在 DOCX 包内部生成。

这保证生成报告不会污染输入数据文件。

---

# 14. 词云为什么是 PNG

Word 没有适合的原生词云对象，所以词云是静态图。

当前词云实现位于：

```text
chart_png.py
```

目标不是“随机散词”，而是适合正式报告的确定性 Editorial Word Cloud。

当前重要特点：

```text
最多约 36 个词
sqrt 频次权重
压缩极端字号差异
全部水平排布
中心向外找空位
按真实字形边界碰撞
裁切后放大到报告所需画布
高分辨率 PNG
固定输入得到稳定布局
```

这样 4–9 个词的稀疏场景不会缩成画布中央很小一团；几十个词时也不依赖随机旋转制造“热闹感”。

词云是展示层，不改变关键词/标签统计。

---

# 15. 中文字体为什么是运行依赖

词云需要真实字形尺寸进行碰撞布局，因此必须有 CJK 字体。

当前会优先寻找平台可用的中文字体，也支持：

```text
AIMA_REPORT_CJK_FONT
```

显式指定字体路径。

如果没有可用中文字体，应该明确失败，不用方框字/乱码继续生成一个“可打开但不可读”的报告。

字体文件不是仓库业务资产，不提交字体二进制到交付文档。

---

# 16. Word 表格怎样处理长明细

普通数据表当前目标：

- 白底；
- 克制表头；
- 轻分隔；
- 数值右对齐；
- 重复表头；
- 尽量使用横向页面宽度。

每日明细在 Markdown 中常是：

```text
日期 | 维度 | 数量
```

Word 为减少重复日期，可以投影为：

```text
日期 | 维度A | 维度B | 维度C ...
```

维度过多再分块。

这只是展示投影，不改变原始统计数据。

---

# 17. 日期范围如何工作

用户可以指定：

```text
2026-08-13 ~ 2026-08-19
```

当前按北京时间自然日闭区间：

```text
start <= business_date <= end
```

内容使用发布时间；评论使用评论时间；标签明细必须能可靠映射到对应内容日期。

如果：

- 日期解析失败；
- 标签明细无法关联日期；
- Sheet 间周期统计不一致；

报告 fail closed。

为什么：

> 一个周报如果混进下一天的数据，比“生成失败需要修数据”更危险。

---

# 18. `imports_test` 怎样调用报告

人工入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/generate_report.py
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

当前 `run_all()` 可形成：

```text
convert
→ filter_keywords
→ deduplicate
→ 可选 database_ingestion
→ AI label
→ export_labeled_excel
→ generate_report
```

只想针对已经生成好的 Excel 出报告，也可以直接调用 `generate_report(...)` 或 `generate_excel_report(...)`。

`imports_test` 只负责触发，不复制：

- Report Template；
- 统计逻辑；
- Word Renderer；
- Chart/Word Cloud。

---

# 19. DOCX 为什么生成后还要做结构校验

“`python-docx`/ZIP save 没报错”不代表 Word 包结构一定完整。

当前会检查至少：

- DOCX ZIP 可读取/CRC；
- 必需 OOXML 文件；
- 关键 XML 可解析；
- Chart Relationship；
- Chart XML；
- 内嵌 XLSX；
- 图片 Relationship；
- PNG 可打开。

实现：

```text
docx_package.py
```

这能发现：

```text
图表 XML 写进去了，但 rel 漏了
chart rel 有了，但 embedded XLSX 丢了
图片文件存在，但 document.xml.rels 没引用
```

这类问题靠肉眼看 Python 代码很难发现。

---

# 20. 结构正确 ≠ 所有办公软件像素一致

DOCX 是可重排 OOXML，不是 PDF 固定画布。

不同：

- Microsoft Word；
- LibreOffice；
- 飞书预览；

可能在：

- 字体替代；
- 行高；
- 图表主题；
- 分页；
- 文本度量；

出现差异。

因此自动测试主要保证：

```text
统计正确
结构正确
OOXML 关系正确
Office Chart 数据正确
词云图片正确
```

正式视觉交付还需要用目标办公软件抽查代表性报告。没有目标 Word 渲染证据时，不宣称“像素级完全一致”。

---

# 21. 修改统计口径应该怎么做

例如要新增：

```text
“负面内容 Top 平台”
```

正确顺序：

```text
excel_report.py
→ 从统一 Context 形成新统计
→ Unit Test 验证数量
→ report_template.md 增加占位/章节
→ visual_docx.py 如需专门视觉投影
```

不要：

```text
直接在 visual_docx.py 重新遍历 Excel 计算
```

否则 Markdown 和 Word 很快漂移。

---

# 22. 修改正文应该怎么做

如果只是：

- 改章节标题；
- 改说明文字；
- 调整章节顺序；
- 增加一个文字结论区；

优先：

```text
report_template.md
```

然后验证：

```text
生成的 report.md
→ 文字正确
report.docx
→ 同一内容进入 Word
```

不应在 `markdown_word.py` 里偷偷写另一套正文。

---

# 23. 修改 Word 视觉应该怎么做

如果只改：

- A4 页面；
- 字号；
- 间距；
- KPI；
- Ranking；
- 表格密度；
- 图文并排；

主要看：

```text
visual_docx.py
```

如果涉及原生 Chart：

```text
chart_spec.py
→ docx_package.py
```

如果涉及词云：

```text
chart_png.py
```

不要因为“Word 看起来不好看”就重构 Excel、AI 或数据库。

---

# 24. 修改图表应该怎么做

先判断是：

```text
数据错
→ excel_report.py

系列/图表类型错
→ chart_spec.py / markdown_word.py

Word 原生 Chart 结构错
→ docx_package.py

尺寸/布局不合适
→ visual_docx.py
```

这四类问题不要混成一个“图表不好看”。

---

# 25. 修改词云应该怎么做

先区分：

```text
词频错误
→ excel_report.py / Context

词云布局不好
→ chart_png.py

Word 中图片大小/位置不好
→ visual_docx.py
```

稀疏词云和高频词云都应该有 Fixture/确定性测试；不要只拿一个几十词案例优化。

---

# 26. 常见故障怎么定位

## `report.md` 数字就错了

先看：

```text
输入 Workbook
→ excel_report.py
```

不要先看 Word。

## Markdown 正确，Word 数字/表格错

看：

```text
markdown_word.py
visual_docx.py
```

## Word 图表不显示

看：

```text
chart_spec.py
→ docx_package.py
→ chart relationship
→ embedded XLSX
```

## 词云乱码/方框

看：

```text
CJK font
AIMA_REPORT_CJK_FONT
chart_png.py
```

## Word 能打开，但飞书分页很差

这可能是渲染器差异。先检查：

```text
页面宽度
表格列宽
固定/自动行高
字体替代
图表尺寸
```

再用目标预览器抽查，不要为了飞书一处差异破坏 Word 的 OOXML 结构。

---

# 27. 报告和正式数据库 Export 的边界

当前正式 Excel Export：

```text
POST /api/v1/data-exports
→ reporting.content-export-excel.v1
→ UnifiedDataExcelV1 Artifact
```

当前 Word Report：

```text
已有统一 Excel
→ generate_excel_report()
→ report.md / report.docx
```

目前没有：

```text
POST /api/v1/reports
report.generate-word.v1 Job
reporting_reports PostgreSQL 表
独立 Reports Vue 页面
```

如果未来产品要“一键从数据库生成 Word 报告”，合理做法是编排：

```text
冻结数据库数据 / Export Read Model
→ 调用现有 Report Renderer
```

而不是让离线 Renderer 自己开始写 SQL。

---

# 28. 当前测试入口

核心目标测试包括：

```text
tests/unit/platform/test_offline_reporting.py
tests/unit/platform/test_docx_package_structure.py
tests/unit/platform/test_reporting_default_template.py
```

`imports_test` 接线：

```text
tests/unit/platform/test_imports_test_reporting.py
tests/unit/collection/test_p1g_imports_run_all.py
```

重点验证：

- 统计值；
- 输入 Excel 不被修改；
- Markdown/Word 文字一致；
- A4 纵向与模板页边距；
- 上期对比区、Ranking/词云/表格布局；
- Office Chart + embedded XLSX；
- 图表数据；
- 词云确定性；
- OOXML Relationship；
- 不支持输入 fail closed；
- `imports_test` 只接线不复制业务逻辑。

最终仍以 PR 最新 HEAD CI 为准。

---

# 29. 当前明确限制

- 当前是离线文件报告，不是网页报告中心；
- 不重新调用 LLM 生成“管理结论”；
- 不直接读取 PostgreSQL；
- Word 转换只支持当前报告需要的 Markdown/图表子集，不是通用 Markdown→DOCX 引擎；
- 词云是 PNG，柱/折/饼主要是 Office Chart；
- 不修改输入 Excel；
- 当前没有正式 Report Job / API / PostgreSQL 父事实。

---

# 30. 飞书方案三：原生正文/表格在线编辑 + 原始 Word 下载

## 30.1 最终交付是什么

同一报告会发布两个互补交付：

```text
报告生成结果
├─ 飞书原生文档：正文和表格在线查看、编辑；图表/词云为高清静态 PNG
└─ 原始 report.docx：保持本地 OOXML/Office Chart 字节，供下载和本地 Word 编辑
```

用户不需要接触内部 `report.md`。Markdown 仍是正文结构的内部来源，飞书发布器直接将它重建为标题、段落、原生表格和图片块，不再把 `report.docx` 或任何视图版 DOCX 导入成在线文档。

## 30.2 图表编辑和更新报告的边界

飞书不会把 Word Office Chart 可靠转换成飞书可编辑图表。在线报告中的图表为了保留清晰度，使用完整标题、坐标轴、标签和图例的高清 PNG；图片本身不是可编辑图表。发布时本地临时生成图表数据 XLSX 并导入为飞书原生“可编辑图表”Sheet，每张报告图下提供该 Sheet 的编辑入口。

飞书报告中的图表不自动修改回写：用户在 Sheet 改数据后自行截图，并手动替换在线报告的对应图片。系统不做同步按钮、不生成同步清单，也不修改原始 Word。临时 XLSX 只是导入 Sheet 的输入；导入任务成功后按本次返回的精确 file token 删除云端上传源文件，并清理同一报告目录下的本地临时 XLSX，不按名称或目录做模糊云端清理。

## 30.3 调用链

```text
generate_excel_report()
→ report.md + report.docx
→ FeishuReportPublisher
   → 上传 report.docx 原始字节（下载件）
   → 临时 chart_workbook.xlsx 导入飞书原生 Sheet，成功后清理源文件
   → 创建空白飞书原生文档
   → report.md + ChartSpec + 本地 PNG
      → 标题 / 正文 block
      → table / table_cell block
      → 图表 PNG / 词云 PNG block
   → 文末追加原始 Word 下载入口
```

`feishu_native_document.py` 不重新读取 Excel 或统计数据；它只消费已有 `report.md`、图片资产和 `ChartSpec`。飞书适配器同样不依赖飞书的 `open_id`、`union_id` 等身份字段。

飞书和 Word 的布局语义保持章节、表格和图表顺序一致。`table-style=compact-daily` 的日期/维度/数量长表会按 Word 相同的首见顺序透视为“日期 × 维度”原生表格，每张表最多五个维度。由于 Word 的分页和并排布局不能一比一映射，飞书中允许“表格后接图”而非像素级复刻页面。

## 30.4 配置、权限与安全

离线 `generate_report.py` 从 `backend/src/aima_ugc/adapters/providers/imports_test/.env` 读取配置；该文件被 Git 忽略，应该由同事从同目录 `.env.example` 复制生成。`.env` 的同名项优先于系统环境变量，避免前任 PowerShell 会话残留的 App ID 或 Folder Token 覆盖交接配置；系统环境变量只为文件未写的项提供回退值。

`.env` 中显式设置：

```text
AIMA_FEISHU_REPORT_ENABLED=false
AIMA_FEISHU_APP_ID=cli_xxx
AIMA_FEISHU_FOLDER_TOKEN=fld_xxx
AIMA_FEISHU_APP_SECRET_REF=feishu/report_app_secret
AIMA_EXTERNAL_SECRET_DIR=.runtime/secrets
```

需要发布时把开关改为 `true`。App Secret 单独写入 UTF-8 只读文件：

```text
<AIMA_EXTERNAL_SECRET_DIR>/feishu/report_app_secret
```

应用需要原始文件上传、创建/编辑新版文档、上传新版文档图片素材的对应最小权限；调用身份还必须拥有目标文件夹编辑权限。代码不会创建 API Key、修改分享范围、邀请用户或发送飞书消息。

DOCX 上传 body 直接使用本地字节并记录 SHA-256。网络错误、限流和导入任务失败会关闭失败；发布可能已创建云端副本时不会隐藏重试。

## 30.5 人工验收

普通 CI 使用 `httpx.MockTransport`，不会调用真实飞书。首次接入真实租户时：

1. 使用小型报告运行 `generate_report.py`；
2. 确认飞书文档的正文可直接编辑，所有 Markdown 表格都是可编辑原生表格且文字完整；
3. 对照章节顺序确认每张图和词云都在相应表格/正文之后，高清可读；
4. 下载“原始 Word”，与本地 `report.docx` 比较 SHA-256，并用 Microsoft Word 检查 Office Chart 仍可编辑。

## 30.6 当前范围

- 当前接在离线 `imports_test` / `generate_report.py`，不是正式 Report API/Job；
- 不保存飞书发布事实到 PostgreSQL；
- 不自动同步飞书修改回本地 Word；
- `chart_png.py` 生成的 PNG 使用真实 CJK 字体并包含标题、坐标轴、日期/分类、数值标签、饼图标签和图例；
- 不修改飞书权限；重跑发布可能创建新的 Word、原生文档和 Sheet 副本。每次发布成功导入 Sheet 后只清理本次上传的临时 XLSX 源文件。

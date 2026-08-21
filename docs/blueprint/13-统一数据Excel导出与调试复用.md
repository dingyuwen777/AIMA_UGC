# 统一数据 Excel 导出与调试复用

## 1. 定位

本设计负责**帖子/评论数据明细 Excel 的唯一公共数据契约与共享导出实现**。它不是 Provider Raw、Canonical 持久化格式，也不是管理层分析报告或 Report Renderer。

长期数据方向：

```text
Provider Raw / 文件输入 / PostgreSQL Read Model
→ Provider-neutral UnifiedContentRecordV1 / Export Read Model
→ UnifiedDataExcelV1
→ 唯一共享 Excel Exporter
→ 受控展示投影
→ .xlsx
```

分析结果可以作为可选结构化列进入数据明细 Excel，但数据明细和分析报告继续是不同产物：

```text
数据明细 Excel
= 内容/评论事实 + 可选结构化标签

Report
= 趋势、统计、图表、结论、解释和管理层汇报
```

## 2. 数据契约与展示列是两层概念

系统长期只维护一个 Provider-neutral Excel 输入契约：

```text
UnifiedDataExcelV1
```

TikHub、小红书、抖音、微博、B站、快手、文件导入或未来其他 Provider 都不能各自定义新的 Excel 业务字段。平台/Provider 差异必须在 Mapper/Canonical 或批准的 Export Read Model 之前解决；共享 Exporter 只消费 Provider-neutral 数据。

**数据契约完整字段不等于每次人工查看都必须显示所有列。**

共享 Exporter 允许调用方分别为三个 Sheet 提供有序列名序列，从各 Sheet **已经存在的共享列**中选择最终显示哪些列以及列顺序：

```python
content_columns = (
    "平台",
    "标题",
    "正文",
    "情感标签",
)

label_detail_columns = (
    "一级标签",
    "二级标签",
    "标题",
)

comment_columns = (
    "平台",
    "评论内容",
    "评论时间",
)
```

规则固定为：

- `content_columns`、`label_detail_columns`、`comment_columns` 分别控制“内容”“标签明细”“评论”Sheet；
- 任一参数不传：该 Sheet 输出当前完整默认列，保持既有调用方行为；
- 传入配置：只显示配置中的已知列，顺序与配置完全一致；
- 空配置、重复列、未知列直接拒绝；
- 列投影只影响最终视图，不删除 `UnifiedDataExcelV1` 中的数据；
- 调用方不能通过这些配置新增自定义列名、公式列、私有字段或第二套字段语义。

因此“选择显示列”是 Viewer/Exporter 层能力，不反向改变 Canonical、Analysis 或数据库 Schema。

## 3. 当前共享 Workbook 字段

Workbook 固定三个 Sheet：

```text
内容
标签明细
评论
```

当前完整内容列为：

```text
平台
内容ID
来源项ID
内容类型
标题
正文
作者
发布时间
内容链接
作者粉丝数
作者关注数
作者内容数
作者获赞数
点赞
评论数
收藏数
分享数
转发数
浏览数
播放数
弹幕数
投币数
下载数
命中关键词
发声类型
是否用户真实发声
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
来源Provider
Raw/来源定位
评论覆盖
```

当前完整标签明细列为：

```text
内容ID
平台
标题
情感标签
一级标签
二级标签
内容链接
```

当前评论列为：

```text
平台
内容ID
评论层级
评论ID
根评论ID
父评论ID
作者
评论内容
评论时间
评论点赞
回复数
来源Provider
Raw/来源定位
```

“标签明细”允许选择全部内容共享列；其中“一级标签”“二级标签”替换为当前展开标签对，其他列来自同一个归一化内容记录。“评论”允许选择上述评论列，也允许选择对应归一化内容的共享列；重名列保持既有评论语义，`作者`、`来源Provider`、`Raw/来源定位` 分别表示评论作者和评论来源，`平台`、`内容ID` 是两者共享的稳定关联。

外部 ID 一律按文本写入；一级/二级评论关系必须保留稳定 comment/root/parent ID，不能依赖 Excel 行位置猜关系。
Excel 的“内容ID”来自归一化记录的 `external_content_id`，不是导出器临时生成的内部 UUID；隐藏该列只改变展示，不改变内容、标签和评论的归一化关联。

“平台”列同样属于受控展示投影。Canonical、`UnifiedDataExcelV1` 输入记录和数据库继续使用
英文稳定平台 ID；共享 Exporter 把当前已知的 `xiaohongshu`、`douyin`、`weibo`、
`bilibili`、`kuaishou` 分别显示为“小红书”“抖音”“微博”“哔哩哔哩”“快手”。
三个 Sheet 复用同一映射，未知平台保持原值。该规则不修改输入 Contract、关联键或上游数据。

### 3.1 源 Excel 表头和 Sheet 发现边界

`aima-monitoring-excel.v1` 只把下列源表头作为 Sheet 必需列：

```text
媒体名称（中文）  -> 平台
标题              -> 标题
内文              -> 正文
作者              -> 作者
出版日期          -> 发布时间
原文链接          -> 内容链接
```

表头校验只判断第一行的精确列名是否存在；不要求序号、监测项名称、文章编号、版面、媒体类型、全文情感或粉丝数等其他列，也不将额外列视为错误。无关列重名也不阻断导入；只有上述 6 个必需列自身重名时，才会因映射语义歧义拒绝。“文章编号”和“粉丝数”存在时 Mapper 仍可使用，但不影响 Sheet 资格。列名存在不等于强制该列每个单元格非空；每行平台和稳定内容身份等仍按 Mapper 现有规则 fail closed。

`sheet_name=None` 时 Reader 扫描全部 Sheet：符合要求的“文章”优先，否则选择唯一符合的 Sheet；多个非默认候选时拒绝猜测并要求显式指定。传入具体 Sheet 名时只读取该页，不静默切换。Reader 会在 `read_only=True` 流式读取前重置来源文件不可信的 Worksheet dimension，避免实际多列文件因元数据误写为 `A1:A1` 而只读取 A 列。字体、字号、颜色、边框等视觉样式不进入 Reader/Mapper 校验边界。

## 4. AI 标签列

平台通用 AI 标签 Contract 由 [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md) 维护。

共享内容视图支持以下 Analysis 列：

```text
发声类型
是否用户真实发声
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
```

其中：

- “相关性”不进入 Excel 展示列。离线打标已从最终 `deduplicated/contents.jsonl` 删除 `irrelevant` 内容；正式查询型导出同样默认排除当前分析判定的无关内容，因此导出表不重复展示恒为 relevant 的字段；
- `voice_type` 在 Contract/数据库中保持稳定英文枚举，Excel 仅做中文展示映射：`user_voice → 真实用户发声`、`creator_marketing → 达人/创作者营销`、`brand_official → 品牌官方传播`、`dealer_promotion → 经销商/门店推广`、`media_information → 媒体/资讯转载`、`other_organization → 其他机构传播`、`unknown → 无法判断`；
- “是否用户真实发声”不由模型重复输出，而由 `voice_type == user_voice` 唯一派生为“是/否”，避免双字段冲突；
- 情感标签仍为单值；一级/二级标签由 Analysis 的一个或多个合法标签对投影；
- `内容` Sheet 保持一条内容一行，一级和二级单元格按同一标签对顺序用换行符逐行展示，两个单元格行与行对应；
- `标签明细` Sheet 直接从同一个归一化 `UnifiedContentRecordV1` 的内容事实和 Analysis 标签对派生，一个标签对一行；完整默认列为内容ID、平台、标题、情感、一级、二级、内容链接，同一内容因此可以在标签明细中出现多行，但不会在内容 Sheet 重复；
- 没有合法 Analysis 时内容标签列保持为空，标签明细只保留表头，不用源 Excel 的“全文情感”或其他上游标签填充；
- 是否显示某列分别由三个 Sheet 的列配置决定，但不改变 Analysis 数据或内容、标签、评论的关联。

## 5. raw 与 labeled 使用同一展示配置

原始人工审阅和打标后视图不能维护两套 Workbook 代码。

同一次调用场景下，raw/labeled 必须使用同一个：

```text
三个 Sheet 定义
content_columns
label_detail_columns
comment_columns
列顺序
公共样式
数据安全规则
```

区别只在：

```text
raw
→ include_analysis = false
→ Analysis 列即使被选择也留空

labeled
→ include_analysis = true
→ 从 UnifiedContentRecordV1.analysis 填入合法 Analysis 值
```

`imports_test` 当前默认内容视图为：

```text
平台
标题
正文
作者
发布时间
内容链接
命中关键词
发声类型
是否用户真实发声
情感标签
一级标签
二级标签
```

这是该人工入口的**默认展示配置**，不是 `UnifiedDataExcelV1` 的字段裁剪，也不改变 TikHub 或未来正式导出在未传配置时的完整默认视图。

## 6. 同源 JSONL 闭环

文件处理链继续保持：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl（UnifiedContentRecordV1，analysis 初始为空）
→ AI 打标（同一次 LLM 调用完成 relevance + voice_type + sentiment + labels）
→ 原子回写同一个 deduplicated/contents.jsonl（relevant 写回 Analysis；irrelevant 行删除）
→ shared Excel Exporter
```

模型成功结果可以先写：

```text
analysis/checkpoints.jsonl
```

用于恢复、费用安全和审计，但 checkpoint 不是下游业务事实源；成功 Analysis 必须回写原 `deduplicated/contents.jsonl`。

最终 Excel 只读取这份统一 JSONL，不再 join 第二份业务 Analysis 文件，也不从 Excel 回读进入关键词、去重、AI 或数据库流程。Report Renderer 可以把最终 Excel 当作**只读派生视图输入**，但不得把报告统计反写为上游业务事实。

## 7. 唯一共享 Exporter

共享实现固定在：

```text
backend/src/aima_ugc/platform/export/excel.py
```

调用关系：

```text
tikhub_test ─────────────┐
imports_test ────────────┼→ platform/export/excel.py
Stage 8D durable Export ─┘
```

共享入口：

```python
export_unified_data_excel(
    ...,
    include_analysis=...,
    content_columns=...,
    label_detail_columns=...,
    comment_columns=...,
)
export_unified_content_jsonl_to_excel(
    ...,
    include_analysis=...,
    content_columns=...,
    label_detail_columns=...,
    comment_columns=...,
)
```

三个列参数都是可选展示参数；`None` 表示对应 Sheet 的完整默认列。

调用方可以做的只有：

- 选择共享 Exporter 为对应 Sheet 定义的已知列；
- 调整这些已知列的顺序；
- 决定是否填充 Analysis。

调用方不得复制或自行维护：

- Workbook 创建/保存；
- 自定义新字段或平行列字典；
- ID 文本格式；
- URL/超链接；
- Formula Injection 防护；
- 时间显示；
- 字体、填充、列宽、行高、冻结窗格、筛选等公共样式；
- 大文件写出策略；
- 导出后重新打开校验。

如果未来 Architecture Check 证明共享实现目录需要调整，可以通过独立 Change 最小迁移；**一个 Provider-neutral 数据契约 + 一个共享 Exporter** 的边界不变。

## 8. 公共 Excel 样式

当前共享样式参考业务 Excel `文章` Sheet 的稳定视觉规则，并直接固化为代码；运行时不依赖本地模板文件。

固定规则：

```text
冻结首行                    A2
自动筛选                    首行到实际数据区
显示网格线                  是
合并单元格                  否
表头填充                    #FFC000
表头字体                    Calibri 11pt bold
正文字体                    Calibri 11pt
表头行高                    16.5
正文默认行高                14.5
二级标签自适应行高          14.5 到 409
页面方向                    portrait
左右页边距                  0.7
上下页边距                  0.75
页眉/页脚边距               0.3
HTTP(S) 链接                可点击 Hyperlink
```

当“内容”或“标签明细”Sheet 显示“二级标签”列时，导出器按该单元格的显式换行和中文/东亚字符显示宽度估算实际行数，以每行 14.5 磅设置确定性行高，并限制在 Excel 的 409 磅上限内；该单元格启用自动换行。隐藏“二级标签”时不设置数据行高度，“评论”Sheet 不参与该规则。该计算在流式写出当前行时完成，不扫描全表，也不二次重写 Workbook。

列宽使用按字段语义固定的有界宽度，例如：

```text
标题/正文/Raw定位           50
内容ID/来源项ID/URL/Hash    34
作者/关键词/一级标签等      20 左右
时间/数值/情感标签          12 左右
平台/Provider               15
```

不扫描全部数据自动计算列宽，因为对约 9 万行数据没有必要，会增加额外时间和内存成本。

样式属于共享 Exporter；调用方不得为了“看起来不一样”在导出后再次打开 Workbook 做第二次格式化。

## 9. 大文件实现规则

仓库继续锁定 openpyxl。现有 90,000 × 13 测量已证明当前方案在既定规模下能够正确完成且无 OOM 证据，因此不新增 pandas。

读取大 XLSX：

```python
load_workbook(
    path,
    read_only=True,
    data_only=True,
)
```

并使用：

```python
iter_rows(values_only=True)
```

最终 XLSX 使用：

```python
Workbook(write_only=True)
```

统一 Exporter 不得为了展示配置或样式：

- 把完整 Cell 对象长期常驻内存；
- 扫描全表自动列宽；
- 使用大量 merge cell；
- 导出完整文件后再二次打开重写所有数据；
- 引入 pandas 复制一套 Excel 路径。

只有新的真实负载证明现有方案不能满足需求时，才通过独立 Change 比较替代实现。

## 10. 安全与可打开性

共享 Exporter统一保证：

- 外部 ID 不因 Excel 数字格式丢失精度或前导零；
- 外部文本防 Formula Injection；
- 中文、emoji 和长文本可读取；
- URL 只在合法 HTTP/HTTPS 时建立链接；
- 不把 Secret、Token、Cookie 或本地敏感配置写入 Workbook；
- 不合法/缺失 Analysis 不伪造标签；
- 三个列配置都不允许越过对应 Sheet 的共享列集合读取任意对象属性；
- 输出完成后重新打开并核对 Sheet、实际表头、行数和可用的关键 ID；
- Stage 8D 正式声音广场导出已通过持久化 Job 分页读取冻结 Content Version、调用本共享 Exporter 并登记
  Artifact；未打标内容保留且 AI 列为空。当前认证与自动保留/删除期限尚未批准，下载只用于受信部署
  边界，不能据此宣称公网权限或自动生命周期已经闭环。

## 11. 与 Canonical、Analysis、数据库和 Report 的关系

统一 Excel 是可读视图，不是上游数据 Schema：

```text
Provider / File Import
→ Canonical
→ Analysis Service（可选）
→ UnifiedContentRecordV1 / Query Export Read Model
→ UnifiedDataExcelV1
→ Shared Excel Exporter
→ 可选列投影
→ .xlsx
→ Report Renderer（只读派生，可选）
```

因此：

- 修改任一 Sheet 的列配置不修改 Canonical；
- 隐藏某个 Excel 列不代表系统删除该字段；
- Excel 列名不能反向成为数据库 Schema；
- LLM 不能直接依赖 Excel 私有列绕过 Analysis 输入边界；
- 正式入库时 Content 与 Analysis 仍分别由各自 Owner 持久化；
- Report Renderer 只能消费已存在的数据视图，不能反向修改 Canonical、Analysis、数据库或统一 Excel Contract。

## 12. 长期维护规则

后续修改 Excel 时按以下原则判断：

### 只想改变人工查看的列

优先修改调用方对应的 `content_columns`、`label_detail_columns` 或 `comment_columns` 配置：

```text
选择已有列
删除已有列
调整列顺序
```

不需要改 `UnifiedDataExcelV1`，也不需要复制 Exporter。

### 想新增一个系统从未存在的导出字段

先确认该字段的真实数据来源和 Owner，再决定是否需要调整 Export Read Model / Contract；不能只在某个测试脚本中硬塞一列。

### 想改变所有 Excel 的公共格式

只修改共享 Exporter 和对应共享测试；TikHub、文件导入和未来正式导出自动复用。

### 想改变某个调用方的默认列

只修改该调用方的列配置，并保证 raw/labeled 使用同一个配置。

长期保持：

- 一个 `UnifiedDataExcelV1` Provider-neutral 数据契约；
- 一个共享 Excel Exporter；
- 默认完整视图向后兼容；
- 允许对三个 Sheet 的已知列分别做受控有序投影；
- raw/labeled 使用相同的三组展示配置；
- 业务中间处理不依赖 Excel 回读；
- 数据明细 Excel 与 Report Renderer 相互独立。

## 13. 当前离线 Report Renderer

当前第一个正式可复用的离线报告实现位于：

```text
backend/src/aima_ugc/platform/reporting/
```

它不是 `imports_test` 私有统计脚本。默认 Markdown 模板、统计、Markdown 渲染、Word 转换和图表嵌入都属于 Provider-neutral 平台能力；`imports_test` 只提供人工调用入口。

### 13.1 输入输出边界

当前离线链路固定为：

```text
统一数据 Excel（只读）
→ Report Statistics
→ Markdown Template Rendering
→ report.md
→ Markdown → Word
→ report.docx
```

`run_all()` 的默认输入是本次 run 的 `labeled_data.xlsx`；也允许显式指定任何符合当前统一 Workbook 结构和报告必要列要求的处理后 `.xlsx`。

报告当前要求：

```text
Sheet: 内容 / 标签明细 / 评论

内容必要列:
平台 / 发布时间 / 命中关键词 / 情感标签 / 一级标签 / 二级标签

标签明细必要列:
平台 / 情感标签 / 一级标签 / 二级标签

评论必要列:
平台
```

调用方可通过 `report_date_range=(开始日期, 结束日期)` 显式指定北京时间自然日闭区间。
指定周期时增加以下条件读取要求：

```text
内容：发布时间
标签明细：发布时间；没有该列时，内容与标签明细必须同时包含内容ID
存在评论记录时：评论时间
```

这是**报告读取要求**，不是新的 Excel Contract。通用 Excel Exporter 的完整字段定义仍由本文第 3 节维护。

### 13.2 报告数据源与统一 Report Dataset

**当前机器实现只有 Excel Report Source。** `imports_test.run_all()` 的离线报告无论是否同时开启 Content 数据库写入，仍读取本次 run 的 `labeled_data.xlsx`，因为它代表本次处理完成后的明确批次快照。

长期固定为两个显式 Source Adapter，共同进入一个 Provider-neutral Report Dataset/Context：

```text
离线单批 / 人工交付
labeled_data.xlsx
→ Excel Report Source
→ Report Dataset

正式系统 / 跨批次 / 时间窗口 / Dashboard
PostgreSQL
→ Query Repository / Report Read Model
→ Report Dataset

Report Dataset
→ Statistics
→ Markdown Template / Renderer
→ report.md / report.docx / Web
```

硬规则：

1. **禁止** `if database_available: read_database else: read_excel` 这类环境驱动自动切换；同一命令不能因为某台机器启动了 PostgreSQL 就改变报告范围。
2. `imports_test` 的“本次 run 报告”默认永远是 Excel 快照，即使 `write_to_database=True`；数据库里可能同时存在历史 Excel、TikHub、其他 Batch 和其他时间数据，不能天然代表本次 run。
3. 正式系统报告、跨 Batch 趋势、7/30/90 天窗口和 Dashboard 默认使用 PostgreSQL Report Read Model；它们不能依赖本地 `output/runs/`。
4. PostgreSQL Report Source 必须通过 Query Repository/Read Model 读取 Content、current Analysis、Comments/必要维度；Report Renderer 不直接 SQL，也不成为表 Owner。
5. 两种 Source 只负责把数据适配为同一 Report Dataset；平台、情感、标签、关键词、趋势等统计规则与 Markdown/Word Renderer 只有一套。
6. 数据库版报告在正式启用前必须先满足 Blueprint 15 的 Analysis 持久化/current Analysis 和对应 Query Read Model；数据库缺少 AI Analysis 时不得静默回退 Excel 或伪造标签。
7. 调用方需要特定来源时必须显式选择 Source/Scope；Excel 路径、Import Batch、日期窗口、平台等 Scope 必须可观察、可复现。
8. 日期窗口只属于 Report Scope；Excel Import、关键词过滤、去重、Analysis 和统一 Excel
   继续保留全量数据。离线报告按内容发布时间、标签对应内容发布时间和评论时间筛选，范围
   包含首尾自然日。
9. 指定日期窗口后，筛选所需日期缺失或无法解析必须 fail closed；周期内内容与标签明细的
   标签记录数、平台、情感、一级/二级标签和标签对必须交叉一致，不能用部分 Sheet 的全量
   统计混入周期报告。

### 13.3 统计口径与默认管理层视图

完整统计继续遵循现有 Workbook 语义：

```text
内容总量、平台、情感、关键词、按日趋势
→ 内容 Sheet

一级/二级总体频次、一级→二级标签对
→ 标签明细 Sheet

评论总量、平台评论量
→ 评论 Sheet
```

一级/二级标签的每日趋势需要时间维度，因此从“内容”Sheet 的 `发布时间` 与对应换行标签列统计；一级/二级总体频次仍以“标签明细”Sheet 为准。

默认共享报告面向营销管理层直接阅读和汇报，不再把实现过程、模板、Workbook/Sheet、Markdown/Word 转换等技术说明放进最终正文。默认正文先展示确定性管理摘要和正负面舆情重点关注，再展开完整统计：

```text
管理摘要
→ 内容/评论声量、覆盖平台、正面/中性/负面占比、声量峰值、主要平台、首要议题、热点关键词

舆情重点关注
→ 客观情感概览、正面平台/一级/二级议题、负面平台/一级/二级议题

平台与情感
→ 平台声量、平台 × 情感交叉结构、平台每日趋势

整体情感
→ 情感结构、情感每日趋势

核心议题与关键词
→ 一级/二级/标签对、关键词及对应趋势

完整统计与数据质量
→ 全量明细、缺失/异常计数和业务口径说明
```

这些摘要全部由既有结构化字段确定性计算，不新增 LLM 请求，不生成脱离数据的主观结论。报告必须保留完整平台、标签、标签对、关键词和每日非零数据表格；图表允许为了阅读性只显示 Top N 序列，但不得因为图表裁剪丢失完整表格数据，也不得修改上游数据。

### 13.4 Markdown 是报告正文唯一模板

默认共享模板当前为：

```text
backend/src/aima_ugc/platform/reporting/report_template.md
```

`generate_excel_report()` 默认使用该模板；需要特定展示时允许调用方显式传入 `template_path=`，但不能复制一套平台私有 Report Renderer。

固定规则：

```text
模板 Markdown
→ 填充统计数据
→ 生成完整 report.md
→ Word 转换器读取 report.md
→ report.docx
```

不得再维护第二套 Word 正文模板。模板普通文本、标题和顺序发生变化时，下一次 Markdown 与 Word 必须一起变化。

### 13.5 Mermaid 与可编辑 Word 图表

Markdown 图表使用 Mermaid fenced block。当前模板只使用：

```text
pie
xychart-beta
```

生成器固定输出 `xychart-beta`，以兼容当前目标 Markdown 阅读器；Word 转换器同时接受 `xychart-beta` 和历史 `xychart` 输入。Markdown 仍保留 Mermaid 源码，并以受控注释保存 XY 图的系列名称，使“同一份 Markdown → Word”时不会丢失平台/情感等业务图例。Word 转换器只承诺支持本报告实际使用的 pie/bar/line 子集；对于未支持的 Mermaid 类型必须 fail closed，不能静默忽略导致 Markdown 与 Word 内容不一致。

Word 当前不再把图表写成静态 PNG，而是生成 Office 原生 Chart，并为每张图嵌入对应的 XLSX 数据包：

```text
word/charts/chartN.xml
word/charts/_rels/chartN.xml.rels
word/embeddings/chartN.xlsx
```

因此支持 Office Chart 编辑的 Word 可以直接“编辑数据”，人工校验或调整分类、系列、数值、标题、图例和样式；报告仍以 Office 原生图表引擎保证正常展示。图表的业务数据必须与 Markdown 中同一份统计数据一致，禁止为了 Word 再计算第二套统计。

Word 的展示层固定为 A4 横向、约 15 mm 页边距和克制的研究报告主题。普通数据表使用
Editorial Table（浅表头、轻横向分隔、无重外框/竖线）；面向领导扫读的 Top 统计在 Word 中
采用“Top 重点 Ranking + 对应图表/词云 + 其余完整紧凑明细”的两层表达，排名、标签、数量、
占比和细比例条保持 Word 原生可编辑，剩余条目以双列紧凑明细保留，不因视觉裁剪丢失数据。
一级议题进一步使用组合视图：上方为标签对总量、一级议题数和 Top1 占比，左侧为完整一级
议题 Ranking，右侧为词云；该视图不加入图标、奖牌、星标或逐行小饼图/圆环图。平台分布和
情感结构等窄表允许与图表并排，平台 × 情感等宽矩阵保持完整横向表格，避免多列数据被硬塞进
半页宽度。

Office bar/line 继续显示数据标签，长分类优先横向 bar；情感每日趋势仍拆为正面+中性主趋势和
负面+混合低量级趋势。平台、一级议题和二级议题等系列较多的每日趋势把最高声量主序列单独
展示，其余每组最多四个系列，所有分层图仍各自保留内嵌 XLSX、使用绝对数量且不使用双 Y 轴。
`report.md` 中完整的日期/维度/数量长表继续保留；Word 展示层利用横向 A4 宽度按日期为行、
维度为列透视为紧凑矩阵，维度过多时每组最多五列分块，只有展示形态变化，数据语义不变。
饼图仍为可编辑 Office Chart，百分比保留两位小数。

一级议题和热点关键词词云是唯一允许图片化的统计视觉：由 Pillow 直接消费同一份报告 Counter，
最多展示 36 个词，以 sqrt 频次权重并进一步温和压缩字号差异；全部水平排布，第一名可使用系统
CJK 粗体，主体采用海军蓝、主蓝、青绿、柔紫和蓝灰，仅少量次级词使用低饱和赭色点缀。布局
从视觉中心寻找最近空位，完成后按实际字形边界裁切并受限放大回固定 1600×900 画布，因此少词
样例不会缩成中央小团，多词样例仍保留必要呼吸感。布局确定性，不使用随机旋转、图形 mask、
阴影、图标或彩虹配色。PNG 以约 300 DPI 输出，Markdown 使用标准图片语法，DOCX 打包到
`word/media/` 并校验 Relationship、Content Type 和图片可打开性。运行环境必须提供 CJK 字体，
缺失时 fail closed；仓库不提交字体文件。当前仍不引入 Pandoc、LibreOffice、Matplotlib、
pandas、`wordcloud` 库、在线服务或 `python-docx`；内嵌图表数据继续复用 openpyxl。
LibreOffice/Office 只作为开发或交付视觉验证工具。以上展示规则不得改变 Markdown 表格/图表
数据、平台映射或报告统计口径。

### 13.6 失败和数据安全边界

Report Renderer 必须：

- 使用只读方式打开输入 Excel；
- 不对输入 Workbook 调用保存、二次格式化或“修复”；
- 不调用 LLM，不写数据库，不产生新的 Canonical/Analysis 事实；
- 日期窗口只筛选内存中的报告统计，不改写输入 Excel 或上游全量产物；
- 周期外内容、标签和评论数量必须进入报告数据质量说明；
- 内容与标签明细的周期内统计不一致时明确失败；
- Markdown 使用临时文件 + `os.replace` 原子发布；
- DOCX 生成后重新打开 ZIP/XML，校验最低包结构、Office Chart、Relationship 数量，并验证每张图内嵌 XLSX 数据包可打开；
- 报告失败时明确失败，不能把完整 `run_all()` 宣称成功；
- 已经成功生成的最终 Excel 不因报告失败被删除或回滚，可以修复报告后直接重新生成。

### 13.7 与未来正式报告中心的关系

当前能力解决“已处理统一 Excel → 人工可交付报告”的独立离线路径，不提前实现正式网页报告中心。正式报告中心必须优先读取 PostgreSQL Report Read Model，而不是回扫人工 Excel 目录；数据库数据源的前置条件是 Content + current Analysis 等正式 Query 能力已经落地。

未来如果增加：

```text
PostgreSQL Query Read Model
→ 持久化 Report Job
→ Artifact 权限/生命周期
→ API
→ Web 报告中心
```

应复用同一统计/渲染边界或通过独立 Change 演进，不得把 `imports_test` 的路径或 run 目录提升为正式 HTTP/数据库 Contract；共享默认模板属于 Report Renderer 自身资源。

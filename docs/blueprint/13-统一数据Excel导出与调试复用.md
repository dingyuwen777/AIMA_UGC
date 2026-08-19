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

共享 Exporter 允许调用方通过一个有序列名序列，从**已经存在的共享内容列**中选择最终显示哪些列以及列顺序：

```python
content_columns = (
    "平台",
    "标题",
    "正文",
    "情感标签",
)
```

规则固定为：

- 不传 `content_columns`：输出当前完整内容列，保持既有默认行为；
- 传入配置：只显示配置中的已知列，顺序与配置完全一致；
- 空配置、重复列、未知列直接拒绝；
- 列投影只影响最终视图，不删除 `UnifiedDataExcelV1` 中的数据；
- 调用方不能通过该配置新增自定义列名、公式列、私有字段或第二套字段语义；
- 评论列当前保持共享完整定义，后续若确有选择需求，再在同一共享 Exporter 中用相同原则扩展。

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

外部 ID 一律按文本写入；一级/二级评论关系必须保留稳定 comment/root/parent ID，不能依赖 Excel 行位置猜关系。

## 4. AI 标签列

平台通用 AI 标签 Contract 由 [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md) 维护。

共享内容视图支持以下 Analysis 列：

```text
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
```

其中：

- 情感标签仍为单值；一级/二级标签由 Analysis 的一个或多个合法标签对投影；
- `内容` Sheet 保持一条内容一行，一级和二级单元格按同一标签对顺序用换行符逐行展示，两个单元格行与行对应；
- `标签明细` Sheet 一个标签对一行，固定保存内容ID、平台、标题、情感、一级、二级、内容链接，用于 Excel 原生下拉筛选和标签统计；同一内容因此可以在标签明细中出现多行，但不会在内容 Sheet 重复；
- 没有合法 Analysis 时内容标签列保持为空，标签明细只保留表头，不用源 Excel 的“全文情感”或其他上游标签填充；
- 是否显示内容 Sheet 的 Analysis 列由 `content_columns` 决定，但不改变 Analysis 数据或标签明细关系。

## 5. raw 与 labeled 使用同一展示配置

原始人工审阅和打标后视图不能维护两套 Workbook 代码。

同一次调用场景下，raw/labeled 必须使用同一个：

```text
三个 Sheet 定义
content_columns
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
→ AI 打标
→ 原子回写同一个 deduplicated/contents.jsonl（analysis 已填）
→ shared Excel Exporter
```

模型成功结果可以先写：

```text
analysis/checkpoints.jsonl
```

用于恢复、费用安全和审计，但 checkpoint 不是下游业务事实源；成功 Analysis 必须回写原 `deduplicated/contents.jsonl`。

最终 Excel 只读取这份统一 JSONL，不再 join 第二份业务 Analysis 文件，也不从 Excel 回读进入关键词、去重、AI 或数据库流程。

## 7. 唯一共享 Exporter

共享实现固定在：

```text
backend/src/aima_ugc/platform/export/excel.py
```

调用关系：

```text
tikhub_test ─────┐
imports_test ────┼→ platform/export/excel.py
未来正式导出 ────┘
```

共享入口：

```python
export_unified_data_excel(..., include_analysis=..., content_columns=...)
export_unified_content_jsonl_to_excel(..., include_analysis=..., content_columns=...)
```

`content_columns` 是可选展示参数；`None` 表示完整默认内容列。

调用方可以做的只有：

- 选择共享 Exporter 已知的内容列；
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
页面方向                    portrait
左右页边距                  0.7
上下页边距                  0.75
页眉/页脚边距               0.3
HTTP(S) 链接                可点击 Hyperlink
```

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
- `content_columns` 不允许越过共享列集合读取任意对象属性；
- 输出完成后重新打开并核对 Sheet、实际表头、行数和可用的关键 ID；
- 大批量导出进入正式系统后仍遵守持久化 Job、Artifact 生命周期、权限和保留规则。

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
```

因此：

- 修改 `content_columns` 不修改 Canonical；
- 隐藏某个 Excel 列不代表系统删除该字段；
- Excel 列名不能反向成为数据库 Schema；
- LLM 不能直接依赖 Excel 私有列绕过 Analysis 输入边界；
- 正式入库时 Content 与 Analysis 仍分别由各自 Owner 持久化。

## 12. 长期维护规则

后续修改 Excel 时按以下原则判断：

### 只想改变人工查看的列

优先修改调用方的 `content_columns` 配置：

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
- 允许对已知内容列做受控有序投影；
- raw/labeled 同内容展示配置，标签明细 Sheet 结构也一致；
- 业务中间处理不依赖 Excel 回读；
- 数据明细 Excel 与 Report Renderer 相互独立。

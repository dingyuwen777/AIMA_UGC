# 统一数据 Excel 导出与调试复用

## 1. 定位

本设计负责**帖子/评论数据明细 Excel 的唯一公共契约与共享导出实现**。它不是 Provider Raw、Canonical 持久化格式，也不是管理层分析报告或 Report Renderer。

长期数据方向：

```text
Provider Raw / 文件输入 / PostgreSQL Read Model
→ Provider-neutral UnifiedContentRecordV1 / Export Read Model
→ UnifiedDataExcelV1
→ 唯一共享 Excel Exporter
→ .xlsx
```

分析结果可以作为可选结构化列进入统一数据 Excel，但这不把数据明细 Excel 变成分析报告：

```text
数据明细 Excel
= 内容/评论事实 + 可选结构化标签

Report
= 趋势、统计、图表、结论、解释和管理层汇报
```

两者继续保持独立业务语义、Job、权限和验收边界。

## 2. 唯一 Excel Contract

系统长期只维护一个 Provider-neutral Excel 契约：

```text
UnifiedDataExcelV1
```

TikHub、小红书、抖音、微博、B站、快手、文件导入或未来其他 Provider 都不能各自定义 Excel 字段。平台/Provider 差异必须在 Mapper/Canonical 之前解决；Excel 只消费 Provider-neutral 数据。

首版 Workbook 固定两个 Sheet：

```text
内容
评论
```

内容 Sheet 至少覆盖：平台、内容 ID、来源项 ID、内容类型、标题、正文、作者、发布时间、内容链接、公开作者统计、互动指标、命中关键词、可选分析字段、来源 Provider 与 Raw/来源定位。

评论 Sheet 至少覆盖：平台、内容 ID、评论层级、评论 ID、根评论 ID、父评论 ID、作者、正文、时间、点赞/回复等指标、来源 Provider 与 Raw/来源定位。

外部 ID 一律按文本写入；一级/二级评论关系必须保留稳定 comment/root/parent ID，不能通过 Excel 行位置猜关系。

## 3. AI 标签列

平台通用 AI 标签 Contract 由 [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md) 维护。

统一 Excel 至少包含：

```text
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
```

其中：

- 情感标签显示：正面 / 中性 / 负面 / 混合；
- 一级标签、二级标签必须来自 Blueprint 15 的闭集；
- 没有合法 Analysis 时保持为空，不用源 Excel 的“全文情感”或其他上游标签填充。

## 4. raw 与 labeled 使用同一契约

原始数据人工审阅和打标后数据只通过**文件名与分析字段是否输出**区分，不能维护两套 Workbook Schema。

```text
<source>_<run-id>_raw_data.xlsx
<source>_<run-id>_labeled_data.xlsx
```

两者必须：

- Sheet 完全相同；
- 列名完全相同；
- 列顺序完全相同；
- 基础内容/评论字段语义完全相同。

区别：

```text
raw_data.xlsx
→ AI 分析列留空

labeled_data.xlsx
→ 从 UnifiedContentRecordV1.analysis 填入闭集标签和版本化分析元数据
```

`raw_data.xlsx` 是可选人工审阅派生物，不是处理链路的必经中间层。任何关键词、去重、AI 或数据库逻辑都不能依赖 raw Excel 回读。

## 5. 同源 JSONL 闭环

已落地的离线文件处理主链固定为：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl（UnifiedContentRecordV1，analysis 初始为空）
→ AI 打标
→ 原子回写同一个 deduplicated/contents.jsonl（analysis 已填）
→ labeled_data.xlsx
```

`label_sentiment()` / 平台中立 `label_content()` 直接消费 `deduplicated/contents.jsonl`。

AI 运行期间可以使用：

```text
analysis/checkpoints.jsonl
```

保存已成功模型调用和恢复事实，但 checkpoint 不是下游业务事实源；成功分析必须合并回原 `deduplicated/contents.jsonl`。

最终 `export_labeled_excel()` **只读取回写后的 `deduplicated/contents.jsonl`**，不再额外 join `analysis/results.jsonl`。

可选 raw Excel 同样读取这份 JSONL，只是调用共享 Exporter 时：

```text
include_analysis = false
```

因此即使内容已经打标，也能从同一 JSONL 生成分析列为空的 raw 人工视图；不需要维护 raw/labeled 两份 JSONL。

## 6. 唯一共享 Exporter

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

整个后端只维护一个 Provider-neutral Excel 核心写出函数：

```python
export_unified_data_excel(...)
```

共享函数接受 Provider-neutral 内容记录/迭代器、可选评论记录、目标路径以及是否输出分析字段的明确参数；调用方不能自己再拼 Workbook。

调用方不得复制：

- Sheet/列定义；
- ID 文本格式；
- URL/超链接；
- 长文本换行；
- Formula Injection 防护；
- 时间显示；
- 列宽/冻结窗格等公共样式；
- 大文件写出策略；
- AI 标签到中文显示值的映射。

若未来 Architecture Check 证明当前共享实现目录不再合法，可以通过新的 Change 最小调整目录，但**“一个 Contract + 一个共享 Exporter”不可改变**，也不能以路径调整为由保留平行实现。

## 7. `tikhub_test` 与 `imports_test` 复用状态

`tikhub_test` 与 `imports_test` 已完成共享 Exporter 收口：

1. 通用 Workbook 规则只在唯一共享实现维护；
2. `tikhub_test` 直接调用共享 Exporter；
3. `imports_test` 只调用共享 Exporter，不维护自己的 Excel 模块；
4. 原 `tikhub_test/core/excel.py` 重复实现已删除；
5. 通用 Excel 单元测试归属共享 Exporter；
6. `tikhub_test` / `imports_test` 只保留各自输入进入共享 Exporter 的集成回归；
7. 后续 Review 必须继续检查 `.xlsx`、`openpyxl`、Workbook/Exporter 相关实现，禁止重新形成第二套内容+评论 Excel 生成器。

任何后续功能若重新引入平行 Workbook 规则，视为违反当前架构边界。

## 8. 大文件实现规则

当前仓库锁定 `openpyxl`。90,000 × 13 Windows 性能验证已证明当前方案在既定规模下能够正确完成且无 OOM 证据，因此当前不新增 pandas。

读取大 XLSX：

```python
load_workbook(
    path,
    read_only=True,
    data_only=True,
)
```

并使用 `iter_rows(values_only=True)` 顺序处理。

最终大 XLSX 写出使用 `write_only` 模式。统一 Exporter 不得为约 9 万行数据：

- 把完整 Cell 对象长期常驻内存；
- 扫描全表做自动列宽；
- 使用大量 merge cell 作为统一长期结构。

当前 90,000 × 13 Windows 基准中，主链总耗时约 `148.919 s`、吞吐约 `604.35 rows/s`、进程峰值 RSS `234,762,240 B`；最终 Excel 写出是主要耗时。该结果是当前实现的测量事实，不代表未来更大规模的性能承诺。只有新的真实负载证明当前方案不能满足需求时，才通过独立 Change 比较 pandas/calamine 等替代方案。

## 9. 安全与可打开性

共享 Exporter 至少统一保证：

- 外部 ID 不因 Excel 数字格式丢失精度或前导零；
- 外部文本防 Formula Injection；
- 中文、emoji、长文本可读；
- URL 只在合法 HTTP/HTTPS 时建立链接；
- 不把 Secret、Token、Cookie 或本地敏感配置写入 Workbook；
- 不合法/缺失 Analysis 不能伪造标签；
- 输出完成后重新打开并核对 Sheet、表头、关键行数和关键字段；
- 大批量导出进入正式系统后仍必须遵守持久化 Job、Artifact 生命周期、权限和保留规则。

## 10. 与 Canonical、Analysis、数据库和 Report 的边界

统一 Excel 展示格式不能反向成为 Canonical Schema，也不能让 LLM 直接读取 Excel 私有列绕过 Analysis 边界。

长期方向：

```text
Provider / File Import
→ Canonical
→ Analysis Service（可选）
→ UnifiedContentRecordV1 / Query Export Read Model
→ UnifiedDataExcelV1
→ Shared Excel Exporter
```

分析结果的标签、模型、Prompt、输入 Hash 和版本语义由 Analysis Contract 维护；Excel 只是最终可读视图，不成为分析事实源。

正式入库时内容和 Analysis 分别由 Content Owner 与 Analysis Owner 持久化，不能把 Excel 或 `UnifiedContentRecordV1` 整体塞进 `contents` 表或单个 JSONB 替代稳定结构。数据库长期规则见 Blueprint 15。

## 11. 长期状态

临时 P1 阶段已经完成，临时阶段文档不再作为长期事实源。本文继续维护以下长期决定：

- 一个 `UnifiedDataExcelV1`；
- raw/labeled 同契约；
- raw Excel 可选而非分析中间层；
- AI 成功结果回写同一 Provider-neutral JSONL 记录，最终导出消费同源记录；
- 业务数据中间处理不依赖 Excel 回读；
- `tikhub_test`、`imports_test`、未来正式导出共用唯一共享 Exporter；
- 数据明细 Excel 与 Report Renderer 保持独立。

P1 的实施过程、性能与真实模型证据由对应归档 Change 保存；后续维护不需要依赖临时 Blueprint 才能理解当前 Excel 边界。

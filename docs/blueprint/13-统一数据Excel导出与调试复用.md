# 统一数据 Excel 导出与调试复用

## 1. 定位

本设计负责**帖子/评论数据明细 Excel 的唯一公共契约与共享导出实现**。它不是 Provider Raw、Canonical 持久化格式，也不是管理层分析报告或 Report Renderer。

长期数据方向：

```text
Provider Raw / 文件输入
→ 正式 Mapper
→ CanonicalContentV1 / CanonicalCommentV1
→ CanonicalContentAggregateV1 或等价 Provider-neutral Export Read Model
→ UnifiedDataExcelV1
→ 唯一共享 Excel Exporter
→ .xlsx
```

分析结果可以作为**可选结构化列**进入统一数据 Excel，但这不把数据明细 Excel 变成分析报告：

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

TikHub、小红书、抖音、微博、B站、快手、文件导入或未来其他 Provider 都不能各自定义 Excel 字段。平台/Provider 差异必须在 Mapper 之前解决；Excel 只消费 Canonical/Aggregate 或经批准的 Provider-neutral Export Read Model。

首版 Workbook 推荐两个 Sheet：

```text
内容
评论
```

内容 Sheet 至少覆盖：平台、内容 ID、来源项 ID、内容类型、标题、正文、作者、发布时间、内容链接、公开作者统计、互动指标、命中关键词、可选分析字段、来源 Provider 与 Raw/来源定位。

评论 Sheet 至少覆盖：平台、内容 ID、评论层级、评论 ID、根评论 ID、父评论 ID、作者、正文、时间、点赞/回复等指标、来源 Provider 与 Raw/来源定位。

外部 ID 一律按文本写入；一级/二级评论关系必须保留稳定 comment/root/parent ID，不能通过 Excel 行位置猜关系。

## 3. raw 与 labeled 使用同一契约

原始数据人工审阅和打标后数据只通过**文件名与分析字段是否填充**区分，不能维护两套 Workbook Schema。

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
→ 舆情倾向 / 分析状态 / 分析模型 / Prompt 版本等分析列为空

labeled_data.xlsx
→ 相同分析列填入版本化结构化结果
```

`raw_data.xlsx` 是可选人工审阅派生物，不是所有处理链路的必经中间层。任何后续分析逻辑都不能依赖 raw Excel 回读。

## 4. P1 离线 JSONL 主链

当前批准的临时 P1 详见 [`14-临时P1-Excel离线导入与舆情打标.md`](14-临时P1-Excel离线导入与舆情打标.md)。P1 的业务数据中间层固定使用 JSONL：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ analysis/results.jsonl
→ labeled_data.xlsx
```

`label_sentiment()` 必须直接消费 `deduplicated/contents.jsonl`，不能依赖 `raw_data.xlsx`。

开发者需要人工检查未打标数据时，可以显式调用 `export_raw_excel()`：

```text
deduplicated/contents.jsonl
→ 共享 Excel Exporter
→ raw_data.xlsx
```

该步骤是旁路人工审阅，不进入默认 `run_all()` 主链。

`run_summary.json`、错误摘要和配置快照属于运行元数据，不是业务数据中间层，可以使用 JSON；业务内容和分析记录本身保持 JSONL 流式边界。

## 5. 唯一共享 Exporter

P1 要建立：

```text
backend/src/aima_ugc/platform/export/excel.py
```

当前 `main` 尚未存在该文件，因此在功能实现合并前它是已批准的目标路径，不得误写成现有机器事实。

建成后调用关系固定为：

```text
tikhub_test ─────┐
imports_test ────┼→ platform/export/excel.py
未来正式导出 ────┘
```

整个后端只维护一个 Provider-neutral Excel 核心写出函数，例如：

```python
export_unified_data_excel(...)
```

调用方只能准备 Provider-neutral 输入和目标文件名；不得自行复制：

- Sheet/列定义；
- ID 文本格式；
- URL/超链接；
- 长文本换行；
- Formula Injection 防护；
- 时间显示；
- 列宽/冻结窗格等公共样式；
- 大文件写出策略。

如果编码时最新 Architecture Check 证明 `platform/export/` 的依赖方向不合法，可以在同一 P1 Change 中最小调整共享实现目录，但**“一个 Contract + 一个共享 Exporter”不可改变**，也不能以路径调整为由保留平行实现。

## 6. `tikhub_test` 与 `imports_test` 迁移门禁

当前 `tikhub_test` 已有阶段性 Excel 代码，实际路径为：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/core/excel.py
```

P1D 建立共享 Exporter 时必须同步收口：

1. 把通用 Workbook 规则迁移到唯一共享实现；
2. `tikhub_test` 改为直接调用共享 Exporter；
3. `imports_test` 从第一天起只调用共享 Exporter，不建立自己的 Excel 模块；
4. 删除 `tikhub_test/core/excel.py` 中已经重复的 Excel 生成实现；
5. 删除只为平行 Excel 生成存在且无其他独立用途的临时显示模型；
6. 通用 Excel 单元测试迁移到共享 Exporter；
7. `tikhub_test` / `imports_test` 只保留各自输入能进入共享 Exporter 的集成回归；
8. PR Review 搜索 `.xlsx`、`openpyxl`、Workbook/Exporter 相关实现，确认不存在第二套内容+评论 Excel 生成器。

正式共享 Exporter 建成但仍保留 `tikhub_test` 或 `imports_test` 的平行 Excel 生成逻辑，视为 P1 未完全闭环。

## 7. 大文件实现规则

当前仓库已经锁定 `openpyxl`。没有真实性能失败证据时，P1 不新增 pandas。

读取大 XLSX：

```python
load_workbook(
    path,
    read_only=True,
    data_only=True,
)
```

并使用 `iter_rows(values_only=True)` 顺序处理。

最终大 XLSX 写出使用 `write_only` 模式或经同一 P1 性能验证证明等价且更合适的共享实现。统一 Exporter 不得为约 9 万行数据：

- 把完整 Cell 对象长期常驻内存；
- 扫描全表做自动列宽；
- 使用大量 merge cell 作为统一长期结构。

P1H 必须用真实相似的 `90,000 × 13` Fixture 和目标 Windows 环境记录读取、JSONL 处理、最终 Excel 写出、rows/s、峰值 RSS 和文件大小。只有当前方案实测不满足需求，才通过独立决策比较 pandas/calamine 等替代方案。

## 8. 安全与可打开性

共享 Exporter 至少统一保证：

- 外部 ID 不因 Excel 数字格式丢失精度或前导零；
- 外部文本防 Formula Injection；
- 中文、emoji、长文本可读；
- URL 只在合法 HTTP/HTTPS 时建立链接；
- 不把 Secret、Token、Cookie 或本地敏感配置写入 Workbook；
- 分析失败不能伪造标签；
- 输出完成后重新打开并核对 Sheet、表头、关键行数和关键字段；
- 大批量导出进入正式系统后仍必须遵守持久化 Job、Artifact 生命周期、权限和保留规则。

## 9. 与 Canonical、Analysis、Report 的边界

统一 Excel 展示格式不能反向成为 Canonical Schema，也不能让 LLM 直接读取 Excel 私有列绕过 Canonical/Analysis 边界。

长期方向：

```text
Provider / File Import
→ Canonical
→ Analysis Service（可选）
→ Provider-neutral Export Input
→ UnifiedDataExcelV1
→ Shared Excel Exporter
```

分析结果的模型、Prompt、输入 Hash 和版本语义由 Analysis Contract 维护；Excel 只是最终可读视图，不成为分析事实源。

## 10. P1 完成后的长期状态

P1 完成后会删除临时 [`14-临时P1-Excel离线导入与舆情打标.md`](14-临时P1-Excel离线导入与舆情打标.md) 和 Blueprint 导航中的临时 P1 阶段说明，但本文继续保留以下长期决定：

- 一个 `UnifiedDataExcelV1`；
- raw/labeled 同契约；
- raw Excel 可选而非分析中间层；
- 业务数据中间处理不依赖 Excel 回读；
- `tikhub_test`、`imports_test`、未来正式导出共用唯一共享 Exporter；
- 数据明细 Excel 与 Report Renderer 保持独立。
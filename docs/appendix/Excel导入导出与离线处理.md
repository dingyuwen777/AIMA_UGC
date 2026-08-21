# Excel 导入、导出与离线处理

这篇文档把几件名字很像、实际职责不同的事情拆开：

```text
Excel 导入      把外部文件读成系统数据
统一 Excel 导出 把系统数据导成固定审阅格式
离线 AI/报告    在文件链路上继续处理，不一定写数据库
正式 Export Job 从 PostgreSQL 快照生成可下载 Artifact
```

理解这四件事后，就不容易在 `imports_test`、Reporting、数据库导出之间重复造代码。

## 1. 为什么需要统一 Excel 契约

Excel 是人工审阅、临时数据交换和线下交付最常用的格式之一。如果每个平台都自己生成一个表：

```text
小红书.xlsx 一套列
抖音.xlsx     一套列
Excel 导入     又一套列
AI 打标结果    再一套列
```

后面的标签、报告、人工筛选都会不断写平台分支。

当前原则是：**Provider 私有结构先变成 Canonical/统一记录，再由一份共享 Excel 导出实现生成 `UnifiedDataExcelV1`。**

## 2. 一条文件链路怎么走

离线模式最常见的完整流程：

```text
输入 Excel
→ Reader / 字段映射
→ 归一化与关键词清洗
→ 稳定身份去重
→ 统一 JSONL / Record
→ 可选 AI 打标
→ UnifiedDataExcelV1
→ 可选 report.md + report.docx
```

这些步骤可以单独调用，也可以由 `imports_test.run_all()` 串起来。

默认离线处理不要求 PostgreSQL；显式开启写库后才进入正式 Import Batch / Ingestion 流程。

## 3. Excel 导入和正式数据库写入是两层

### 3.1 读取/清洗层

负责：

- 读取 Excel；
- 识别当前支持的输入 Profile；
- 清理文本/关键词；
- 把平台字段映射为统一记录；
- 建立稳定 `platform + external_content_id` 身份；
- 输出可供后续步骤使用的数据。

这层不应该直接手写 `INSERT contents`。

### 3.2 正式入库层

显式数据库模式使用：

```text
Input Artifact
→ Processing Import Batch
→ ingestion.import-excel.v1 Job
→ Worker
→ Canonical
→ Relevance
→ Content Ingestion
→ PostgreSQL
```

详细见 [`数据入口与统一入库.md`](数据入口与统一入库.md)。

## 4. UnifiedDataExcelV1 是什么

可以把它理解成：**系统统一的“可给人看的数据明细表”。**

它既可以装未打标的统一内容，也可以装已经带 Analysis 的内容，但字段顺序、基础格式、安全规则由共享 Exporter 管理。

不要：

- 在 `tikhub_test` 重新写一套 openpyxl 列；
- 在 `imports_test` 再维护另一套样式；
- 在数据库 Export Job 再定义第三套字段名字。

具体字段以共享 Exporter 代码和测试为准，本文不复制一份容易过期的完整列清单。

## 5. Raw Excel 和报告不是一回事

统一 Excel 的目标是**数据完整、可筛选、可继续处理**。

舆情报告的目标是**把数据汇总成适合阅读和汇报的视图**。

因此：

```text
UnifiedDataExcelV1
→ 是数据交付/审阅格式

report.md / report.docx
→ 是统计与视觉报告
```

不要为了报告好看去删 Excel 明细，也不要把报告中的 Top N 当成原始数据被裁剪。

## 6. AI 打标后的 Excel 怎么处理无关数据

当前 AI V3 一次返回：

```text
relevance
voice_type
sentiment
labels
```

离线链路中，如果判定为无关：

- 不进入最终业务 JSONL/Excel/报告；
- checkpoint 保留最小处理决策，便于恢复；
- 原始输入/Raw 不因为业务过滤而被销毁。

正式数据库链路中，无关记录保留必要审计事实，并由 `contents.is_relevant` 让默认业务查询隐藏。

也就是说，“离线最终文件删除”与“数据库物理删除”不是同一个行为。

## 7. 发声类型在 Excel 里怎么理解

当前唯一业务字段是 `voice_type`，三类：

```text
professional_media       专业媒体/机构发声
influencer_self_media    达人/自媒体发声
ordinary_user            普通用户发声
```

Excel 可以把它翻译成中文给人看，但不要再派生并保存一个平行的“是否用户发声”布尔列作为第二事实。

## 8. 大文件为什么不用 openpyxl 单元格逐条做所有业务计算

`openpyxl` 适合：

- 读写 `.xlsx`；
- 样式；
- 公式/工作簿结构；
- 流式只读/只写场景。

它不应该承担：

- Provider 解析；
- 数据库去重；
- AI 调用；
- 大量业务分组计算的全部职责。

当前离线流程会把“文件 IO”和“业务记录处理”拆开。处理九万行这类数据时，真正影响性能的通常还包括字符串归一化、去重、LLM 调用和输出，而不是只看 Excel 库本身。

## 9. imports_test 怎么用

`imports_test` 是人工调试入口，不是第二套业务实现。

原则：

```text
配置本地路径/开关
→ 调正式 Reader/清洗/去重/AI/Exporter/Reporting
→ 每个步骤可以单独运行
→ run_all() 可以串联
```

默认数据库写入关闭。这样可以在本地快速验证文件处理，又不会意外改业务库。

具体参数和入口以目录内 README/`test.py` 当前代码为准。

## 10. tikhub_test 为什么也能导统一 Excel

`tikhub_test` 用来真实调试五个平台 Provider。它拿到 Raw/Canonical 后，不应该自己拼一份 Excel，而是复用同一个 Unified Exporter。

这样才能保证：

```text
TikHub 调试导出
Excel 导入后的导出
正式数据库 Export Job
```

最终都使用相同的业务列语义。

## 11. 正式数据库 Export Job

当前 Reporting Domain 已有正式 PostgreSQL 表：

```text
reporting_exports
reporting_export_items
```

流程：

```text
用户提交导出
→ 创建 reporting.export-excel.v1 Job
→ 冻结本次 export_items 内容集合
→ Worker 读取统一数据
→ 共享 Exporter 生成 Excel
→ ArtifactService 保存文件
→ reporting_exports 记录终态与 artifact_id
```

为什么要冻结 `reporting_export_items`？

如果导出十万条数据要跑几分钟，而内容在这几分钟内还在更新，只靠“最后再执行一次查询”会让导出内容不可复现。冻结的是“本次要导哪些 Content ID”，不是把整行数据复制到另一张大表。

## 12. Excel 结果怎么继续生成报告

统一 Excel 可以继续进入离线 Reporting：

```text
UnifiedDataExcelV1
→ 统计上下文
→ Markdown 模板
→ report.md
→ Word Renderer
→ report.docx
```

Word 报告的细节见 [`Word舆情报告.md`](Word舆情报告.md)。

## 13. 常见误区

### “只要 Excel 列一样，就是同一个契约”

不对。还要保持：

- 字段业务语义；
- 空值语义；
- 时间格式；
- 平台身份；
- Analysis 字段含义；
- 安全/公式注入处理；
- 排序和稳定输出。

### “AI 过滤掉无关数据，就应该把数据库记录 DELETE”

不对。离线业务结果可以不输出无关数据；正式数据库仍需要保留必要来源/分析审计，并通过默认查询过滤。

### “报告只展示 Top 8，所以 Excel 也保留 Top 8”

不对。报告是展示投影，统一 Excel 继续保留完整明细。

## 14. 主要代码入口

| 能力 | 位置 |
| --- | --- |
| Excel 手工调试 | `backend/src/aima_ugc/adapters/providers/imports_test/` |
| TikHub 调试 | `backend/src/aima_ugc/adapters/providers/tikhub_test/` |
| Analysis | `backend/src/aima_ugc/modules/analysis/` |
| 正式 Export Domain | `backend/src/aima_ugc/modules/reporting/` |
| 离线 Excel/Word Reporting | `backend/src/aima_ugc/platform/reporting/` |
| Import Batch | `backend/src/aima_ugc/modules/ingestion/` |

精确字段、函数名和参数必须以当前代码/测试为准。

## 15. 深入阅读

- 统一入库：[`数据入口与统一入库.md`](数据入口与统一入库.md)
- AI：[`AI舆情分析与打标.md`](AI舆情分析与打标.md)
- Word：[`Word舆情报告.md`](Word舆情报告.md)
- 数据与存储原则：[`../blueprint/03-数据库与文件存储.md`](../blueprint/03-数据库与文件存储.md)

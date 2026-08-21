# Excel 导入、导出与离线处理

这篇文档把几件名字很像、实际职责不同的事情拆开：

```text
Excel 导入      把外部文件读成系统数据
统一 Excel 导出 把系统数据导成固定审阅格式
离线 AI/报告    在文件链路上继续处理，不一定写数据库
正式 Export Job 从 PostgreSQL 冻结内容版本后生成可下载 Artifact
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

当前原则是：**Provider 私有结构先变成 Canonical/统一记录，再由共享 Excel Exporter 生成统一数据表。**

## 2. 一条离线文件链路怎么走

常见流程：

```text
输入 Excel
→ Reader / 字段映射
→ 归一化与关键词清洗
→ 稳定身份去重
→ 统一 JSONL / Record
→ 可选 AI 打标
→ 统一 Excel
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
→ 规则 Relevance
→ Content Ingestion
→ PostgreSQL
```

详细见 [`数据入口与统一入库.md`](数据入口与统一入库.md)。

## 4. 统一 Excel 是什么

可以把它理解成：**系统统一的“可给人看的数据明细表”。**

它既可以装未打标的统一内容，也可以装已经带 Analysis 的内容，但字段顺序、基础格式、安全规则由共享 Exporter 管理。

不要：

- 在 `tikhub_test` 重新写一套 openpyxl 列；
- 在 `imports_test` 再维护另一套样式；
- 在正式数据库 Export Job 再定义第三套同义字段。

具体字段以共享 Exporter 代码和测试为准，本文不复制一份容易过期的完整列清单。

## 5. 统一 Excel 和报告不是一回事

统一 Excel 的目标是：

> 数据完整、可筛选、可继续处理。

舆情报告的目标是：

> 把完整数据汇总成适合阅读和汇报的视图。

因此：

```text
统一 Excel
→ 数据交付/审阅格式

report.md / report.docx
→ 统计与视觉报告
```

不要为了报告好看去删 Excel 明细，也不要把报告中的 Top N 当成原始数据被裁剪。

## 6. AI 打标后的离线 Excel 怎么处理无关数据

当前 AI V3 一次返回：

```text
relevance
voice_type
sentiment
labels
```

离线链路中，如果 AI 判定：

```text
relevance = irrelevant
```

当前业务结果处理为：

- 不进入最终业务 JSONL/Excel/报告；
- checkpoint 保留恢复所需的最小处理决策；
- 原始输入/Raw 不因为业务过滤而被销毁。

正式数据库 Analysis 则把 `relevance` 保存进：

```text
analysis_content_results.relevance
```

这不是 `contents.is_relevant`。当前 `contents` 没有这个 AI 投影列。

所以“离线最终文件不输出”与“数据库物理删除 Content”完全不是一回事。

## 7. 发声类型在 Excel 里怎么理解

当前唯一业务字段是 `voice_type`，合法机器值是：

```text
user_voice
creator_marketing
brand_official
dealer_promotion
media_information
other_organization
unknown
```

给人工看的 Excel 可以翻译成中文，例如：

```text
user_voice           → 真实用户发声
creator_marketing    → 创作者营销
brand_official       → 品牌官方
dealer_promotion     → 经销商/门店推广
media_information    → 媒体资讯
other_organization   → 其他机构
unknown              → 无法可靠判断
```

不要再派生并保存一个平行的“是否真实用户发声”布尔列作为第二业务事实。真实用户发声就是：

```text
voice_type = user_voice
```

完整分类规则仍以当前 V3 Prompt 为准。

## 8. 大文件为什么不让 openpyxl 承担所有业务逻辑

`openpyxl` 适合：

- 读写 `.xlsx`；
- 样式；
- 公式/工作簿结构；
- 流式只读/只写场景。

它不应该承担：

- Provider 解析；
- 数据库去重；
- AI 调用；
- 全部业务分组计算。

当前离线流程把“文件 IO”和“业务记录处理”拆开。处理大量数据时，真实性能还会受到字符串归一化、去重、LLM 调用和输出方式影响，不能只看 Excel 库本身。

## 9. `imports_test` 怎么用

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

## 10. `tikhub_test` 为什么也能导统一 Excel

`tikhub_test` 用来真实调试五个平台 Provider。它拿到 Raw/Canonical 后，不应该自己拼一份 Excel，而是复用共享导出能力。

目标是让：

```text
TikHub 调试导出
Excel 离线处理导出
正式数据库 Export Job
```

尽可能共享相同的数据语义，而不是三套同名不同义的列。

## 11. 正式数据库 Export Job

当前 Reporting Domain 的正式 PostgreSQL 表：

```text
reporting_data_exports
reporting_data_export_items
```

正式 Job 类型：

```text
reporting.content-export-excel.v1
```

流程：

```text
用户提交导出请求
→ 创建 reporting_data_exports + Job
→ 冻结 reporting_data_export_items
   （content_id + content_version + ordinal）
→ Worker 读取冻结内容版本
→ 共享 Exporter 生成 Excel
→ ArtifactService 保存文件
→ reporting_data_exports 关联 artifact_id / stats / completed_at
```

### 为什么要冻结 Content Version

假设导出十万条数据要跑几分钟，而这几分钟里 Content Current 还在更新。

如果只保存 Content ID，然后执行时永远读取“最新版本”，同一次导出的业务内容可能随执行时刻变化。

因此当前冻结：

```text
content_id
+ content_version
+ ordinal
```

它不是把整行内容复制到 Reporting 表，而是保存“这次导出明确针对哪一版 Content”。

## 12. AI relevance 在正式导出里怎么用

HTTP `ContentFilterSnapshot` 当前支持 `relevance` 筛选。用户/调用方可以在创建内容选择/导出请求时显式约束：

```text
relevant
irrelevant
```

不要在文档里假设系统永远默认排除某一类；默认筛选行为必须以当前调用方和 Query Service 实现为准。

## 13. Excel 结果怎么继续生成报告

统一 Excel 可以继续进入离线 Reporting：

```text
统一 Excel
→ 统计上下文
→ Markdown 模板
→ report.md
→ Word Renderer
→ report.docx
```

Word 报告的细节见 [`Word舆情报告.md`](Word舆情报告.md)。

## 14. 常见误区

### “只要 Excel 列一样，就是同一个契约”

不对。还要保持：

- 字段业务语义；
- 空值语义；
- 时间格式；
- 平台身份；
- Analysis 字段含义；
- 安全/公式注入处理；
- 排序和稳定输出。

### “AI 判无关，就应该 DELETE 数据库 Content”

不对。离线业务结果可以不输出；正式 Analysis 保存 `relevance` 事实，Raw/Content 来源不能因为一次模型结论被直接销毁。

### “报告只展示 Top 8，所以 Excel 也只保留 Top 8”

不对。报告是展示投影，统一 Excel 继续保留完整明细。

### “正式 Export 已经有 token/cost 等 Analysis 数据库列”

不对。当前 `analysis_content_results` 没有这些成本列，不能从离线 LLM 成本能力推断数据库 Schema。

## 15. 主要代码入口

| 能力 | 位置 |
| --- | --- |
| Excel 手工调试 | `backend/src/aima_ugc/adapters/providers/imports_test/` |
| TikHub 调试 | `backend/src/aima_ugc/adapters/providers/tikhub_test/` |
| Analysis | `backend/src/aima_ugc/modules/analysis/` |
| 正式 Export Domain | `backend/src/aima_ugc/modules/reporting/` |
| 离线 Excel/Word Reporting | `backend/src/aima_ugc/platform/reporting/` |
| Import Batch | `backend/src/aima_ugc/modules/ingestion/` |

精确字段、函数名和参数必须以当前代码/测试为准。

## 16. 深入阅读

- 统一入库：[`数据入口与统一入库.md`](数据入口与统一入库.md)
- AI：[`AI舆情分析与打标.md`](AI舆情分析与打标.md)
- Word：[`Word舆情报告.md`](Word舆情报告.md)
- 数据与存储原则：[`../blueprint/03-数据库与文件存储.md`](../blueprint/03-数据库与文件存储.md)

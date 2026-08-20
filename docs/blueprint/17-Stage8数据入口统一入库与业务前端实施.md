# Stage 8 数据入口、统一入库与业务前端实施

> 适用范围：Stage 8 正式业务 API / 前端，以及 `imports_test` / `tikhub_test` 的可选数据库写入  
> 相关文档：[`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md)、[`03-数据库与文件存储.md`](03-数据库与文件存储.md)、[`04-后端任务API与前端.md`](04-后端任务API与前端.md)、[`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md)、[`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)、[`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md)、[`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md)、[`16-前端页面架构与Figma设计工作流.md`](16-前端页面架构与Figma设计工作流.md)

## 1. 本文负责什么

本文是 Stage 8 的**数据入口、统一入库、手工调试可选入库、首个业务前端纵切与实施顺序**的唯一详细长期事实源。

它解决以下问题：

1. 第一版产品以什么作为主要数据入口；
2. Excel、TikHub 和未来其他 Provider 如何在同一个 Canonical / Ingestion / PostgreSQL 体系汇合；
3. `imports_test` / `tikhub_test` 手工运行时怎样保持“文件优先可调试”同时允许显式写库；
4. 手工写库时对本地 PostgreSQL 的前置条件是什么；
5. 文件内去重与数据库跨来源去重各负责什么；
6. 最新 Figma/页面目标中的哪些能力已经有后端、哪些只具备底层能力、哪些尚未实现；
7. Stage 8 应按什么顺序开发，避免先批量做 API 或先批量画页面造成返工。

本文不复制 Canonical 字段、数据库列、OpenAPI 字段或 TikHub endpoint。机器事实形成后仍以当前 Contract、Migration、锁文件、代码和测试为准。

## 2. 当前机器事实与目标状态必须分开

Stage 8A 已建立 Unified Manual Ingestion Foundation；当前机器事实为：

- `imports_test` 仍保留人工 Excel 文件链，并支持一个人工 run 按显式顺序合并一个或多个 Excel：Excel → Canonical JSONL → 关键词清洗 → 稳定身份去重 → AI 打标 → Excel；默认 `WRITE_TO_DATABASE = False`，不要求 PostgreSQL；
- `imports_test` 显式 `write_to_database=True` 或单独调用 `ingest_database(run_dir=...)` 时，当前 Stage 8A 只复用正式 File Import bootstrap 写入 PostgreSQL Content；该数据库阶段发生在 AI 打标之前，成功 AI Analysis 目前仍只回写 JSONL/Excel，这是**当前机器限制而不是长期目标**；
- `tikhub_test` 五个平台 `run_*()` 默认 `write_to_database=False`，仍逐请求保存本地 Raw、Canonical、run summary 与 Excel；
- `tikhub_test` 显式 DB 模式要求正式 `provider_config_id`，复用 manual Collection Run/Scope、Provider Request/Attempt、Provider Dispatch、正式 Raw、Candidate-before-Mapper 和 fenced Ingestion；同一次 Provider 响应同时写本地调试 Raw 与正式 Raw Artifact，不为写库额外发送第二次 TikHub 请求；
- 正式 TikHub Collection/Scheduler/Worker 继续通过既有生产链进入 PostgreSQL；
- Excel Mapper 继续输出 Provider-neutral `CanonicalContentV1`；
- `ContentIngestionService` 是 Canonical Content/Comment 的统一生产摄取入口，Content 业务表仍只由 Content Owner Repository 写；
- `processing_import_batches` 已作为 Excel File Import 的最小业务父事实；
- `ProviderRequestV1/provider_requests` 已一般化为 Collection Scope / Import Batch 恰好一个来源父级；
- Excel File Import 使用真实 Input Artifact + Import Batch + import-parent Request/non-billable Attempt 建立来源链，不制造虚假的 Collection Run/Scope/Candidate，也不伪造 `provider_attempt_id/raw_artifact_id`；
- Stage 8B 已建立单文件 multipart Excel 上传、Batch/Import Job 查询、Keyword Pack 最小管理和系统全局
  Relevance 配置的 Pydantic HTTP Contract；固定 OpenAPI 与 Orval Fetch Client 由同一生成链维护；
- `ingestion.import-excel.v1` 已注册到既有 PostgreSQL Job Runtime/Worker：HTTP 只保存 Artifact 并在同一
  PostgreSQL 事务创建 Job、Batch 和 Artifact 关联，Worker 从冻结输入执行正式 Stage 8A 链；
- 同一个 Provider-neutral Relevance Service 已接入 Excel 与 TikHub；Collection Run/Import 创建时冻结全局
  Pack/Config 版本与有效关键词，TikHub 最终未命中保留 `filtered` Candidate 账本而不写 Content；
- Stage 8B 仍没有正式 Vue 页面、Batch 列表/KPI/Cursor Read Model、Content Center 或 TikHub 补采 UI。

因此：**Stage 8A Foundation 与 Stage 8B Import HTTP/Job/Relevance 产品化已经是机器事实；正式运行中心
页面及其列表/KPI/Cursor Query 仍属于 Stage 8C，不得把生成 Client 冒充页面已经实现。**

## 3. 已确认的第一版产品数据入口

第一版产品固定采用：

```text
Excel 手工导入 = 主要业务数据入口
TikHub          = 辅助发现 / 补漏 / 补充详情与评论
未来其他来源    = 继续通过 Provider Adapter / Mapper 接入
```

这描述的是**产品数据入口优先级**，不是说 Excel 文件成为业务数据库。

PostgreSQL 仍然是唯一业务事实库：

```text
Excel / TikHub / 官方 API / Apify / 自建采集 / 历史文件
        ↓
各自 Reader / Adapter / Mapper
        ↓
CanonicalContentV1 / CanonicalCommentV1
        ↓
ContentIngestionService
        ↓
PostgresContentRepository
        ↓
PostgreSQL Current / Version / Metric / Coverage
```

`02-采集系统与数据标准化.md` 中 TikHub 的关键词滚动发现、话题、账号、热榜、搜索建议等仍然是**Collection 子系统启用时的采集策略**；它们不再表示第一版产品整体的数据入口优先级高于 Excel。

## 4. Canonical 之后只有一套数据库写入代码

不同来源的差异必须在 Canonical 之前结束。

### 4.1 Excel

```text
Excel 文件
→ Excel Reader
→ Excel Mapper
→ Canonical
→ 相关性清洗 / 稳定身份去重
→ 统一 Ingestion
→ PostgreSQL
```

Stage 8A 的显式数据库阶段不会复制 Reader/Mapper/Filter/Dedup；它把原始 XLSX 保存为 Input Artifact，建立 Processing / Import Batch 与 import-parent Provider Request/non-billable Attempt，再把去重后的 `UnifiedContentRecordV1.content` 绑定到真实 Request/Attempt/Artifact 后交给正式 Ingestion。

人工多 Excel run 仍只有一套合并后的 Canonical/Filter/Dedup/Analysis/Export 文件链；合并顺序就是
配置顺序，同一稳定身份保留首次记录。数据库 opt-in 时不把多个原文件伪装成一个 Artifact：系统按
Canonical `source_value` 把全局去重后的保留记录分回来源文件，并为每个源 Excel 分别建立 Input
Artifact 与 Processing / Import Batch。当前一个 Batch 仍只引用一个 `input_artifact_id`，无需改变
Stage 8A Schema。

这些 Batch 按配置顺序独立提交；后续源文件失败不会回滚已经成功且可追溯的 Batch。修复失败原因后
允许从同一合并 run 重跑数据库阶段，正式内容身份和数据库唯一约束继续保证 Current 幂等收敛。

### 4.2 TikHub

```text
TikHub HTTP
→ Raw Artifact
→ TikHub Mapper
→ Canonical
→ 统一 Ingestion
→ PostgreSQL
```

`tikhub_test` DB 模式复用同一生产链，并通过一次 Transport 响应同时保留调试 Raw 与正式 Raw Artifact；禁止把已导出的 JSONL/Excel 再交给平行 DB Writer。

### 4.3 硬规则

禁止：

```text
ExcelDatabaseWriter
TikHubDatabaseWriter
OfficialApiDatabaseWriter
```

所有 Provider-neutral Canonical 最终都必须复用：

```text
ContentIngestionService
→ PostgresContentRepository
```

以后增加官方 API、Apify、自建采集器、其他 Excel Profile 或历史导入时，只增加必要的 Reader/Adapter/Mapper 和来源证据，不增加第二套 Content 业务表写入逻辑。

## 5. 文件和数据库同时保留，但职责不同

第一版手工采集与正式导入都遵循：

```text
文件 = 原始证据 / 调试产物 / 可重放输入 / 人工审阅派生物
数据库 = 业务事实、统一 Current、历史、查询和前端数据源
```

开启数据库写入以后，不能因为数据库写入成功就删除本次已经生成的 Raw/Canonical/JSONL/Excel 文件。

同样，也不能因为文件已经存在就把本地 `output/runs/` 当作正式业务数据库。

如果文件阶段成功而数据库写入失败：

- 已生成文件继续保留；
- 数据库阶段明确失败；
- 不把“文件已保存”冒充“业务已入库”；
- 修复数据库或来源链后允许幂等重试入库；
- 重试不能产生第二条同身份 Content/Comment。

## 6. 两层去重必须同时存在

### 6.1 批次内去重

`imports_test` 当前已有 Provider-neutral 稳定身份去重：

```text
(platform, external_content_id)
```

`tikhub_test` 当前也按平台稳定内容 ID / 评论 ID 避免同一次运行重复处理和重复付费。

这一层用于：

- 降低同批重复处理；
- 避免同一内容重复 AI；
- 避免同一帖子跨关键词重复详情/评论费用；
- 输出清晰的批次统计和冲突审计。

### 6.2 数据库跨来源收敛

数据库仍然必须执行最终业务身份收敛。

内容：

```text
(platform, external_content_id)
```

评论：

```text
(content_id, external_comment_id)
```

典型情况：

```text
上午 Excel 导入 xhs + note_123
→ 写入同一个 Content

下午 TikHub 再观察到 xhs + note_123
→ 更新同一个 Content 的 Current/Version/Metric/来源历史
→ 不创建第二条业务内容
```

因此“Excel 已经去重”不能成为绕过数据库唯一约束/Upsert 的理由；数据库层是跨批次、跨来源、跨时间的最终去重边界。

重复 Observation 的来源证据和历史不得因为业务内容收敛而被静默删除。

## 7. 采用方案 B：Processing / Import Batch 是用户可理解的业务父记录

Stage 8 固定采用方案 B：增加一个面向用户和页面的 **Processing / Import Batch（处理/导入批次）** 作为 Excel 主入口的业务执行父记录。

它不是新的内容事实库，也不替代现有 `collection_run`。

概念关系：

```text
Processing / Import Batch
│
├─ Source Excel Artifact
│
├─ Import execution
│   ├─ read / map
│   ├─ relevance filter
│   ├─ batch deduplicate
│   └─ database ingestion
│
├─ downstream Job（能力真正产品化后）
│   └─ Analysis 等
│
└─ optional supplement
    └─ TikHub Collection Run
```

规则：

- Batch 只保存执行身份、来源、阶段、统计、错误摘要、关联 Job/Run/Artifact 等业务执行事实；
- Batch 不复制 `contents/comments` 业务字段；
- 最终 Content/Comment 仍只归 Content Owner；
- TikHub 补采继续复用 Collection Run，不复制一套 TikHub Batch；
- 一个 Batch 可以没有 TikHub 补采；
- TikHub 补采不是 Excel 数据入库成功的必要条件。

Stage 8A 已将机器结构冻结为 `processing_import_batches`；Stage 8B 沿用该结构，只保存 `id`、`input_artifact_id`、可空唯一 `job_id`、`status`、最小 `stats`、`error_summary` 与创建/开始/结束时间，Owner 仍为 `ingestion`。同步人工入口继续允许 `job_id = null`；Stage 8B HTTP 入口则在同一事务中绑定持久 Job，不为未来页面预建字段。

因此一个多 Excel 人工 run 对应多个最小 Import Batch，每个 Batch 对应一个原始 Excel Artifact；
“一个人工 run”不是数据库新增父表，也不把多个文件塞进单个 `input_artifact_id`。某个源文件的记录
如果全部被相关性过滤或全局去重移除，该文件的 Batch 仍可成功且 `rows_ingested=0`，以保留输入与
执行事实。

## 8. 来源追溯不能为了文件导入而降级

当前 PostgreSQL Content 历史要求合法：

```text
provider_attempt_id
+
raw_artifact_id
```

因此正式 Excel 入库和手工调试可选入库都必须先解决**文件来源如何进入正式来源链**。

Stage 8A 已采用并验证以下最小实现：

```text
Input Excel Artifact
→ ProcessingImportBatch
→ ProviderRequestV1(import_batch_id=...)
→ non-billable ProviderAttempt
→ Attempt.raw_artifact_id = Input Artifact
→ Canonical Source
→ ContentIngestionService
```

对应 `provider_requests` 约束为：

```text
scope_id        nullable FK collection_scopes
import_batch_id nullable FK processing_import_batches
CHECK exactly_one(scope_id, import_batch_id)
UNIQUE(scope_id, request_fingerprint)
UNIQUE(import_batch_id, request_fingerprint)
```

固定原则仍是：

1. Excel 源文件/受控输入必须有不可变 Artifact/来源证据；
2. 文件读取/导入必须形成可追溯执行 Attempt/等价正式来源事实；
3. Canonical 写入前补齐 Content Owner 所需的合法来源引用；
4. 不允许给 Excel 伪造随机 `provider_attempt_id/raw_artifact_id`；
5. 不允许删除 `PostgresContentRepository` 的来源校验来“方便导入”；
6. 不创建第二套 FileAttempt/FileArtifact 来源体系；
7. File Import 不制造虚假的 Collection Run/Scope/Candidate，逐行定位继续保存在 Canonical `source.item_locator`。

## 9. `imports_test` / `tikhub_test` 永久保留

两个目录继续作为人工调试/验证入口，不删除。

### 9.1 默认模式：只写文件

当前行为保持兼容：

```text
imports_test: WRITE_TO_DATABASE = False
tikhub_test: write_to_database = False
```

含义：

- 不要求 PostgreSQL 可用；
- 不启动 API/Scheduler；
- 不写业务数据库；
- 继续保存既有 Raw/Canonical/JSONL/Excel/run summary；
- 调试逻辑继续复用生产 Reader/Mapper/Decision/Analysis/Exporter。

### 9.2 可选模式：文件 + 数据库

`imports_test`：

```python
run_all(write_to_database=True)
# 或在同一个 run 上显式调用
ingest_database(run_dir=...)
```

`tikhub_test` 五个平台：

```python
write_to_database=True
provider_config_id=<正式 provider_configs.id>
```

硬规则：

- 文件仍然保留；
- `imports_test` 不直接写 SQL；
- `tikhub_test` 不直接写 SQL；
- 二者都不得新建自己的 Content/Comment Repository；
- 二者最终复用 ContentIngestionService/Content Owner Repository；
- `tikhub_test` 开启写库后复用既有正式 Collection/Provider/Raw/Candidate/Ingestion 执行链，不把调试 JSONL/Excel 再走一套生产回灌路径；
- `imports_test` 开启写库后复用正式 File Import/Processing Batch 执行入口；调试脚本只准备参数并调用正式实现；
- `imports_test` 多文件 run 先全局过滤/去重，再按唯一源文件名分别调用正式 File Import 入口；同名文件在付费或写库前 fail closed，避免来源绑定歧义；
- 数据库阶段失败必须向调用方暴露，不静默退回 file-only 成功。

### 9.3 已批准的后续数据库完整写入目标

一旦 Blueprint 15 的正式 Analysis Persistence 通过独立 L3 Change 落地，`imports_test`/正式 Import Job 的数据库模式不能停留在“只写 Content”。目标链路固定为：

```text
File/TikHub/其他来源
→ Canonical
→ ContentIngestionService
→ Content Owner PostgreSQL
→ stable content_id
→ Analysis Service / Validator
→ Analysis Owner PostgreSQL
→ JSONL / Excel（需要时）
```

规则：

- 同一份 Validator 成功 Analysis 同时服务文件输出和数据库持久化，不能二次调用模型；
- Content 成功但 Analysis DB 写入失败时，必须让 Batch/Job/人工调用方看到 partial/failed Analysis 阶段，并允许幂等补写；
- file-only 模式仍不要求 PostgreSQL，也不因为未来 Analysis DB 存在而改变；
- 当前 Stage 8A 不补做这部分 Schema/Migration，本节只把后续开发目标固化，防止未来实现遗漏。

## 10. 手工写库模式的本地数据库前置条件

显式数据库模式固定假设：

> 开发者机器上已经有一个可访问的 PostgreSQL 18 开发数据库实例，通常就是开发者已经启动的本地数据库容器。

调试入口只负责：

```text
读取现有 AIMA_DB_* 配置
+ Secret 边界
→ 连接
→ 校验可用性/Stage 8A 必要 Schema
→ 执行正式摄取
```

调试入口禁止：

- 自动 `docker compose up/down`；
- 自动创建/删除数据库容器；
- 自动执行 Alembic Migration；
- 为了方便修改宿主机 Docker 配置；
- 数据库不可用时静默退回“看起来成功”的文件模式。

`tikhub_test` DB 模式还必须显式提供稳定 `provider_config_id`，并在发送前验证正式 Provider Config 已启用、`provider=tikhub`，且其 `base_url`/Secret 与本次调试 `.env` 实际使用的 Base URL/API Key 一致。

如果开发数据库未启动、连接失败或 Schema 不满足当前代码要求：

- DB stage 明确失败；
- 已生成文件保留；
- 给出可定位错误；
- 不把文件阶段成功冒充数据库阶段成功。

Migration 仍由仓库既有 Alembic 入口显式执行，调试代码不代替 Migration 管理。

## 11. 正式网页 Excel 导入链

Stage 8B 当前后端入口为：

```text
Browser / API Client
→ 上传/选择 Excel
→ FastAPI
→ Processing / Import Batch
→ Source Artifact
→ 持久化 Job
→ 正式 Excel Reader / Mapper
→ Canonical
→ 相关性过滤
→ 稳定身份去重
→ 合法来源链
→ ContentIngestionService
→ PostgresContentRepository
→ PostgreSQL
→ Batch / Job Query API
→ OpenAPI / Orval Client
```

长文件处理不能在单次 HTTP 请求生命周期内同步跑完。

HTTP 只负责：

- 创建 Batch/上传输入；
- 返回 Batch/Job 身份；
- 查询状态和统计；
- 查询错误摘要；

Worker 执行实际文件处理和数据库摄取。

当前上传仅接受一个 `.xlsx` `file`，Router 不处理工作簿。ArtifactStore 的临时/正式 storage key 都由
系统生成；原文件名只作 Batch 审计元数据，Worker 在 Windows/Linux 均使用固定临时名，避免宿主路径
规则改变处理语义。Stage 8B 已生成 Client，但 Vue 页面仍属于 Stage 8C/8F。

## 12. AI 的 Stage 8 边界

P1 已经存在可复用的 Analysis Service、Prompt/Taxonomy、Validator、LLM Adapter、checkpoint、费用审计和离线 JSONL 回写；Stage 8A 也已经能把 Content 写入 PostgreSQL。

当前机器事实仍是：正式 Analysis PostgreSQL DDL/Migration/Repository/Job/HTTP Contract 尚未落地，`imports_test(write_to_database=True)` 当前只持久化 Content，AI 成功结果随后进入 JSONL/Excel。

已经批准的目标状态为：

```text
PostgreSQL Content
→ stable content_id

Analysis Service
→ Validator success
→ Analysis Owner Repository
→ PostgreSQL Analysis Result + Label Pairs
```

因此后续硬门禁：

- Stage 8 不把 AI 标签塞进 `contents` 表；
- 正式数据库模式最终必须同时拥有 Content 与成功 Analysis，不能让 Excel 成为唯一带标签的数据事实；
- Analysis Persistence 必须作为独立 L3 Change 落 DDL/Migration/Repository/Job/事务/幂等/current Analysis，并同步 Blueprint 03/15；
- 在 Analysis Persistence 落地前，页面不能把 AI 数据库状态冒充已实现，也不能通过前端 Mock 替代；
- **任何依赖数据库 AI 标签的正式报告、Dashboard、跨批次趋势或 AI 页面，在 Analysis Persistence + current Analysis Query Read Model 完成前不得进入实现闭环。**

报告数据源固定按场景选择：

```text
imports_test 本次离线 run 报告
→ labeled_data.xlsx

正式系统报告 / 跨批次趋势 / Dashboard
→ PostgreSQL Report Read Model
```

即使 `imports_test` 开启 `write_to_database=True`，本次 run 的离线报告也继续读取本次 Excel 快照；禁止根据数据库是否启动自动切换报告源。数据库正式报告通过 Query Repository/Read Model 读取 Content + current Analysis 等事实，再适配为统一 Report Dataset，复用 Blueprint 13 的同一 Renderer/Markdown 模板。

本次只固化目标，不在 Stage 8A 现有代码中偷偷补 Analysis 表或迁移，也不重排 8B—8F 编号。后续如果将 Analysis Persistence 产品化纳入某个 Stage 8 正式单元，必须先建立独立 L3 Change 并以当时最新 main 重新确认范围。

## 13. 第一张正式页面：采集运行中心

当前选定的第一个正式业务页面为：

```text
采集运行中心
```

首版页面从用户角度统一看“数据处理/采集运行”，但后端仍保持正确 Owner：

- Excel 主入口对应 Processing/Import Batch；
- TikHub 补采对应 Collection Run；
- 内容结果对应 Content Query；
- Job 对应 PostgreSQL Job Runtime；
- 后续 Analysis 对应 Analysis Owner。

页面不能通过一个万能表把这些 Owner 混成一套数据库模型。

## 14. Figma / 页面能力映射门禁

任何正式 Figma Frame 在开发前，都必须把用户可见能力逐项映射为：

```text
IMPLEMENTED
= 后端机器能力与必要 Contract 已存在

REUSE_BUT_PRODUCTIZE
= 底层正式生产能力存在，但缺网页 API/持久化 Job/Query/编排等产品化闭环

PLANNED
= 页面目标存在，但后端当前没有对应正式能力
```

只有纯视觉状态可以不需要后端能力。

当前“采集运行中心”目标页的基线映射：

| 页面能力 | 当前状态 | Stage 8 处理 |
| --- | --- | --- |
| Excel Reader / Mapper | REUSE_BUT_PRODUCTIZE | 复用，不重写 |
| 关键词相关性清洗 | REUSE_BUT_PRODUCTIZE | 复用，不重写 |
| 稳定身份批次去重 | REUSE_BUT_PRODUCTIZE | 复用，不重写 |
| PostgreSQL Content Ingestion | IMPLEMENTED | Stage 8A 已补 File Import 合法来源桥接，不新建 Writer |
| TikHub 正式 Collection → PostgreSQL | IMPLEMENTED | 保持；作为辅助补采 |
| `imports_test` 文件输出 | IMPLEMENTED | 永久保留 |
| `tikhub_test` 文件输出 | IMPLEMENTED | 永久保留 |
| `imports_test` 可选写库 | IMPLEMENTED | Stage 8A 已实现，默认仍 file-only |
| `tikhub_test` 可选写库 | IMPLEMENTED | Stage 8A 已实现，复用正式 Collection |
| Processing / Import Batch | IMPLEMENTED | Stage 8A 已建立最小机器结构 |
| 网页可调用的 Excel 上传 API | IMPLEMENTED | Stage 8B 已交付 multipart 202 Contract/Orval；Vue 入口在 8C |
| Batch 详情 | IMPLEMENTED | Stage 8B 已交付按 ID 查询 |
| Batch 列表 | IMPLEMENTED | Stage 8C Query Read Model；稳定 Cursor、状态/阶段/时间/ID 筛选 |
| 阶段进度/统计 | IMPLEMENTED | Stage 8B 按 Batch ID 返回阶段、固定计数与关联 Job |
| KPI：处理中/今日完成/今日导入 | IMPLEMENTED | Stage 8C PostgreSQL Summary；今日按 Asia/Shanghai |
| 筛选/分页 | IMPLEMENTED | Stage 8C HTTP 签名 Cursor/Query |
| Import Job 状态 | IMPLEMENTED | Stage 8B 按 ID 查询；8C 负责页面轮询 |
| 错误记录/安全摘要 | IMPLEMENTED | Stage 8B 固定 Error Contract/request_id 与 Batch/Job 摘要 |
| 查看处理内容 | REUSE_BUT_PRODUCTIZE | Stage 8D Content Query/API |
| AI 打标核心 | REUSE_BUT_PRODUCTIZE | 复用现有 Service/Prompt/Validator；正式 DB 模式最终必须持久化成功 Analysis |
| Analysis PostgreSQL Persistence | PLANNED | 独立 L3 Change；Result + Label Pairs + 幂等/历史/current Analysis |
| AI 数据库/页面状态 | PLANNED | Analysis Persistence + Query Read Model 完成前不得冒充已接入 |
| 正式数据库报告/跨批次趋势 | PLANNED | 先完成 Analysis Persistence，再建立 PostgreSQL Report Read Model；Renderer 继续复用 Blueprint 13 |
| TikHub 补采按钮 | PLANNED | Stage 8E |

以后 Figma 修改如果增加按钮、筛选项、状态或统计，必须先更新本能力映射/当前 Change，再决定是否需要 HTTP Contract、Query、Job、Schema 或只改前端。

## 15. Stage 8 固定采用 Contract-First Vertical Slice

不采用：

```text
先把所有后端 API 做完
→ 再设计整个前端
```

也不采用：

```text
先把所有 Figma 页面画完
→ 再让后端追着页面补接口
```

固定流程：

```text
业务目标
→ 页面信息结构 / 粗 Figma
→ UI → Backend Capability Matrix
→ 明确页面需要的数据和行为
→ Pydantic HTTP Contract
→ API/Contract Test
→ 固定 OpenAPI
→ Orval 生成 TypeScript Client
→ 后端 Service/Query 与正式 Figma/Vue 并行
→ 真实联调
→ E2E
→ 视觉验收
```

Figma 决定已确认视觉/交互目标；Pydantic/OpenAPI 决定 HTTP 数据语义；Vue/测试决定当前运行实现。

## 16. Stage 8 实施顺序

Stage 8 不作为一个巨型 PR 一次完成。按以下最小正式单元推进；每个单元仍必须重新从当时 main 事实判断是否已闭环。

### 8A：Unified Manual Ingestion Foundation

目标：先证明“手工文件/TikHub 调试数据最终可以安全、幂等地进入同一 PostgreSQL Content 体系”。

主要工作：

- 冻结 Processing / Import Batch 的最小业务边界；
- 结合当前 Schema 决定文件 Source Artifact / Attempt / Candidate 如何满足正式来源链；
- 不降低 `provider_attempt_id/raw_artifact_id` 等当前来源约束；
- 建立 File Import 正式执行 Service 边界；
- 复用现有 Excel Reader/Mapper/Filter/Dedup；
- 复用 ContentIngestionService/PostgresContentRepository；
- 建立 `imports_test` 默认文件-only + 显式数据库写入模式；
- 建立 `tikhub_test` 默认文件-only + 显式数据库写入模式，复用正式 Collection 运行链；
- 数据库模式假定本地 PostgreSQL 18 容器/实例已启动，调试代码不管理容器和 Migration；
- 证明 Excel 与 TikHub 同一内容 ID 最终收敛到同一 Content；
- 文件阶段成功、DB 阶段失败时可安全重试。

**当前状态：Stage 8A 机器实现、Migration、PostgreSQL 18 自动化验收与 Change 归档均已闭环。**

### 8B：Import HTTP / Job Productization

目标：把 8A 的正式 Import 能力暴露为浏览器可用的 Contract，而不是让网页调用调试脚本。

主要工作：

- 使用一个 `multipart/form-data` `file` 字段一步上传并创建 Import；文件流式保存为 Source Artifact，
  再由 Service/UoW 创建 Batch + Job 并返回 `202`，不建立先上传 Artifact 再创建 Import 的两步协议；
- `.xlsx` 文件本身最大 500 MiB，必须有界流式写入/读取，不把整个上传或 Artifact 载入内存；multipart
  解析依赖由根 Python 工程精确锁定，应用仍必须独立执行实际字节计数、请求体限制与 XLSX 安全校验；
- multipart HTTP 请求体最大 550 MiB；XLSX 中央目录声明的解压总大小最大 5 GiB、单成员最大 4 GiB、
  成员数最大 2,048，整体和单成员压缩比最大 100:1。资源上限超出返回统一 `413`，扩展名、ZIP/OOXML
  结构、加密/重复/不安全成员名或不支持压缩算法不合法返回统一 `422`；上传 Router 不解压整份文件；
- 复用 System Owner 现有 `keyword_packs`、`keywords`、`keyword_pack_items`，建立本阶段 Import
  所需的最小关键词写入/读取 HTTP Contract；
- 建立一个通过外键引用 Keyword Pack 的系统全局 Relevance 配置；Import/Collection 不允许按请求或
  Plan 覆盖，配置缺失时正式执行 fail closed；
- 关键词 HTTP 写入只接收原始文本，后端用 `trim → NFKC → casefold` 生成数据库唯一身份，并保留内部
  空白和 `-/_/·`；Relevance 匹配仍额外忽略这些字符，过滤等价词按 Pack 稳定顺序只执行一次；
- Import Job 与 Collection Run 创建时冻结全局 Pack 身份、版本与实际执行关键词快照；
- 把现有 Excel 关键词判定提取为 Provider-neutral Canonical Relevance Service，并接入正式
  Excel/TikHub 当前生产链；未通过的 TikHub Candidate 保留 Raw/账本，不写 Content；
- TikHub Search Canonical 未命中时，必须通过现有 Provider Runtime 最多请求一次 Detail 并重新映射后
  终判；Detail 命中则复用该次结果继续既有采集决策，最终未命中才记为 `filtered`，且不再请求
  Comment/Reply。Search 已命中时不为 Relevance 额外请求 Detail；
- 创建 Processing/Import Batch；
- 创建并查询持久化 Import Job；
- Import Job 每个 Attempt 最长 30 分钟，最大 10 次；每次从冻结的 Source Artifact 与 Relevance 快照
  重新执行完整导入，Heartbeat 不延长 Deadline，多次 Attempt 不累计处理中间进度；
- 重试保持整批事务回滚和稳定身份幂等，所有业务可见提交必须验证当前 Job Fence；单文件 500 MiB
  接受上限不构成 30 分钟完成或 ETA 承诺，连续超时在第 10 次后终态失败；
- Batch 状态、阶段、统计、错误摘要；
- 统一 HTTP 错误和 request_id；
- 固定 OpenAPI；
- 生成 Orval Client；
- API/Contract/PostgreSQL Integration 测试。

Stage 8B 不实现 Keyword Pack Vue 页面；本阶段生成的 Orval Client 供 Stage 8F 页面直接复用，不能
为提前展示页面而手写平行 Client。

跨 Attempt 的阶段/分块检查点和断点续跑是已识别的后续优化方向，不属于 Stage 8B。只有真实容量或
运行证据证明全量重试不能满足要求时，才能通过新的 L3 Change 冻结检查点 Contract、Schema/Migration、
分块事务与部分数据可见性、处理中间 Artifact 保留/清理、Fencing、幂等和回滚后实现；当前不得预建
未使用的检查点表、Service 或兼容字段。

**当前机器状态：上述 Stage 8B HTTP、Artifact、Batch/Job、Worker、全局 Relevance、TikHub 门禁、
Migration、固定 OpenAPI 与 Orval Client 已落地；是否达到正式闭环仍必须以对应 Active/归档 Change 的
最终 PR CI、Review、合并和合并后 main 新鲜证据为准。Stage 8B 没有实现 Vue 页面。**

### 8C：采集运行中心首个完整前后端纵切

目标：实现当前选定 Figma 的首个正式业务页面。

主要工作：

- App/Shared/Feature 最小前端骨架；
- Processing Batch 列表/详情 Query Read Model；
- 必要的 KPI、筛选、Cursor、状态；
- Job 轮询；
- Loading/Empty/Error；
- Feature API/Store；
- Vue 页面；
- Playwright E2E 可执行入口；
- Figma 视觉验收。

首版页面只展示真实后端已经提供的阶段/字段；未落地 AI 或其他目标能力不得用 Mock 冒充生产支持。

当前 Active Change 已实现上述列表、Summary、签名 Cursor、生成 Client、Feature API/Store、Vue 页面和
Playwright 机器能力；用户批准的 PNG 仅作为本 Stage 一次性视觉例外。是否正式闭环仍必须由最终 PR
Head CI、两阶段 Review、正常合并、Change 归档和合并后 `main` 新鲜验证共同证明。

### 8D：内容中心

目标：前端不区分 Excel/TikHub 来源读取统一 PostgreSQL Content。

主要工作：

- Content 列表 Query；
- Content 详情；
- 评论/coverage（已有数据时）；
- 来源/Batch/Run 过滤；
- Cursor；
- 统一时间与 64 位 ID；
- 从“采集运行中心 → 查看处理内容”跳转并带合法查询条件。

### 8E：TikHub 辅助补采

目标：TikHub 从独立后台能力变成可从业务上下文显式发起的辅助补充来源。

主要工作：

- 从 Batch/Content 上下文明确补采目标；
- 复用正式 Collection Run/Job；
- 不在 UI 暴露 Provider 私有 cursor/search_id/page 等；
- 通过 Capability 只暴露真实业务参数；
- 补采结果仍进入同一 ContentIngestionService/PostgreSQL；
- 页面能从 Batch 看到关联的补采 Run 状态。

### 8F：Keyword / Plan / Stage 8 Integration

目标：完成剩余 Stage 8 配置页和整体集成。

主要工作按已解决业务门禁推进：

- Keyword Pack Vue 页面，以及页面需要但 Stage 8B Import 最小 Contract 未覆盖的管理 API；
- Collection Plan 页面/API；
- Provider Config/Secret 写入只在安全边界批准后实现；
- App Shell；
- 跨页面 E2E；
- 文档/生成物一致性；
- 完整适用 CI；
- Stage 8 收口。

Alias 正式关系等尚未批准的业务语义仍不能由 Agent 静默选择；Discovery/Relevance 边界与正式关键词
数据库/匹配 normalization 已在 Stage 8B 固化。

## 17. Stage 8A 验收底线

8A 至少必须证明：

1. `imports_test` 默认运行仍完全不要求数据库；
2. `tikhub_test` 默认运行仍完全不要求数据库；
3. 两个调试入口的既有文件输出兼容；
4. 开启写库时，数据库不可用会明确失败且不会破坏文件产物；
5. 调试入口不自动启动/停止 PostgreSQL 容器，不自动执行 Migration；
6. Excel Mapper 和 TikHub Mapper 仍输出统一 Canonical；
7. Excel/TikHub 不增加平行数据库 Writer；
8. 数据库写入复用 ContentIngestionService/PostgresContentRepository；
9. 同一 `(platform, external_content_id)` 跨 Excel/TikHub/重复运行只形成一个当前 Content；
10. 更晚合法 Observation 仍可推进 Current/Version/Metric；
11. 文件来源具备合法、可审计、可重放的 Artifact/Attempt/来源链；
12. 不使用伪造来源 ID 绕过 PostgreSQL 外键/来源约束；
13. DB 写入失败后幂等重试不会制造业务重复；
14. 新 Migration 有 base→head、上一正式 Revision→head、downgrade/re-upgrade 与 `alembic check`；
15. `imports_test` 多 Excel run 按配置顺序合并、全局去重，并在数据库模式为每个源文件保留独立 Artifact/Import Batch；
15. 相关 Blueprint/API/测试说明与机器事实同步。

当前自动化已经覆盖以上 Stage 8A 机器行为；最终仍以实现 PR 的实际最新 head CI、Review、合并与合并后 main 验证作为闭环证据。

## 18. 文档同步规则

- 第一版数据入口优先级、Processing Batch、手工可选入库、Stage 8 子阶段变化：更新本文；
- Provider/Raw/Mapper/Canonical/Collection 通用来源链变化：按需同步 `02/08`；
- PostgreSQL Table/Owner/Migration/Artifact 变化：同步 `03` 与机器 Migration；
- HTTP Contract、错误、Cursor、Job API、Query 边界变化：同步 `04`、固定 OpenAPI、生成 Client 和 `docs/API接口说明.md`；
- Excel Workbook/Exporter 契约变化：同步 `13`；
- Analysis Prompt/Contract/数据库 Owner 变化：同步 `15`；
- Figma/页面组织/Design-to-Code 规则变化：同步 `16`；
- 具体页面只发生视觉调整且不改变长期规则时，不修改本文。

## 19. 最终固定原则

```text
Excel 是第一版主要数据输入，不是业务数据库
TikHub 是辅助补充，不是第二套数据模型

来源差异截止在 Mapper
Canonical 后只有一套 Ingestion
PostgreSQL 是唯一业务事实库
正式数据库模式最终同时持久化 Content 与成功 Analysis
文件证据和调试产物继续保留

imports_test / tikhub_test 永久保留
默认不写数据库
显式开启才写库
写库时假定本地 PostgreSQL 18 容器/实例已经启动
调试脚本不管理容器、不跑 Migration、不写 SQL

Stage 8A 已完成统一手工摄取 Foundation
Stage 8B 已建立 Import HTTP / Job / 全局 Relevance Productization
Stage 8C 当前实现第一个 Vue 采集运行中心页面；正式闭环后下一最小单元是 Stage 8D 内容中心
离线单批报告读 Excel；正式系统报告读 PostgreSQL Read Model
报告源显式选择，不按数据库可用性自动切换
不要用目标 UI 冒充后端已经存在
```

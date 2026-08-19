# Stage 8 数据入口、统一入库与业务前端实施

> 适用范围：Stage 8 正式业务 API / 前端，以及 `imports_test` / `tikhub_test` 的可选数据库写入  
> 相关文档：[`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md)、[`03-数据库与文件存储.md`](03-数据库与文件存储.md)、[`04-后端任务API与前端.md`](04-后端任务API与前端.md)、[`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md)、[`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)、[`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md)、[`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md)、[`16-前端页面架构与Figma设计工作流.md`](16-前端页面架构与Figma设计工作流.md)

## 1. 本文负责什么

本文是 Stage 8 的**数据入口、统一入库、手工调试可选入库、首个业务前端纵切与实施顺序**的详细长期事实源。

它负责：

1. 第一版产品的主要/辅助数据入口；
2. Excel、TikHub 和未来其他 Provider 如何收敛到同一 Canonical / Ingestion / PostgreSQL；
3. Processing / Import Batch 的业务定位；
4. File Import 与 TikHub 的合法来源链；
5. `imports_test` / `tikhub_test` 的 file-only 与 database 两种模式；
6. 手工数据库模式对 PostgreSQL 18、Schema 和 Provider Config 的前置条件；
7. 数据库跨批次/跨来源去重与历史保留；
8. Stage 8A—8F 的实施顺序和页面能力映射。

本文不复制 Canonical 字段、具体 TikHub endpoint、OpenAPI 字段或完整数据库 DDL。机器事实形成后，以当前 Contract、Migration、代码、锁文件和测试为准。

## 2. 当前阶段事实

### 2.1 已闭环

- Stage 1—7 已闭环；
- 临时 P1 已闭环；
- **Stage 8A：Unified Manual Ingestion Foundation 已完成代码实现和 PostgreSQL 18 验证，当前等待 PR 集成闭环。**

Stage 8A 当前机器事实：

- `processing_import_batches` 已由 forward Migration `20260820_0019` 建立；
- `ProviderRequestV1/provider_requests` 已一般化为 Collection Scope XOR Import Batch 双父级；
- Excel File Import 不伪造 Collection Run/Scope/Candidate；
- Excel 原始 XLSX 通过 `ArtifactService` 保存为 Input Artifact；
- Import Batch 通过真实 non-billable Provider Request/Attempt 绑定 Input Artifact；
- Canonical 后统一走 `ContentIngestionService → PostgresCompleteContentRepository → PostgresContentRepository`；
- `imports_test` 默认 file-only，显式 `write_to_database=True` 后调用正式 File Import bootstrap；
- `tikhub_test` 默认 file-only，显式数据库模式后复用正式 manual Collection Run/Scope、Provider Request/Attempt、ProviderDispatchService、Raw、Candidate-before-Mapper 和正式 Ingestion；
- TikHub DB 模式同一次外部响应同时保留本地调试 Raw 镜像并进入正式 Raw Artifact，不发第二次付费请求，不从 JSONL 二次回灌；
- 数据库/Schema 不可用时明确失败，不自动管理 Docker，不自动运行 Migration；
- 同一 Excel 重复导入、Excel→TikHub 跨来源、较新 Observation 更新、数据库失败后重试均已由真实 PostgreSQL 18 集成测试覆盖。

### 2.2 尚未实现

Stage 8A 完成不代表以下能力已经存在：

- Stage 8B 文件上传/Import Batch HTTP API；
- Stage 8C 采集运行中心正式页面/API；
- KPI/Cursor 页面查询；
- Content Center；
- TikHub 补采按钮；
- Keyword Pack / Collection Plan 正式业务页面；
- Analysis 数据库页面；
- 新认证/权限系统；
- 预算系统；
- Redis/Kafka/RabbitMQ；
- 正式 Vue/Figma 页面实现。

这些能力必须按后续最小正式单元继续开发，不能把底层 Foundation 冒充成产品页面已经完成。

## 3. 第一版产品数据入口

固定采用：

```text
Excel 手工导入 = 主要业务数据入口
TikHub          = 辅助发现 / 补漏 / 补充详情与评论
未来其他来源    = 继续通过 Provider Adapter / Mapper 接入
```

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
Content Owner Repository
        ↓
PostgreSQL Current / Version / Metric / Coverage / Source History
```

Excel 文件、调试 JSONL、Raw、导出 Excel 都不是业务数据库。

## 4. Canonical 之后只有一套业务数据库写入

### 4.1 Excel

P1 文件处理链保持：

```text
Excel 文件
→ Excel Reader
→ Excel Mapper
→ CanonicalContentV1
→ 关键词相关性清洗
→ 稳定身份批次去重
→ UnifiedContentRecordV1 JSONL
```

Stage 8A 显式数据库阶段：

```text
原始 XLSX
→ ArtifactService 保存 Input Artifact
→ ProcessingImportBatch
→ import-parent Provider Request / non-billable Attempt
→ Attempt.raw_artifact_id = Input Artifact
→ 读取既有 UnifiedContentRecordV1.content
→ 用真实 Request / Attempt / Artifact 绑定 Canonical Source
→ ContentIngestionService
→ PostgresCompleteContentRepository
→ PostgresContentRepository
→ PostgreSQL
```

数据库阶段**不复制 Excel Reader/Mapper/Filter/Dedup**，也不把调试脚本变成第二套生产实现；它消费前一文件阶段已经产生并通过 Contract 的 Provider-neutral 内容记录，并将其来源绑定到正式 Import 执行事实。

### 4.2 TikHub

默认 file-only：

```text
TikHub HTTP
→ 本地调试 Raw
→ 生产 Mapper
→ 本地 Canonical
→ 本地 Excel / run summary
```

显式 DB 模式：

```text
manual Collection Run / keyword Scope
→ Provider Request / billable Attempt
→ ProviderDispatchService
→ 同一次 TikHub HTTP
→ 本地调试 Raw 镜像
+ 正式 Raw Artifact
→ Candidate-before-Mapper
→ 生产 Mapper
→ Canonical
→ 本地 Canonical / Excel
+ 正式 ContentIngestionService
→ PostgreSQL
```

禁止做成：

```text
先跑 tikhub_test
→ 导出 JSONL
→ 再写 TikHubDatabaseWriter
→ PostgreSQL
```

### 4.3 硬规则

禁止新增：

```text
ExcelDatabaseWriter
TikHubDatabaseWriter
OfficialApiDatabaseWriter
imports_test 私有 Repository
tikhub_test 私有 Repository
```

所有 Provider-neutral Canonical 最终复用 Content Owner；调试入口只负责配置、调用和展示结果。

## 5. 文件与数据库职责

```text
文件
= 原始证据 / 可重放输入 / 调试产物 / 人工审阅派生物

PostgreSQL
= 唯一业务事实 / Current / History / Query / Frontend Source
```

数据库模式开启后：

- 既有文件仍保留；
- 不因为 DB 成功删除文件；
- 不因为文件存在就把 `output/runs` 当数据库；
- 文件阶段成功而 DB 阶段失败时，文件继续保留；
- DB 阶段必须报告失败；
- 修复 DB/Schema/输入后允许重试；
- 重试不允许制造第二条同身份业务内容。

## 6. 两层去重

### 6.1 批次内

Excel P1 去重：

```text
(platform, external_content_id)
```

TikHub 调试同一运行内也按稳定 Content/Comment ID 避免重复处理与重复详情/评论费用。

作用：

- 降低同批重复处理；
- 避免同一内容重复 AI；
- 避免同一帖子跨关键词重复详情/评论；
- 形成清晰的冲突审计。

### 6.2 PostgreSQL 最终收敛

Content：

```text
(platform, external_content_id)
```

Comment：

```text
(content_id, external_comment_id)
```

数据库层是跨批次、跨来源、跨时间的最终去重边界。

示例：

```text
上午 Excel 导入 xhs + note_123
→ 一个 Current Content

下午 TikHub 观察到同一个 xhs + note_123
→ 仍是同一个 Current
→ 合法较新字段/Version/Metric 更新
→ 新 Attempt / Raw / Candidate / Source History 仍保留
```

## 7. Processing / Import Batch

Stage 8 固定采用方案 B：Processing / Import Batch 是 Excel 主入口一次业务处理的父事实。

实际 Stage 8A Schema：

```text
processing_import_batches
├─ id
├─ input_artifact_id   # NOT NULL FK artifacts
├─ job_id              # 当前可空，unique FK jobs
├─ status              # processing / succeeded / failed
├─ stats               # 当前 rows_seen/rows_ingested/rows_rejected
├─ error_summary
├─ created_at
├─ started_at
└─ finished_at
```

规则：

- Owner = `ingestion`；
- 不复制 `contents/comments` 业务字段；
- 当前同步人工入口允许 `job_id=null`；
- Stage 8B 产品化后再冻结上传 API、持久 Job、页面进度的正式绑定；
- TikHub 补采继续使用 Collection Run，不创建 TikHub Import Batch；
- 一个 Import Batch 可以完全没有 TikHub 补采。

## 8. File Import 正式来源链

Stage 8A 最终采用：

```text
Input Excel Artifact
→ ProcessingImportBatch
→ ProviderRequestV1(import_batch_id=...)
→ non-billable ProviderAttempt
→ Attempt.raw_artifact_id = Input Artifact
→ Canonical Source
→ Content Ingestion
```

`provider_requests` 约束：

```text
scope_id        nullable FK collection_scopes
import_batch_id nullable FK processing_import_batches

CHECK exactly_one(scope_id, import_batch_id)
UNIQUE(scope_id, request_fingerprint)
UNIQUE(import_batch_id, request_fingerprint)
```

这是对既有 Provider Request 来源父级的**最小一般化**：

- Collection 历史仍使用 `scope_id`；
- File Import 使用 `import_batch_id`；
- Provider Attempt/Content 来源复合约束保持不变；
- 不新增 FileAttempt/FileArtifact 第二套体系；
- 不伪造 Collection Run/Scope；
- 不删除 Content Repository 来源校验；
- 不改写历史 Alembic Revision。

File Import 不创建 Collection Candidate。逐行来源位置继续保存在 Canonical `source.item_locator`；真实来源父事实由 Artifact/Batch/Request/Attempt 保证。

## 9. `imports_test` 两种模式

### 9.1 默认：file-only

```python
WRITE_TO_DATABASE = False
```

或：

```python
run_all(write_to_database=False)
```

默认行为：

- 不读取正式数据库配置；
- 不要求 PostgreSQL；
- 不管理 Docker；
- 不运行 Alembic；
- 继续保存 Canonical、过滤/去重 JSONL、Analysis、Excel 和 run summary；
- 继续复用生产 Reader/Mapper/Analysis/Exporter。

### 9.2 显式数据库模式

```python
run_all(write_to_database=True)
```

文件处理阶段完成后调用正式：

```text
aima_ugc.bootstrap.manual_ingestion.ingest_excel_run_to_postgres
```

数据库模式：

- 使用当前仓库 `AIMA_DB_*`/Secret 配置；
- 真实 `SELECT 1` 检查 PostgreSQL；
- 检查 Stage 8A Schema/约束；
- 不自动运行 Migration；
- 不自动启动容器；
- DB 失败向调用方抛错；
- 已生成文件不删除。

## 10. `tikhub_test` 两种模式

### 10.1 默认：file-only

五平台公共入口和 `run_platform()` 都固定：

```python
write_to_database=False
provider_config_id=None
```

默认行为与 Stage 7 调试保持兼容，不装配数据库 Runtime。

### 10.2 显式数据库模式

需要：

```python
write_to_database=True
provider_config_id=<正式 provider_configs.id>
```

前置检查：

1. PostgreSQL 18 可访问；
2. Schema 已迁到 Stage 8A；
3. `provider_config_id` 存在、启用、`provider=tikhub`；
4. DB Provider Config `base_url` 与调试 `.env` 相同；
5. 正式 `secret_ref` 读取的 API Key 与调试 `.env` API Key 相同；
6. Secret 只做常量时间比较，不输出原文。

显式 DB 模式仍使用现有五平台 Operation/Mapper/Decision；同一网络请求的响应同时用于调试文件和正式来源链。

## 11. 数据库连接与 Migration 门禁

调试数据库模式统一假设：

> 开发者已经启动一个可访问的 PostgreSQL 18 开发数据库。

调试入口只负责：

```text
读取正式配置
→ 连接
→ ping
→ 校验必要 Schema
→ 执行正式摄取
```

禁止：

- `docker compose up/down`；
- 创建/删除容器；
- 自动 Alembic upgrade/downgrade；
- 修改 Docker 配置；
- DB 不可用后静默降级成功。

Stage 8A Migration：

```text
20260818_0018
→ 20260820_0019_stage8a_manual_ingestion
```

必须继续满足：

- base → head；
- previous → head；
- downgrade/re-upgrade；
- `alembic check`；
- 真实 PostgreSQL 18。

## 12. AI / Analysis 边界

Stage 8A 不改变 Blueprint 15 的 Analysis Contract、Prompt、taxonomy 或数据库 Owner。

当前 `imports_test` 仍可以在数据库摄取前/后继续现有 P1 AI 文件处理。Stage 8A 只建立手工数据入口统一入库基础，不把 Analysis 数据库页面、分析 Query API 或正式异步分析 Job 提前塞入本阶段。

因此 Blueprint 15 本轮无需修改。

## 13. Stage 8 首个产品纵切目标

Stage 8A 已完成底层 Foundation。下一步 Stage 8B 才开始产品化：

```text
网页上传 Excel
→ Input Artifact
→ ProcessingImportBatch
→ 持久 Job
→ 复用 Stage 8A File Import / Ingestion
→ 页面查询批次状态/统计/错误
```

Stage 8B 不应重新实现 Reader/Mapper/Ingestion/Repository。

## 14. 页面能力与后端状态映射

| 页面/能力 | 当前后端状态 | Stage 8 处理方式 |
| --- | --- | --- |
| Excel Reader/Mapper | 已实现 | 直接复用 |
| 关键词过滤/稳定去重 | 已实现 | 直接复用 |
| Processing/Import Batch Schema/Repository | **Stage 8A 已实现** | Stage 8B 产品化 API/Job |
| Excel 正式 DB Ingestion | **Stage 8A 已实现** | Stage 8B 从 HTTP/Job 调用 |
| imports_test 可选 DB | **Stage 8A 已实现** | 永久保留调试入口 |
| 正式 TikHub Collection→DB | 已实现 | 继续复用 |
| tikhub_test 可选 DB | **Stage 8A 已实现** | 永久保留调试入口 |
| 跨 Excel/TikHub Current 收敛 | **Stage 8A 已验证** | 继续保持 Owner 约束 |
| Excel 上传 HTTP API | 未实现 | Stage 8B |
| Import Batch Query/Progress API | 未实现 | Stage 8B |
| 采集运行中心 API/页面 | 底层 Run/Job 已有，页面未实现 | Stage 8C |
| Keyword Pack / Collection Plan 页面 | 底层 System/Collection 已有 | 后续纵切 |
| Content Center 查询 | 未实现正式页面查询层 | 后续纵切 |
| Analysis 数据库页面 | 未实现 | 后续纵切 |

不能因为底层表/Service 已有就把页面标记成“已完成”。

## 15. Stage 8 实施顺序

### Stage 8A：Unified Manual Ingestion Foundation — 已实现，待 PR 集成

本阶段机器闭环包括：

- ProcessingImportBatch；
- Provider Request 双父级；
- File Import 合法 Artifact/Attempt 来源链；
- Excel 正式数据库摄取；
- imports_test 默认 file-only + 可选 DB；
- tikhub_test 默认 file-only + 可选 DB；
- PostgreSQL/Schema fail-closed；
- 跨来源去重和历史；
- 失败重试幂等；
- Migration/Contract/PG18 测试。

### Stage 8B：Excel Upload + Import Batch HTTP/Job — 下一正式单元

目标：

- 正式上传 API；
- Input Artifact；
- 创建 Import Batch；
- 持久 Job；
- 查询状态/进度/统计/错误；
- HTTP 幂等与权限边界按当前仓库门禁冻结；
- 复用 Stage 8A，不重写 Ingestion。

### Stage 8C：Collection Run Center

把已有 Plan/Run/Scope/Job/Provider 状态形成最小业务运行中心，不提前扩展 KPI/Content Center。

### Stage 8D：Keyword / Plan Productization

把已有词包、Provider Config、Plan Capability 形成产品化配置纵切。

### Stage 8E：Content Center

建立正式 Query Repository/Read Model/Query Service/API/页面，不允许 Router 直接 SQL。

### Stage 8F：Analysis / Reporting Productization

在 Blueprint 15/Reporting 已批准 Contract 之上继续，不反向污染 Stage 8A 数据入口。

若后续 Blueprint 对 Stage 8B—8F 有更细子阶段，以最新已批准 Change/Blueprint 为准；一个对话默认仍只完成一个最小正式单元。

## 16. Stage 8A 验收事实

Stage 8A 只有在以下条件都满足时才允许进入 Review/集成：

1. `imports_test` 默认不依赖数据库；
2. `tikhub_test` 默认不依赖数据库；
3. 两个入口既有文件输出兼容；
4. 显式 DB 模式可写 PostgreSQL；
5. DB/Schema 不可用明确失败；
6. 调试入口不管理 Docker/Migration；
7. 没有新增平行 Content/Comment Writer；
8. Canonical 后统一 Content Ingestion；
9. File Import 使用真实 Artifact/Attempt；
10. 不伪造来源 ID；
11. 同一 Excel 重复导入只有一个 Current；
12. Excel/TikHub 同身份只有一个 Current；
13. 较新 Observation 可以生成新的 Current/Version/Metric；
14. 来源历史保留；
15. DB 阶段失败后可重试；
16. Unit/Contract/PostgreSQL Integration 通过；
17. Migration 全门禁通过；
18. 文档与代码一致；
19. Diff 无无关修改；
20. Active Change 记录新鲜证据；
21. PR/CI/Branch Protection 按仓库流程闭环。

## 17. 回滚与兼容

Stage 8A 是向前兼容 Schema 扩展：

- 旧 Collection Request 继续使用 `scope_id`；
- 新 File Import Request 使用 `import_batch_id`；
- 不重写历史数据；
- 不修改 Content 业务唯一键；
- 不修改现有 TikHub Operation/Mapper 公共语义；
- 不修改 imports_test/tikhub_test 默认 file-only 行为。

回滚顺序：

1. 关闭新的 DB opt-in 使用；
2. 停止产生 import-parent Provider Request；
3. 确认/处理已引用 Import Batch 的新来源事实；
4. 应用普通 Git revert；
5. 仅在数据引用条件允许时执行 Alembic downgrade `0019 → 0018`；
6. 不 force push、不改写历史 Revision。

## 18. 当前下一步

Stage 8A 集成闭环后，**下一正式最小单元只能是 Stage 8B**。

不要在 Stage 8A 的 PR 中提前实现 Stage 8B/8C，也不要因为 Stage 8A 已具备底层数据库入口就开始正式 Vue/Figma 页面代码。

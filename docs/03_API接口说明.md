# AIMA_UGC HTTP API 实现说明

本文面向前端开发、接口联调和后端开发，说明**当前代码真正注册的 HTTP API、每组接口背后的 Application Service/Job/数据 Owner，以及修改接口时需要同步什么**。

精确机器事实始终以：

```text
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/contracts/runtime.py
backend/src/aima_ugc/contracts/relevance_review.py
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/bootstrap/analysis_capability_http.py
backend/src/aima_ugc/entrypoints/api_main.py
contracts/openapi/openapi.json
frontend/src/generated/api/
```

为准。

本文不会提前写不存在的 `/alerts`、`/reports` 等未来 URL；接口真正进入最终 FastAPI Assembly + OpenAPI + Test 后，才属于当前 API。

---

# 1. API 调用链

普通查询：

```text
Vue Feature
→ generated API Client
→ FastAPI Route
→ Query/Application Service
→ PostgreSQL Query Repository
→ Response Model
```

耗时任务：

```text
Vue / HTTP Client
→ FastAPI Route
→ 短事务创建业务父事实 + 当前阶段必须存在的 Job
→ 202 Accepted
→ Worker 认领 Job
→ 执行业务
→ 更新业务父事实 / Job Result
→ 前端轮询查询
```

Router 不直接 SQL，也不直接请求 TikHub/LLM。目录发现、XLSX 预检/Chunk、历史导入、Analysis Run Planner、Analysis Shard、Excel Export 等长任务都不能退回 HTTP 请求内同步跑完。

---

# 2. Contract、生成 Client 与错误结构

HTTP Request/Response 主要维护在：

- [`backend/src/aima_ugc/contracts/http.py`](../backend/src/aima_ugc/contracts/http.py)

运行能力类的安全只读 Contract：

- [`backend/src/aima_ugc/contracts/runtime.py`](../backend/src/aima_ugc/contracts/runtime.py)

人工相关性复核 Contract：

- [`backend/src/aima_ugc/contracts/relevance_review.py`](../backend/src/aima_ugc/contracts/relevance_review.py)

生成链：

```text
Pydantic
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
→ frontend/src/generated/api/
```

统一错误：

```text
HttpErrorResponse
```

主要结构：

```json
{
  "type": "https://aima.example/problems/xxx",
  "title": "错误标题",
  "status": 422,
  "detail": "可安全展示的说明",
  "request_id": "...",
  "errors": []
}
```

规则：

- 业务失败不返回 200；
- 未找到通常是 404；
- 状态冲突/结果未就绪通常是 409；
- 请求 Contract 不合法通常是 422；
- 未预期异常返回安全 500，不暴露 SQL、Secret、内部路径或 traceback；
- `request_id` 用来关联应用日志。

生成目录禁止手工修改；后端 Contract 变化后必须重新生成 OpenAPI/generated Client 并跑对应 Contract/API/Frontend 验证。

---

# 3. Health API

## `GET /health/live`

作用：进程是否存活并能响应 HTTP。

不是：数据库完整业务检查、TikHub 实时 Probe、LLM 在线/余额证明。

## `GET /health/ready`

当前 Readiness 检查关键本地/基础依赖边界，包括：

- PostgreSQL；
- ArtifactStore；
- 日志目录。

代码：

- [`backend/src/aima_ugc/bootstrap/api.py`](../backend/src/aima_ugc/bootstrap/api.py)
- [`backend/src/aima_ugc/platform/health.py`](../backend/src/aima_ugc/platform/health.py)

---

# 4. Collection Runtime API

代码：

- [`backend/src/aima_ugc/bootstrap/collection_http.py`](../backend/src/aima_ugc/bootstrap/collection_http.py)
- [`backend/src/aima_ugc/modules/collection/http.py`](../backend/src/aima_ugc/modules/collection/http.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py`](../backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py)

## 4.1 `GET /api/v1/collection-capabilities`

用于前端读取当前可执行 Provider Config、Platform Capability 和 Provider-neutral Search 选项。平台支持的排序、时间筛选、评论/二级评论等不能在前端维护第二套能力表。

## 4.2 `POST /api/v1/collection-runs`

创建一次手工 Collection Run。

当前模式：

```text
discovery
→ 一次性关键词发现

batch_supplement
→ 基于已有 Import Batch 做补采
```

HTTP 只创建 Run/Scope/Job；真正 Provider 调用由 `collection.run.v1` Worker 完成。

## 4.3 `GET /api/v1/collection-runs/{run_id}`

读取一个 Run 当前状态、Scope、进度、统计、错误摘要等。Scope 返回 Provider-neutral 运行事实，不把 TikHub 私有分页 Cursor 当公共 Contract。

## 4.4 `GET /api/v1/collection-runtime/runs`

采集运行中心统一 Read Model，可投影兼容 Excel Import 与 TikHub Run。统一发生在 Query 层，不表示数据库把 Import Batch、Collection Run、Data Import Campaign 合成万能父表。

## 4.5 `GET /api/v1/collection-runtime/summary`

返回运行中心 KPI Read Model。精确字段以当前 `CollectionRuntimeSummaryResponse` 为准。

---

# 5. 统一 Data Import API：当前页面主导入工作流

当前采集运行中心只有一个“导入数据”入口，页面主工作流使用 `/api/v1/data-import-*`。

实现入口：

- [`backend/src/aima_ugc/bootstrap/historical_import_http.py`](../backend/src/aima_ugc/bootstrap/historical_import_http.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_worker.py`](../backend/src/aima_ugc/bootstrap/historical_import_worker.py)
- [`backend/src/aima_ugc/modules/ingestion/historical_http.py`](../backend/src/aima_ugc/modules/ingestion/historical_http.py)
- [`backend/src/aima_ugc/modules/ingestion/historical_jobs.py`](../backend/src/aima_ugc/modules/ingestion/historical_jobs.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py`](../backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py)
- [`frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue`](../frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue)

完整业务语义：

- [`appendix/08_数据入口与统一入库实现.md`](appendix/08_数据入口与统一入库实现.md)
- [`roadmap/03_4000万历史数据迁移实施方案.md`](roadmap/03_4000万历史数据迁移实施方案.md)

## 5.1 `GET /api/v1/data-import-sources/server/directories`

枚举管理员批准的服务器只读根目录内的目录/`.xlsx` 元数据。

安全边界：

- HTTP 只接受/返回批准根内相对路径；
- 拒绝绝对路径、`..`、UNC/设备路径和路径逃逸；
- 拒绝 Symlink/Junction/Reparse Point 等链接组件；
- 这是只读发现能力，不是通用文件管理器。

## 5.2 `POST /api/v1/data-import-campaigns/server`

从批准服务器目录创建 Data Import Campaign。

创建时独立冻结：

```text
source_kind = server_path
ingestion_policy = standard_observation | historical_fill_only
```

`source_kind` 只决定文件怎样获得；`ingestion_policy` 决定 Content Owner 写入语义，二者不能互相推导。

## 5.3 `POST /api/v1/data-import-campaigns/local`

根据浏览器显式选择的本地文件/文件夹清单创建本地 Campaign。页面只提交安全相对路径、大小和必要元数据，不获得/提交本机绝对路径。

## 5.4 `PUT /api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content`

为本地 Campaign 的一个冻结 Source Item 流式上传 `.xlsx` 内容。

重复 PUT 必须与被冻结的文件名、大小和 SHA-256 等身份一致；不能用重试替换成另一份文件。

## 5.5 `POST /api/v1/data-import-campaigns/{campaign_id}/finalize`

本地上传清单全部完成后显式 finalize，进入后续 Snapshot/Preflight/Chunk 流程。服务器来源由自身 Discover/Snapshot 状态机推进，不使用浏览器本地字节上传。

## 5.6 Campaign 查询

```text
GET /api/v1/data-import-campaigns
GET /api/v1/data-import-campaigns/{campaign_id}
GET /api/v1/data-import-campaigns/{campaign_id}/items
GET /api/v1/data-import-campaigns/{campaign_id}/conflicts
```

Campaign Response 中的 `progress` 来自 PostgreSQL 持久事实集合式聚合：

```text
发现阶段
→ 总量未知，允许不确定进度，不伪造百分比

预检/快照
→ Source Item / Snapshot Job 的真实进度

迁移
→ 冻结 Chunk row_count 与终态行数的真实聚合
```

## 5.7 Campaign 操作

```text
POST /api/v1/data-import-campaigns/{campaign_id}/start
POST /api/v1/data-import-campaigns/{campaign_id}/cancel
POST /api/v1/data-import-campaigns/{campaign_id}/retry-failed
```

当前 Worker 物理 Job type：

```text
ingestion.historical-discover.v1
ingestion.historical-snapshot.v1
ingestion.historical-import-chunk.v1
```

物理名称沿用 `historical_*` 是兼容选择，不代表当前页面存在第二套“历史导入”业务入口。

`historical_fill_only` 的长期规则是只补空值、不覆盖已有非空 Current、差异留冲突账本；`standard_observation` 继续使用普通字段新鲜度语义。导入不会自动创建 AI Job。

---

# 6. 兼容 Excel Import API

旧单文件 Import 仍是合法兼容 Contract，但**不是当前页面的第二套主导入入口**。

代码：

```text
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/import_worker.py
backend/src/aima_ugc/modules/ingestion/
```

## 6.1 `POST /api/v1/import-batches`

接受一个 multipart `.xlsx` 和当前 Contract 要求的 `keyword_pack_ids`，保存 Input Artifact，冻结关键词选择，创建 `processing_import_batches + ingestion.import-excel.v1 Job`，真正处理由 Worker 完成。

## 6.2 查询

```text
GET /api/v1/import-batches
GET /api/v1/import-batches/summary
GET /api/v1/import-batches/{batch_id}
GET /api/v1/jobs/{job_id}
```

`GET /api/v1/jobs/{job_id}` 由 Import HTTP Service 暴露通用 Job Read Model；这不表示 `jobs` 表中所有内部 Job 自动成为公共 API。

旧 `/api/v1/historical-import-*` Route 也继续作为 Stage 12 兼容边界存在，但当前页面不依赖它建立平行工作流。

---

# 7. Content / 声音广场 API

代码：

- [`backend/src/aima_ugc/bootstrap/content_http.py`](../backend/src/aima_ugc/bootstrap/content_http.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`](../backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py)
- [`backend/src/aima_ugc/modules/content/query.py`](../backend/src/aima_ugc/modules/content/query.py)
- [`backend/src/aima_ugc/modules/content/content_cursor.py`](../backend/src/aima_ugc/modules/content/content_cursor.py)

前端：

```text
frontend/src/features/voice-plaza/
```

## 7.1 `GET /api/v1/contents`

用于声音广场列表、Analysis/Export 目标查询的基础 Read Model。

查询层组合：

- Content Current / current version；
- 当前版本匹配的 Analysis；
- AI 原始 relevance；
- 最新人工相关性事件形成的 `effective_relevance / relevance_source`；
- 来源链；
- 作者和 Current Metrics。

默认列表按**有效相关性**排除当前仍为 irrelevant 的内容；没有 current Analysis 的 Content 仍可显示。

Analysis 状态：

```text
completed
stale
pending
```

AI 原判仍在 `analysis_content_results.relevance`，没有复制为 `contents.is_relevant`。

## 7.2 `GET /api/v1/contents/{content_id}`

读取详情，包括 media、comments、coverage、source_records 等审计/展示数据。单条详情不会因为 AI irrelevant 物理删除或隐藏 Content 业务事实。

## 7.3 `POST /api/v1/content-relevance-reviews`

对当前 Content Version 追加人工相关性决定：

```text
relevant
irrelevant
inherit_ai
```

模型原始 Result 不 UPDATE/DELETE；人工决定写入 `analysis_content_relevance_reviews`。批量请求先校验/锁定全部目标，任一目标不可操作时整批失败；已有人工覆盖要切到相反结论必须先撤销。精确 Contract 看 [`contracts/relevance_review.py`](../backend/src/aima_ugc/contracts/relevance_review.py)。

---

# 8. Content Analysis API：当前新版 Run + 兼容 Request

代码：

- [`backend/src/aima_ugc/contracts/runtime.py`](../backend/src/aima_ugc/contracts/runtime.py)
- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/bootstrap/content_http.py`](../backend/src/aima_ugc/bootstrap/content_http.py)
- [`backend/src/aima_ugc/bootstrap/analysis_worker.py`](../backend/src/aima_ugc/bootstrap/analysis_worker.py)
- [`backend/src/aima_ugc/modules/analysis/content_analysis_job.py`](../backend/src/aima_ugc/modules/analysis/content_analysis_job.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis.py`](../backend/src/aima_ugc/adapters/persistence/postgres/analysis.py)

详细：

[`appendix/07_AI舆情打标与分析实现.md`](appendix/07_AI舆情打标与分析实现.md)

## 8.1 `GET /api/v1/content-analysis-capabilities`

安全只读能力投影，只返回当前 API/Worker 是否形成可执行 LLM 本地配置所需的 `configured` 等允许字段。

源码开发和正式 Worker 必须从同一个当前 `settings.external_secret_root` 读取 LLM Secret；源码 launcher 通过 `AIMA_EXTERNAL_SECRET_DIR` 暴露外部 Secret Root。内部 PostgreSQL/Cursor Secret Root 不是 LLM Secret Root。

这个接口不会返回 Base URL、Model、API Key、Secret 路径，也不证明外部 LLM 此刻网络/余额正常。

## 8.2 `POST /api/v1/analysis/content-runs/preview`

新版页面先预检用户显式选择的 Content，返回冻结目标数、预计 Shard 等创建 Run 前所需信息/身份。

当前新版 Run 只开放显式选择的 **1—1000 个 Content ID**；query scope 暂不作为新版页面 Contract 开放。

## 8.3 `POST /api/v1/analysis/content-runs`

创建 Analysis Run Header + `analysis.content-run-plan.v1` Planner Job。

Planner 在 PostgreSQL 中：

```text
冻结 content_id + content_version
→ 复核 Preview 数量
→ 有界创建 analysis.content-label.v1 Shard Job
```

HTTP 不扫描/物化百万级目标，也不直接执行 LLM。

## 8.4 Run 查询/取消

```text
GET  /api/v1/analysis/content-runs
GET  /api/v1/analysis/content-runs/{run_id}
POST /api/v1/analysis/content-runs/{run_id}/cancel
```

不同 Run 对同一 Content Version 的结果全部保留；Current 按 Run 创建顺序选择，较新 Run 失败/取消不会删除旧成功结果。页面进度使用冻结 `target_count` 和持久 Shard 进度，不从前端猜测。

## 8.5 `POST /api/v1/content-analysis-requests`

这是兼容入口，不是新版页面主入口。它继续兼容既有 selected/query 语义和既有 `request_id/job_id` Response，但当前后台也会纳入 Analysis Run/Shard 模型并保持冻结 Content Version 的语义。

不要再把它描述成“当前新版 Analysis 唯一入口”或“直接创建一个覆盖全部目标的单一 Analysis Job”。

## 8.6 `GET /api/v1/content-analysis-jobs/{job_id}`

兼容读取 Analysis Job 状态/Result。新版页面主要以 Analysis Run 资源展示一轮用户任务的历史和进度。

当前真实 Analysis Worker Job type：

```text
analysis.content-run-plan.v1
analysis.content-label.v1
```

---

# 9. 正式 Excel Export API

代码：

```text
backend/src/aima_ugc/bootstrap/reporting_http.py
backend/src/aima_ugc/bootstrap/export_worker.py
backend/src/aima_ugc/modules/reporting/
```

## 9.1 `POST /api/v1/data-exports`

创建正式 Excel Export。创建时冻结目标 Content Version，随后创建：

```text
reporting.content-export-excel.v1
```

## 9.2 查询/下载

```text
GET /api/v1/data-exports
GET /api/v1/data-exports/{export_id}
GET /api/v1/data-exports/{export_id}/download
```

列表当前没有自动等价于创建请求 Filter 的分页 Contract；精确 Query 以 OpenAPI 为准。下载只有 Artifact 已就绪时成功，未就绪返回状态冲突，不返回空文件。

当前没有 Word Report 的正式 `/reports` API；离线 Word Report 位于 `backend/src/aima_ugc/platform/reporting/`。

---

# 10. Keyword Pack / Relevance API

当前 Route：

```text
POST /api/v1/keyword-packs
GET  /api/v1/keyword-packs
POST /api/v1/keyword-packs/{pack_id}/keywords
GET  /api/v1/keyword-packs/{pack_id}
PUT  /api/v1/keyword-packs/{pack_id}/enabled
PUT  /api/v1/relevance-config
GET  /api/v1/relevance-config
```

规则 Relevance 是确定性关键词筛选，不是 AI Semantic Relevance。Data Import Campaign 会按当前 Contract 冻结其所选 Keyword Pack/关键词事实；不能让 Worker 执行时重新读取变化后的选择。

---

# 11. Collection Plan API

代码：

- [`backend/src/aima_ugc/bootstrap/collection_strategy_http.py`](../backend/src/aima_ugc/bootstrap/collection_strategy_http.py)
- [`backend/src/aima_ugc/modules/collection/planning.py`](../backend/src/aima_ugc/modules/collection/planning.py)

当前：

```text
POST /api/v1/collection-plans
GET  /api/v1/collection-plans
GET  /api/v1/collection-plans/{plan_id}
PUT  /api/v1/collection-plans/{plan_id}/enabled
```

当前 Scheduler 长期边界：

```text
timezone = Asia/Shanghai
misfire_policy = latest_only
max_catch_up_runs = 0
```

完整 Scheduler 语义：[`appendix/05_Scheduler调度执行与停机恢复.md`](appendix/05_Scheduler调度执行与停机恢复.md)。

---

# 12. Cursor 分页

当前多个列表使用不透明 Cursor，而不是简单 Offset 页码。

典型实现：

```text
Content
→ backend/src/aima_ugc/modules/content/content_cursor.py

Import Batch
→ backend/src/aima_ugc/modules/ingestion/import_batch_cursor.py

Collection Runtime
→ backend/src/aima_ugc/modules/collection/runtime_cursor.py
```

前端只原样回传 `next_cursor`，禁止解析/改写内部 Cursor、跨筛选复用或把数据库密码当 Cursor signing key。

Data Import 目录/Campaign 的分页/游标以其当前 Pydantic Contract 和 `historical_*` 实现为准，不强行复用 Import Batch Cursor。

---

# 13. 当前前端与 API 对应关系

真实路由：

- [`frontend/src/app/routes.ts`](../frontend/src/app/routes.ts)

当前页面：

```text
/collection-runtime
→ collection-runs / collection-runtime
→ data-import-* 当前统一导入入口
→ import-batches 兼容运行事实

/collection-strategy
→ keyword-packs / relevance-config / collection-plans

/voice-plaza
→ contents / content-relevance-reviews
→ content-analysis-capabilities
→ analysis/content-runs
→ data-exports
```

当前后端有兼容 `/content-analysis-requests`、`/import-batches`、`/historical-import-*`，不表示前端要维持平行主入口。

后端有 `data-exports` API，但没有独立 `/export` Route；Analysis Run 在 `/voice-plaza`，也没有独立 Analysis 管理 Route。

---

# 14. 修改 API 时的完整影响面

## 新增/修改 Query 字段

```text
Pydantic Contract
→ Query Service/Repository
→ Cursor query hash（如果改变结果集）
→ API Test
→ OpenAPI
→ generated Client
→ Frontend Feature
→ 当前文档
```

## 新增长任务

```text
业务父事实
→ 版本化 Job Payload/Handler
→ Worker Registry
→ Executor
→ Retry/Deadline/Fencing/Progress/Cancel
→ API Contract
→ API + Integration Tests
```

## 修改 Response

```text
兼容性判断
→ Pydantic Response
→ Route
→ API Test
→ OpenAPI regenerate
→ Orval regenerate
→ Frontend typecheck/test
```

不要用前端 `as any`、手写平行 Type 或 Mock Contract 掩盖后端变更。

---

# 15. 本地联调如何确认 API 事实

推荐顺序：

```text
1. 看 contracts/http.py / runtime.py / relevance_review.py
2. 看 bootstrap/api.py / 各领域 HTTP Assembly / entrypoints/api_main.py
3. 看 contracts/openapi/openapi.json
4. 看 frontend/src/generated/api/
5. 看对应 API/Contract/Full-stack tests
6. 再按当前 OpenAPI 构造人工请求
```

本文是人类导航，不替代 OpenAPI。

---

# 16. 当前明确不存在的 API / 产品资源

当前最终系统不能被描述成已经有：

```text
/api/v1/alerts
/api/v1/reports
/api/v1/client-events
企业登录 / Session API
LLM 配置编辑 / Secret 查询 API
独立顶层 /api/v1/analysis-runs 资源
```

当前 Analysis Run 的真实路径是 `/api/v1/analysis/content-runs`，并由声音广场使用。未来资源进入最终 FastAPI Assembly + OpenAPI + 测试后再加入本文。

---

# 17. 相关文档

- API/Job/Frontend 架构：[`blueprint/04_后端任务API与前端.md`](blueprint/04_后端任务API与前端.md)
- 数据入口：[`appendix/08_数据入口与统一入库实现.md`](appendix/08_数据入口与统一入库实现.md)
- Stage 12 已实现软件与生产门禁：[`roadmap/03_4000万历史数据迁移实施方案.md`](roadmap/03_4000万历史数据迁移实施方案.md)
- Analysis：[`appendix/07_AI舆情打标与分析实现.md`](appendix/07_AI舆情打标与分析实现.md)
- Excel Export：[`appendix/06_Excel统一数据导出与离线调试.md`](appendix/06_Excel统一数据导出与离线调试.md)
- PostgreSQL：[`appendix/01_PostgreSQL查询与调试实战.md`](appendix/01_PostgreSQL查询与调试实战.md)
- 代码修改导航：[`01_代码结构与修改导航.md`](01_代码结构与修改导航.md)

# AIMA_UGC HTTP API 实现说明

本文面向前端开发、接口联调和后端开发，说明**当前代码真正注册的 HTTP API、每组接口背后的 Application Service/Job/数据 Owner，以及修改接口时需要同步什么**。

精确机器事实始终以：

```text
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/contracts/runtime.py
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
→ 同一事务创建业务父事实 + Job
→ 202 Accepted
→ Worker 认领 Job
→ 执行业务
→ 更新业务父事实 / Job Result
→ 前端轮询查询
```

Router 不直接 SQL，也不直接请求 TikHub/LLM。

---

# 2. 统一 Contract 与错误结构

HTTP Request/Response 主要维护在：

```text
backend/src/aima_ugc/contracts/http.py
```

运行能力类的安全只读 Contract 维护在：

```text
backend/src/aima_ugc/contracts/runtime.py
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

错误处理的精确实现看 `bootstrap/api.py`。

---

# 3. Health API

## `GET /health/live`

作用：进程是否存活并能响应 HTTP。

不是：

- 数据库完整业务检查；
- TikHub 实时 Probe；
- LLM 可用性证明。

## `GET /health/ready`

当前 Readiness 会检查关键本地/基础依赖边界，包括：

- PostgreSQL；
- ArtifactStore；
- 日志目录。

代码：

```text
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/platform/health.py
```

---

# 4. Collection Runtime API

代码：

```text
backend/src/aima_ugc/bootstrap/collection_http.py
backend/src/aima_ugc/modules/collection/http.py
backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
```

## 4.1 `GET /api/v1/collection-capabilities`

用于前端获取当前可以用于手工 Collection Run 的 Provider Config 和平台 Capability。

不要在前端自己维护：

```text
某个平台有哪些排序
是否支持评论
是否支持二级评论
```

这类业务支持应由后端 Capability 驱动。

## 4.2 `POST /api/v1/collection-runs`

创建一次手工 Collection Run。

Request：

```text
CollectionRunCreateRequest
```

当前模式：

```text
discovery
→ 提交一次性 keywords
→ 不允许 import_batch_id

batch_supplement
→ 必须 import_batch_id
→ 不允许同时提交 discovery keywords
```

平台选择：

```text
platform + provider_config_id
```

并可控制：

```text
include_comments
include_sub_comments
```

如果抓二级评论，必须同时启用一级评论。

成功返回：

```text
run_id
job_id
mode
import_batch_id
status=queued
```

HTTP 只创建 Run/Scope/Job，不同步完成 TikHub 采集。

## 4.3 `GET /api/v1/collection-runs/{run_id}`

读取一个 Run 当前状态、平台、关键词、Scope 进度、统计、错误摘要等。

Response：

```text
CollectionRunResponse
```

Scope 返回 Provider-neutral 进度，不把 TikHub `cursor/search_id` 等私有分页状态公开给前端。

## 4.4 `GET /api/v1/collection-runtime/runs`

采集运行中心统一列表。

当前 Read Model 可以同时投影：

```text
excel_import
tikhub_discovery
tikhub_batch_supplement
```

数据库并没有因此把 Import Batch 和 Collection Run 合成一张表；统一是在 Query 层完成。

Query：

```text
CollectionRuntimeListQuery
```

支持当前 Contract 中的：

- search；
- record_types；
- status；
- stage；
- created_from / created_to；
- opaque cursor；
- limit。

精确字段以 `contracts/http.py` 为准。

## 4.5 `GET /api/v1/collection-runtime/summary`

返回运行中心 KPI，例如：

```text
processing_count
completed_today_count
contents_ingested_today
as_of
```

这些是运行中心 Read Model，不是持久化 KPI 业务表。

---

# 5. Excel Import API

代码：

```text
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/import_worker.py
backend/src/aima_ugc/modules/ingestion/
```

详细实现：

[`appendix/08_数据入口与统一入库实现.md`](appendix/08_数据入口与统一入库实现.md)

## 5.1 `POST /api/v1/import-batches`

当前接受一个 multipart：

```text
file
```

API 阶段：

```text
接收/校验上传边界
→ 保存 Input Artifact
→ 冻结 Relevance Snapshot
→ 创建 Processing Import Batch
→ 创建 ingestion.import-excel.v1 Job
→ 202
```

真正 Excel Reader/Mapper/Filter/Dedup/Ingestion 由 Worker 完成。

成功返回：

```text
ImportBatchCreatedResponse
→ batch_id
→ job_id
→ status=queued
```

## 5.2 `GET /api/v1/import-batches`

分页查询 Batch。

Query：

```text
ImportBatchListQuery
```

当前支持：

```text
identifier
status
stage
created_from
created_to
cursor
limit
```

返回：

```text
items
next_cursor
has_more
```

## 5.3 `GET /api/v1/import-batches/summary`

返回导入运行摘要：

```text
processing_count
completed_today_count
rows_ingested_today
as_of
```

## 5.4 `GET /api/v1/import-batches/{batch_id}`

查看单个 Batch，包括：

```text
input_artifact_id
source_filename
status
stage
stats
error_summary
job
生命周期时间
```

精确字段由 `ImportBatchResponse` 维护。

## 5.5 `GET /api/v1/jobs/{job_id}`

当前这个通用 Job 查询入口由 Import HTTP Service 暴露，并可以读取当前允许公开的 Job 状态/Result。

不要因此假设：

> `jobs` 表里的任何内部 Job 类型都自动成为公共 API。

Analysis 目前还有自己的：

```text
GET /api/v1/content-analysis-jobs/{job_id}
```

---

# 6. Content / 声音广场 API

代码：

```text
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
backend/src/aima_ugc/modules/content/query.py
backend/src/aima_ugc/modules/content/content_cursor.py
```

前端：

```text
frontend/src/features/voice-plaza/
```

## 6.1 `GET /api/v1/contents`

用于声音广场列表和 Analysis/Export 的查询条件基础。

Query Contract：

```text
ContentListQuery
ContentFilterSnapshot
```

当前查询层可以组合：

- Content Current；
- 当前 Content Version；
- 当前 Analysis Identity 匹配的最新 Analysis；
- 当前来源 Request/Attempt/Raw；
- 作者展示信息；
- Current Metrics。

默认语义：

```text
未显式指定 relevance
→ 排除 current Analysis 明确 irrelevant
→ 没有当前 Analysis 的 Content 仍显示
```

Analysis 状态：

```text
completed
→ 当前 Content Version 有当前 Analysis Identity 结果

stale
→ 当前版本没有当前结果，但该 Content 历史有 Analysis

pending
→ 从未有 Analysis
```

当前 AI relevance 不在 `contents.is_relevant`，而在 `analysis_content_results.relevance`。

## 6.2 `GET /api/v1/contents/{content_id}`

读取详情，包括当前列表字段以及：

- media；
- comments；
- latest comment coverage；
- source_records。

单条详情使用审计友好读取，可以查看 current Analysis 为 irrelevant 的真实 Content，不会物理隐藏/删除业务事实。

---

# 7. Content Analysis API

代码：

```text
backend/src/aima_ugc/contracts/runtime.py
backend/src/aima_ugc/bootstrap/analysis_capability_http.py
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/bootstrap/analysis_worker.py
backend/src/aima_ugc/modules/analysis/
```

详细实现：

[`appendix/07_AI舆情打标与分析实现.md`](appendix/07_AI舆情打标与分析实现.md)

## 7.1 `GET /api/v1/content-analysis-capabilities`

这是声音广场使用的**安全运行能力读模型**，只回答当前 API/Worker 运行环境是否具备创建可执行 AI Analysis Job 的最低配置。

Response：

```json
{
  "configured": true
}
```

`configured=true` 的最低前提与正式 Worker 装配保持一致：

```text
LLM Base URL 已配置
+ LLM Model 已配置
+ <AIMA_SECRET_DIR>/llm_api_key 可安全读取
```

`AIMA_LLM_PROVIDER_NAME` 仍可按现有 OpenAI-compatible Adapter 规则从 Base URL 推导，因此不是这里的强制条件。

这个接口**不会返回**：

- Base URL；
- Provider Name；
- Model；
- API Key；
- Secret 路径；
- 原始异常详情。

它也不是 Provider 在线健康探测：`configured=true` 只表示本应用具备发起 Analysis 的本地运行配置，不能证明外部 LLM 此刻网络可达、余额充足或请求一定成功。

前端行为：

```text
configured=false
→ 声音广场明确提示“AI 未配置”
→ AI 打标按钮 disabled
→ 不创建注定失败的 Analysis Job

configured=true
→ 保持现有 selected/query Analysis Request 行为
```

Worker 的执行时配置校验仍然保留，前端 capability 只用于用户体验和避免明显无效请求，不能替代服务器最终守卫。

## 7.2 `POST /api/v1/content-analysis-requests`

Request：

```text
ContentAnalysisSubmitRequest
```

当前 target scope：

```text
query
→ 根据 ContentFilterSnapshot 冻结当时目标

selected
→ 根据指定 content_ids 冻结目标
```

无论哪种，API 都会把：

```text
content_id + current_version
```

冻结进 `analysis_content_request_items`，然后同事务创建：

```text
analysis.content-label.v1 Job
```

因此 Worker 后续分析的是请求创建时版本，不重新解释排队期间已经变化的 Content Current。

成功返回：

```text
request_id
job_id
target_count
```

## 7.3 `GET /api/v1/content-analysis-jobs/{job_id}`

查询正式 Content Analysis Job。

成功 Job Result：

```text
request_id
succeeded
failed
stale
```

精确字段：`ContentAnalysisJobResultResponse`。

---

# 8. 正式 Excel Export API

代码：

```text
backend/src/aima_ugc/bootstrap/reporting_http.py
backend/src/aima_ugc/bootstrap/export_worker.py
backend/src/aima_ugc/modules/reporting/
```

详细：

- `backend/src/aima_ugc/modules/reporting/README.md`
- [`appendix/06_Excel统一数据导出与离线调试.md`](appendix/06_Excel统一数据导出与离线调试.md)

## 8.1 `POST /api/v1/data-exports`

创建正式 Excel Export。

和 Analysis 一样，创建时会冻结目标：

```text
content_id
content_version
ordinal
```

随后创建：

```text
reporting.content-export-excel.v1 Job
```

Worker 后续使用冻结版本生成 XLSX Artifact。

## 8.2 `GET /api/v1/data-exports`

查询最近的 Export 列表。

**当前这个 Route 没有 Query 参数，也没有 Cursor/分页/筛选 Contract。** `bootstrap/api.py` 直接调用 `PostgresReportingHttpService.list_exports()`，由 Reporting Repository 读取当前最近记录并返回 `DataExportListResponse.items`。

不要把 `POST /api/v1/data-exports` 创建 Export 时使用的 `ContentFilterSnapshot` 误写成“Export 列表筛选”。如果后续需要按状态、日期等过滤或分页列表，必须正式修改 HTTP Contract、Route/Service/Repository、OpenAPI/generated Client 和测试后再更新本文。

## 8.3 `GET /api/v1/data-exports/{export_id}`

查看单个 Export 的：

- Job/状态；
- Artifact 是否就绪；
- Request Snapshot；
- Stats；
- 时间等。

## 8.4 `GET /api/v1/data-exports/{export_id}/download`

只有：

```text
artifact_id 已关联
+ Artifact 已可读取
```

才允许下载。

结果尚未就绪时返回状态冲突，而不是给空文件。

注意：当前没有 Word Report 的正式 `/reports` API。离线 Word Report 属于 `platform/reporting/`。

---

# 9. Keyword Pack / Relevance API

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

代码主要由：

```text
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/modules/system/
```

提供。

## 9.1 Keyword Pack

当前关键词写入只接受原始 `text`，数据库唯一身份和匹配归一化是两层不同规则。

关系属性如：

```text
priority
enabled
note
platform
```

属于 pack item，不属于全局 Keyword 身份。

## 9.2 Global Relevance

```text
PUT /api/v1/relevance-config
```

选择全局 Rule Relevance Keyword Pack。

Import/Collection 创建运行事实时冻结有效配置/关键词，Worker 不在执行中途重新读取一套变化后的配置。

这层 Relevance 是确定性关键词规则，不是 AI Semantic Relevance。

---

# 10. Collection Plan API

代码：

```text
backend/src/aima_ugc/bootstrap/collection_strategy_http.py
backend/src/aima_ugc/modules/collection/planning.py
```

当前：

```text
POST /api/v1/collection-plans
GET  /api/v1/collection-plans
GET  /api/v1/collection-plans/{plan_id}
PUT  /api/v1/collection-plans/{plan_id}/enabled
```

当前 Plan 固定长期调度边界包括：

```text
timezone = Asia/Shanghai
misfire_policy = latest_only
max_catch_up_runs = 0
```

完整 Scheduler 语义：

[`appendix/02_Scheduler调度执行与停机恢复.md`](appendix/02_Scheduler调度执行与停机恢复.md)

不要在 API 文档提前声明并不存在的“全量 Plan 编辑 URL”。具体可编辑字段以当前 Request Model/Route 为准。

---

# 11. Cursor 分页

当前多个列表使用不透明 Cursor，而不是简单 `page=1&offset=20`。

原因：业务数据持续新增，Offset 更容易出现跳项/重复。

Content Cursor：

```text
backend/src/aima_ugc/modules/content/content_cursor.py
```

Import Batch Cursor：

```text
backend/src/aima_ugc/modules/ingestion/import_batch_cursor.py
```

Collection Runtime Cursor：

```text
backend/src/aima_ugc/modules/collection/runtime_cursor.py
```

前端只做：

```text
收到 next_cursor
→ 下一次原样传回
```

禁止：

- 解析内部 Cursor；
- 自己改时间/ID；
- 把一个筛选条件的 Cursor 用到另一组筛选；
- 用数据库密码当 Cursor signing key。

---

# 12. 当前前端与 API 对应关系

真实路由：

```text
frontend/src/app/routes.ts
```

当前页面：

```text
/voice-plaza
→ contents / content-analysis-capabilities / content-analysis

/collection-runtime
→ import-batches / collection-runs / collection-runtime

/collection-strategy
→ keyword-packs / relevance-config / collection-plans
```

当前后端已经有 `data-exports` API，但没有独立 `/export` 前端 Route；不能把“API 已实现”写成“页面已实现”。

生成 Client：

```text
frontend/src/generated/api/
```

禁止手改。

---

# 13. 修改 API 时的完整影响面

## 新增/修改 Query 字段

```text
Contract
→ Query Service/Repository
→ Cursor query hash（如果改变结果集）
→ API Test
→ OpenAPI
→ generated Client
→ Frontend Feature
→ 本文
```

## 新增长任务

```text
业务父事实
→ Job Payload/Handler
→ Worker Registry
→ Executor
→ Retry/Deadline/Fencing
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

不要只让前端 `as any` 绕过后端 Contract 变化。

---

# 14. 本地联调时怎么确认 API 事实

不要仅靠本文手写 curl 作为 Contract 事实。

推荐：

```text
1. 看 contracts/http.py / contracts/runtime.py
2. 看 bootstrap/api.py / bootstrap/analysis_capability_http.py / entrypoints/api_main.py
3. 看 contracts/openapi/openapi.json
4. 用 FastAPI/OpenAPI 或 generated Client 发请求
5. 看 API tests
```

如果需要人工请求，可根据当前 OpenAPI 构造 curl/Postman，但 Request Body/Query 字段以 OpenAPI 为准。

---

# 15. 当前明确不存在的 API

当前最终 FastAPI Assembly 没有：

```text
/api/v1/alerts
/api/v1/reports
/api/v1/client-events
独立 /analysis-runs 资源
企业登录/Session API
LLM 配置编辑/Secret 查询 API
```

未来实现后再加入本文。

---

# 16. 相关文档

- API/Job/Frontend 架构：[`blueprint/04_后端任务API与前端.md`](blueprint/04_后端任务API与前端.md)
- 数据入口：[`appendix/08_数据入口与统一入库实现.md`](appendix/08_数据入口与统一入库实现.md)
- Analysis：[`appendix/07_AI舆情打标与分析实现.md`](appendix/07_AI舆情打标与分析实现.md)
- Excel Export：[`appendix/06_Excel统一数据导出与离线调试.md`](appendix/06_Excel统一数据导出与离线调试.md)
- PostgreSQL：[`appendix/01_PostgreSQL查询与调试实战.md`](appendix/01_PostgreSQL查询与调试实战.md)
- 代码修改导航：[`01_代码结构与修改导航.md`](01_代码结构与修改导航.md)

# 后端任务、API 与前端

本文解释当前代码中：

```text
Vue 页面
→ generated Client
→ FastAPI
→ Application Service
→ PostgreSQL / Job
→ Worker
```

这条链怎样真正工作，以及修改 API、Job 或页面时应该从哪里下手。

精确 HTTP 字段看：

```text
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/contracts/runtime.py
backend/src/aima_ugc/contracts/relevance_review.py
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/bootstrap/analysis_capability_http.py
backend/src/aima_ugc/entrypoints/api_main.py
contracts/openapi/openapi.json
```

前端真实路由看：

```text
frontend/src/app/routes.ts
```

---

## 1. 普通读取请求怎样走

```text
Vue Page
→ Feature API / Store
→ frontend/src/generated/api/
→ FastAPI Route
→ Query/Application Service
→ PostgreSQL Query Repository
→ PostgreSQL
```

例如声音广场：

```text
frontend/src/features/voice-plaza/
→ generated Client
→ GET /api/v1/contents
→ bootstrap/content_http.py
→ PostgresContentQueryRepository
→ contents + current Analysis + source lineage
```

相关代码：

```text
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
```

页面不理解数据库表，Router 不写 SQL，Query Repository 不解释 TikHub 私有字段。

---

## 2. 写请求和长任务怎样走

耗时能力不在 HTTP 请求里直接执行。

```text
Vue / API Client
→ FastAPI Route
→ Application Service
→ 同一 PostgreSQL 事务创建业务父事实 + Job
→ 202 Accepted
→ Worker 认领 Job
→ 执行业务
→ 更新业务事实 + Job 结果
```

当前 Worker Registry 的机器事实：

```text
backend/src/aima_ugc/bootstrap/worker.py
```

当前正式 Job：

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

注意：离线 Markdown/Word 报告当前不是上述 PostgreSQL Worker Registry 中的独立正式 Job；它目前由 `platform/reporting/` 和 `imports_test/generate_report.py` 提供离线生成能力。不能因为“报告通常耗时”就把它写成当前已经产品化的 Job。

---

## 3. Router、Service、Repository 分别负责什么

### 3.1 Router

当前主 Router 与最终 API Assembly：

```text
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/bootstrap/analysis_capability_http.py
backend/src/aima_ugc/entrypoints/api_main.py
```

Router 负责：

- HTTP 方法/路径；
- Path / Query / Body / multipart 校验；
- 调用 Application Service；
- Response Model；
- 业务错误 → HTTP 错误；
- `request_id`。

禁止：

- SQL；
- 直接请求 TikHub；
- 自己循环跑批量任务；
- 直接解析 Provider Raw；
- 复制 Worker 业务逻辑；
- 吞异常后返回 200。

### 3.2 Application / Domain Service

Service 表达一个业务动作，例如：

```text
创建一次 Collection Run
列出采集运行中心记录
上传并创建 Excel Import Batch
冻结一批 Content Analysis 目标
创建 Excel Export
创建/启停 Collection Plan
```

真实生产 Service 主要在：

```text
backend/src/aima_ugc/bootstrap/collection_http.py
backend/src/aima_ugc/bootstrap/collection_strategy_http.py
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/bootstrap/reporting_http.py
```

这里的 Bootstrap Service 会组装真实 Repository，并在需要时协调跨 Owner 的同一事务。

### 3.3 Repository

业务写入由 Owner Repository 负责；查询由 Query Repository 负责。

当前 PostgreSQL 实现集中在：

```text
backend/src/aima_ugc/adapters/persistence/postgres/
```

例如：

```text
content_queries.py
→ 声音广场/Analysis 目标冻结的只读查询

analysis.py
→ Analysis Request / Result / Label Pair

collection_planning.py
→ Plan / Occurrence

collection_run_execution.py
→ Run 执行事实
```

不创建万能 BaseRepository，也不让多个 Repository 同时拥有一张表的写权限。

---

## 4. HTTP Contract 的唯一事实链

```text
Pydantic Request / Response
→ FastAPI Route
→ OpenAPI
→ Orval
→ frontend/src/generated/api/
```

手写 Contract：

```text
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/contracts/runtime.py
```

其中 `runtime.py` 只承载安全的运行能力读模型，不保存 Secret，也不成为 LLM 配置的第二事实源。

生成 OpenAPI：

```text
contracts/openapi/openapi.json
```

前端生成代码：

```text
frontend/src/generated/api/
```

规则：

- generated 文件禁止手改；
- Route 使用稳定 `operation_id`；
- 字段删除、改名、类型变化、默认排序变化都按 Contract 变化处理；
- 后端 Contract 变化后必须重新生成并验证前端 Client；
- 前端不能维护另一套平行 Request/Response Type 来“暂时对齐”。

---

## 5. 当前真实 HTTP API 面

下面来自当前 `bootstrap/api.py` 与最终 `entrypoints/api_main.py` Assembly，不是未来规划列表。

### 5.1 Health

```text
GET /health/live
GET /health/ready
```

`ready` 当前检查 PostgreSQL、Artifact Store 和日志目录；响应不泄露内部异常详情。

### 5.2 Collection Runtime

```text
GET  /api/v1/collection-capabilities
POST /api/v1/collection-runs
GET  /api/v1/collection-runs/{run_id}
GET  /api/v1/collection-runtime/runs
GET  /api/v1/collection-runtime/summary
```

代码：

```text
backend/src/aima_ugc/bootstrap/collection_http.py
backend/src/aima_ugc/modules/collection/http.py
```

`collection-runtime/runs` 是统一只读投影，不意味着 Excel Import Batch 和 Collection Run 被合并成一张万能表。

### 5.3 Content / 声音广场 / Analysis

```text
GET  /api/v1/contents
GET  /api/v1/contents/{content_id}
GET  /api/v1/content-analysis-capabilities
POST /api/v1/content-analysis-requests
GET  /api/v1/content-analysis-jobs/{job_id}
POST /api/v1/content-relevance-reviews
```

代码：

```text
backend/src/aima_ugc/contracts/runtime.py
backend/src/aima_ugc/bootstrap/analysis_capability_http.py
backend/src/aima_ugc/bootstrap/content_http.py
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
backend/src/aima_ugc/adapters/persistence/postgres/relevance_reviews.py
```

`GET /content-analysis-capabilities` 是安全只读运行能力投影，只返回 `configured`。它用于让声音广场在 LLM Base URL / Model / Secret 未形成可执行配置时明确提示并禁用 AI 打标；前端不得读取 `env.local`、Secret 文件或复制后端配置判断。该接口不返回 Base URL、Model、Provider、Secret 路径或 API Key，也不证明外部 LLM 此刻在线；Worker 的执行时配置守卫仍是最终防线。

`POST /content-analysis-requests` 会先冻结 Content ID + `current_version`，再创建 `analysis.content-label.v1` Job。Worker 分析的不是“未来可能变化的查询结果”，而是请求创建时冻结的目标版本。

`POST /content-relevance-reviews` 是同步短事务：接收 1—1000 个不重复 Content ID，只允许把**当前版本、当前 AI 原判为 `irrelevant`** 的内容人工纳入相关业务数据。批量请求先锁定并校验全部目标，任一目标不可复核则整批返回 409；同一当前版本重复提交幂等。模型原始 `analysis_content_results` 不会被更新或删除。

### 5.4 正式 Excel Export

```text
POST /api/v1/data-exports
GET  /api/v1/data-exports
GET  /api/v1/data-exports/{export_id}
GET  /api/v1/data-exports/{export_id}/download
```

代码：

```text
backend/src/aima_ugc/bootstrap/reporting_http.py
backend/src/aima_ugc/modules/reporting/
backend/src/aima_ugc/bootstrap/export_worker.py
backend/src/aima_ugc/platform/export/excel.py
```

下载只有在 Export 已完成且 Artifact 就绪时可用；未就绪返回 409，而不是空文件或 200。

### 5.5 Excel Import

```text
POST /api/v1/import-batches
GET  /api/v1/import-batches
GET  /api/v1/import-batches/summary
GET  /api/v1/import-batches/{batch_id}
GET  /api/v1/jobs/{job_id}
```

`POST /api/v1/import-batches` 当前接受 multipart：一个 `file` 和 1—20 个不重复 `keyword_pack_ids`。HTTP 层执行请求体大小与 multipart 形状校验；Import Service 冻结所选词包/关键词快照并创建 `ingestion.import-excel.v1` Job，真正 Excel 处理由 Worker 完成。

`GET /api/v1/jobs/{job_id}` 当前由 Import HTTP Service 提供，是 Import 产品面的通用 Job 查询入口；Analysis 还有独立的 `/content-analysis-jobs/{job_id}`。不要据此假设所有内部 `jobs` 表记录都自动成为公共 HTTP Contract。

代码：

```text
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/import_worker.py
```

### 5.6 Keyword Pack / Relevance

```text
POST /api/v1/keyword-packs
GET  /api/v1/keyword-packs
POST /api/v1/keyword-packs/{pack_id}/keywords
GET  /api/v1/keyword-packs/{pack_id}
PUT  /api/v1/keyword-packs/{pack_id}/enabled
PUT  /api/v1/relevance-config
GET  /api/v1/relevance-config
```

规则 Relevance 是导入/采集入口的关键词相关性能力；它和 AI Semantic Relevance 不是同一个字段，也不能混为一层。

### 5.7 Collection Plan

```text
POST /api/v1/collection-plans
GET  /api/v1/collection-plans
GET  /api/v1/collection-plans/{plan_id}
PUT  /api/v1/collection-plans/{plan_id}/enabled
```

代码：

```text
backend/src/aima_ugc/bootstrap/collection_strategy_http.py
backend/src/aima_ugc/modules/collection/planning.py
```

当前正式 API 没有 `/alerts`、`/reports`、`/analysis-runs` 之类未来占位路径。未来新增资源时以当时 Pydantic Contract 和 Route 为准，不提前在 Blueprint 冻结不存在的 URL。

---

## 6. 当前前端真实实现

真实 Router：

```text
frontend/src/app/routes.ts
```

当前注册：

```text
/
/voice-plaza
/collection-runtime
/collection-strategy
```

主要 Feature：

```text
frontend/src/features/voice-plaza/
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
```

含义：

- `/voice-plaza`：内容查询、筛选、详情、Analysis 交互；Analysis 按钮资格由后端 `content-analysis-capabilities` 驱动；“AI 相关性”可显式查看待复核 `irrelevant`，并支持单条/批量人工标记为相关；
- `/collection-runtime`：Excel Import / TikHub Run 的统一运行中心视图；
- `/collection-strategy`：Keyword Pack、全局 Relevance 和 Collection Plan 管理；
- `/`：当前 HomeView。

后端已经有 Export API，并不等于当前已经有独立 `/export` Vue 页面；类似地，Analysis 使用声音广场中的能力，不存在独立 `features/analysis/` 就不能写成已有 Analysis 页面。

---

## 7. 前端怎样调用 API

正确链路：

```text
Feature Page
→ Feature 内 API/Store
→ generated Client
→ HTTP
```

禁止：

- Page 里直接散落裸 `fetch()`；
- 手写一套后端 Response Type；
- 修改 `frontend/src/generated/api/`；
- Feature 直接导入另一个 Feature 的私有 Store；
- 在页面代码里理解 PostgreSQL 表结构；
- 直接读取 `env.local`、Secret 或复制后端配置规则来判断业务能力。

如果设计稿字段和后端 Contract 不一致，先判断需求是否要改后端，不要在页面层“猜字段”。

Figma 到代码流程：

[`../guides/01_Figma与前端设计开发工作流.md`](../guides/01_Figma与前端设计开发工作流.md)

---

## 8. Cursor 分页为什么不是页码

大列表当前使用不透明 Cursor，例如：

```json
{
  "items": [],
  "next_cursor": "opaque-value",
  "has_more": false
}
```

声音广场的 Cursor 实现：

```text
backend/src/aima_ugc/modules/content/content_cursor.py
backend/src/aima_ugc/bootstrap/content_http.py
```

它会把查询过滤条件 Hash 绑定到 Cursor，防止把一个查询的 Cursor 拿去另一个查询继续翻页。

Import Batch 和 Collection Runtime 也有各自独立 Cursor/Secret；不能复用数据库密码，也不能让前端解析并自行构造。

为什么这样做：

```text
created_at / published_at 在持续变化
+ 数据会新增
+ 页码 offset 很容易跳项/重复
→ 使用稳定排序位置 + ID 的 Cursor
```

---

## 9. Content Query 的当前 Analysis 语义

声音广场不是简单：

```sql
SELECT * FROM contents
```

当前 Query Adapter 会把：

```text
Content Current
+ current Content Version
+ 当前配置身份匹配的最新 Analysis Result
+ 当前来源 Request/Attempt/Raw
```

组装成 Read Model。

关键代码：

```text
backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
```

当前默认列表：

- 如果未显式筛 `relevance`，按**有效相关性**排除仍为 `irrelevant` 的内容；
- 有效相关性只在查询层计算：同一 `content_id + current_version` 存在人工 `relevant` 复核时优先采用人工决定，否则采用当前 AI relevance；
- `ContentAnalysisResponse.relevance` 继续返回模型原始判断，不被人工复核改写；
- 显式 `relevance=irrelevant` 只返回尚未人工纳入的当前不相关内容；`relevance=relevant` 同时包含 AI relevant 和当前版本人工纳入内容；
- 没有当前 Analysis 的内容仍可显示；
- 当前版本没有匹配 Analysis，但历史版本分析过时，会表现为 `stale`；
- 完全没分析过为 `pending`；
- 单条详情 `get_content()` 使用审计友好的读取，可读取 raw irrelevant Analysis 事实。

这也是为什么 AI relevance 当前不需要复制到 `contents.is_relevant`。

---

## 10. Job Runtime 的核心保证

公共代码：

```text
backend/src/aima_ugc/platform/jobs/
```

持久 Job 需要保证：

```text
queued
→ claim
→ running + lease + fencing token
→ heartbeat / progress
→ succeeded / failed / cancelled
```

关键点：

- Worker 可以接管 Lease 已过期的 running Job；
- 新 Worker 拿到新 Fencing Token；
- 旧 Worker 后续写入必须被 Token 拦住；
- Heartbeat 续 Lease，但不能无限延长 Attempt Deadline；
- Reaper 负责超时、取消、重试次数耗尽等终态处理。

业务 Job Handler 不应自己再实现一套“任务表/锁/重试”。

---

## 11. Scheduler 和 Worker 的区别

```text
Scheduler
→ 决定什么时候创建 Job

Worker
→ 执行已经存在的 Job
```

Scheduler 当前使用：

```text
(plan_id, schedule_version, scheduled_for)
```

作为 Occurrence 唯一身份，并在 PostgreSQL 短事务里创建：

```text
Occurrence
+ Job
+ scheduled Run
+ Scope
+ cursor 推进
```

详细语义：

[`../appendix/05_Scheduler调度执行与停机恢复.md`](../appendix/05_Scheduler调度执行与停机恢复.md)

---

## 12. 错误响应

统一错误结构由：

```text
HttpErrorResponse
```

定义于：

```text
backend/src/aima_ugc/contracts/http.py
```

典型形状：

```json
{
  "type": "https://aima.example/problems/invalid_xxx",
  "title": "请求失败",
  "status": 422,
  "detail": "可安全展示的错误说明",
  "request_id": "...",
  "errors": []
}
```

规则：

- 业务失败不返回 200；
- 响应不暴露 SQL、文件路径、Secret、原始 traceback；
- `request_id` 用于和日志关联；
- 未预期异常记录安全调用栈，用户只看到统一 500。

---

## 13. 当前认证边界

当前代码已经有真实业务 API 和页面，但企业认证尚未正式接入。

因此：

- 不能把当前 API 描述成已具备公网生产权限控制；
- 不能提前在业务模块绑定飞书 `open_id/union_id`；
- 未来身份 Provider 应进入统一 `Principal/AuthContext`；
- Authentication 与 Authorization 分开；
- 对象级下载/敏感资源权限最终由后端判断，不靠前端隐藏按钮。

认证接入属于独立高风险变更。

---

## 14. 修改一个 API 时应该检查什么

### 新增查询字段

```text
contracts/http.py / contracts/runtime.py（按边界选择）
→ Query Service / Repository
→ Cursor query hash（如果影响分页结果）
→ API Test
→ OpenAPI
→ generated Client
→ Feature
→ 文档
```

### 新增长任务

```text
Job Payload / Handler
→ Worker Registry
→ 业务父事实 + Job 同事务
→ Executor
→ Retry / Deadline / Fencing
→ API
→ Test
```

### 修改已有 Response

```text
先判断兼容性
→ Pydantic Contract
→ API Test
→ generate OpenAPI
→ generate Client
→ Frontend Typecheck/Test
```

更完整的任务导航：

[`../01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)

---

## 15. 当前不要假设存在的能力

当前代码不能证明以下能力已经存在：

```text
/api/v1/alerts
/api/v1/reports
独立 monitoring 模块
独立 dashboard 模块
企业登录/正式授权
Word Report 的正式 PostgreSQL Job/API
LLM 配置编辑/Secret 查询 API
```

未来实现时再由实际 Contract、代码和测试更新本文。

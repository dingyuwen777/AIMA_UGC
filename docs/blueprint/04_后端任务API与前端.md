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

- [`backend/src/aima_ugc/contracts/http.py`](../../backend/src/aima_ugc/contracts/http.py)
- [`backend/src/aima_ugc/contracts/runtime.py`](../../backend/src/aima_ugc/contracts/runtime.py)
- [`backend/src/aima_ugc/contracts/relevance_review.py`](../../backend/src/aima_ugc/contracts/relevance_review.py)
- [`backend/src/aima_ugc/bootstrap/api.py`](../../backend/src/aima_ugc/bootstrap/api.py)
- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/entrypoints/api_main.py`](../../backend/src/aima_ugc/entrypoints/api_main.py)
- [`contracts/openapi/openapi.json`](../../contracts/openapi/openapi.json)

前端真实路由看：

- [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts)

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

- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../backend/src/aima_ugc/bootstrap/content_http.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py)

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

- [`backend/src/aima_ugc/bootstrap/worker.py`](../../backend/src/aima_ugc/bootstrap/worker.py)

当前正式 Job：

```text
collection.run.v1
ingestion.import-excel.v1
ingestion.historical-discover.v1
ingestion.historical-snapshot.v1
ingestion.historical-import-chunk.v1
analysis.content-run-plan.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

三个 `ingestion.historical-*` 是统一 Data Import Campaign 继续沿用的物理 Job type；`analysis.content-run-plan.v1` 是新版 Analysis Run Planner。它们已经由当前 [`bootstrap/worker.py`](../../backend/src/aima_ugc/bootstrap/worker.py) 注册，不是未来规划。

注意：离线 Markdown/Word 报告当前不是上述 PostgreSQL Worker Registry 中的独立正式 Job；它目前由 `platform/reporting/` 和 [`imports_test/generate_report.py`](../../backend/src/aima_ugc/adapters/providers/imports_test/generate_report.py) 提供离线生成能力。不能因为“报告通常耗时”就把它写成当前已经产品化的 Job。

---

## 3. Router、Service、Repository 分别负责什么

### 3.1 Router

当前主 Router 与最终 API Assembly：

- [`backend/src/aima_ugc/bootstrap/api.py`](../../backend/src/aima_ugc/bootstrap/api.py)
- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/entrypoints/api_main.py`](../../backend/src/aima_ugc/entrypoints/api_main.py)

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
创建/预检/启动 Data Import Campaign
兼容上传单个 Excel Import Batch
预检并创建 Content Analysis Run
创建 Excel Export
创建/启停 Collection Plan
```

真实生产 Service 主要在：

- [`backend/src/aima_ugc/bootstrap/collection_http.py`](../../backend/src/aima_ugc/bootstrap/collection_http.py)
- [`backend/src/aima_ugc/bootstrap/collection_strategy_http.py`](../../backend/src/aima_ugc/bootstrap/collection_strategy_http.py)
- [`backend/src/aima_ugc/bootstrap/import_http.py`](../../backend/src/aima_ugc/bootstrap/import_http.py)
- [`backend/src/aima_ugc/bootstrap/historical_import_http.py`](../../backend/src/aima_ugc/bootstrap/historical_import_http.py)
- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../backend/src/aima_ugc/bootstrap/content_http.py)
- [`backend/src/aima_ugc/bootstrap/reporting_http.py`](../../backend/src/aima_ugc/bootstrap/reporting_http.py)

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
→ Analysis Run / Request / Result / Label Pair

historical_import.py / historical_content.py
→ Data Import Campaign/Item/Chunk 事实与历史补空写入协调

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

- [`backend/src/aima_ugc/contracts/http.py`](../../backend/src/aima_ugc/contracts/http.py)
- [`backend/src/aima_ugc/contracts/runtime.py`](../../backend/src/aima_ugc/contracts/runtime.py)

其中 `runtime.py` 只承载安全的运行能力读模型，不保存 Secret，也不成为 LLM 配置的第二事实源。

生成 OpenAPI：

- [`contracts/openapi/openapi.json`](../../contracts/openapi/openapi.json)

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

时间 Contract 统一规则：AIMA 自有 HTTP `datetime` 以带 `+08:00` 偏移的 ISO-8601 北京时间序列化；带时区的时间筛选进入 Contract 后先归一到 `Asia/Shanghai` 再解释。第三方 Raw 或外部协议必须保持原始 timestamp/epoch/timezone 语义的事实层不改写，只有进入 AIMA 自有展示/序列化边界时才按该边界规则转换。前端 generated Client 不维护第二套 UTC 假设。

---

## 5. 当前真实 HTTP API 面

下面来自当前 [`bootstrap/api.py`](../../backend/src/aima_ugc/bootstrap/api.py) 与最终 [`entrypoints/api_main.py`](../../backend/src/aima_ugc/entrypoints/api_main.py) Assembly，不是未来规划列表。

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

- [`backend/src/aima_ugc/bootstrap/collection_http.py`](../../backend/src/aima_ugc/bootstrap/collection_http.py)
- [`backend/src/aima_ugc/modules/collection/http.py`](../../backend/src/aima_ugc/modules/collection/http.py)

`collection-runtime/runs` 是统一只读投影，不意味着 Excel Import Batch 和 Collection Run 被合并成一张万能表。

`GET /collection-capabilities` 同时返回各 Provider/Platform 的可执行 Operation 和 Provider-neutral Search 选项。手工 Discovery 可以不传 `search_config`，后端会按 Capability 补齐并冻结“最新、一天内、不限内容”的可支持部分；新建周期 Plan 必须逐平台显式提交完整 `search_config`。平台不支持的维度不进入 Contract，前端不得自行维护另一套平台参数表。

历史 Plan 可能持久化空的 `config={}`。读取、重新启用和 Scheduler 执行继续接受这类记录，并沿用原 Adapter 默认行为；系统不把历史 Plan 静默改成新的手工 Discovery 默认值。

### 5.3 Content / 声音广场 / Analysis

```text
GET  /api/v1/contents
GET  /api/v1/contents/{content_id}
GET  /api/v1/content-analysis-capabilities
POST /api/v1/content-analysis-requests
GET  /api/v1/content-analysis-jobs/{job_id}
POST /api/v1/analysis/content-runs/preview
POST /api/v1/analysis/content-runs
GET  /api/v1/analysis/content-runs
GET  /api/v1/analysis/content-runs/{run_id}
POST /api/v1/analysis/content-runs/{run_id}/cancel
POST /api/v1/content-relevance-reviews
```

代码：

- [`backend/src/aima_ugc/contracts/runtime.py`](../../backend/src/aima_ugc/contracts/runtime.py)
- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../backend/src/aima_ugc/bootstrap/content_http.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/analysis.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/analysis.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/relevance_reviews.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/relevance_reviews.py)

`GET /content-analysis-capabilities` 是安全只读运行能力投影，只返回 `configured`。它用于让声音广场在 LLM Base URL / Model / Secret 未形成可执行配置时明确提示并禁用 AI 打标；前端不得读取 `env.local`、Secret 文件或复制后端配置判断。源码开发时，能力接口与 Worker 都从 `AIMA_EXTERNAL_SECRET_DIR` 对应的外部 Secret Root 读取 `llm_api_key`，不能误用只存 PostgreSQL/Cursor Secret 的内部 Root。该接口不返回 Base URL、Model、Provider、Secret 路径或 API Key，也不证明外部 LLM 此刻在线；Worker 的执行时配置守卫仍是最终防线。

`POST /content-analysis-requests` 是兼容入口，为保持既有 `request_id/job_id` Response，仍在 HTTP 短事务内冻结目标、创建首个 Shard 并建立 Analysis Run，并兼容历史 selected/query 语义。新页面只允许显式选择 1—1000 条内容：先调用 `/analysis/content-runs/preview` 取得目标数、Shard 数和模型/Prompt/配置身份，再由用户确认创建 Run；新版 Preview/Create Contract 不接受 query scope。创建 HTTP 只保存 Run 头与 Planner Job。Planner 在 PostgreSQL 事务内用 `INSERT ... SELECT` 冻结 Content ID + `current_version`，复核 Preview 数量并维持有界 Shard Job 窗口；数量变化时整次冻结回滚，Run 返回 Planner `error_code` 供页面展示。查询范围 Run 要等真实付费模型 Gold Set、费用和容量报告后重新决策。不同 Run 结果全部保留，Current 按 Run 创建顺序选择，最新失败/取消不会抹掉旧成功结果。

`POST /content-relevance-reviews` 是同步短事务：接收 1—1000 个不重复 Content ID，并显式提交 `decision=relevant / irrelevant / inherit_ai`。`relevant/irrelevant` 分别把当前 Content Version 人工覆盖为业务相关/不相关；`inherit_ai` 撤销活动人工覆盖并恢复当前 AI 基线。批量请求先锁定并校验全部目标，任一目标不可操作则整批返回 409；重复提交当前已经生效的决定幂等。已有人工覆盖要切换到相反人工结论时必须先撤销。模型原始 `analysis_content_results` 不会被更新或删除。`GET /contents` 与 Detail 同时返回 AI 原判和查询层派生的 `effective_relevance / relevance_source`，前端据此显示人工覆盖与撤销入口，不能从筛选条件猜测人工状态；AI 变为 `stale` 时活动人工覆盖仍可撤销。

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

### 5.5 Excel Import 兼容入口

```text
POST /api/v1/import-batches
GET  /api/v1/import-batches
GET  /api/v1/import-batches/summary
GET  /api/v1/import-batches/{batch_id}
GET  /api/v1/jobs/{job_id}
```

`POST /api/v1/import-batches` 当前接受 multipart：一个 `file` 和 1—20 个不重复 `keyword_pack_ids`。HTTP 层执行请求体大小与 multipart 形状校验；Import Service 冻结所选词包/关键词快照并创建 `ingestion.import-excel.v1` Job，真正 Excel 处理由 Worker 完成。

该入口仍是合法兼容 Contract，但当前采集运行中心的“导入数据”页面主入口使用 5.8 的 `/api/v1/data-import-*` Campaign，不再把 `/import-batches` 作为第二套页面工作流。

`GET /api/v1/jobs/{job_id}` 当前由 Import HTTP Service 提供，是 Import 产品面的通用 Job 查询入口；Analysis 还有独立的 `/content-analysis-jobs/{job_id}`。不要据此假设所有内部 `jobs` 表记录都自动成为公共 HTTP Contract。

代码：

- [`backend/src/aima_ugc/bootstrap/import_http.py`](../../backend/src/aima_ugc/bootstrap/import_http.py)
- [`backend/src/aima_ugc/bootstrap/import_worker.py`](../../backend/src/aima_ugc/bootstrap/import_worker.py)

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

- [`backend/src/aima_ugc/bootstrap/collection_strategy_http.py`](../../backend/src/aima_ugc/bootstrap/collection_strategy_http.py)
- [`backend/src/aima_ugc/modules/collection/planning.py`](../../backend/src/aima_ugc/modules/collection/planning.py)

### 5.8 统一数据导入 Campaign

```text
GET  /api/v1/data-import-sources/server/directories
POST /api/v1/data-import-campaigns/server
POST /api/v1/data-import-campaigns/local
PUT  /api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content
POST /api/v1/data-import-campaigns/{campaign_id}/finalize
GET  /api/v1/data-import-campaigns
GET  /api/v1/data-import-campaigns/{campaign_id}
GET  /api/v1/data-import-campaigns/{campaign_id}/items
GET  /api/v1/data-import-campaigns/{campaign_id}/conflicts
POST /api/v1/data-import-campaigns/{campaign_id}/start
POST /api/v1/data-import-campaigns/{campaign_id}/cancel
POST /api/v1/data-import-campaigns/{campaign_id}/retry-failed
```

页面以 `source_kind=local_upload / server_path` 区分文件怎样进入服务器，以 `ingestion_policy=standard_observation / historical_fill_only` 区分进入 Content Owner 后怎样写；两者相互独立并冻结在 Campaign。本地来源先提交安全相对路径和大小清单，再逐 Item 流式上传；服务器来源只收发管理员批准根目录内的相对路径。两者都必须先完成源文件 Artifact、SHA-256、流式预检和全部 Chunk 冻结，进入 `ready` 后页面才允许 start。Chunk 使用低优先级、有界窗口和逐行终态账本；导入不会自动创建 AI Job。

既有 `/api/v1/import-batches` 和 `/api/v1/historical-import-*` 暂时保留兼容，页面不再调用它们建立平行入口。物理表和 Job type 沿用 `historical_*` 名称是兼容选择，不改变统一业务资源。4000 万容量门禁仅覆盖 `server_path + historical_fill_only`；普通 `standard_observation` 复用既有逐记录 Content Owner 行为，未取得同规模吞吐证据。

Campaign Response 的 `progress` 由后端从 Source Item、Snapshot Job 和 Chunk Item 的持久状态集合式聚合，不由页面扫描有界明细或猜测。目录发现阶段尚不知道文件总数，页面显示不确定进度且不输出百分比；进入快照后按文件和 Snapshot Job 进度显示预检百分比；迁移阶段按已进入 `succeeded / failed / cancelled` 终态的 Chunk 行数除以冻结总行数显示，因此会按有界 Chunk 前进。终态进度表示“已完成对账”，成功、失败和取消仍由状态与统计分别表达。Analysis Run 列表不复制全部 Shard；页面只对活动 Run 补读既有详情接口，并以冻结的 Run `target_count` 为分母汇总 `Shard target_count × progress`，尚未进入有界调度窗口的目标因此保持 0%。Excel Export 和 Collection Scope 直接显示已有 Job/Scope 进度；普通 Excel Import 和 Collection Run 总进度继续复用原有实现。

当前正式 API 仍没有 `/alerts`、通用 Web Report Center 等未来占位路径。未来新增资源时以当时 Pydantic Contract 和 Route 为准，不提前在 Blueprint 冻结不存在的 URL。

---

## 6. 当前前端真实实现

真实 Router：

- [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts)

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
- `/collection-runtime`：Excel/TikHub 统一运行中心视图；其中只有一个“导入数据”入口，可选本地电脑或批准的服务器目录，并在同一 Campaign UI 中完成预检/启动/取消/重试、真实进度与冲突查看；
- `/voice-plaza`：Analysis Run 预检、显式创建、历史、加权进度与取消；导出弹窗同时展示持久 Export Job 进度；
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

- [`backend/src/aima_ugc/modules/content/content_cursor.py`](../../backend/src/aima_ugc/modules/content/content_cursor.py)
- [`backend/src/aima_ugc/bootstrap/content_http.py`](../../backend/src/aima_ugc/bootstrap/content_http.py)

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

- [`backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py)

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

- [`backend/src/aima_ugc/contracts/http.py`](../../backend/src/aima_ugc/contracts/http.py)

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

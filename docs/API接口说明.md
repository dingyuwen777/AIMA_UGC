# AIMA_UGC API 接口说明

本文是面向开发、联调、测试和维护人员的 **AIMA_UGC 人类可读 API 说明入口**。

它帮助人快速理解“系统有哪些公开 API、每个接口解决什么问题、前端怎样调用、成功/失败如何判断”。它不是第二套机器 Contract。

## 1. 事实源与生成关系

HTTP 接口的唯一手写事实源是后端 Pydantic Request/Response Model 与 FastAPI Route。固定机器契约由应用生成：

```text
Pydantic Request / Response
→ FastAPI Route + 稳定 operation_id
→ contracts/openapi/openapi.json
→ Orval
→ frontend/src/generated/api/
```

其中：

- `backend/src/aima_ugc/` 中的 Pydantic HTTP Contract 与 Route 是手写实现事实；
- `contracts/openapi/openapi.json` 是仓库固定、可机器校验的 OpenAPI 契约；
- `frontend/src/generated/api/` 是由 OpenAPI 生成的 TypeScript Client，禁止手工修改；
- **本文只负责给人解释接口用途和使用方式，不复制第二份完整字段 Schema。** 字段类型、必填/可选、枚举、响应结构等精确定义以固定 OpenAPI 和对应 Pydantic Contract 为准。

如果本文与代码、固定 OpenAPI 或测试冲突，必须先判断是实现缺陷还是本文过期，并在同一任务中修正；不能静默把本文当作机器事实覆盖代码。

## 2. 文档维护规则

任何新增、删除或实质修改公开 HTTP API 的任务，在完成前必须同时检查并按需更新本文。至少覆盖：

- 业务用途；
- HTTP 方法与路径；
- 稳定 `operation_id`；
- 主要请求输入；
- 主要成功响应；
- 重要错误与状态码；
- 是否创建异步 Job；
- 权限/身份要求（进入真实认证阶段后）；
- 分页、幂等、时间和 ID 等特殊规则；
- 前端应使用的生成 Client / Feature API 调用边界；
- 必要的最小调用示例。

以下内容不要在本文手工维护第二份完整定义：

- 所有 Request/Response 字段逐项类型表；
- 完整 JSON Schema；
- 自动生成 TypeScript 类型；
- Provider 私有字段；
- 数据库表结构。

这些内容应分别由 Pydantic、OpenAPI、生成 Client、Canonical Contract 和 Migration/Schema 维护。

## 3. 前端调用原则

前端调用链固定为：

```text
Vue Page / Component
→ Feature Store / Feature API
→ OpenAPI 生成 TypeScript Client
→ FastAPI Router
→ Application / Query Service
```

页面和按钮不得各自手写 `fetch` / `axios` URL、重复定义 Request/Response Type，或绕过生成 Client 建立第二套 API Contract。

一个需要前端使用的业务功能，默认按以下顺序闭环：

```text
后端业务能力
→ Pydantic HTTP Contract
→ FastAPI Route
→ API/Contract Test
→ 固定 OpenAPI
→ 生成 TypeScript Client
→ Feature API / Store
→ Vue 页面或组件
→ E2E
```

后端内部的 Repository、Mapper、Provider Adapter、Worker Lease/Fencing、Migration 等能力不因为“存在功能”就自动暴露 HTTP API；只有需要浏览器或外部受支持调用方使用的业务边界才建立公开 Route。

## 4. 全局 HTTP 约定

### 4.1 ID

公开 HTTP API 中的业务 ID 以字符串传输，避免 JavaScript 超过安全整数范围。

### 4.2 时间

HTTP 时间使用 UTC ISO-8601。前端负责按用户时区显示。

### 4.3 错误

业务 API 使用固定的 `type/title/status/detail/request_id/errors[]` Pydantic 错误结构；失败不得用 HTTP
200 冒充成功。`errors[]` 项固定包含可空 `field`、`code` 和 `message`。公开错误不暴露 SQL、Secret、
Token、服务器内部路径、堆栈或原始异常；响应头 `x-request-id` 与响应体 `request_id` 相同。
未处理的 500 错误会以 `api.request_failed` 记录同一 `request_id`、方法、路径和异常类型，不记录原始
异常消息或堆栈，避免连接串与 Secret 进入日志。

### 4.4 分页

大列表使用不透明 Cursor；Cursor 必须绑定稳定排序和查询条件，不能由前端解析其内部结构。

### 4.5 长任务

采集、回补、批量 AI、报告、导入导出等长任务通过持久化 Job 执行。HTTP API 负责创建/查询/取消 Job，而不是在请求生命周期中运行长任务。

## 5. 当前已经实现的公开接口

以下只列出当前已经存在于固定 OpenAPI 的接口。完整字段、枚举、默认值和错误响应以固定 OpenAPI 为准。

### 5.1 `GET /health/live`

- `operation_id`：`healthLive`
- 用途：判断 API 进程是否存活；不检查 PostgreSQL、Artifact 或日志目录等外部依赖。
- 成功：HTTP 200。
- 主要响应：`status = "ok"`。
- 前端用途：通常用于服务存活诊断，不作为业务页面是否可正常工作的充分依据。

### 5.2 `GET /health/ready`

- `operation_id`：`healthReady`
- 用途：检查 PostgreSQL、Artifact 根目录和日志目录是否就绪。
- 成功：依赖全部就绪时 HTTP 200。
- 未就绪：HTTP 503。
- 响应只暴露各组件 `ok/error`，不返回连接串、Secret 或原始异常。

### 5.3 `POST /api/v1/import-batches`

- `operation_id`：`createImportBatch`。
- 请求：`multipart/form-data`，且只允许一个 `file` 字段；只接受合法 `.xlsx`。
- 成功：HTTP 202，返回 `batch_id`、`job_id` 与 `queued`；请求结束后由持久化 Worker 继续处理。
- 安全边界：multipart body 最大 550 MiB，文件最大 500 MiB；XLSX 解压总量、单成员、成员数和压缩比
  另有固定上限。资源超限返回 413，文件/OOXML/成员路径不合法返回 422。
- 前置条件：必须已经通过 Relevance 配置 API 选择一个启用且有有效关键词的全局 Pack，否则返回 409。
- 当前未实现 HTTP actor 幂等或公网认证；该写接口只用于受控部署环境。

### 5.4 `GET /api/v1/import-batches`

- `operation_id`：`listImportBatches`。
- 用途：为采集运行中心返回 Excel Import Batch 列表；只读取关联
  `ingestion.import-excel.v1` Job，不把其他 Job 类型混入该 Read Model。
- 筛选：`identifier` 精确匹配 Batch ID 或 Job ID；`status`、`stage`、`created_from`、
  `created_to` 为可选条件。时间必须带时区，默认按 `created_at DESC, id DESC` 排序。
- 分页：默认 20、最大 100；响应返回 `items/next_cursor/has_more`。Cursor 由服务端签名、绑定当前
  查询条件并在 30 分钟后过期；前端只原样回传，非法、过期、篡改或跨查询复用返回统一 400。
- 安全：Cursor 签名配置不可用时关闭失败并返回统一 503，不暴露 Secret 内容或文件路径。

### 5.5 `GET /api/v1/import-batches/summary`

- `operation_id`：`getImportBatchSummary`。
- 用途：返回采集运行中心的三个数据库聚合事实：处理中 Batch 数、北京时间今日成功完成数、北京时间
  今日成功 Batch 的 `rows_ingested` 合计；不从当前 Cursor 页在前端推算。
- `processing_count` 统计关联 Job 为 `queued/running` 的 Batch；“今日”按 `Asia/Shanghai` 自然日
  切分后转换为 UTC 查询边界；`as_of` 返回本次统计的 UTC 时间。

### 5.6 `GET /api/v1/import-batches/{batch_id}`

- `operation_id`：`getImportBatch`。
- 返回固定 Batch 状态、阶段、计数统计、安全错误摘要、时间、可空安全原文件名和关联 Job 快照。
- Batch 状态由关联 Job 当前事实投影；不存在返回 404，非法 UUID 返回统一 422。

### 5.7 `GET /api/v1/jobs/{job_id}`

- `operation_id`：`getJob`。
- 当前公开查询只接受 Stage 8B `ingestion.import-excel.v1` Job，返回状态、Attempt/max_attempts、进度、
  安全错误码、时间与成功结果；其他内部 Job 类型不自动成为公共 API。
- 不存在或不是当前公开类型返回 404。

### 5.8 Keyword Pack

- `POST /api/v1/keyword-packs`：`createKeywordPack`，创建启用的空 Pack；同名返回 409。
- `POST /api/v1/keyword-packs/{pack_id}/keywords`：`addKeywordToPack`，添加或复用关键词；只接收原始
  `text`，数据库唯一身份由后端生成。
- `GET /api/v1/keyword-packs/{pack_id}`：`getKeywordPack`，读取 Pack 和稳定排序的关键词项。
- Stage 8B 只提供生成 Client 所需的最小 Contract；正式 Vue 配置页面属于 Stage 8F。

### 5.9 Global Relevance Config

- `PUT /api/v1/relevance-config`：`setGlobalRelevanceConfig`，用外键选择系统唯一 Keyword Pack；Pack
  不存在返回 404，停用或没有有效关键词返回 409。
- `GET /api/v1/relevance-config`：`getGlobalRelevanceConfig`，返回 Pack/Config 版本和实际有效关键词；
  尚未配置或不可用返回 409。
- Import Job 与 Collection Run 创建时冻结该快照，后续配置变化不会改写排队或运行中的执行语义。

### 5.10 TikHub Collection / 统一运行中心

- `GET /api/v1/collection-capabilities`：`getCollectionCapabilities`。只返回已启用且 Registry 可路由的
  Provider Config 稳定 ID/显示名，以及 `provider/platform/business operations`；不返回 Secret、
  Base URL、endpoint、Provider Operation、私有分页或 Pricing。
- `POST /api/v1/collection-runs`：`createCollectionRun`，成功返回 202。`discovery` 接收本次 Run 的一次性
  关键词；`batch_supplement` 接收一个已有 `import_batch_id` 且不得提交关键词。两种模式都显式选择
  1—5 个平台及其 `provider_config_id`，可选评论/二级回复，并在同一事务创建 Run/Scope 与既有
  `collection.run.v1` Job。请求结束后 Worker 执行 TikHub/Raw/Mapper/全局 Relevance/Ingestion；Router
  不执行长任务。当前没有 HTTP actor 幂等或公网认证，只适用于受信部署边界。
- `GET /api/v1/collection-runs/{run_id}`：`getCollectionRun`。返回固定 Run/Job 状态、阶段、Attempt、平台、
  一次性关键词、关联 Batch、Scope 进度/统计与安全错误摘要；不公开 Provider 私有游标或 Raw。
- `GET /api/v1/collection-runtime/runs`：`listCollectionRuntimeRuns`。用只读 UNION 集中返回
  `excel_import/tikhub_discovery/tikhub_batch_supplement`，支持文本、类型、状态、阶段和带时区创建时间
  筛选；默认 20、最大 100，使用绑定完整查询、30 分钟过期的 HMAC Cursor。签名配置不可用返回 503，
  非法/篡改/过期/跨查询复用返回 400。
- `GET /api/v1/collection-runtime/summary`：`getCollectionRuntimeSummary`。在 PostgreSQL 跨 Import Batch
  与 Collection Run 聚合处理中、北京时间今日完成及今日入库/采集内容；不从当前页在浏览器计算。
- Stage 8E Discovery 关键词只冻结在 Run，不保存为 Keyword Pack 或 Plan；持久配置属于 Stage 8F。

### 5.11 Content / 声音广场查询

- `GET /api/v1/contents`：`listContents`。查询统一 PostgreSQL Content Read Model，不区分 Excel、
  TikHub 或未来其他来源；支持文本、平台、内容类型、时间、来源 Batch/Run、AI 状态/情感/一级/二级
  标签过滤。文本搜索覆盖标题、正文、作者和外部内容 ID；Batch/Run 来源筛选匹配 Content 全部版本的
  来源账本，因此后续渠道更新 Current 后仍可从原 Batch/Run 找回相关内容。
- 分页默认 20、最大 100；按发布时间（缺失时用 last-seen）和 Content ID 倒序，使用绑定完整查询条件、
  30 分钟过期的 HMAC Cursor。非法、篡改、过期或跨查询复用返回统一 400。
- 列表的 `analysis.labels` 是按模型合法顺序返回的结构化 `{primary_label, secondary_label}` 数组；调用方
  必须展示全部标签对，不能只取首项。只有匹配当前 Content Version 和当前选定 Prompt/Taxonomy/
  Provider/Model 的成功结果是 `completed`；存在其他历史时返回 `stale`，从未分析为 `pending`。
- `GET /api/v1/contents/{content_id}`：`getContent`。除列表字段外返回合法媒体元数据、最多 100 条当前
  评论、最新 Coverage 和来源记录；没有图片时不会伪造缩略图。不存在返回 404。

### 5.12 显式 Content Analysis

- `POST /api/v1/content-analysis-requests`：`createContentAnalysis`。接收显式选择的 Content ID，或当前
  查询过滤快照；服务立即冻结 Content ID + Version，并在同一事务创建 Analysis Request 与
  `analysis.content-label.v1` durable Job，成功返回 202。
- `GET /api/v1/content-analysis-jobs/{job_id}`：`getContentAnalysisJob`。返回状态、Attempt、进度、错误码
  和成功/失败/stale 统计；HTTP 请求不会等待模型完成。
- 只有用户显式提交才调用模型；Import/Collection 默认不自动触发付费 Analysis。模型 Secret 只从
  Secret 文件装配，不进入 Payload、数据库、日志或响应。

### 5.13 声音广场 Excel 导出

- `POST /api/v1/data-exports`：`createDataExport`。冻结显式选择或当前查询结果的 Content ID + Version，
  创建 `reporting.content-export-excel.v1` durable Job，返回 202；Router 不生成 Excel。
- `GET /api/v1/data-exports`：`listDataExports`；`GET /api/v1/data-exports/{export_id}`：`getDataExport`。
  状态来自关联 Job，完成统计包含总内容、已打标、未打标和评论数。
- `GET /api/v1/data-exports/{export_id}/download`：`downloadDataExport`。只有 Job 成功且 Artifact 已 linked
  才返回 XLSX binary；未就绪返回 409，不存在返回 404。响应不暴露 storage key 或服务器路径。
- Worker 复用唯一 `UnifiedDataExcelV1 → export_unified_data_excel`；未打标/stale 内容仍导出，AI 列为空，
  不会被静默丢弃。当前没有已批准的自动删除期限。
- 当前认证尚未实现，上述写入与下载只适用于受信部署边界，不得直接宣称可公网开放。

## 6. 规划中的业务 API 分类

以下其余资源路径来自当前 Blueprint，是后续业务阶段的目标边界；**未实现前不得把本节视为现有 API。** 实际接口只有进入对应阶段、建立 Pydantic Contract、固定 OpenAPI 和测试后才算存在。

```text
/api/v1/collection-plans
/api/v1/collection-runs
/api/v1/comments
/api/v1/analysis-runs
/api/v1/alerts
/api/v1/reports
```

典型业务动作规划为：

```text
POST /api/v1/collection-plans/{id}/runs
POST /api/v1/jobs/{id}/cancel
POST /api/v1/comments/{id}/reviews
```

## 7. 如何确认本文没有落后

修改或新增 HTTP Contract 后，应从仓库根执行当前已有的 Contract 门禁：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
```

并运行与本次 API 相关的 Unit / Contract / API / Frontend / E2E 检查。最终以本轮实际测试、固定 OpenAPI 零漂移和 CI 结果证明接口可用，不能只因为本文已经更新就宣称 API 完成。

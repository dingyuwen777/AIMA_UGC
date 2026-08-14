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

业务 API 逐步统一为稳定错误结构；失败不得用 HTTP 200 冒充成功。公开错误不暴露 SQL、Secret、Token、服务器内部路径或原始异常。

### 4.4 分页

大列表使用不透明 Cursor；Cursor 必须绑定稳定排序和查询条件，不能由前端解析其内部结构。

### 4.5 长任务

采集、回补、批量 AI、报告、导入导出等长任务通过持久化 Job 执行。HTTP API 负责创建/查询/取消 Job，而不是在请求生命周期中运行长任务。

## 5. 当前已经实现的公开接口

当前仓库仍处于基础设施开发阶段，业务 API 尚未批量实现。以下表格只列出当前已经存在于固定 OpenAPI 的接口。

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

## 6. 规划中的业务 API 分类

以下资源路径来自当前 Blueprint，是后续业务阶段的目标边界；**未实现前不得把本节视为现有 API。** 实际接口只有进入对应阶段、建立 Pydantic Contract、固定 OpenAPI 和测试后才算存在。

```text
/api/v1/keyword-packs
/api/v1/collection-plans
/api/v1/collection-runs
/api/v1/contents
/api/v1/comments
/api/v1/analysis-runs
/api/v1/alerts
/api/v1/reports
/api/v1/jobs
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

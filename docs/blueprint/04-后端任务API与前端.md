# 后端任务、API 与前端

这篇文档回答：**页面点击一个按钮以后，请求怎样经过后端；为什么耗时操作必须创建 Job；前后端为什么不能各自猜字段。**

精确 HTTP 路径和字段见 [`../API接口说明.md`](../API接口说明.md) 与 `contracts/openapi/openapi.json`；Scheduler 细节见 [`../appendix/Scheduler运行与恢复.md`](../appendix/Scheduler运行与恢复.md)。

## 1. 普通读取怎么走

```text
Vue Page
→ Feature Store / Feature API
→ OpenAPI Generated Client
→ FastAPI Router
→ Query/Application Service
→ Query Repository / Read Model
→ PostgreSQL
```

最重要的原则：**每层只做自己负责的事情。**

- Page：组织页面和用户交互；
- Feature：一个具体业务能力；
- Generated Client：按后端 Contract 发 HTTP；
- Router：处理 HTTP 边界；
- Service：表达业务动作；
- Repository：读写 PostgreSQL；
- 数据库：保存业务事实。

## 2. 普通写入怎么走

短事务：

```text
Page
→ Generated Client
→ Router
→ Application Service
→ Owner Repository
→ PostgreSQL
```

耗时任务：

```text
Page
→ Generated Client
→ Router
→ Application Service
→ 创建业务父事实 + Job
→ PostgreSQL
→ 立即返回 202

Worker
→ 后台认领 Job
→ 执行业务
→ 更新进度/结果
```

Router 不等待十几分钟的 Excel 导入、Provider 采集或批量 AI。

## 3. Router、Service、Repository 分别做什么

### Router

负责：

- HTTP 方法/路径；
- Path/Query/Body 校验；
- 当前/未来身份授权依赖；
- 调 Service；
- 返回 Pydantic Response；
- 把业务错误映射成统一 HTTP 错误。

禁止：

- 直接 SQL；
- Provider 调用；
- 批量业务循环；
- 报告渲染；
- `except Exception: return 200`。

### Service

Service 表达一个真正的业务动作，例如：

```text
创建 Excel Import Batch
创建一次 Collection Run
更新 Relevance Config
创建 Analysis
创建 Excel Export
```

Service 负责业务校验、事务和模块协作，不依赖 Vue 字段布局。

### Repository

Repository 负责数据库事实。

- Owner Repository：本模块正式写入口；
- Query Repository：只读查询/Read Model。

不建一个“万能 BaseRepository”承载所有模块 SQL。

## 4. HTTP Contract 怎么保持前后端一致

唯一手写 HTTP 事实源：Pydantic Request/Response。

```text
Pydantic Request/Response
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
→ frontend/src/generated/api/
```

所以：

- Route 必须有稳定 `operation_id`；
- 生成目录禁止手工修改；
- 前端不复制一套 TypeScript 请求类型；
- Contract 改变后重新生成 Client 并跑 Contract/Frontend 验证。

删除字段、改名、改类型、可选变必填、改默认排序或错误语义，都可能是破坏性变化。

## 5. 当前正式业务 API 已经存在

当前系统不再是“只有 health smoke”。已经有与 Stage 8 对应的正式业务能力，例如：

- Excel Import Batch；
- Job 查询；
- Collection Capability / Run / Runtime；
- Keyword Pack；
- Global Relevance Config；
- Collection Plan；
- 声音广场 Content 查询；
- Analysis；
- Excel Export；
- Audit/设置等现有边界。

不要在 Blueprint 复制全部 URL/字段。实际联调入口：

- [`../API接口说明.md`](../API接口说明.md)
- `contracts/openapi/openapi.json`
- `frontend/src/generated/api/`

## 6. 当前前端边界

当前 Feature 已包括：

```text
analysis
export
import-excel
jobs
keyword-planning
overview
providers
runs
settings
voice-plaza
```

依赖方向：

```text
Page
→ Feature
→ Generated Client
```

### `pages/`

负责一个完整页面怎样组合多个 Feature。

### `features/`

负责一个具体业务能力的 Store、Feature API 和局部组件。

### `shared/`

只放真正跨业务复用的 UI/工具，不要把所有组件都提前搬成公共组件。

### `generated/api/`

后端 Contract 的生成结果。禁止手改。

Figma 工作流见 [`../guides/前端与Figma工作流.md`](../guides/前端与Figma工作流.md)。

## 7. 为什么长任务必须使用 PostgreSQL Job

如果 HTTP 请求直接做：

```text
上传 9 万行 Excel
→ 等 20 分钟
→ 浏览器断开
```

调用方无法可靠知道任务是否仍在运行，服务重启也难恢复。

当前长任务使用持久化 Job：

- Collection；
- Excel Import；
- AI Analysis；
- Excel Export；
- 后续报告、清理等真正长任务。

API 通常只需要返回：

```text
202 Accepted
job_id
resource_id
status=queued
```

页面再查询业务资源/Job 进度。

## 8. Job Runtime 怎么保证重启后还能继续

Job 不是一个 Python 内存队列。它保存在 PostgreSQL。

### Lease

某个 Worker 在一段时间内拥有任务执行权。

### Heartbeat

Worker 定期证明自己还活着。

### Deadline

当前 Attempt 不能无限运行；Heartbeat 不能把 Deadline 永远延长。

### Fencing Token

如果 Worker A 的 Lease 过期，Worker B 接管后会获得新 Token。A 即使后来恢复，也不能继续写业务结果。

白话理解：

> 不只要知道“谁在跑”，还要防止一个已经失去资格的旧 Worker 继续提交数据。

## 9. Job Payload 为什么要版本化

每个 Job 使用版本化 Pydantic Payload，例如：

```text
collection.run.v1
ingestion.import-excel.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

Payload 只保存稳定执行输入，不复制数据库可以通过受约束关系反查的事实，也不保存 Secret。

例如 `collection.run.v1` Handler 通过当前 Job ID 反查 Run，而不是在 Payload 再保存一个无法加外键约束的 `run_id`。

## 10. Scheduler 只负责“创建该跑的 Job”

Scheduler 链路：

```text
Plan
→ Occurrence
→ Run
→ Job
```

Scheduler 不直接请求 TikHub，也不直接运行 AI。

当前停机恢复策略固定 `latest_only`。详见 [`../appendix/Scheduler运行与恢复.md`](../appendix/Scheduler运行与恢复.md)。

## 11. API 错误为什么要统一

错误不能一会儿：

```json
{"error":"bad"}
```

一会儿：

```json
{"message":"失败"}
```

当前统一 Problem 风格响应包含稳定的：

```text
type
title
status
detail
request_id
errors（需要时）
```

原则：

- 4xx：调用方可修正；
- 5xx：服务端失败；
- 错误不伪装成 200；
- 响应不暴露 SQL、文件路径、Token/Secret；
- `request_id` 用于和日志关联。

精确结构由 Pydantic/OpenAPI/测试维护。

## 12. Cursor 为什么是不透明字符串

大列表如果使用 Cursor，前端只保存并原样回传，不自己解析。

Cursor 应绑定：

- 版本；
- 稳定排序位置；
- 查询条件；
- 过期时间；
- HMAC 签名。

只做 Base64 不是防篡改。

当前 Import Batch、Collection Runtime、声音广场等需要 Cursor 的场景使用独立签名 Secret，不能复用数据库密码或彼此复用一个 Key。

## 13. 认证当前是什么状态

当前第一版登录/企业身份接入明确延期。

长期依赖方向：

```text
飞书 / OIDC / 其他企业身份源
→ Identity Adapter
→ Principal / AuthContext
→ Authorization
→ 业务 Service
```

业务代码未来只消费统一 Principal/AuthContext，不直接用某个 Provider 的 `open_id` 做权限判断。

当前虽然已有业务页面/API，但**不能宣称具备公网生产认证能力**。

## 14. HTTP 幂等和 Job 幂等不要混

### Job 幂等

当前使用：

```text
job_type + internal_idempotency_key
```

### HTTP Idempotency-Key

长期需要稳定 actor/Principal 作用域。由于正式认证/Principal 尚未落地，当前不提前建立一套绑定虚假用户语义的 API 幂等表。

未来接认证时再明确 actor、过期时间、payload hash 和 409 语义。

## 15. 时间和 ID

- HTTP ID 一律按字符串使用；
- 数据库时间 `timestamptz`；
- API 返回 UTC ISO-8601；
- 前端负责显示本地/北京时间；
- 人工 `.log` 使用北京时间 `YYYY-MM-DD HH:mm:ss.SSS`。

不要在同一 Contract 混 Unix 秒、毫秒和无时区文本。

## 16. 一个最小例子：用户上传 Excel

```text
1. 前端 import-excel Feature 选择文件
2. Generated Client 调 POST Import Batch API
3. Router 校验 multipart
4. Service 保存 Input Artifact
5. 同事务创建 Processing Import Batch + Job
6. 返回 202
7. Worker 后台执行 ingestion.import-excel.v1
8. 前端查询 Batch/Job
9. 完成后页面看到统计/结果
```

浏览器关闭不会删除持久 Job。

## 17. 一个最小例子：声音广场 AI 打标

```text
1. Voice Plaza 查询 Content
2. 用户显式提交 Analysis
3. API 创建 analysis.content-label.v1 Job
4. Worker 调 LLM
5. Analysis Owner 保存 Result/Label Pairs
6. 页面重新查询 current Analysis
```

Router 不同步等待大批量模型调用。

## 18. 不要做的事

- Router 写 SQL；
- Page 直接 `fetch()` 另建业务 Client；
- 手改生成 Client；
- 把 Provider JSON 暴露成公共 API；
- 长任务占住 HTTP 请求；
- Worker 失去 Fencing 后仍写业务；
- 前端隐藏按钮就当成授权；
- 为了未来认证提前造本地用户/Session 表；
- 同一业务在两个 Feature 各写一套 Store/API。

## 19. 主要代码入口

- API 生产装配：`backend/src/aima_ugc/bootstrap/api.py`
- Router：`backend/src/aima_ugc/entrypoints/` 与对应 API 模块
- Job Runtime：`backend/src/aima_ugc/platform/jobs/`
- Worker：`backend/src/aima_ugc/bootstrap/worker.py`
- Scheduler：`backend/src/aima_ugc/bootstrap/scheduler.py`
- 前端：`frontend/src/`
- OpenAPI：`contracts/openapi/openapi.json`
- 人类 API 说明：[`../API接口说明.md`](../API接口说明.md)

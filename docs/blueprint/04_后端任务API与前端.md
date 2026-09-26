# 后端任务、API 与前端

本文解释 AIMA 中一条用户动作怎样跨越 Vue、HTTP、业务父事实、Durable Job、Worker 和 PostgreSQL。重点是**职责与状态流**，不是复制完整 API Catalog。

精确 HTTP Method / Path / Request / Response 只看：

- [backend/src/aima_ugc/contracts/http.py](../../backend/src/aima_ugc/contracts/http.py)
- [contracts/openapi/openapi.json](../../contracts/openapi/openapi.json)
- [frontend/src/generated/api/](../../frontend/src/generated/api/)

人类调用语义见 [docs/03_API接口说明.md](../03_API接口说明.md)。

## 1. 普通读取请求

~~~text
Vue Page
→ Feature API / Store
→ Generated Client
→ FastAPI Route
→ Query / Application Service
→ Query Repository
→ PostgreSQL
→ Response Model
~~~

Router 负责 HTTP 边界，不直接把 SQL、Provider JSON 或数据库 Row 暴露给前端。

## 2. 写请求和长任务

短写可以在一个请求事务内完成。

分钟级或需要恢复的长任务使用：

~~~text
HTTP
→ 校验权限和输入
→ 冻结业务请求 / Snapshot
→ 原子建立业务父事实 + Job
→ 返回 Accepted / Resource
→ Worker 认领
→ 执行并持久更新
→ 前端查询业务父事实
~~~

关键点是业务父事实与 Job 必须能解释彼此。不能出现“API 返回成功但 Job 根本没有创建”，也不能让 Worker 只有一个孤立 Job ID、无法知道用户到底提交了什么业务请求。

## 3. Router / Service / Repository

### Router

拥有：

- HTTP 参数解析；
- Principal / 权限入口；
- Pydantic Request / Response；
- HTTP 状态码与 Problem Response；
- 调用 Application Service。

不拥有 SQL、Provider HTTP、长循环或业务表状态机。

### Application / Domain Service

拥有业务编排和不变量，例如：

- 创建 Campaign / Run；
- 冻结 Snapshot；
- 计算幂等身份；
- 判断状态转换；
- 组织 Owner Repository。

### Repository

拥有持久化细节：

- SQL；
- Row lock；
- 唯一约束冲突解释；
- 原子查询/更新；
- 领域 Table Owner 规则。

跨 Owner 业务编排可以在 Service/Bootstrap 层完成，但各业务表仍由自己的 Repository 写。

## 4. HTTP Contract 的唯一事实链

~~~text
Pydantic
→ FastAPI
→ OpenAPI
→ Orval
→ Generated Client
→ Feature API / Store / Page
~~~

机器事实：

- [contracts/openapi/openapi.json](../../contracts/openapi/openapi.json)
- [frontend/src/generated/api/](../../frontend/src/generated/api/)

前端类型错时，先判断是后端 Contract 错还是 consumer 用错；不要在前端新建平行 Request/Response Type。

## 5. 业务 API 按资源域理解，不按 Route 清单理解

完整 Route 已由 OpenAPI 持有。Blueprint 只保留资源边界：

| 资源域 | 用户看到的业务对象 | 长任务/查询关系 |
| --- | --- | --- |
| Collection | Plan / Run / Scope / Runtime Read Model | Run 创建 Job，Runtime 聚合多类父事实 |
| Data Import | Campaign / Source Item / Conflict / Revocation | Discover / Snapshot / Chunk / Revocation Job |
| Replay | Replay Request / Run / Reversal | Planner / Replay / Shard / Reversal Job |
| Content | Content / Comment / Filter / Manual Review | 主要是 Query；部分人工动作短事务 |
| Analysis | Scheme / Run / Result / Manual Override | Planner / Label Shard Job |
| Reporting | Export Request / Artifact | Export Job |
| Administration | Provider / Brand / Vehicle / Scheme / Audit | 多为配置短事务 |
| Identity | Connector / Principal / Session | 登录、登出和授权边界 |

调用者需要精确 Path 时直接查 [contracts/openapi/openapi.json](../../contracts/openapi/openapi.json)，不要从 Blueprint 复制 URL。

## 6. 采集运行中心为什么是 Read Model

采集运行中心会同时展示：

- Data Import Campaign；
- 兼容 Import；
- Collection Run；
- Canonical Replay 等。

这不表示数据库应该把它们合成一张万能业务表。

正确模型：

~~~text
各自业务父事实
→ Query 层统一投影
→ Collection Runtime Read Model
→ 前端统一列表
~~~

这样用户得到一个入口，同时每种任务仍保留自己的状态机和审计来源。

## 7. 前端结构

当前 Route 唯一机器事实：

- [frontend/src/app/routes.ts](../../frontend/src/app/routes.ts)

当前前端组织和页面 Owner：

- [frontend/README.md](../../frontend/README.md)

稳定调用边界：

~~~text
Page / Component
→ Store / local state
→ Feature api.ts
→ Generated Client
→ HTTP
~~~

页面不拼业务 URL、不复制后端状态机，也不根据 Figma 示例值扩展后端枚举。

## 8. Cursor 为什么是不透明值

Cursor 绑定：

- 当前资源；
- Query / Filter；
- 排序；
- 最后位置；
- 签名/完整性。

前端只保存和原样回传 next_cursor，不能解析数据库字段、跨筛选条件复用或自己生成。

这样后端可以改变内部排序键编码，而不把数据库实现变成公共 Contract。

## 9. Content Query 与 Analysis

Content 是 UGC 事实，Analysis 是对某个 Content Version 的推理结果。

查询层可以投影：

- 当前有效 Analysis；
- 人工覆盖；
- active/historical taxonomy 值；
- 品牌车型证据；

但不能把这些结果反向写回 Provider Canonical，也不能为了筛选方便破坏历史 Analysis Result。

声音广场当前用户语义见 [docs/product/02_当前产品能力与用户流程.md](../product/02_当前产品能力与用户流程.md)。

## 10. Durable Job 的核心保证

正式 Job Registry：

- [backend/src/aima_ugc/bootstrap/worker.py](../../backend/src/aima_ugc/bootstrap/worker.py)

Job Runtime 长期必须保证：

- 持久身份；
- Lease / Heartbeat；
- Fencing；
- Deadline；
- Retry / Fail 分类；
- Cancellation；
- Progress / Result；
- 进程崩溃后的接管。

业务 Handler 不能因为“这个任务简单”绕过公共 Runtime 建一套线程/内存恢复机制。

## 11. 父任务与子 Job

大任务可以拆 Shard / Chunk / 子 Job，但父业务事实仍承担用户终态。

完成条件不能只是“父 Job 的 Python 函数跑完”，而应是：

~~~text
全部业务工作单元结清
+ 子 Job 终态符合规则
+ 父计数/断点对账
→ 父资源成功
~~~

Replay / 撤销等具体恢复语义见 [docs/appendix/08_数据入口与统一入库实现.md](../appendix/08_数据入口与统一入库实现.md)。全历史 Replay 的 HTTP 只负责冻结目录与受理边界并排队 Planner；历史 Artifact 枚举和子 Run 创建属于 Worker 长任务，不能重新塞回 API 短事务。

## 12. Scheduler 和 Worker 的区别

Scheduler：

~~~text
Plan
→ logical slot
→ Occurrence
→ Run / Job
~~~

Worker：

~~~text
Job
→ 执行业务
→ 持久化结果
~~~

Scheduler 不做 Provider/AI/Content 工作。Worker 不自行推导“现在是不是应该创建一轮周期任务”。

## 13. 错误响应与 request_id

HTTP 失败必须使用真实非 2xx 语义；未预期异常不能泄露 SQL、Secret、内部路径或 traceback。

request_id 用于把前端错误与服务端日志关联。

精确 Problem Contract 继续看 OpenAPI / Pydantic，不在 Blueprint 手抄字段全集。

## 14. Identity / Authorization

业务接口读取 Provider-neutral Principal。

通常：

~~~text
401
→ 没有有效会话 / 会话失效

403
→ 已有身份，但角色/用户组不允许该动作
~~~

管理员写接口必须由后端最终授权，前端隐藏按钮只是体验，不是安全边界。

Identity 产品状态见 [docs/product/03_角色权限与产品状态.md](../product/03_角色权限与产品状态.md)。

## 15. 修改 API / Job / 页面时从哪条链反查

### 查询字段

~~~text
业务语义
→ Contract
→ Query Service / Repository
→ Cursor identity（受影响时）
→ OpenAPI / Generated Client
→ Frontend consumer
→ Tests / Docs
~~~

### 长任务

~~~text
业务父事实
→ Frozen input / idempotency
→ Job Payload / Registry / Handler
→ Retry / Fence / Progress / Cancel
→ Query Read Model
→ Tests / Operations
~~~

### Response

~~~text
兼容性
→ Pydantic
→ OpenAPI
→ Generated Client
→ consumer
~~~

### 页面交互

~~~text
Product behavior / Figma
→ Page / Store / Feature API
→ Generated Contract
→ real backend behavior
~~~

通用研发和 Review 方法由 [AGENTS.md](../../AGENTS.md) 指定的 Agent_Skills 提供；本页只维护 AIMA 的系统事实链。

## 16. 本文明确不承担什么

- 完整 API Path/字段清单；
- 完整 Job type 清单；
- 完整前端 Route 清单；
- 每个页面组件树；
- 单次 Stage/PR/CI 历史；
- 通用 Coding / Testing / Review 方法。

精确集合由对应机器 Owner 持有，人类调用语义去 [docs/03_API接口说明.md](../03_API接口说明.md)。

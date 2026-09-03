---
schema: coding-change/v1
id: CHG-20260904-010706-analysis-provider-concurrency
title: AI Analysis Provider 并发、动态 Shard 与批量持久化
level: L3
status: in_progress
owner: chatgpt
branch: feature/335-analysis-provider-concurrency
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - system
  - administration-api
  - frontend-admin
  - postgres
  - runtime
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/bootstrap/analysis_worker.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/adapters/llm/
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/platform/config/settings.py
  - frontend/src/features/admin-configuration/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - tests/
  - compose.yaml
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - docs/blueprint/04_后端任务API与前端.md
contracts:
  - ProviderConfigCreateRequest
  - ProviderConfigUpdateRequest
  - ProviderConfigResponse
  - AnalysisContentRunPreviewResponse
data_changes: []
---

# 目标

让声音广场正式 AI Analysis 的模型调用吞吐从当前近似串行执行，升级为由每个 LLM Provider 自己的 `max_concurrency / max_rps` 驱动的有界并发流水线，并让离线 JSONL 与正式 PostgreSQL Worker 复用同一个并发核心。与此同时，以动态 Shard、批量短事务和背压避免千万级目标和 250/500/1000 模型并发把 PostgreSQL Job/事务/连接数量放大成新的瓶颈。

本 Change 的上游 Requirement Source 是 GitHub Issue #335；本文件只承担施工、验证和完成门禁，不把自己作为需求事实源。

# 当前事实与根因

- LLM Provider 已有数据库字段 `max_concurrency`、`max_rps`，且会冻结到 Analysis Run `runtime_config_snapshot`；无需新增容量字段或第二事实源。
- 管理员页面已在 Base URL / Model / API Key 旁暴露最大并发和最大 RPS，但前后端 Contract 当前把最大并发硬限制为 500。
- 离线 JSONL 链已经使用 Canary + `ThreadPoolExecutor` + `FIRST_COMPLETED` + 单内容单请求，DeepSeek 调试入口默认 250。
- 正式 `PostgresContentAnalysisJobExecutor` 当前同步执行 `ContentLabelingService.label_contents(...)`，Provider `max_concurrency` 只被传给 HTTP 连接池，并未创建真实的并发 LLM 调用。
- 正式 Worker 当前每条结果新建 Session/事务并重复 Fence/版本检查；随着模型并发提高，这会成为数据库写放大热点。
- Analysis Run 当前直接读取 `AIMA_ANALYSIS_RUN_SHARD_SIZE`，默认 1、代码上限 20；千万级目标会产生数量级过大的 Request/Job 生命周期。
- `JobWorker` 仍一次认领一个 Job；本 Change 通过每个 Shard 内部的有界模型并发取得吞吐，不新增第二套队列或消息中间件。

# 已确认关键决定

1. `max_concurrency` 是 LLM Provider 级容量，由管理员维护，不写死 DeepSeek 250；至少支持配置 1000。
2. Shard Size 不由管理员配置；根据 Run 冻结的 Provider concurrency 自动计算并冻结到 Run。
3. 初始自动 Shard 目标为 `max_concurrency × 20 waves`，并使用内部安全上下限；250 约 5,000，1000 约 20,000。
4. 保持“一条 Content = 一个独立逻辑 LLM 请求”。
5. 离线和正式模式复用同一有界并发调度核心；不复制两套并发算法。
6. `max_rps` 限制每次物理 HTTP Attempt，包括 Transport Retry；Validation Retry 与 Transport Retry 分层。
7. 1000 模型并发不对应 1000 数据库连接。模型请求完成后由有界结果批次写入 PostgreSQL，外部 HTTP 永不进入 DB 事务。
8. 本任务不新增数据库业务字段、不引入 Redis/Kafka/RabbitMQ/Celery、不升级 Runtime/框架/依赖。

# 方案比较

## 方案 A：只把 `max_connections` 和前端上限改大

优点：改动最小。

缺点：HTTP connection pool 本身不产生并发；正式 Worker仍同步执行，无法解决根因；数据库逐条事务不变。拒绝。

## 方案 B：为每条 Content 建 Job / 增加大量 Worker 进程

优点：复用现有 Job claim。

缺点：千万级数据会制造千万级 Job/Request 调度和 PostgreSQL 元数据开销；1000 LLM 并发会演变成大量 Worker/DB 连接，破坏当前模块化单体和 durable Job 设计的成本边界。拒绝。

## 方案 C：Shard 内部 Provider 驱动有界并发 + 批量持久化（采用）

优点：直接复用离线已验证的并发机制；Job Runtime 只负责 Shard 生命周期；模型并发与 DB 连接解耦；不需要新中间件；可用同一个执行核心证明离线/正式机制一致；旧 Run 仍使用冻结 shard_size/runtime snapshot。

代价：需要同时修改 Analysis Worker、Repository、Provider Adapter 包装、动态 Shard、Contract/generated client 和测试，是跨模块 L3 变更。

# 范围

1. 新建 Analysis 通用有界并发执行核心，支持 Canary、峰值并发、`FIRST_COMPLETED` 收割、停止调度、fail-fast/错误隔离与完成批次回调。
2. Offline JSONL 改为复用该公共执行器，保持 DeepSeek 默认 250、单内容请求、checkpoint/失败恢复语义。
3. Formal Analysis Worker 按 Run 冻结 `max_concurrency` 真实并发执行单内容模型请求；Canary 通过后才 fan-out。
4. `max_rps` 通过 LLM Adapter wrapper 对每次物理 Attempt 限速；Transport Retry wrapper 对单条请求生效。
5. Formal Worker 把完成结果以有界批次写入 PostgreSQL；Repository 一次批量持久化锁定 Fence/Request，保持版本、配置身份、幂等和标签完整性。
6. `stats()` 等按 Shard 放大的 Python 全量计数改为 SQL 聚合。
7. Analysis Preview/Create 根据 Provider concurrency 自动计算并冻结 Shard Size；移除管理员/Compose 的手工 `AIMA_ANALYSIS_RUN_SHARD_SIZE` 入口。
8. Provider 管理 Contract/UI 至少支持 1000，并把 `max_retries` 的界面文案明确为 Validation Retry；Shard 不在管理员页面可编辑。
9. 重新生成 OpenAPI/generated client，补齐 Unit/Contract/PostgreSQL Integration/Frontend/性能边界回归和文档。

# 非目标

- 不修改 Prompt、Taxonomy、模型输入字段或 Analysis Result 业务语义。
- 不新增 Analysis token/cost 数据库列或预算系统。
- 不改变内容保留、Current Analysis 选择、人工 Review 或声音广场轮询语义。
- 不引入独立消息系统、Celery、微服务或 Kubernetes。
- 不在普通 CI 中调用付费真实 LLM；真实 Provider 容量只在明确费用/环境授权下做有界 Probe。
- 不在没有测量证据前做表分区、分库或 PostgreSQL 大规模参数调优。

# 必须保持不变

- Run 创建后继续冻结 Prompt/Taxonomy/Provider/Model/generation/runtime snapshot；旧 Run 不因新 Provider 配置变化而改变。
- 每条成功结果仍验证 Content Version、Run 配置身份和当前 Job Fence。
- Job/Result 幂等、Run sequence Current 语义、cancel/retry/terminal callback 保持可恢复。
- API Key 不回显、不进入数据库明文/日志/审计。
- 外部 LLM HTTP 在 PostgreSQL 事务外执行。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Provider 并发由管理员按模型配置，至少支持 1000，不写死 250 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待实现并验证 Provider Contract/UI/generated client。 |
| R2 | Formal Worker 真正按冻结 `max_concurrency` 有界并发且一条 Content 一次逻辑请求 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待公共并发核心与 Formal Worker 回归。 |
| R3 | Offline/Formal 复用同一个并发核心，Canary/收割/停止调度机制同源 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待代码复用和测试证据。 |
| R4 | `max_rps` 约束物理 Attempt，Transport Retry 与 Validation Retry 分层 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待 LLM wrapper 和 retry/rate-limit tests。 |
| R5 | Shard 自动按 Provider concurrency 计算并冻结；250≈5000、1000≈20000；管理员不配置 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待 Preview/Create/旧 Run 回归。 |
| R6 | LLM 并发与 DB 连接解耦，批量短事务/背压避免逐条 Session 写放大 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待 Repository batch persistence + PostgreSQL Integration。 |
| R7 | Fence、版本、配置身份、幂等、标签、取消/失败隔离不回归 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待 unit/integration/job regression。 |
| R8 | 250/500/1000 受控性能边界有证据；正式链目标达到离线链 90%，目标 95%+ | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待 Fake benchmark/CI；真实 Provider 若未授权则明确为外部容量未验证。 |
| R9 | 不引入新中间件/Schema/依赖升级，文档/CI/Review/归档完整 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | not_satisfied | 待最终 diff、CI、Review 与 main-fresh 证据。 |

# Validation Matrix

| Layer | Required | Scope / Planned Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 公共并发执行器、自动 Shard、Rate Limit、Retry、Formal item failure/cancel、Offline 同源执行；真实线程并发断言 peak-in-flight。 |
| 接口 / Contract | required | Provider `max_concurrency>=1000` 的 Pydantic/OpenAPI/generated client 漂移和前端类型/表单约束。 |
| 集成 / Persistence / Runtime Dependency | required | 真实 PostgreSQL batch persistence：Fence、版本 stale、幂等、label pair、失败项、SQL 聚合统计；Worker/Job runtime 相关回归。 |
| 用户 / Workflow Acceptance | required | 管理员从正式 Provider 配置入口保存/读取 1000 并发；Analysis Preview 显示自动 shard_size 且无可编辑 Shard。 |
| 跨组件 Golden Path | required | 关键真实链：Provider config → Analysis Run snapshot/shard → Worker Fake LLM 并发 → PostgreSQL Result/Run terminal；不调用付费 Provider。 |
| External Dependency / Provider Probe | not_applicable | 本任务不改变外部 Provider 协议；真实 LLM 并发额度/吞吐需要独立费用和环境授权，普通 CI 不承担。 |
| Build / Package / Runtime | required | 后端 wheel/静态检查、前端 lint/typecheck/unit/build、正式 CI scope；Compose/配置解析回归。 |
| Docs / Governance / Other | required | Change Ready、Contract generation drift、Blueprint/Analysis README/Appendix 与最终实现一致、独立 Review。 |

# 实施步骤

1. 建立失败测试：Provider 1000、动态 Shard、公共 bounded executor、Formal concurrency/error isolation、rate limit/retry、batch persistence。
2. 抽取公共 bounded executor，并把 Offline 改为复用；证明原离线行为不变。
3. Formal Worker 接入 Provider concurrency、Canary、单内容请求、per-item Transport Retry/RPS、取消停止调度。
4. Repository 增加 batch persistence + SQL aggregate stats；Worker 分批落库并形成自然背压。
5. Preview/Create 改为自动 Shard；删除手工 shard_size runtime 配置，保持旧 Run 冻结字段兼容。
6. Provider Contract/UI 上限和文案调整；生成 OpenAPI/generated client。
7. 执行 20/250/500/1000 Fake 并发/性能边界、PostgreSQL integration、用户/Golden Path、build 和永久 CI。
8. 同步文档，完成 Completion Audit、独立 Review、PR/CI，guarded merge main 后跑 main-fresh 验证并归档 Change。

# Migration / 部署 / 回滚

- 数据库 Schema：计划不变；现有 Integer/JSONB/Run shard_size 能承载本变更，不创建 Migration。
- 部署：正常应用镜像升级即可；新 Run 自动使用新的 Shard/并发引擎，旧 Run 读取自己的冻结 `shard_size/runtime_config_snapshot`。
- 回滚：代码回退到上一个 Release 即可继续读取既有 Run/Provider 数据；因为不新增 Schema，数据级回滚不需要 destructive migration。
- 风险：Provider 配置过高可能放大线程/网络/模型压力；实现必须使用有界 in-flight、RPS、Canary、批量 DB 背压和可观测峰值；CI 不能把“配置允许 1000”误写成“任意 Provider/机器都已验证能承受 1000”。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 当前状态

- Issue #335 已建立；当前分支从 main `59edfe793b913d11283952567f4e1a6e0003c6df` 创建。
- 根因和方案已由当前代码、正式架构和离线正常参照确认；尚未开始宣称性能提升。

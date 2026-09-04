---
schema: coding-change/v1
id: CHG-20260904-010706-analysis-provider-concurrency
title: AI Analysis Provider 并发、动态 Shard 与批量持久化
level: L3
status: ready_for_review
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
  - backend/src/aima_ugc/bootstrap/analysis_concurrent_worker.py
  - backend/src/aima_ugc/bootstrap/analysis_high_throughput_planner.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/runtime_config.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/adapters/llm/
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_batch.py
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_high_throughput.py
  - backend/src/aima_ugc/contracts/administration.py
  - frontend/src/features/admin-configuration/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - tests/unit/analysis/
  - tests/unit/content/test_stage12_analysis_planner.py
  - tests/integration/content/test_analysis_provider_concurrency.py
  - frontend/e2e-fullstack/stage12-historical-analysis.spec.ts
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/02_环境运行与部署.md
  - docs/appendix/07_AI舆情打标与分析实现.md
contracts:
  - ProviderConfigCreateRequest
  - ProviderConfigUpdateRequest
  - ProviderConfigResponse
  - AnalysisContentRunPreviewResponse
data_changes: []
---

# 目标

让声音广场正式 AI Analysis 的模型调用吞吐从近似串行执行，升级为由每个 LLM Provider 自己的 `max_concurrency / max_rps` 驱动的有界并发流水线，并让离线 JSONL 与正式 PostgreSQL Worker 复用同一个并发核心。与此同时，以动态 Shard、批量短事务和背压避免千万级目标和 250/500/1000 模型并发把 PostgreSQL Job/事务/连接数量放大成新的瓶颈。

本 Change 的上游 Requirement Source 是 GitHub Issue #335；本文件只承担施工、验证和完成门禁，不把自己作为需求事实源。

# 当前事实与根因

- LLM Provider 已有数据库字段 `max_concurrency`、`max_rps`，且会冻结到 Analysis Run `runtime_config_snapshot`；无需新增容量字段或第二事实源。
- 原管理员 Contract 把最大并发限制为 500；Provider 容量虽然能进入 HTTP connection pool，但原正式 Analysis Executor 没有据此并发模型调用。
- 离线 JSONL 链已有单内容单请求、Canary、有界线程并发与 `FIRST_COMPLETED` 收割，DeepSeek 调试入口默认 250。
- 原正式 Worker 同步执行 `ContentLabelingService.label_contents(...)`，并且每条结果独立 Session/事务/Fence；高并发下会同时受到模型串行和数据库逐条写放大限制。
- 原新 Analysis Run 读取静态 `analysis_run_shard_size`；对千万级目标若 shard_size 很小会产生数量级过大的 Request/Job 生命周期。
- `JobWorker` 仍一次认领一个 Job；本 Change 通过每个 Shard 内部的有界模型并发取得吞吐，不新增第二套队列或消息中间件。

# 已确认关键决定

1. `max_concurrency` 是 LLM Provider 级容量，由管理员维护，不写死 DeepSeek 250；至少支持配置 1000。
2. Shard Size 不由管理员配置；新数据库 Provider Run 根据冻结 Provider concurrency 自动计算并冻结。迁移前 legacy env bootstrap 路径保留历史静态 shard 兼容，旧 Run 始终读取自己已冻结的 shard_size。
3. 初始自动 Shard 目标为 `max_concurrency × 20 waves`，并使用内部安全上下限；250 约 5,000，1000 约 20,000。
4. 保持“一条 Content = 一个独立逻辑 LLM 请求”。
5. 离线和正式模式复用同一有界并发调度核心；不复制两套并发算法。
6. `max_rps` 限制每次物理 HTTP Attempt，包括 Transport Retry；Validation Retry 与 Transport Retry 分层。
7. 1000 模型并发不对应 1000 数据库连接。模型请求在线程侧执行，完成结果由调度线程有界批量短事务写 PostgreSQL；外部 HTTP 永不进入 DB 事务。
8. 本任务不新增数据库业务字段、不引入 Redis/Kafka/RabbitMQ/Celery、不升级 Runtime/框架/依赖。

# 方案比较

## 方案 A：只把 `max_connections` 和前端上限改大

优点：改动最小。

缺点：HTTP connection pool 本身不产生并发；正式 Worker 仍同步执行，无法解决根因；数据库逐条事务不变。拒绝。

## 方案 B：为每条 Content 建 Job / 增加大量 Worker 进程

优点：复用现有 Job claim。

缺点：千万级数据会制造千万级 Job/Request 调度和 PostgreSQL 元数据开销；1000 LLM 并发会演变成大量 Worker/DB 连接，破坏当前模块化单体和 durable Job 设计的成本边界。拒绝。

## 方案 C：Shard 内部 Provider 驱动有界并发 + 批量持久化（采用）

优点：直接复用离线已验证的并发机制；Job Runtime 只负责 Shard 生命周期；模型并发与 DB 连接解耦；不需要新中间件；可用同一个执行核心证明离线/正式机制一致；旧 Run 仍使用冻结 shard_size/runtime snapshot。

代价：需要同时修改 Analysis Worker、Repository、Provider Adapter 包装、动态 Shard、Contract/generated client 和测试，是跨模块 L3 变更。

# 实施结果

1. `modules/analysis/concurrent_labeling.py` 提供 Offline/Formal 共用 bounded executor：Canary、bounded in-flight、`FIRST_COMPLETED`、错误隔离/fail-fast、停止补调度和 scheduler-thread 完成回调。
2. Offline `label_unified_content_jsonl` 的公开入口已切到 `offline_concurrent_labeling.py`，继续保持默认 250、单内容请求、checkpoint/失败恢复与最终重写语义。
3. Formal Worker 已切到 `ConcurrentPostgresContentAnalysisJobExecutor`：按 Run 冻结 Provider `max_concurrency` 并发执行单内容请求，共享一个 HTTP Client，模型调用不持有 DB Session/事务。
4. `RateLimitedContentLabelingLLM` 对每次物理 Attempt 取得 RPS slot；外层 `RetryingContentLabelingLLM` 使每次 Transport Retry 重新限速，Validation Retry 继续由 `ContentLabelingService` 管理。
5. 完成结果以 200 条为有界批次写入 `PostgresAnalysisBatchRepository`；每批一次 Fence，批量校验 Content Version/配置身份、幂等 Result/Label，并用 executemany 更新 Request Item。
6. 高吞吐 Run 统计优先读取已完成 Job 的 result 计数，仅对少量非成功/活动 Shard 扫 Request Item，避免随大 Run 重复做 Python O(n) 聚合。
7. `HighThroughputContentAnalysisPlanJobExecutor` 对 all scope 以 10,000 条 UUID keyset 批次冻结目标，并只维持配置允许的少量 Shard Job in-flight；Shard 终态回调继续补调度。
8. 新数据库 Provider 的 Preview/Create 使用 `calculate_analysis_shard_size(max_concurrency)` 冻结 Shard Size；legacy env bootstrap 保持历史静态 shard 兼容。
9. Provider 管理 Contract/UI/generated client 已同步至 `max_concurrency <= 5000`，界面明确为“模型并发上限”；`max_retries` 明确为 Validation Retry；Shard 不对管理员暴露编辑入口。
10. Stage12 声音广场验收已同步当前产品语义：活动 Run 留在声音广场；快速结束的历史 Run 在全局任务中心“最近完成”验证终态。

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
| R1 | Provider 并发由管理员按模型配置，至少支持 1000，不写死 250 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | `ProviderConfigCreateRequest/UpdateRequest`、OpenAPI/generated client 与 `ProviderConfigurationPanel.vue` 统一支持至少 1000；`tests/unit/analysis/test_provider_concurrency_contract.py` 覆盖 1000 与安全上限。 |
| R2 | Formal Worker 真正按冻结 `max_concurrency` 有界并发且一条 Content 一次逻辑请求 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | `analysis_concurrent_worker.py` 使用 Run snapshot concurrency 调用公共 executor；`tests/integration/content/test_analysis_provider_concurrency.py` 在真实 PostgreSQL Job 链断言 peak_active=4 且 `item_sizes == [1] * 8`。 |
| R3 | Offline/Formal 复用同一个并发核心，Canary/收割/停止调度机制同源 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | `modules/analysis/__init__.py` 的 Offline 公开入口切到 `offline_concurrent_labeling.py`，与 Formal 同用 `run_bounded_concurrently`；`test_bounded_concurrency.py` 覆盖 Canary、错误隔离和取消后停止补调度。 |
| R4 | `max_rps` 约束物理 Attempt，Transport Retry 与 Validation Retry 分层 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | `RateLimitedContentLabelingLLM` 位于 Transport Retry 内层；`tests/unit/analysis/test_llm_rate_limit.py` 用虚拟时钟证明 2 RPS 下 3 次物理 Attempt 分别从 0.0/0.5/1.0 秒启动。 |
| R5 | Shard 自动按 Provider concurrency 计算并冻结；250≈5000、1000≈20000；管理员不配置 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | `calculate_analysis_shard_size()` 采用 20 waves + 20/50000 内部边界；`test_analysis_sharding.py` 断言 250→5000、1000→20000；真实 PostgreSQL Integration 验证 Run snapshot/shard 冻结。 |
| R6 | LLM 并发与 DB 连接解耦，批量短事务/背压避免逐条 Session 写放大 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | Worker threads 只执行 LLM；scheduler 回调按最多 200 条调用 `PostgresAnalysisBatchRepository.persist_batch()`；每批短事务一次 Fence，PostgreSQL Integration 全链验证持久化。 |
| R7 | Fence、版本、配置身份、幂等、标签、取消/失败隔离不回归 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | Batch Repository 保留 Fence/version/config/idempotency/label 校验；PostgreSQL Integration、Job Runtime regression 与 `test_parallel_transport_error_only_fails_one_content` 验证单条失败隔离，公共 executor 单测验证取消停止补调度。 |
| R8 | 20/250/1000 受控并发边界有证据；正式链目标达到离线链 90%，目标 95%+ | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | satisfied | 公共 executor 真实线程回归覆盖 20/250，1000 档验证 bounded in-flight；零付费同源基准在同一 runner、8 条、并发 4、固定 3 秒 LLM 延迟下测得 Offline 0.888 item/s、Formal 0.877 item/s、Formal/Offline=98.86%（门槛 90%）。真实 Provider 250/1000 的额度、网络/GPU 容量仍属于未授权的外部 Probe，不由该结果冒充。 |
| R9 | 不引入新中间件/Schema/依赖升级，文档/CI/Review/归档完整 | https://github.com/dingyuwen777/AIMA_UGC/issues/335 | explicitly_deferred | 当前 PR 未新增 Migration/中间件/依赖升级，文档、Contract 与独立 Review 已同步；永久 CI、guarded merge、main-fresh 校验、Issue 自动关闭、分支清理和 Change archive 属于合并门禁/合并后动作，不能在 Active Change 的 Ready 阶段提前伪造完成。 |

# Validation Matrix

| Layer | Required | Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `test_bounded_concurrency.py` 覆盖 20/250、1000 bounded in-flight、Canary、错误隔离、取消；`test_analysis_sharding.py`、`test_llm_rate_limit.py`、Provider contract unit 覆盖容量规则。 |
| 接口 / Contract | required | Pydantic Provider Contract、`contracts/openapi/openapi.json`、Orval generated client 同步；Repository Quality 的 generated-contract drift gate 已在候选分支通过过，最终 HEAD 仍由永久 CI 复核。 |
| 集成 / Persistence / Runtime Dependency | required | `tests/integration/content/test_analysis_provider_concurrency.py` 通过真实 PostgreSQL/Job Runtime 验证 Provider snapshot→Planner→Shard→并发 Fake LLM→批量 Result/Run 终态与失败隔离；永久 PostgreSQL Integration 在候选 HEAD 复核。 |
| 用户 / Workflow Acceptance | required | Provider 管理前端测试验证 1000 配置/文案；Stage12 Full-stack 从真实 API/Worker/Browser 入口验证 Analysis Run 活动/历史终态语义。 |
| 跨组件 Golden Path | required | Real Full-stack Golden Path 使用真实 API、Worker、PostgreSQL 与 Browser；外部 LLM 仅替换为可控 Fake，避免付费 Provider 成为普通 CI 前置。 |
| External Dependency / Provider Probe | not_applicable | 本任务未获真实 Provider 费用/环境 Probe 授权；真实 DeepSeek/其他部署在 250/1000 下的额度、网络和模型服务容量不在本轮声称范围。 |
| Build / Package / Runtime | required | Ruff format/lint、mypy、wheel/build、Runtime Acceptance、Developer Tooling、Release dry-run 由永久 workflow 验证；当前最终候选 HEAD 必须保持 required checks 全绿才可 merge。 |
| Docs / Governance / Other | required | `modules/analysis/README.md`、`docs/02_环境运行与部署.md`、`docs/appendix/07_AI舆情打标与分析实现.md` 已同步；PR `Requirement-Source: #335`；本 Change 进入 `ready_for_review` 后由 Completion Gate 机器复核。 |

# 受控吞吐基准

为避免把纯 helper Unit 冒充“Formal 已接近 Python 脚本”，额外执行了一次零付费、一次性的同机受控基准，并在完成后删除临时 workflow/script，不进入最终 PR diff。

基准条件：

- 同一 GitHub runner；
- 8 条相同业务内容；
- 相同 Prompt/Taxonomy/Fake Provider 输出；
- `max_concurrency=4`；
- 每个物理模型请求固定模拟 3.0 秒延迟；
- Offline 使用正式 `label_unified_content_jsonl` 公共入口；
- Formal 使用真实 PostgreSQL、Import、Analysis Planner、Job Worker、批量持久化和 Run 终态链；
- 两边均断言单 Content 单请求和峰值并发为 4。

结果：

- Offline：9.013 秒，0.888 item/s；
- Formal：9.117 秒，0.877 item/s；
- Formal / Offline：98.86%；
- 验收门槛：≥90%。

该结果证明当前代码编排/持久化额外开销在受控高延迟 LLM 场景下没有重新把 Formal 路径串行化；它不证明任何真实 Provider 当前能承受 250/1000 并发，也不替代上线前按具体模型部署做容量压测。

# Migration / 部署 / 回滚

- 数据库 Schema：不变；现有 Integer/JSONB/Run shard_size 能承载本变更，不创建 Migration。
- 部署：正常应用镜像升级即可；新数据库 Provider Run 使用新的 Shard/并发引擎，旧 Run 读取自己的冻结 `shard_size/runtime_config_snapshot`；迁移前 legacy env bootstrap 保留历史静态 shard 兼容。
- 回滚：代码回退到上一个 Release 即可继续读取既有 Run/Provider 数据；因为不新增 Schema，数据级回滚不需要 destructive migration。
- 风险：Provider 配置过高可能放大线程/网络/模型压力；实现使用 bounded in-flight、RPS、Canary、批量 DB 背压和可观测峰值。配置允许 1000/更高不等于任意 Provider/机器已经完成对应真实容量认证。

# 独立 Review

Review Target：PR #336，base `59edfe793b913d11283952567f4e1a6e0003c6df` → 当前 feature HEAD；模式为 review-and-fix/test，需求源为 Issue #335。

审查覆盖：Provider 配置事实源、Preview/Create shard 冻结、bounded executor、Formal Worker、RPS/Transport Retry、PostgreSQL batch persistence、Planner/Shard 补调度、Run stats、旧 Run/legacy env 兼容、前端配置、generated contract、Stage12 用户可见历史语义、测试证据等级及受控吞吐 benchmark。

当前 Verdict：`NO_FINDINGS_WITHIN_SCOPE`。Review 过程中暴露的 generated drift、Stage12 旧验收语义、Ruff/mypy 和过期 Unit Fake 均已修复并重新进入回归链；没有通过降低生产断言或跳过真实 PostgreSQL/Full-stack 边界换取绿色。

证据边界：真实 Provider 的并发配额、429 行为、网络、GPU/推理服务吞吐和服务器线程资源没有进行付费/外部 Probe；部署前仍应按实际 Provider/机器从低到高做容量 ramp，并以错误率、p95 延迟、CPU/内存/FD 和 Provider 限流为准确定生产值。

# Completion Audit

- [x] upstream_re_read: 重新读取 Issue #335、项目 AGENTS/架构门禁、Analysis 正式说明及最终关键调用链；没有以 PR 描述或本 Change 自身替代上游需求。
- [x] change_coverage: R1-R8 均映射到代码、Contract、Unit、真实 PostgreSQL/Full-stack 或受控基准证据；R9 的 merge/main-fresh/archive 明确按时序 `explicitly_deferred`，未伪造完成。
- [x] reverse_audit: 从最终 PR changed files 反查公开入口、Worker registry、Provider snapshot、DB writer、tests/docs/generated consumer；一次性生成/静态修复/吞吐 benchmark workflow 与脚本均已从最终 diff 清理。
- [x] unresolved_cleared: 当前独立 Review 无 BLOCKER/HIGH/MEDIUM Finding；真实 Provider 容量和合并后归档属于明确证据边界/后续门禁，不作为已验证事实隐藏。

# 当前状态

- Issue #335 为唯一上游需求来源，PR #336 已声明 `Requirement-Source: #335`。
- 功能实现、测试资产、文档和 generated artifacts 已完成；受控 Formal/Offline 吞吐比为 98.86%。
- Change 已进入 `ready_for_review`。最终合并仍要求该最终候选 HEAD 的永久 CI/Completion Gate 全绿；不得用更早 HEAD 的绿色结果替代。
- 真实 Provider 容量 Probe 未执行，不能从当前 Fake/受控证据推断某个实际模型部署一定能承受 250/1000 并发。

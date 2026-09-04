---
schema: coding-change/v1
id: CHG-20260904-155626-analysis-unified-execution
title: 统一 AI 打标执行与结果刷新
level: L2
status: ready_for_review
owner: codex
branch: fix/analysis-unified-concurrent-execution
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - task-center
  - voice-plaza
  - llm
  - ci
affected_paths:
  - backend/src/aima_ugc
  - frontend/src/features/task-center
  - frontend/src/features/voice-plaza
  - tests
  - frontend/tests
  - frontend/e2e
  - frontend/e2e-fullstack
  - docs
  - .github/workflows/fullstack.yml
  - scripts/quality/classify_ci_scope.py
contracts: []
data_changes: []
---

# 目标

用户创建 AI 打标任务后，首批直接并发调用模型；持续收割并提交结果，页面及时自动显示最终标签。正式 Worker 与无数据库离线入口共享执行核心，并覆盖取消、恢复和陈旧响应。

# 成功标准

- [x] 模型真实 HTTP 首批并发、跨页慢尾不阻塞后续工作；模型线程不持有数据库事务。
- [x] 两条内容场景中，先返回的结果在另一 HTTP 仍阻塞时已可由 API 查询，不等待一秒提交计时器。
- [x] 活动任务每秒共享查询；不变统计不重复取内容，终态标签自动显示，无须手动刷新。
- [x] 停止补充、重试退避、限流等待、取消、Lease/Deadline、接管和离线 checkpoint 回归通过。
- [x] 不改变 Prompt、分类校验、模型参数、公共 Contract、数据库 Schema 或依赖版本。

# 范围

统一 Formal/Offline 执行入口、LLM 停止信号与测量、短事务持久化、轻量 Run 状态读取、前端共享状态及刷新、对应测试、CI 场景选择和正式说明。

# 非目标

不部署生产、不调用付费模型、不改业务开发库、不建立预算系统或跨进程账户限流、不改变打标 taxonomy 和模型推理参数，不承诺外部请求 exactly-once、零开销或任意真实模型容量。

# 必须保持不变

- 一条内容一次逻辑模型调用，Transport Retry 与 Validation Retry 分层；已发送同步 HTTP 只能收尾，不能撤回。
- Run 冻结配置和身份、内容版本、幂等、Job Fencing、Current 选择与人工复核语义。
- imports_test 复用生产离线实现，无数据库也能打标、checkpoint 恢复和导出。
- API/Worker/Scheduler 分进程，PostgreSQL 为唯一业务事实库，外部 HTTP 不在数据库事务中。

# 关键决策

需求来源为 [Issue #344](https://github.com/dingyuwen777/AIMA_UGC/issues/344) 和本轮用户明确决定。此前已经授权的本地实现尚未提交，本 Change 在合并交付阶段建立以归集同一任务，不声称它早于实施创建。

删除旧同步 Worker、串行 Canary、静态 batch/shard 配置与离线 batch_size 别名，是用户明确要求的兼容边界变更。所有执行由 max_concurrency 和冻结 Provider 参数控制；保留旧 Run 的冻结身份及分片读法。无数据库 Migration、新依赖或公共 HTTP/Job 字段变化。

大任务保留 200 条或约一秒提交；全部工作已取出且余量不超过并发窗口时及时提交，每次仍复核停止状态和 Fence。前端复用 task-center 唯一 Analysis 状态；活动轮询一秒不是端到端延迟 SLO。

上线由后续正常流程重启 API/Worker 并更新前端产物；先等待活动任务终态或正式取消并等待在途请求收尾。回滚使用之前验证的应用版本及匹配配置，无需数据回滚。本次不执行部署。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 正式与离线统一执行并删除旧配置/代码 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | analysis_concurrent_worker.py、offline_concurrent_labeling.py；删除 analysis_worker.py 与旧 Canary 测试；离线、Job 和配置回归。 |
| R2 | 首批真实并发，跨页无慢尾屏障，数据库与模型并发解耦 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | concurrent_labeling.py 的连续调度；test_analysis_provider_concurrency.py 的实际 HTTP 屏障、跨页慢尾与独立事务验收。 |
| R3 | 及时提交小结果，轻量列表，可区分的性能日志 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | Worker 尾部提交、PostgresAnalysisRunQueryRepository 已完成 shard 快照；实际请求/重试/DB 日志；750 ms 可读结果回归。 |
| R4 | 启动、取消、限流/退避、Lease/Deadline 和接管可恢复 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | LLM stop_event 不进入模型 Payload；test_llm_transport_retry.py、test_analysis_provider_concurrency.py 和 checkpoint 回归。 |
| R5 | 无数据库 imports_test 与 Ctrl+C checkpoint 恢复 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | test_offline_labeling_concurrency.py 禁用数据库后调用生产打标及导出，test_offline_labeling_stop.py 保留认证失败边界。 |
| R6 | 活动每秒共享刷新、终态显示结果、无重复查询及旧响应倒退 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | task-center/voice-plaza Store、26 项前端单测、9 项 Browser Mock 和 analysis-streaming.spec.ts 真实全栈验收。 |
| R7 | 保持质量语义与冻结身份，不升级依赖/Schema | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | Prompt/Validator/Contract/lock/Migration 无差异；人工复核、旧 Run 身份与结果完整性回归；不将受控测试称为准确率评测。 |
| R8 | 文档、分层验收、PR/主分支验证与归档交付 | https://github.com/dingyuwen777/AIMA_UGC/issues/344 | satisfied | 本 Change 跟踪已完成的本地验证；正式文档与 CI 接线随三个工作提交进入 PR。PR/main CI、归档、Issue 关闭属于下方明确时序门禁，完成前不宣称已合并。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | bounded executor、停止/恢复、前端刷新竞争和 CI 场景选择；本地记录与 PR CI。 |
| 接口 / 契约 | required | HTTP/Job/生成 Client 无变化，完整 CI 的 Contract drift 验证生产者消费者。 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL + 实际本地 HTTP，14 项 AI 并发/取消/接管/提前可读回归；相关内容复核集成回归。 |
| 用户 / 工作流验收 | required | Browser Mock 覆盖慢来源、活动刷新、取消旧响应、隐藏/卸载、错误重试。 |
| 跨组件关键路径 | required | analysis-streaming.spec.ts 用真实 API/Worker/PostgreSQL 与本地假 LLM 验证两条内容同时发送、终态自动显示标签。 |
| 外部依赖 / 供应方探测 | not_applicable | 本次没有变更 Provider 协议或模型，未授权新的付费容量/准确率实验；受控 HTTP 不证明真实 Provider 当前配额与质量。 |
| 构建 / 打包 / 运行 | required | TypeScript/Vue/Vite 构建、Python Ruff/mypy 与主分支 Compose 门禁。 |
| 文档 / 治理 / 其他 | required | 项目文档链接、Change 追溯/完成审计、PR 和 main 新鲜检查。 |

# 完成审计

- [x] upstream_re_read：重新读取 Issue #344、用户已确认决定、AGENTS、Analysis 正式说明并独立重建要求。
- [x] change_coverage：逐项比较要求与全部变更，核对正式、离线、前端、取消和可观测性均覆盖。
- [x] reverse_audit：从前端创建/取消/刷新反查 API/Worker/数据库，从模型结果反查终态内容展示，并核对 CI 实际选择新验收。
- [x] unresolved_cleared：检查全部需求状态和两阶段 Review，没有未解决的阻断问题。

# 任务

- [x] 恢复调用链、真实运行日志及已有改动。
- [x] 建立失败回归并完成最小实现、清理失效代码。
- [x] 完成局部单元、真实 PostgreSQL、Browser Mock、真实全栈和构建验证。
- [x] 完成最终变更与证据 Review，标记 Ready。
- [ ] PR 必需 CI 通过后受保护合并，再验证 implementation main。
- [ ] 单独归档并验证 archive main，关闭 Issue，清理本任务分支。

# 验证

本地已有 211 项后端相关回归证据；最后刷新优化覆盖 26 项前端单测、14 项真实 PostgreSQL、9 项 Browser Mock、1 项真实全栈、前端构建和目标静态检查。合并前新增 CI 选场回归 Red 证明遗漏，修复后 19 项通过。详细结果见同目录 EVIDENCE.md。

合并门禁：运行 `python scripts/quality/check_change_completion.py --root . --require-active-ready`，在最终候选 SHA 上取得 PR 完整检查，再执行主分支新鲜检查。中间工作提交不代表 Ready。

# 文档影响

更新 Analysis/LLM/imports_test README、代码导航、运行/API/测试说明、AI 专题、大规模打标/历史迁移和相关架构说明。历史 archive 作为当时事实不重写。

# 交付

三个工作提交分别归集后端执行、前端刷新与验收、文档与审计。Issue #344 保持 open；PR #345 已建立；合并 SHA、main CI 和归档结果在实际发生后记录。不提交忽略的运行日志、Secret 或业务数据。

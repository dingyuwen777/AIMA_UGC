---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-correctness
title: 修复 Stage 1-7 未闭环正确性与恢复缺陷
level: L3
status: in_progress
owner: dingyuwen777
branch: fix/stage1-stage7-correctness
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260815-stage7-completion]
affected_areas: [platform, jobs, collection, content, provider, database, migration, testing, ci, documentation]
affected_paths: [backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/bootstrap/, migrations/versions/, tests/unit/, tests/integration/, .github/workflows/, README.md, docs/]
contracts: []
data_changes: [comment_coverage_observations]
---

# 背景与现状

当前 `main@7e923680bf4931657597d8756c378480d9fe95b6` 已合入并归档 Stage 7，但重新按仓库机器事实审计后确认：Stage 1—7 中存在若干“本阶段本应闭环、却没有在正式生产调用链成立”的缺陷。主要包括 Provider `dispatching` 崩溃恢复组件未接入正式 Worker、Collection Run/Scope 缺少可恢复 checkpoint/终态 Scope 跳过、失败请求统计失真、评论软目标裁掉已付费整页数据、Content/Comment/Account 首次并发摄取竞态、评论 Coverage 机器事实未落库，以及受影响 CI/长期文档没有覆盖当前真实状态。

用户于 2026-08-17 明确要求：不仅修 Stage 7，也要检查并补齐 Stage 1—7 中任何当前阶段本应闭环但仍有缺陷的事项；只有 Blueprint/Change 已明确延期到后续 Stage/Release 的能力可以继续保留为未实现。本 Change 不进入 Stage 8。

# 目标

在不改变既定模块化单体、Provider/Canonical/Owner、PostgreSQL Job/Scheduler 和五平台 Operation 方案的前提下，把 Stage 1—7 当前机器实现修回已经批准的正确语义，使崩溃、Lease takeover、并发采集、Provider 失败、评论抽样和数据追溯都能在正式生产调用链下正确恢复或收敛，并让长期文档、Change、CI 与最终机器事实一致。

# 成功标准

- [ ] 新 Worker 接管 `collection.run.v1` 前会通过正式生产装配收敛遗留 `dispatching` Provider Attempt；已校验 Raw 存在时不重复发送 Provider。
- [ ] Collection Run 恢复时跳过已终态 Scope；running Scope 从持久化 checkpoint 继续，避免从头重放已完成分页/请求。
- [ ] Provider Request/Attempt 已发生但 Scope 失败时，Run/Scope 的 requested/succeeded/failed 统计与持久化执行事实一致，不再出现已请求却计数为零。
- [ ] 评论和二级回复 target 保持软目标：当前已付费响应页全部 Mapper/Ingestion 后才决定是否请求下一页。
- [ ] Account/Content/Comment 首次并发发现同一业务身份时，以现有 PostgreSQL Unique 为最终事实，竞争事务收敛为同一业务记录而不是正常竞态失败。
- [ ] 较旧的乱序 Observation 不覆盖较新的 Current 业务字段/指标；来源账本和历史事实仍保留，A→B→A 的正常时间顺序语义保持不变。
- [ ] 每次评论采集形成可追溯 `comment_coverage_observations`，至少持久化 coverage、reported_total、collected_count、sample_mode、sort_mode、target_count、stop_reason、observed_at，并能区分 complete/partial/not_requested/unavailable。
- [ ] Stage 1—7 中审计到的正式入口/Schema/CI/文档冲突被修正；明确延期到 Stage 8/Release 的认证、正式业务 API/前端、生产 Docker/Release、协调 Backup/Restore 不提前实现。
- [ ] 目标回归经历正确 Red→Green；真实 PostgreSQL 覆盖 takeover、并发 first insert、checkpoint resume、Coverage/Migration；通用和受影响专项 CI 在最终 PR head 全绿。
- [ ] 完成两阶段 Review，严重/重要问题清零后正常合入 `main`；合并后 `main` 重新取得新鲜验证证据后才允许本 Change done/archive，并重新认定 Stage 1—7 闭环。

# 范围

- Stage 4/5/6/7 正式 Job/Collection/Provider/Content 运行时正确性和崩溃恢复。
- 复用已有 `ProviderAttemptReconciler`、`checkpoint_scope`、Job Fencing、Provider Request 幂等键、Content Owner Repository 和 PostgreSQL Unique。
- 为评论 Coverage 当前已批准语义增加最小增量 Migration 和 Content Owner 写入能力。
- 对审计过程中确认的 Stage 1—7 其他同等级缺陷追加回归和最小修复。
- 同步相关 Blueprint、根/模块 README、环境运行说明、测试说明和 CI path filter；删除已失效的一次性 Stage 7 Workflow。

# 非目标

- 不开始 Stage 8 HTTP CRUD、正式业务页面、Provider Secret 写 API、认证授权。
- 不实现 Stage 11/Release 的 Docker Compose、离线 Release、生产备份/恢复和维护写屏障；这些继续按 Blueprint 的后续 Release 门禁处理。
- 不引入 Redis、Celery、Kafka、工作流引擎或第二套 Job/Scheduler/Provider/Mapper/Repository。
- 不改变五个平台已批准主 Operation、快手 App 评论主链或自动 fallback 决策。
- 不恢复已撤回的请求/金额 Budget、Budget Account、Reservation Ledger 或发送预算门禁。
- 不升级或新增依赖。

# 必须保持不变

- `Provider Adapter → Raw Artifact → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL` 主链不变。
- Provider 不写业务表，Mapper 不访问数据库/HTTP；一个表只有一个写 Owner。
- PostgreSQL Job Claim/Lease/Deadline/Fencing、Scheduler `latest_only + max_catch_up_runs=0` 和 Occurrence 唯一性不变。
- 同一 Attempt 最多一次外部发送；已校验 Raw 存在时禁止再次调用 Provider；网络结果未知继续保守记录 `potential_duplicate_charge`。
- Secret 只经 `secret_ref` 服务端解析；TikHub Bearer Secret 只发送到批准 Origin。
- Canonical V1、Provider V1、当前 OpenAPI/生成 Client 和合法 Stage 1—7 公共行为保持兼容。
- 已发布 `20260813_0001`—`20260817_0015` Migration 不改写，只允许新增向前 Revision。

# 关键决策

## 方案比较

### 方案 A：在现有生产链做最小增量修复（采用）

复用当前已有的 Reconciler、Scope checkpoint 字段、Request fingerprint、Unique/Fencing 和 Owner Repository；只在 Coverage 已批准但 Schema 信息不足处新增向前 Migration。优点是兼容当前 Contract/Migration、改动可逆、每个故障窗口可直接用现有 PostgreSQL/Fake Transport 验证；缺点是需要补若干生产装配和跨事务恢复测试。

### 方案 B：新建通用 Step Ledger / Workflow Engine（拒绝）

可统一表达任意步骤，但会引入当前规模没有证据需要的新状态机和迁移面，重复 Job/Scope/Provider 已有事实，违反最小实现。

### 方案 C：只修表面异常，把 checkpoint/Coverage/并发问题推到 Stage 8（拒绝）

改动最少，但会让 Stage 8 API/前端建立在错误或不可解释的机器事实之上，并违反用户“本阶段该闭环的现在闭环”的决定。

用户已明确授权按既有设计补齐 Stage 1—7，因此采用方案 A，不重新询问已经由 Blueprint/本轮授权固定的业务语义。

## Migration 与兼容

- 不改写既有 Revision；如 Coverage 需要扩列，新增 `20260817_0016`，`down_revision=20260817_0015`。
- 新列只用于以后新 Observation；当前尚未生产部署，不伪造历史 Coverage 回填。
- downgrade 只移除本 Revision 新增列，不删除既有评论/Content/Raw 事实。

## 部署与回滚

当前仍是生产 No-Go，本 Change 不部署生产。若未来发布包含本 Change，顺序仍按 Release 设计先备份/迁移再启动。代码回滚若已执行 `0016`，先停写并按 Release 兼容边界评估，再执行受控 downgrade；不得通过改写历史 Revision 回滚。

# 任务

- [x] 重新读取当前 `main` 的 AGENTS、Skill、Blueprint、Change/PR/commit 基线并确认无并行 Active Change。
- [ ] 重新核对 Stage 1—7 直接相关代码/Contract/Migration/测试，确认哪些缺口是当前阶段缺陷、哪些已明确延期。
- [ ] Red：增加生产 Worker Reconciler/takeover、Scope resume/checkpoint、失败计数、软目标整页、并发 first insert、乱序 Observation、Coverage/Migration 回归并取得正确失败证据。
- [ ] Green：以最小生产修改逐项修复，禁止为通过测试建立旁路或第二套实现。
- [ ] Refactor：只整理本轮产生的重复/状态命名，不无关重构。
- [ ] 更新受影响 CI path filter/专项门禁并删除已失效的一次性 Stage 7 Workflow。
- [ ] 同步当前长期 Blueprint/README/环境与测试说明，明确 Stage 1—7 当前事实和后续延期边界。
- [ ] 执行需求符合性 Review 与代码质量/安全/并发/兼容 Review。
- [ ] 取得最终 PR head 与合并后 main 新鲜 CI；满足全部成功标准后归档 Change。

# 验证

## 计划

- Red/目标测试：Stage 7 Collection production composition、Provider recovery、Scope resume、comment/reply target crossing、Run counters。
- PostgreSQL：Content 并发首次插入、乱序 Observation、Coverage 写入；Alembic `0015 → 0016 → 0015 → 0016`、`base → head`、`alembic check`。
- 回归：`tests/unit/jobs`、`tests/integration/jobs`、`tests/unit/collection`、`tests/integration/collection`、`tests/unit/content`、`tests/integration/content`、Contract tests。
- 质量：Ruff format/check、mypy、architecture、table ownership、secret scan、docs、Contract generate/check/compatibility。
- 构建/联调：通用 CI、Stage 4/5A/5B/5C/5D/6/7 受影响专项 CI，前端 lint/type/unit/build 和本地 stack smoke 由通用 CI 保持。

## 新鲜证据

- 尚未进入 Red；当前只完成仓库事实基线与 Change 建立。

# 文档影响

需要同步：Blueprint 当前阶段/Stage 7 实施描述、根 README、Collection/Content README、环境运行与部署、测试调试说明，以及已经撤回 Budget 的过期长期描述。Archive Change 保持历史，不回写旧过程。

# 交付

- 分支：`fix/stage1-stage7-correctness`
- Commit：当前仅建立 Change，后续按 Red/Green/Review 分段提交。
- PR：尚未创建。
- 发布：不执行生产部署。

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

`main@7e923680bf4931657597d8756c378480d9fe95b6` 已完成 Stage 7，但重新按机器事实审计发现，Stage 1—7 中仍存在本阶段应闭环的正确性缺陷：Provider `dispatching` 崩溃恢复没有接入正式 Scope、Collection Run/Scope 缺少可恢复 checkpoint/终态 Scope 跳过、失败请求统计会丢失、评论软目标会裁掉已付费响应页、Content/Comment/Account 首次并发存在竞态、旧 Observation 可能回滚 Current、评论 Coverage 没有形成完整机器事实，以及长期文档/CI 中存在过期描述和一次性 Stage 7 Workflow 残留。

本 Change 只修复 Stage 1—7 已批准语义，不进入 Stage 8；认证、正式业务 API/前端、生产 Docker/离线 Release、协调 Backup/Restore 和维护写屏障继续保留在后续 Stage/Release 门禁。

# 目标

保持现有模块化单体、Provider/Canonical/Owner、PostgreSQL Job/Scheduler、五平台 Operation 和 Secret 边界不变，以最小增量修复崩溃恢复、Lease takeover、Provider 重试、并发摄取、乱序 Current、评论抽样/Coverage 和相关 CI/文档，使 Stage 1—7 的正式生产调用链与已批准设计重新一致。

# 成功标准

- [x] 新 Worker 接管 `collection.run.v1` 前通过正式 Scope 装配收敛遗留 `dispatching` Provider Attempt；已校验 Raw 存在时直接恢复/回放，不重复发送 Provider。
- [x] Collection Run 恢复时跳过已终态 Scope；running Scope 使用持久化 `pagination_state/progress/stats` checkpoint，避免从头重复已完成页。
- [x] Provider Request/Attempt 已发生但 Scope 失败时，Run/Scope requested/succeeded/failed 与 PostgreSQL Attempt/Candidate durable 事实一致。
- [x] 评论和二级回复 target 为跨页软目标：当前 Provider 已返回的整页全部 Mapper/Ingestion 后才决定是否请求下一页。
- [x] Account/Content/Comment 首次并发发现同一业务身份时，以 PostgreSQL Unique + `ON CONFLICT` 收敛，正常竞争不再因“先查后插”失败。
- [x] 较旧乱序 Observation 不覆盖较新的 Current 业务字段/指标；历史/来源事实仍可保留，正常时间顺序 A→B→A 语义不变。
- [x] 评论采集持久化 `comment_coverage_observations`，包含 coverage、reported_total、collected_count、sample_mode、sort_mode、target_count、stop_reason、observed_at 和 Attempt/Raw 来源，可区分 complete/partial/not_requested/unavailable。
- [x] 非重试 HTTP 4xx 已完成并持久化后，即使 Worker 在 Scope 终态提交前崩溃，takeover 也复用该失败 Attempt 并终止，不建立新 Attempt 再次发送；408/425/429/5xx、`not_sent/unknown` 的既有新 Attempt 重试语义保持不变。
- [x] Stage 1—7 审计到的正式入口/Schema/CI/文档冲突已修正；明确延期到 Stage 8/Release 的能力未提前实现。
- [x] 目标回归均经历有效 Red→Green；真实 PostgreSQL 覆盖 takeover、并发 first insert、乱序 Current、checkpoint、Coverage、Provider retry/recovery 与 Migration round-trip。
- [x] 需求符合性 Review 与代码质量/安全/并发/兼容性 Review 已完成；当前未发现未解决的严重/重要问题。
- [ ] PR 最终 head 全部正式 CI 再次通过、正常合入 `main`，且合并后 `main` 取得新鲜 CI 后，才允许 Change `done` / archive 并重新认定 Stage 1—7 闭环。

# 范围与非目标

范围：Stage 4/5/6/7 的 Job/Collection/Provider/Content 正确性与崩溃恢复；复用 Reconciler、Scope checkpoint、Request fingerprint、Fencing、Owner Repository、PostgreSQL Unique；新增最小 Coverage 向前 Migration；同步受影响 Blueprint/README/环境/测试说明和正式 CI；删除已失效的一次性 Stage 7 Workflow，保留仍有效的正式 Scheduler 门禁与手动 Real Shape 验证入口。

非目标：不开始 Stage 8 HTTP CRUD、业务页面、Provider Secret 写 API、认证授权；不实现 Release Docker Compose、离线 Release、协调 Backup/Restore 或维护写屏障；不引入 Redis/Celery/Kafka/工作流引擎；不改变五平台已批准主 Operation、快手 App 评论主链或 fallback 决策；不恢复 Budget Account/Reservation Ledger/发送预算；不新增或升级依赖。

# 必须保持不变

- `Provider Adapter → Raw Artifact → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL` 主链不变。
- Provider 不写业务表，Mapper 不访问数据库/HTTP，一个表只有一个写 Owner。
- PostgreSQL Job Claim/Lease/Deadline/Fencing、Scheduler `latest_only + max_catch_up_runs=0`、Occurrence 唯一性不变。
- 同一 Attempt 最多一次外部发送；完整 Raw 可恢复时禁止再次调用 Provider；网络结果未知继续保守记录潜在重复计费。
- Secret 只经 `secret_ref` 服务端解析；TikHub Bearer Secret 只发送到批准 Origin。
- Canonical V1、Provider V1、当前 OpenAPI/生成 Client 与合法公共行为保持兼容。
- 已发布 `20260813_0001`—`20260817_0015` 不改写；本 Change 仅新增向前 Revision `20260817_0016`。

# 已实施方案

采用原方案 A：在现有生产链最小增量修复，不建立第二套 Step Ledger/Workflow Engine。

Provider 恢复按逻辑 Request 复用：遗留 `dispatching` 先由 Reconciler 收敛；成功且完整 Raw 直接 replay；明确可重试失败建立新 Attempt；已完成且不可重试的 4xx 在 takeover 时复用失败 Attempt 并结束。Scope checkpoint 与统计继续受 Job Fence 约束。

Content 首次插入使用 PostgreSQL `ON CONFLICT DO NOTHING` 后锁定赢家；较旧 Observation 只扩展时间边界和保留合法历史，不回滚较新 Current。指标历史只保存本次 `observed_fields` 真正观察到的指标，未观察字段保持 `NULL`。

评论 Coverage 由 Content Owner 写入；`20260817_0016` 增加 `sample_mode/sort_mode/target_count/stop_reason` 和来源幂等约束，不伪造 `0016` 前历史字段。

# 任务状态

- [x] 读取并复核 AGENTS、Skill、相关 Blueprint、代码、Migration、测试和当前分支/PR 事实。
- [x] 区分当前阶段缺陷与 Stage 8/Release 明确延期项。
- [x] Red：生产 Worker/Raw takeover、Scope resume/checkpoint、失败统计、软目标整页、并发 first insert、乱序 Observation、Coverage/Migration、Provider retry 和非重试 4xx takeover 回归均取得正确失败证据。
- [x] Green：以最小生产修改逐项修复；未建立旁路或第二套实现。
- [x] Refactor/质量：只处理本轮 formatter/lint/mypy 与状态命名，不做无关重构。
- [x] 更新受影响 CI，删除失效的一次性 Stage 7 Workflow；保留 Scheduler 正式门禁与手动 Real Shape 入口。
- [x] 同步 AGENTS、根/模块 README、Blueprint 03、环境运行与部署、测试与调试说明。
- [x] 完成需求符合性 Review 与代码质量/安全/并发/兼容 Review。
- [ ] 最终 PR head 新鲜 CI → Ready → merge → 合并后 main 新鲜 CI → Change done/archive。

# 验证与新鲜证据

## Red→Green

- Content 并发/乱序：新增 `tests/integration/content/test_content_current_concurrency.py`，真实 PostgreSQL 验证 Account/Content/Comment 首次并发、旧 Observation 不回滚 Current、稀疏指标历史。
- Coverage/详情后重决策：新增 `test_collection_comment_coverage_runtime.py`；验证未知评论数在 Detail 后重决策、整页软目标、`reported_total=0`、Coverage 字段/来源。
- Raw takeover：新增 `test_collection_scope_recovery_runtime.py`；构造“2xx + Raw 已落盘 + Attempt 仍 dispatching + Lease takeover”，正式 Scope 恢复后搜索请求不再次进入 Transport。
- Provider retry：新增 `test_collection_worker_retry_runtime.py`；验证 HTTP 500 → Job retry → 同一逻辑 Request 新 Provider Attempt → 成功，旧 Attempt/Raw/错误事实保留。
- 非重试 4xx：新增 `test_collection_nonretryable_4xx_recovery.py`；修复前 takeover `resumed_transport.call_count == 1`，修复后为 `0`，且仍只有原 HTTP 400 Attempt。
- Run/Scope：新增 `tests/unit/collection/test_collection_run_recovery.py`；验证终态 Scope 跳过、running checkpoint、retryable Scope 结果与计数恢复。

## PR head 验证基线

`72c45c1ad0afb93b87e72d857b26a62fd5e57ca6` 已取得 11/11 正式 Workflow 成功：

- CI `32016751131`
- Stage 4 Job Runtime `32016751205`
- Stage 5A Provider Raw `32016751127`
- Stage 5B Collection Execution `32016751107`
- Stage 5C Provider Persistence `32016751184`
- Stage 5D Provider Dispatch `32016751113`
- Stage 6 XHS Vertical Slice `32016751237`
- Stage 7 Keyword Packs `32016751132`
- Stage 7 Provider Config Routing `32016751163`
- Stage 7 Plan Occurrence Run Snapshot `32016751147`
- Stage 7 Scheduler Runtime `32016751285`

其中 Stage 5D 在 Green 提交前还单独验证：204 个 Unit/Contract、非重试 4xx takeover、Coverage、Raw takeover、完整 Collection Integration、Ruff format/check、mypy、architecture、table ownership、secret/docs、Contract，以及 `base → head` / Stage 5C → head Migration round-trip 全部成功。

本文件更新会产生新的 PR head；合并前仍必须以新的最终 head 再取得正式 CI，不复用上述结果冒充最终合并证据。

# Review 结论

需求符合性：当前改动均可追溯到本 Change 成功标准；未进入 Stage 8/Release，未恢复 Budget，未改五平台主 Operation/自动 fallback。

代码质量/安全/兼容性：无新增依赖或版本升级；Canonical/Provider/OpenAPI 公共 Contract 未改；历史 Migration 未改写；新增 `0016` 可 downgrade；Provider/Content 表写 Owner 和 Job Fencing 保持；Secret 边界未扩大；已清理临时 corrective Workflow 与旧的一次性 Stage 7 Probe Workflow。

# 文档、部署与回滚影响

文档已同步 Stage 1—7 当前机器事实、Provider retry/recovery、Coverage、并发/乱序语义，以及 Stage 8/Release 仍 No-Go 的边界。Archive Change 保持历史，不回写旧过程。

当前不执行生产部署。未来发布若包含 `0016`，按 Release 设计先受控备份/迁移再启动；代码回滚涉及 `0016` 时必须先停写并评估兼容，再执行受控 downgrade，不得改写历史 Revision。

# 交付状态

- 分支：`fix/stage1-stage7-correctness`
- PR：`#57 修复 Stage 1-7 正确性与恢复缺陷`，当前保持 Draft，等待本次 Change 更新后的最终 head CI。
- 发布：不执行生产部署。
- Change：保持 `in_progress`；只有 PR 合并、main 新鲜 CI 和归档闭环完成后才改为 `done`。

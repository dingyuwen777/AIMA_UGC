---
schema: rvc-change/v1
id: CHG-20260817-stage1-stage7-audit-final-closure
title: 闭环 Stage 1-7 审计剩余问题
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/stage1-stage7-audit-final-closure
created: 2026-08-17
updated: 2026-08-17
depends_on: [CHG-20260817-stage1-stage7-audit-correctness]
affected_areas: [content, collection, platform, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/pricing.toml, tests/unit/content/, tests/unit/collection/, tests/integration/jobs/, docs/blueprint/06-开发约束与分阶段实施.md, changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md]
contracts: []
data_changes: []
---

# 背景与现状

`main@3519fcd360b8e8201ed03ff1a7c0013c662ab528` 已完成前一轮 Stage 1—7 正确性整改及 Change 归档，相关 PR/main CI 均取得新鲜成功证据。交付前重新逐项反查 2026-08-17 全面审计原始 Findings 后确认：P1 与大部分 P2/P3 已闭环，但仍有 5 个审计项没有真正清零。前一归档 Change 不重新激活，本 Change 只处理这些剩余事实。

# 目标

1. 让 `InMemoryContentRepository` 在其已支持的 Content 子集上与生产 PostgreSQL Repository 使用相同的字段级 sparse/out-of-order Current freshness 语义，避免 Unit Fake 证明第二套错误状态机。
2. 在当前正式 Job / Collection / Provider 主链补齐 Blueprint 已批准的关键稳定结构化生命周期事件，复用现有 `log_event` 和统一 Formatter，不增加第二套日志框架。
3. 修正 `docs/blueprint/06-开发约束与分阶段实施.md` 中当前阶段无条件要求不存在 Compose、以及已撤回 Budget/Reservation 专项仍被写成当前强制测试的问题。
4. 修正 `pricing.toml` 中已经失效的“硬预算/Reservation”注释，只保留当前 Pricing/Billing 事实。
5. 修正 Stage 7 Completion Change 最终 frontmatter `data_changes` 仍包含已撤回并删除的 Budget 表的事实冲突。

# 可观察成功标准

- [ ] InMemory Content 回归先在旧实现证明：较旧 Observation 会错误回滚更晚已观察字段；修复后通过。
- [ ] InMemory 支持“较旧 Observation 补充更晚未观察字段”和“更晚显式 null 阻止较旧非空回滚”，且 `last_seen_at` 保持实体级单调向前。
- [ ] JobWorker 通过现有生产入口输出稳定 `job.started`、`job.completed`、`job.retry_scheduled`、`job.failed`、`job.cancelled`，Lease 丢失使用 `job.lease_lost`；日志不含 Lease Token/Payload/Secret。
- [ ] CollectionRunExecutor 输出 `collection.run.started`、`collection.scope.completed`、`collection.run.completed`，包含可关联 ID、状态与安全聚合字段，不记录 Provider/用户原文。
- [ ] ProviderDispatchService 输出 `provider.request.started`、`provider.request.completed` / `provider.request.failed`；只记录 lineage/status/duration/billing/artifact 等安全字段，不记录请求/响应正文或 Secret。
- [ ] 日志事件测试从正式 Worker/Executor/Dispatch 入口验证 `record.event` 和关键关联字段，不只测试 Mock Logger。
- [ ] Blueprint 06 不再把当前不存在的 `compose.yaml` 作为所有任务无条件必读，也不再把已撤回 Budget/Reservation Ledger 测试写成当前强制 Integration 专项；未来 Budget 仍需新的 L3 Change。
- [ ] `pricing.toml` 不再声称当前存在硬预算或 Reservation；Pricing endpoint/价格数据不改变。
- [ ] `CHG-20260815-stage7-completion` 最终 `data_changes` 不再包含 `provider_budget_accounts/provider_budget_reservations`，历史正文过程保持不改写。
- [ ] 不新增/升级依赖，不改变公共 Contract、Schema/Migration、五平台 Operation、Scheduler 策略、Budget 回撤或 Stage 8/Release 非目标。
- [ ] 目标测试、相关 Unit/PostgreSQL Integration、Ruff、mypy、Architecture/Table Owner、Secret、Docs 与主/相关 Stage CI 取得最终 head 新鲜成功证据。
- [ ] 完成需求符合性与代码质量两阶段 Review；正常 PR 合并后 `main` 再取得新鲜成功 CI，再归档本 Change。

# 范围

- `backend/src/aima_ugc/modules/content/ingestion.py` 的 InMemory Content Current 测试语义；
- `backend/src/aima_ugc/platform/jobs/worker.py` 的稳定 Job 生命周期事件；
- `backend/src/aima_ugc/modules/collection/collection_run_executor.py` 的 Run/Scope 事件；
- `backend/src/aima_ugc/modules/collection/provider_dispatch.py` 的 Provider Request 生命周期事件；
- 直接相关测试；
- Blueprint 06、Pricing 注释、Stage 7 Completion Change 最终 metadata。

# 非目标

- 不开始 Stage 8 API/UI/Auth；
- 不实现 Worker/Reaper 常驻 supervisor loop；该进程管理继续属于 Release；
- 不实现 Docker/Compose/Offline Release/Backup Restore；
- 不恢复 Budget Runtime、Budget Account、Reservation Ledger 或发送预算门禁；
- 不改变 Provider Operation、Mapper、Canonical、数据库 Schema/Migration；
- 不新增日志基础设施、Tracing SDK 或第三方日志依赖；
- 不为 Content 单条摄取增加高频 INFO 日志。

# 必须保持不变

- 模块化单体与现有 Owner/依赖方向；
- Provider → Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL；
- Current 字段级 freshness 的 PostgreSQL 机器语义；
- Scheduler `latest_only + max_catch_up_runs=0`；
- Budget Runtime 保持删除；
- 日志 Formatter/脱敏/轮转现有边界；
- 普通 CI 不访问真实付费 Provider。

# 已确认实现原则

- InMemory Fake 只同步它已经公开支持的 Content 字段子集，不复制完整 PostgreSQL Repository；字段 freshness 作为 Repository 私有状态保存，不扩张 `ContentCurrent` 的公共测试数据结构。
- 生命周期事件直接使用 `aima_ugc.platform.logging.log_event` 和现有模块 logger；事件在对应持久化状态成功后记录。`job.started` 在成功 Claim 后记录，终态事件只在数据库状态转换完成后记录；Handler 抛出的未收敛异常不能伪装成 `job.failed` 终态。
- Provider 日志不记录 `transport_request`、Raw、响应正文、request_params、Authorization；只记录稳定 lineage、Attempt 状态、费用快照与可安全关联 ID。
- 文档/Archive 修复只纠正最终当前事实，不重写历史决策过程。

# 分步计划

[步骤 1：建立 Red]
→ 修改范围：`tests/unit/content/test_ingestion_contract.py`、Job/Collection/Provider 现有测试
→ 预期结果：旧实现因 InMemory 乱序回滚与缺失结构化生命周期事件失败
→ 验证方式：对应 GitHub Actions/目标 pytest，确认失败断言来自目标行为而非环境

[步骤 2：最小 Green]
→ 修改范围：InMemory Content、JobWorker、CollectionRunExecutor、ProviderDispatchService
→ 预期结果：字段 freshness 与生产子集一致；关键事件在正确状态边界记录
→ 验证方式：目标测试及相关 Unit/PostgreSQL Integration

[步骤 3：事实源收尾]
→ 修改范围：Blueprint 06、`pricing.toml` 注释、Stage 7 Completion Change metadata
→ 预期结果：长期设计、配置注释和最终 Change metadata 与机器事实一致
→ 验证方式：Docs/Secret/quality gates + 人工三向复核

[步骤 4：Review 与集成]
→ 修改范围：完整 PR diff
→ 预期结果：无剩余原审计 P0/P1/P2/P3 blocker
→ 验证方式：两阶段 Review、最终 PR CI、正常 merge、合并后 main 新鲜 CI

# 兼容、部署与回滚

- 公共 API/Canonical/Provider Contract：不变化。
- 数据库/Migration：不变化。
- 依赖/锁文件：不变化。
- 日志新增稳定事件属于运维可观测性补齐；不删除现有日志文件、Formatter 或事件。
- 回滚代码只会失去本次新增生命周期事件和 InMemory parity，不涉及持久化 Schema 回滚。
- 生产部署仍 No-Go，Release 边界不改变。

# 验证计划

```text
uv run pytest tests/unit/content/test_ingestion_contract.py -q
uv run pytest tests/integration/jobs/test_job_runtime.py -q
uv run pytest tests/unit/collection/test_collection_run_executor.py -q
uv run pytest tests/unit/collection/test_provider_dispatch.py -q
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

并以最终 PR head 的 GitHub Actions 和合并后 `main` push workflows 作为完整集成证据。

# Git

- 基线 main：`3519fcd360b8e8201ed03ff1a7c0013c662ab528`
- 开发分支：`fix/stage1-stage7-audit-final-closure`
- PR：尚未创建
- 合并：尚未执行
- Change：`in_progress`

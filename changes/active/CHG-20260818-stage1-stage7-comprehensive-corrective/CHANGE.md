---
schema: rvc-change/v1
id: CHG-20260818-stage1-stage7-comprehensive-corrective
title: Stage 1-7 全面正确性与一致性整改
level: L3
status: ready_for_review
owner: dingyuwen777
branch: fix/stage1-stage7-comprehensive-corrective
created: 2026-08-18
updated: 2026-08-18
depends_on: []
affected_areas: [collection, content, system, platform, provider, scheduler, database, migration, security, logging, testing, ci, documentation]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/modules/content/, backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/bootstrap/, backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/platform/security/, backend/src/aima_ugc/platform/logging/, backend/src/aima_ugc/contracts/, migrations/versions/, tests/, .github/workflows/, docs/blueprint/, docs/collection/, README.md]
contracts: [CanonicalContentV1, CanonicalCommentV1, CanonicalContentAggregateV1, CollectionDecisionPolicyV1, ProviderPlatformCapabilityV1]
data_changes: [collection_plans, collection_plan_decision_policies, collection_runs, collection_scopes, collection_content_actions, collection_candidates, provider_request_attempts, keyword_packs, contents, comments, comment_coverage_observations, comment_thread_coverage_observations, canonical_content_extensions]
---

# 目标

在进入 Stage 8 前，一次性闭环当前 `main@16a97e0aa3b5990b1babf5e0512413242286ae53` 已确认的 Stage 1—7 正确性、一致性、恢复、数据完整性、安全与文档问题。整改后必须以最新分支事实证明：采集在正常、失败、重试、崩溃恢复、分页、乱序回放和多平台配置场景下行为可重复、数据可追溯、Coverage 自洽、Secret 不泄漏，且完整 CI/构建/测试无错误；本 Change 完成前禁止进入 Stage 8。

# 成功标准

- [x] Search 已写 Current 后 Detail/Comments/Replies 失败或进程崩溃，重试仍按本次已批准 durable action 完成未完成动作，不因 previous state 被本次 Search 改写而跳过。
- [x] 已存在 Raw 回放使用 Raw 自身观察时间，不以恢复时当前时间覆盖 `field_observed_at`，旧 Raw 不得回滚更新 Current。
- [x] 单个非法 Cron/异常 backlog Plan 只对该 Plan fail closed，不退出 Scheduler 常驻循环，不阻塞其他合法 Plan。
- [x] Plan 保存/调度前保证可执行：Cron、平台、词包、可用关键词、Provider Config、Registry/Capability、业务配置和支持的策略均闭环；0 Scope Run 不允许记成功。
- [x] Plan/Run 的 `CollectionDecisionPolicyV1` 真正传入正式 Worker；关闭评论、评论目标、回复目标和受控刷新等已批准策略可观察生效。
- [x] Collection Job Deadline 不再使用未经容量依据的固定 300 秒魔数；合法采集不会因默认深度正常耗时被错误杀死，Deadline 仍不可由 Heartbeat 无限延长。
- [x] 当前生产 Mapper 已确认产生的 `alternate_ids/media/topics/mentions/locations` 等 Canonical 事实进入 PostgreSQL 稳定业务结构，不只停留在 Raw。
- [x] 二级回复具有线程级 Coverage；顶层评论 Coverage 与线程/root/reply 数据可无损构造 `CanonicalContentAggregateV1`。
- [x] `pagination_not_advanced/cursor_unavailable/response_data_unavailable/page_limit/known_comment_reached` 等停止原因与 `complete/partial` 正确对应；target 以唯一业务身份统计，不用重复 Provider 行提前吃满。
- [x] Capability 可公开值与 Runtime/Operation/Mapper/Canonical 一致；不存在配置项被静默忽略或声明内容类型映射为错误类型。
- [x] Run Snapshot 的 Provider 执行事实语义明确且可重复；Run 创建后修改/禁用 Provider Config 不得静默改变已创建 Run 的非 Secret 执行配置。Secret rotation 如采用最新 Secret，需在正式文档中明确该唯一例外。
- [x] Candidate 在 Mapper/Ingestion 前形成逐项发现事实，Mapper invalid/failed 也有 ledger；生产 item locator 使用可稳定追溯 Raw item 的身份而非过滤后数组下标。
- [x] Keyword Pack 成员/关系语义变化必然提升 pack version；同一 version 不对应不同关键词集合。
- [x] Plan Secret 检查覆盖敏感后缀；Secret 读取拒绝 symlink 越界；日志递归脱敏嵌套 dict/list；Raw 字符串型 token/query 具有对应负例保护。
- [x] `CanonicalCommentV1.observed_fields` 嵌套叶子严格校验；`author.external_account_id` 显式 null 正确推进 freshness；Attempt 与 Raw Artifact 来源必须在 Fenced Ingestion/数据库边界绑定一致。
- [x] Scope 评论统计使用真实 Canonical identity，不假设 comment ID 跨内容全局唯一。
- [x] TikHub 正式 Worker 复用受控连接池/Client 生命周期，不为每次请求无条件新建 TLS 连接。
- [x] Blueprint/README/模块文档只描述当前机器事实；删除 Stage 7 已过期单平台/当前 Change 表述，并新增覆盖上述跨生命周期不变量的长期测试门禁。
- [x] P0=0、P1=0、P2=0；P3 在本 Change 范围内清零或有经用户批准且不影响正确性/安全/当前验收的明确延期事实。
- [x] 目标测试、相关 Unit/Contract/PostgreSQL Integration、Ruff、mypy、Architecture、Table Ownership、Secret Scan、Docs、Contract 生成/兼容、Alembic upgrade/check/round-trip、前端现有构建/测试与适用 GitHub Actions 全部取得本分支最新 head 的新鲜成功证据。
- [x] 最终只对本 Change diff 做需求符合性 + 代码质量终审；严重/重要问题为 0 后才允许进入 Stage 8。

# 范围

1. Collection Run/Scope 的 durable action/checkpoint、分页、Coverage、Candidate、计数和恢复语义。
2. Scheduler/Plan/Run Snapshot/Provider Config/Keyword Pack 的执行前门禁和版本语义。
3. Content Owner 对当前正式 Canonical 字段、来源链、字段 freshness 和 Aggregate 可重构性的持久化。
4. TikHub Capability/Runtime/Operation/Mapper 的五平台一致性。
5. Secret、日志、Raw 脱敏和 HTTP Client 生命周期。
6. 直接需要的 PostgreSQL Schema/Alembic Migration、Contract、测试、CI 和长期文档。
7. 上述 18 组 Finding 的跨生命周期回归矩阵。

# 非目标

- 不开始 Stage 8 HTTP CRUD、正式业务页面或前端业务功能。
- 不接入认证授权、第三方身份、Session、MFA 等已延期能力。
- 不恢复请求次数/金额 Budget、Budget Account、Reservation Ledger 或发送前 Budget Gate。
- 不实现 Release 阶段 Docker/Compose、协调 Backup/Restore、advisory write barrier、SLO/RPO/RTO。
- 不切换 TikHub 已批准主 endpoint，不新增自动 App/Web/Provider fallback。
- 不引入 Redis、Celery、Kafka、工作流引擎、第二数据库或新的外部基础设施。
- 不升级无关依赖或技术栈版本。

# 必须保持不变

- 模块化单体，API/Worker/Scheduler/Migration 分进程。
- Provider Adapter → immutable Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL。
- PostgreSQL 是唯一业务事实源；Raw 是 Provider 原始证据而不是业务 Current 替代物。
- 一张表只有一个写 Owner；外部 HTTP 不放进数据库事务；所有业务可见写受 Job Fencing 约束。
- 同一 Attempt 不隐藏网络重试；已校验 Raw 存在时不再次调用 Provider；真实重发使用新 Attempt 并保留费用/潜在重复计费事实。
- Scheduler 继续 `Asia/Shanghai + latest_only + max_catch_up_runs=0`；不借整改改变 misfire 业务策略。
- 快手正式 comments/sub-comments 保持 App 主链，Web 仅显式 verified backup。
- 当前公共 HTTP API、Stage 8 非目标和 Budget 回撤状态保持不变。

# 关键决策与方案比较

## A. Run 内后续动作恢复

- 方案 A1：重试时继续完全重算 Decision。实现最少，但 Search 已经改变 Current，无法恢复“本次尚未完成”的原动作，否决。
- 方案 A2：把整条采集流程塞进一个数据库长事务。可保持 previous，但外部 HTTP 会进入长事务，违反仓库硬边界，否决。
- **方案 A3（采用）**：在 Collection Owner 中持久化每个 Run/Scope/Content 的已批准动作与完成 checkpoint；首次 Decision 后先 durable 写动作，再逐项执行/标记完成；重试先恢复未完成动作。保持 HTTP 短事务、可恢复、可审计。

## B. Canonical 扩展字段持久化

- 方案 B1：继续只保 Raw。违反 PostgreSQL 业务事实源与 Canonical 语义，否决。
- 方案 B2：全部塞进单个 JSONB。改动小但稳定业务结构不可约束、难查询且违背稳定字段/关系用列与关联表的仓库规则，否决。
- **方案 B3（采用）**：沿当前 Blueprint 建立 Content Owner 的稳定子表/关系表；Current/Version 仍保持当前核心列，子实体以稳定 identity/position + observed/freshness 语义维护。

## C. Provider Config Snapshot

- 方案 C1：Worker 始终读取当前 Config。会让排队 Run 行为漂移，否决。
- 方案 C2：把 Secret 明文冻结进 Run。违反 Secret 规则，否决。
- **方案 C3（采用）**：Run Snapshot 冻结 provider/provider_config_id/base_url/非敏感执行配置和策略；Secret 只冻结 `secret_ref` 身份，不保存 Secret 值。Run 创建后普通 Config 修改不改变已创建 Run；Secret 文件内容可按同一 `secret_ref` 合规轮换，并在 Blueprint 明确这一例外。

## D. Deadline

- 方案 D1：删除 Deadline。违反 Job Runtime 门禁，否决。
- 方案 D2：继续 300 秒魔数。无法覆盖合法多页采集，否决。
- **方案 D3（采用）**：按 Run Snapshot 中的请求/分页上限和 Provider timeout 推导有上限的 Job Deadline，并设置安全余量；保留不可续期 Deadline 与 Reaper。默认值必须由当前正式采集上限可计算、测试可证明，而不是隐式无限。

# 数据与 Migration

- 允许新增向前 Alembic Revision；禁止改写已发布 `20260813_0001`—`20260817_0017`。
- 预计新增：Collection content action/checkpoint；Content Canonical 子实体表；thread/reply coverage；必要唯一/复合来源约束；Keyword Pack 版本触发/Repository 更新语义。
- Migration 必须覆盖 `0017 → head` 与 `base → head`，并针对包含历史数据的升级路径写真实 PostgreSQL 集成测试；不得只验证空库建表。
- 新结构对既有历史数据不能凭空伪造来源；无法证明的历史子字段保持缺失/unknown，不从 Raw 批量重算除非显式编写受控 backfill。

# 安全、性能、部署和回滚

- 安全：所有新 Snapshot/Checkpoint 禁止存 Secret；Secret root 越界 fail closed；日志/Raw 不因调试扩大暴露面。
- 性能：新增子表按 Content/Comment identity 建必要唯一索引；Plan 校验在保存边界做有界查询；TikHub Client 由 Worker 生命周期复用并在进程退出关闭。
- 部署：本 Change 只修改当前开发基线；未来部署必须先执行新增 Alembic head，再启动新版 Worker/Scheduler/API。
- 回滚：代码可回滚到当前基线，但若已写入新表数据，downgrade 前必须停 Worker/Scheduler并备份/确认新事实可丢弃；不得把结构可 downgrade 等同业务无损回滚。

# 任务

- [x] 读取 `AGENTS.md`、RVC Skill、Change/Development/Repository/Verification 约束、Blueprint README/07，并确认当前 main/Active Change 状态。
- [x] 固化 18 组 Findings、成功标准、方案比较、兼容/Migration/回滚边界。
- [x] 为 P1/P2 建立跨生命周期失败回归（Red），包含 Search 已提交后下游失败、old Raw replay、invalid Plan 隔离、0 Scope、Decision Policy、Coverage、Capability roundtrip、Attempt↔Raw、Secret/freshness 等。
- [x] 实现 Collection durable action/checkpoint 与 retry 恢复。
- [x] 修复 Raw observation time、Plan/Scheduler/Run Snapshot/Deadline/Keyword Pack version。
- [x] 完成 Canonical 子实体、Thread Coverage、来源复合约束与 Comment Contract/freshness。
- [x] 修复五平台 Capability/Runtime/Mapper 与 pagination/unique-count 语义。
- [x] 修复 Secret/Logging/Raw 脱敏与 TikHub Client 生命周期。
- [x] 同步 Blueprint/README/测试说明和 CI 门禁。
- [x] 运行目标测试→模块测试→Contract/DB/Provider→完整 CI，并读取全部失败根因直至绿色。
- [x] 对最终 diff 做需求符合性 Review，再做代码质量/安全/兼容 Review；阻塞项清零。

# 跨生命周期回归矩阵

至少证明：

1. Search Current 已提交 → Detail 429/500 → Retry → Detail/Comments 最终完成。
2. Search Current 已提交 → Comments 429/500 → Retry → 不因 previous 改变而 skip。
3. old Raw replay → newer Current 不回滚。
4. invalid Cron Plan 与 valid Plan 并存 → Scheduler 继续处理 valid Plan。
5. 0 platform/0 keyword/0 executable scope → fail closed；0 Scope Run 不成功。
6. `comments_enabled=false` → 正式 Worker 0 comment requests。
7. `sample_target=N/reply_target=N` → 正式 Worker 深度按 Snapshot 生效。
8. 正常合法长采集的推导 Deadline 大于其最大批准请求预算且仍有限。
9. Mapper 产生的 media/topic/location/alternate_ids 等 → PostgreSQL → Read Model 不丢。
10. root + replies → thread coverage + top-level coverage 自洽并可构造 Aggregate。
11. pagination_not_advanced/cursor unavailable/page_limit → 不伪造 complete。
12. 重复评论 + cursor 推进 → target 按唯一身份计数。
13. Capability 每个可公开值 → Runtime/Operation/Mapper roundtrip 或在保存边界拒绝不支持组合。
14. Run 创建后修改 Provider Config → Snapshot 语义不漂移；同 `secret_ref` Secret rotation 行为明确。
15. Mapper failure → Candidate + failed ingestion ledger 存在。
16. Pack 成员变化 → version 变化。
17. Plan `client_secret/refresh_token/foo_api_key` → 拒绝。
18. Secret root symlink → 拒绝越界。
19. nested dict/list password/token → Log Formatter 不泄漏。
20. Raw URL/query `xsec_token/refresh_token/client_secret` → 脱敏或拒绝。
21. Comment `metrics.invalid_field/author.invalid_field` → Contract 拒绝。
22. `author.external_account_id` 显式 null → Current 与 freshness 正确。
23. Attempt A + Raw B → Fenced Ingestion/数据库拒绝。
24. 同一 Scope 不同 Content 复用同 comment ID 的构造用例 → 统计为两条真实评论身份。

# 验证

## 计划

- Unit/Contract：`uv run pytest tests/unit tests/contracts -q`
- Collection PostgreSQL：`uv run pytest tests/integration/collection -q`
- Content PostgreSQL：`uv run pytest tests/integration/content -q`
- Database/Job：`uv run pytest tests/integration/database tests/integration/jobs -q`
- 全后端：`uv run pytest tests -q`
- Ruff：`uv run ruff check .`
- mypy：`uv run mypy backend/src tests`
- Architecture：`uv run python scripts/quality/check_architecture.py`
- Table Ownership：`uv run python scripts/quality/check_table_ownership.py`
- Secret Scan：`uv run python scripts/quality/scan_secrets.py`
- Docs：`uv run python scripts/quality/check_docs.py`
- Contract：生成物/兼容检查使用仓库现有 CI 命令。
- Alembic：`upgrade head`、`check`、`downgrade/upgrade` 及历史数据升级回归。
- Frontend：保持当前 `npm ci`、lint/typecheck/test/build 现有门禁。
- GitHub Actions：最终 PR head 读取所有适用 workflow/job，failure/cancelled/timed_out/in_progress 均为 0。

## 新鲜证据

- 最终终审新增 5 组回归先在未修实现上稳定 Red：短周期 Deadline 无执行窗口下限、Thread Coverage upsert 返回假 ID、Reply soft-target 误报 complete、SubComments 显式空页未覆盖旧 reply_count、Reply 身份失败缺 Candidate ledger。
- GitHub-hosted PostgreSQL 18 Red→Green Run `32112722378`：5 组目标回归 Green；mypy 143 source files 无错误；Unit/Contract 236 passed；Collection Integration 66 passed；Content Integration 19 passed；Database Integration 8 passed；Architecture/Table Ownership/Secret Scan/Docs/Contract/Alembic round-trip 全部通过。
- 修复落盘后的代码候选 `63686850f233656fcee3c3c25d622a2c9c10f5aa` 取得 12/12 适用正式 GitHub Actions 成功：CI、Stage 4、5A/5B/5C/5D、Stage 6、Stage 7 Keyword Packs/Provider Config Routing/Plan Occurrence Run Snapshot/Scheduler Runtime、Stage 1-7 Audit Correctness。
- 最终文档提交仍必须由 PR 当前 head 的适用 GitHub Actions 重新验证；任何 Red 都会把本 Change 退回 `in_progress`，不得合并。

# 文档影响

整改后同步 `docs/blueprint/02/03/05/07/08/09`、Blueprint README、Collection 模块/平台说明、测试说明和必要根 README；只写最终当前事实，不把本 Change 流水账复制进长期文档。

# 交付

- 基线 main：`16a97e0aa3b5990b1babf5e0512413242286ae53`
- 分支：`fix/stage1-stage7-comprehensive-corrective`
- Commit：代码整改已落到 PR #65 分支；最终文档事实同步由本 Change 收尾提交完成。
- PR：#65 `修复 Stage 1-7 全面正确性与一致性问题`；当前 Change 达到 `ready_for_review` 后才允许把 Draft 转 Ready，未授权不得合并 main。
- 发布：本 Change 不部署生产。

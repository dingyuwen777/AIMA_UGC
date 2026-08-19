---
schema: rvc-change/v1
id: CHG-20260818-stage1-stage7-comprehensive-corrective
title: Stage 1-7 全面正确性与一致性整改
level: L3
status: ready_for_review
owner: dingyuwen777
branch: fix/stage1-stage7-shared-baseline-ci
created: 2026-08-18
updated: 2026-08-19
depends_on: []
affected_areas:
  - collection
  - content
  - system
  - platform
  - provider
  - scheduler
  - database
  - migration
  - security
  - logging
  - testing
  - ci
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/system/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/adapters/providers/tikhub/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/platform/
  - backend/src/aima_ugc/contracts/
  - contracts/collection/
  - migrations/versions/
  - tests/
  - scripts/quality/
  - scripts/contracts/
  - .github/workflows/
  - docs/blueprint/
  - docs/collection/
  - README.md
  - .reliable-vibe-coding/project-context.json
contracts:
  - CanonicalContentV1
  - CanonicalCommentV1
  - CanonicalContentAggregateV1
  - CollectionDecisionPolicyV1
  - ProviderPlatformCapabilityV1
data_changes:
  - collection_plans
  - collection_plan_decision_policies
  - collection_runs
  - collection_scopes
  - collection_content_actions
  - collection_candidates
  - provider_request_attempts
  - keyword_packs
  - contents
  - comments
  - comment_coverage_observations
  - comment_thread_coverage_observations
  - canonical_content_extensions
---

# 目标

在进入 Stage 8 前，一次性闭环 Stage 1—7 的正确性、一致性、恢复、数据完整性、安全与文档问题。整改后必须以最新分支事实证明：采集在正常、失败、重试、崩溃恢复、分页、乱序回放和多平台配置场景下行为可重复、数据可追溯、Coverage 自洽、Secret 不泄漏，且完整 CI/构建/测试无错误；本 Change 完成前禁止进入 Stage 8。

## 2026-08-19 共享基线重新打开

PR #65 已于 `0446b4a2bda3160f61a88d9ed662040f46ee2ac9` 合并。随后 `main` 又包含 `4d493801bbdf2bf5e6e0a8b188464f68cc40c0b2`（`调整tikhub_test目录结构`）和 `0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`（Windows 环境引导修复）。这两个提交以及其中合法的 TikHub 调试目录重组、抖音调试容错、北京时间展示和 Windows 引导变化必须保留，不做整提交 revert。

用户已确认：当前任务不是撤销这些提交，而是让长期文档、质量门禁、Contract 生成/兼容检查和 GitHub Actions 与当前代码事实重新一致，为 P1 后续合并恢复共享基线。

本轮优先按以下边界处理：

1. `backend/src/aima_ugc/platform/` 仍是当前真实 Platform 基础设施目录；质量脚本和 Workflow 不得要求不存在的 `backend/src/aima_ugc/operations/`。
2. `ProviderPlatformCapabilityV1` 的固定公共身份继续保持 `provider-platform-capability.v1`，Route 保持 `provider-platform-route.v1`；本轮恢复源码、固定 JSON Schema、生成器、兼容检查和测试的一致性，不把 Provider 内部 `operations` 能力列表误当成公共 Contract 重命名。
3. 不通过放宽、删除或跳过 Architecture、Contract、Migration、Database 测试来掩盖源码内部错误。若同一机器事实内部存在机械重命名残留（例如表定义字段名与同文件索引/Repository 实际访问列不一致），只允许做不改变业务语义的最小一致性修正。
4. 不修改 P1 的 Analysis/Excel/Prompt/Taxonomy 业务逻辑，不向 PR #66 塞 Stage 1—7 整改。

### 本轮新增成功标准

- [x] Architecture 检查与真实 `platform/` 目录一致，不再要求不存在的 `operations/` 路径，同时继续保持既有模块依赖硬边界。
- [x] Collection Contract 当前源码、固定 JSON Schema、生成脚本、兼容检查和测试统一保持 `provider-platform-capability.v1` / `provider-platform-route.v1`；Contract drift 检查继续启用并通过。
- [x] Content/Collection/Keyword 等表定义、Repository 访问列和现有 Migration 机器事实内部一致；数据库模块可正常 import，Alembic 不因列名自相矛盾失败。
- [x] AGENTS/Blueprint/README/测试说明与当前机器事实一致；历史归档 Change 恢复为当时事实，RVC 项目索引由 GitHub-hosted runner 重新生成。
- [x] 代码/文档/索引候选 `2e442db7c94577ffe2055d8cc1c5691b93a049b6` 的目标测试、相关回归、Ruff、mypy、Architecture、Table Ownership、Secret、Docs、Contract、Migration、前端现有门禁和 12/12 适用 GitHub Actions 均取得新鲜绿色证据。
- [ ] corrective PR 合并后，最新 `main` 再取得适用 Stage 1—7 CI 绿色，才满足回到 P1H 收口的条件。

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
- [x] PR #65 合并前目标测试、相关 Unit/Contract/PostgreSQL Integration、Ruff、mypy、Architecture、Table Ownership、Secret Scan、Docs、Contract 生成/兼容、Alembic upgrade/check/round-trip、前端构建/测试及适用 GitHub Actions 已取得当时 head 的成功证据。
- [x] PR #65 合并前最终 diff 已完成需求符合性 + 代码质量终审，严重/重要问题为 0。

# 范围

1. Collection Run/Scope 的 durable action/checkpoint、分页、Coverage、Candidate、计数和恢复语义。
2. Scheduler/Plan/Run Snapshot/Provider Config/Keyword Pack 的执行前门禁和版本语义。
3. Content Owner 对当前正式 Canonical 字段、来源链、字段 freshness 和 Aggregate 可重构性的持久化。
4. TikHub Capability/Runtime/Operation/Mapper 的五平台一致性。
5. Secret、日志、Raw 脱敏和 HTTP Client 生命周期。
6. 直接需要的 PostgreSQL Schema/Alembic Migration、Contract、测试、CI 和长期文档。
7. 上述跨生命周期 Finding 的长期回归矩阵。
8. PR #65 合并后新增的 Stage 1—7 共享基线 CI/文档/机器事实一致性收口。

# 非目标

- 不开始 Stage 8 HTTP CRUD、正式业务页面或前端业务功能。
- 不接入认证授权、第三方身份、Session、MFA 等已延期能力。
- 不恢复请求次数/金额 Budget、Budget Account、Reservation Ledger 或发送前 Budget Gate。
- 不实现 Release 阶段 Docker/Compose、协调 Backup/Restore、advisory write barrier、SLO/RPO/RTO。
- 不切换 TikHub 已批准主 endpoint，不新增自动 App/Web/Provider fallback。
- 不引入 Redis、Celery、Kafka、工作流引擎、第二数据库或新的外部基础设施。
- 不升级无关依赖或技术栈版本。
- 不撤销 `4d493801` 或 `0dc66619`，不恢复 tikhub_test 的旧目录结构。
- 不操作 P1 PR #66。

# 必须保持不变

- 模块化单体，API/Worker/Scheduler/Migration 分进程。
- Provider Adapter → immutable Raw → Mapper → Canonical → Ingestion → Owner Repository → PostgreSQL。
- PostgreSQL 是唯一业务事实源；Raw 是 Provider 原始证据而不是业务 Current 替代物。
- 一张表只有一个写 Owner；外部 HTTP 不放进数据库事务；所有业务可见写受 Job Fencing 约束。
- 同一 Attempt 不隐藏网络重试；已校验 Raw 存在时不再次调用 Provider；真实重发使用新 Attempt 并保留费用/潜在重复计费事实。
- Scheduler 继续 `Asia/Shanghai + latest_only + max_catch_up_runs=0`；不借整改改变 misfire 业务策略。
- 快手正式 comments/sub-comments 保持 App 主链，Web 仅显式 verified backup。
- 当前公共 HTTP API、Stage 8 非目标和 Budget 回撤状态保持不变。
- tikhub_test 当前 `core/ + operations/ + test.py` 目录组织保持不变。

# 关键决策与方案比较

## A. Run 内后续动作恢复

- 方案 A1：重试时继续完全重算 Decision。实现最少，但 Search 已经改变 Current，无法恢复“本次尚未完成”的原动作，否决。
- 方案 A2：把整条采集流程塞进一个数据库长事务。可保持 previous，但外部 HTTP 会进入长事务，违反仓库硬边界，否决。
- **方案 A3（采用）**：在 Collection Owner 中持久化每个 Run/Scope/Content 的已批准动作与完成 checkpoint；首次 Decision 后先 durable 写动作，再逐项执行/标记完成；重试先恢复未完成动作。

## B. Canonical 扩展字段持久化

- 方案 B1：继续只保 Raw。违反 PostgreSQL 业务事实源与 Canonical 语义，否决。
- 方案 B2：全部塞进单个 JSONB。稳定业务结构不可约束、难查询且违背仓库规则，否决。
- **方案 B3（采用）**：沿当前 Blueprint 建立 Content Owner 的稳定子表/关系表。

## C. Provider Config Snapshot

- 方案 C1：Worker 始终读取当前 Config。会让排队 Run 行为漂移，否决。
- 方案 C2：把 Secret 明文冻结进 Run。违反 Secret 规则，否决。
- **方案 C3（采用）**：Run Snapshot 冻结非敏感执行配置；Secret 只冻结 `secret_ref` 身份。

## D. Deadline

- 方案 D1：删除 Deadline。违反 Job Runtime 门禁，否决。
- 方案 D2：继续 300 秒魔数。无法覆盖合法多页采集，否决。
- **方案 D3（采用）**：按 Run Snapshot 的请求/分页上限和 Provider timeout 推导有上限的 Job Deadline。

## E. PR #65 合并后共享基线漂移

- 方案 E1：整体 revert `4d493801`。会撤销用户明确要求保留的 tikhub_test 重组和其他合法改动，否决。
- 方案 E2：修改/降低 CI，让错误机器事实不再被测试。会绕过 Architecture/Contract/Migration/Database 门禁，否决。
- **方案 E3（采用）**：保留后续提交；把文档、质量脚本、Contract 生成/固定产物和 Workflow 对齐当前机器事实；仅对源码内部无法运行的机械残留做最小一致性修正，不改变业务行为。

# 数据与 Migration

- 历史已发布 Revision 继续作为机器事实参与 `base → head`、历史 revision → head、downgrade/re-upgrade 和 drift 验证。
- 本轮不新增业务 Schema，不新增 Migration；如果发现当前源码表定义与当前已提交 Migration 因机械命名残留而不一致，优先恢复同一既有业务语义的一致性，不借机引入新字段/新表。
- 新结构对既有历史数据不凭空伪造来源。

# 安全、性能、部署和回滚

- 安全：不放宽 Secret、日志、Raw 和 Provider 出站边界。
- 性能：本轮不改变采集请求深度、分页、并发或模型性能策略。
- 部署：本 Change 只修复共享开发基线，不部署生产。
- 回滚：本轮 corrective PR 可整体 revert；不得以回滚本轮为理由同时撤销 `4d493801`/`0dc66619`。

# 任务

- [x] 重新读取 `AGENTS.md`、RVC Skill、Blueprint README/07 和当前 Active Change。
- [x] 确认 PR #65 已合并、旧 corrective 分支已不存在，当前 `main=0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`。
- [x] 确认 `4d493801` 与 `0dc66619` 必须保留，不做整提交 revert。
- [x] 确认当前仓库不存在 `backend/src/aima_ugc/operations/`，Architecture 的 11 个 operations 路径要求是门禁漂移。
- [x] 确认 `4d493801` 曾把 `ProviderPlatformCapabilityV1.schema_version` 误改为 `provider-operations-capability.v1`，而固定 Contract 仍是 provider-platform 文件名；本轮已恢复固定 Provider Platform Contract 身份并验证生成/兼容一致。
- [x] 确认 `modules/content/tables.py` 的 `operations` 列与 `contents_table.c.platform`/Repository 当前访问形成源码内部矛盾，不能靠跳过测试解决。
- [x] 在 corrective PR #67 上复现最新 GitHub Actions Red 并保存日志证据。
- [x] 修复 Architecture/Contract/Docs/Workflow 漂移，同时保留已批准的 TikHub/tikhub_test 重组、抓取逻辑、`.dev` 默认域名、抖音调试容错和 Windows bootstrap。
- [x] 对源码内部机械一致性错误建立/复用失败测试后做最小修正；未新增业务 Schema、Migration 或 P1 业务逻辑。
- [x] 运行目标测试、相关 PostgreSQL、Ruff、mypy、Architecture、Ownership、Secret、Docs、Contract、Migration、前端及全部适用 CI，并取得候选 `2e442db7` 的 12/12 成功。
- [x] 完成需求符合性 + 代码质量终审：与 PR #65 合并基线比较后，剩余差异仅为已批准 TikHub/tikhub_test、北京时间、Windows bootstrap、对应测试/文档/Active Change 与 RVC 索引；未发现 P1 路径或共享误替换残留。
- [ ] corrective PR 合并后验证最新 main 全绿，再允许回到 P1H。

# 跨生命周期回归矩阵

PR #65 已建立并保留原 24 组回归；本轮额外证明：

25. Architecture Required Paths 必须存在且与当前真实 Platform 目录一致。
26. Provider Capability 固定 Schema 文件名、schema_version 与生成结果一致。
27. `database_schema`/Content Table import 不因列名不一致抛 `AttributeError`。
28. Repository/Migration/SQLAlchemy metadata 对内容、Scope、Keyword Pack、Plan 平台身份字段保持同一业务语义。
29. tikhub_test 新目录结构和 Windows bootstrap 后续改动在整改后仍保留。
30. P1 Analysis/Excel/Prompt/Taxonomy diff 不进入本 corrective PR。

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
- Contract：`uv run python scripts/contracts/generate.py --check` 与现有兼容检查。
- Alembic：`upgrade head`、`check`、`downgrade/upgrade` 及历史数据升级回归。
- Frontend：保持当前 `npm ci`、lint/typecheck/test/build 现有门禁。
- GitHub Actions：最终 PR head 读取所有适用 workflow/job，failure/cancelled/timed_out/in_progress 均为 0。

## 历史证据

- PR #65 终审 Red→Green Run `32112722378`：目标回归、mypy、Unit/Contract、Collection/Content/Database Integration、Architecture/Table Ownership/Secret/Docs/Contract/Alembic round-trip 当时全部通过。
- PR #65 head `931850258cb41cac44748c60e84f53ca73a79c6f` 当时取得 12/12 适用 GitHub Actions 成功。

## 本轮新鲜证据

- 初始 Red：PR #67 的 Stage 6 Run `32200828033` 在 Unit 收集阶段出现 `AttributeError: platform`、tikhub_test 导入错误，PostgreSQL Job 在 `alembic upgrade head` 前加载 metadata 时同样因 `contents_table.c.platform` 不存在退出；Architecture 另由不存在的 `operations/` Required Paths 失败。
- TikHub 行为 Red→Green：新增/调整目标测试先得到 `241 passed / 3 failed`（北京时间 run-id、默认 `.dev`、第三方 Origin 应拒绝）；实现后为 `243 passed / 1 failed`（仅目录安全化丢失 `+`）；允许 `+0800` 后转 Green。
- 代码/文档/索引候选 `2e442db7c94577ffe2055d8cc1c5691b93a049b6` 取得 12/12 正式 Stage 1—7 Workflow 全部 `success`：CI `32202997908`、Stage 4 `32202997959`、Stage 5A `32202997905`、Stage 5B `32202997910`、Stage 5C `32202997967`、Stage 5D `32202997929`、Stage 6 `32202997901`、Stage 7 Keyword Packs `32202997949`、Provider Config Routing `32202997924`、Plan Occurrence Run Snapshot `32202997904`、Scheduler Runtime `32202997890`、Stage 1-7 Audit Correctness `32202997885`；failure/cancelled/timed_out/in_progress 均为 0。
- Stage 5D Run `32202997929`：`pytest tests/unit/collection tests/unit/jobs tests/contracts/test_provider_v1.py -q` 为 `244 passed in 4.79s`；`pytest tests/integration/collection -q` 为 `66 passed in 10.76s`；Ruff `270 files already formatted` / `All checks passed!`；mypy `Success: no issues found in 146 source files`；Architecture、Table Ownership、Secret、Docs、Contract 生成/兼容、Alembic base 与 Stage 5C round-trip 全部成功。
- RVC 项目索引通过 GitHub-hosted Run `32202877294` 执行仓库自带 `rvc.py discover --root . --json` 真实生成并提交；临时生成 Workflow 已删除。
- TikHub 正式 Operation/Mapper/Runner 与脱敏真实响应 fixture 回归由现有 CI 覆盖；本轮未执行付费/外部真实 TikHub 在线调用，因为当前 GitHub connector 没有可安全注入 Secret 的 workflow-dispatch 输入，本轮未把真实 key 写入代码、Workflow、日志或 PR。

# 文档影响

已完成语义检查与同步：Architecture/Workflow 保持真实 `platform/` 目录；固定 Provider Platform Contract 恢复一致；TikHub 调试 README 同步 `.dev + 300s + core/operations + 北京时间 +0800`；被批量替换误改的历史归档 Change 恢复为当时事实；RVC 项目索引按当前仓库重新生成。根 `AGENTS.md` 本轮未修改。

# 交付

- 当前基线 main：`0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`
- 当前分支：`fix/stage1-stage7-shared-baseline-ci`
- 原实现 PR：#65，已合并；merge commit=`0446b4a2bda3160f61a88d9ed662040f46ee2ac9`。
- 本轮 corrective PR：#67 `修复 Stage 1-7 共享基线 CI 漂移`，当前为 Open / Draft / 未合并；候选 `2e442db7c94577ffe2055d8cc1c5691b93a049b6` 已 12/12 正式 Stage 1—7 Workflow 成功。
- P1 PR #66：不操作。
- 发布：本 Change 不部署生产。

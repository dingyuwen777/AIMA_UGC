---
schema: rvc-change/v1
id: CHG-20260818-stage1-stage7-comprehensive-corrective
title: Stage 1-7 全面正确性与一致性整改
level: L3
status: done
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
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
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

在进入 Stage 8 前，一次性闭环 Stage 1—7 的正确性、一致性、恢复、数据完整性、安全与文档问题。整改后必须以最新仓库事实证明：采集在正常、失败、重试、崩溃恢复、分页、乱序回放和多平台配置场景下行为可重复、数据可追溯、Coverage 自洽、Secret 不泄漏，且完整 CI/构建/测试无错误。

本 Change 已完成并归档。PR #67 已合并到 `main`，随后通过一次明确不合并的 post-merge 验证 PR #68 重新触发全部 12 个正式 Stage 1—7 workflow；12/12 全部成功。验证 marker 已全部删除，验证分支最终与 `main@0d7e242c0e0a8871830a22974f20aa3f5a902f7b` 文件差异为 0。

## 2026-08-19 共享基线重新打开

PR #65 已于 `0446b4a2bda3160f61a88d9ed662040f46ee2ac9` 合并。随后 `main` 又包含 `4d493801bbdf2bf5e6e0a8b188464f68cc40c0b2`（`调整tikhub_test目录结构`）和 `0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`（Windows 环境引导修复）。这两个提交以及其中合法的 TikHub 调试目录重组、抖音调试容错、北京时间展示和 Windows 引导变化必须保留，不做整提交 revert。

用户已确认：当前任务不是撤销这些提交，而是让长期文档、质量门禁、Contract 生成/兼容检查和 GitHub Actions 与当前代码事实重新一致，为 P1 后续合并恢复共享基线。

本轮按以下边界完成收口：

1. `backend/src/aima_ugc/platform/` 仍是当前真实 Platform 基础设施目录；质量脚本和 Workflow 不要求不存在的 `backend/src/aima_ugc/operations/`。
2. `ProviderPlatformCapabilityV1` 的固定公共身份继续保持 `provider-platform-capability.v1`，Route 保持 `provider-platform-route.v1`；源码、固定 JSON Schema、生成器、兼容检查和测试保持一致，不把 Provider 内部 `operations` 能力列表误当成公共 Contract 重命名。
3. 不通过放宽、删除或跳过 Architecture、Contract、Migration、Database 测试掩盖源码内部错误；机械重命名残留只做不改变业务语义的最小一致性修正。
4. 不修改 P1 的 Analysis/Excel/Prompt/Taxonomy 业务逻辑，不向 PR #66 混入 Stage 1—7 整改。
5. TikHub / `tikhub_test` 以用户批准的“调整 tikhub_test 目录结构”目标行为为准，保留 `core/ + operations/ + test.py`、五平台调试入口、Runner、分页、去重、调试容错和正式抓取调用链；不恢复旧 TikHub 实现。

### 本轮新增成功标准

- [x] Architecture 检查与真实 `platform/` 目录一致，不再要求不存在的 `operations/` 路径，同时继续保持既有模块依赖硬边界。
- [x] Collection Contract 当前源码、固定 JSON Schema、生成脚本、兼容检查和测试统一保持 `provider-platform-capability.v1` / `provider-platform-route.v1`；Contract drift 检查继续启用并通过。
- [x] Content/Collection/Keyword 等表定义、Repository 访问列和现有 Migration 机器事实内部一致；数据库模块可正常 import，Alembic 不因列名自相矛盾失败。
- [x] AGENTS/Blueprint/README/测试说明与当前机器事实一致；历史归档 Change 恢复为当时事实，RVC 项目索引由 GitHub-hosted runner 重新生成。
- [x] 最终 corrective PR head `6e84a8566d3431da15c83d02b4ae45cf8f9a498c` 的目标测试、相关回归、Ruff、mypy、Architecture、Table Ownership、Secret、Docs、Contract、Migration、前端现有门禁和 12/12 适用 GitHub Actions 均取得新鲜绿色证据。
- [x] PR #67 合并后，以 `main@0d7e242c0e0a8871830a22974f20aa3f5a902f7b` 为基线的 post-merge 验证 PR #68 再次触发 12/12 正式 Stage 1—7 workflow，全部 `success`。

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
4. TikHub Capability/Runtime/Operation/Mapper 的五平台一致性，以及 `tikhub_test` 调试复用正式生产实现的边界。
5. Secret、日志、Raw 脱敏和 HTTP Client 生命周期。
6. 直接需要的 PostgreSQL Schema/Alembic Migration、Contract、测试、CI 和长期文档。
7. 上述跨生命周期 Finding 的长期回归矩阵。
8. PR #65 合并后新增的 Stage 1—7 共享基线 CI/文档/机器事实一致性收口。

# 非目标

- 不开始 Stage 8 HTTP CRUD、正式业务页面或前端业务功能。
- 不接入认证授权、第三方身份、Session、MFA 等已延期能力。
- 不恢复请求次数/金额 Budget、Budget Account、Reservation Ledger 或发送前 Budget Gate。
- 不实现 Release 阶段 Docker/Compose、协调 Backup/Restore、advisory write barrier、SLO/RPO/RTO。
- 不改变已批准的 TikHub 五平台抓取主链，不新增自动 App/Web/Provider fallback。
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
- TikHub 正式 Transport 默认 `https://api.tikhub.dev`，兼容显式旧 `https://api.tikhub.io`，任意第三方 Origin 在发送 Secret 前拒绝。
- `tikhub_test` 默认请求超时 300 秒；人工可见 run-id 使用北京时间并保留显式 `+0800`。

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

## F. TikHub Origin 与调试边界

- 方案 F1：为支持 `.dev` 直接去掉 Origin 校验。会扩大 Secret 出站范围，否决。
- 方案 F2：只允许旧 `.io`。与当前批准的 `.dev` 默认行为冲突，否决。
- **方案 F3（采用）**：默认 `.dev`，兼容显式旧 `.io`，严格拒绝其他 Origin；不改变正式 endpoint、请求参数、分页、Mapper 或 Runner。

# 数据与 Migration

- 历史已发布 Revision 继续作为机器事实参与 `base → head`、历史 revision → head、downgrade/re-upgrade 和 drift 验证。
- 本轮不新增业务 Schema，不新增 Migration；被 `4d493801` 机械替换误改的历史 Migration 恢复到 PR #65 合并时已验证事实。
- 新结构对既有历史数据不凭空伪造来源。

# 安全、性能、部署和回滚

- 安全：不放宽 Secret、日志、Raw 和 Provider 出站边界；TikHub Origin allowlist 在发送凭据前生效。
- 性能：本轮不改变正式采集请求深度、分页、并发或模型性能策略；`tikhub_test` 300 秒是独立调试请求超时，不等于生产 Job Deadline。
- 部署：本 Change 只修复共享开发基线，不部署生产。
- 回滚：PR #67 可整体 revert；不得以回滚本轮为理由同时撤销 `4d493801`/`0dc66619` 的合法行为。

# 任务

- [x] 重新读取 `AGENTS.md`、RVC Skill、Blueprint README/07 和当前 Active Change。
- [x] 确认 PR #65 已合并，整改开始时 `main=0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`。
- [x] 确认 `4d493801` 与 `0dc66619` 必须保留，不做整提交 revert。
- [x] 确认当前仓库不存在 `backend/src/aima_ugc/operations/`，Architecture 的 operations 路径要求是门禁漂移。
- [x] 确认 `4d493801` 曾把 `ProviderPlatformCapabilityV1.schema_version` 误改为 `provider-operations-capability.v1`，而固定 Contract 仍是 provider-platform 文件名；本轮恢复固定 Provider Platform Contract 身份并验证生成/兼容一致。
- [x] 确认 Content Table/Repository 中 `operations` / `platform` 的机械替换矛盾不能靠跳过测试解决。
- [x] 在 corrective PR #67 上复现最新 GitHub Actions Red 并保存日志证据。
- [x] 修复 Architecture/Contract/Docs/Workflow 漂移，同时保留已批准的 TikHub/tikhub_test 重组、抓取逻辑、`.dev` 默认域名、抖音调试容错和 Windows bootstrap。
- [x] 对源码内部机械一致性错误建立/复用失败测试后做最小修正；未新增业务 Schema、Migration 或 P1 业务逻辑。
- [x] 运行目标测试、相关 PostgreSQL、Ruff、mypy、Architecture、Ownership、Secret、Docs、Contract、Migration、前端及全部适用 CI。
- [x] 完成需求符合性 + 代码质量终审：与 PR #65 合并基线比较后，剩余差异仅为已批准 TikHub/tikhub_test、北京时间、Windows bootstrap、对应测试/文档/Active Change 与 RVC 索引；未发现 P1 路径或共享误替换残留。
- [x] PR #67 最终 head `6e84a8566d3431da15c83d02b4ae45cf8f9a498c` 取得 12/12 正式 workflow success 后合并到 `main`，merge commit=`0d7e242c0e0a8871830a22974f20aa3f5a902f7b`。
- [x] 合并后通过 PR #68 重新触发全部 12 个 Stage 1—7 workflow；12/12 success 后关闭且未合并，marker 已清理，验证分支最终与 main 文件差异为 0。

# 跨生命周期回归矩阵

PR #65 已建立并保留原 24 组回归；本轮额外证明：

25. Architecture Required Paths 必须存在且与当前真实 Platform 目录一致。
26. Provider Capability 固定 Schema 文件名、schema_version 与生成结果一致。
27. `database_schema`/Content Table import 不因列名不一致抛 `AttributeError`。
28. Repository/Migration/SQLAlchemy metadata 对内容、Scope、Keyword Pack、Plan 平台身份字段保持同一业务语义。
29. tikhub_test 新目录结构和 Windows bootstrap 后续改动在整改后仍保留。
30. P1 Analysis/Excel/Prompt/Taxonomy diff 不进入 corrective PR #67。
31. TikHub 默认 `.dev`、显式旧 `.io` 兼容和第三方 Origin 拒绝同时成立。
32. `tikhub_test` run-id 使用北京时间 `+0800`，目录安全化不再把 `+` 机械替换掉。
33. RVC `project-context.json` 由当前仓库事实重新发现生成，不手工伪造哈希。
34. PR #67 合并后，对 `main` 基线重新执行正式 Stage 1—7 workflow，避免只凭 pre-merge 绿色宣称闭环。

# 验证

## Red → Green 证据

- 初始 Red：PR #67 的 Stage 6 Run `32200828033` 在 Unit 收集阶段出现 `AttributeError: platform`、tikhub_test 导入错误，PostgreSQL Job 在 `alembic upgrade head` 前加载 metadata 时同样因 `contents_table.c.platform` 不存在退出；Architecture 另由不存在的 `operations/` Required Paths 失败。
- TikHub 行为 Red→Green：新增/调整目标测试先得到 `241 passed / 3 failed`（北京时间 run-id、默认 `.dev`、第三方 Origin 应拒绝）；实现后为 `243 passed / 1 failed`（仅目录安全化丢失 `+`）；允许 `+0800` 后转 Green。

## 合并前最终证据

- PR #67 最终 head：`6e84a8566d3431da15c83d02b4ae45cf8f9a498c`。
- 12/12 正式 Stage 1—7 workflow 全部 `success`：CI `#1245`、Stage 4 `#663`、Stage 5A `#953`、Stage 5B `#953`、Stage 5C `#950`、Stage 5D `#947`、Stage 6 `#1083`、Stage 7 Keyword Packs `#878`、Provider Config Routing `#991`、Plan Occurrence Run Snapshot `#876`、Scheduler Runtime `#1218`、Stage 1-7 Audit Correctness `#390`；failure/cancelled/timed_out/in_progress 均为 0。
- 同一最终代码树在此前候选上已取得 Stage 5D 目标集 `244 passed`、Collection PostgreSQL `66 passed`、Ruff、mypy、Architecture、Table Ownership、Secret、Docs、Contract 和 Alembic round-trip 全绿。
- PR #67 合并方式为普通 merge；合并前 head `6e84a856...` 与 merge commit `0d7e242c...` 的 Git tree 均为 `fd1cc533a3b73434f1f6a0ad125b5d716246248b`，合并没有改变文件内容。

## 合并后 main 复验证据

GitHub App 的 `fetch_commit_workflow_runs` 只返回 pull_request 事件，不能直接列出 push-main run。为避免把工具缺口误当成“已验证”，本轮在 PR #67 合并之后从 `main@0d7e242c0e0a8871830a22974f20aa3f5a902f7b` 创建一次性验证 PR #68，仅增加 3 个不会被 Alembic/pytest/Ruff/mypy 执行的 `.txt` marker，以命中现有 workflow `paths`。PR #68 明确禁止合并。

PR #68 head `82b0291974ac6387198c315fd84f280ea592931a` 重新触发并取得 12/12 success：

- CI `#1247` / Run `32204236317`；
- Stage 4 Job Runtime `#665` / Run `32204236364`；
- Stage 5A Provider Raw `#955` / Run `32204236320`；
- Stage 5B Collection Execution `#955` / Run `32204236346`；
- Stage 5C Provider Persistence `#952` / Run `32204236383`；
- Stage 5D Provider Dispatch `#949` / Run `32204236284`；
- Stage 6 XHS Vertical Slice `#1085` / Run `32204236482`；
- Stage 7 Keyword Packs `#880` / Run `32204236366`；
- Stage 7 Provider Config Routing `#993` / Run `32204236334`；
- Stage 7 Plan Occurrence Run Snapshot `#878` / Run `32204236391`；
- Stage 7 Scheduler Runtime `#1220` / Run `32204236315`；
- Stage 1-7 Audit Correctness `#391` / Run `32204236300`。

Stage 5D post-merge Run `32204236284` 的新鲜日志证据：

- `uv run pytest tests/unit/collection tests/unit/jobs tests/contracts/test_provider_v1.py -q`：`244 passed in 3.66s`；
- `uv run pytest tests/integration/collection -q`：`66 passed in 12.76s`；
- nonretryable 4xx：`1 passed`；Coverage/detail：`3 passed`；Scope recovery：`1 passed`；
- Ruff format：`270 files already formatted`；Ruff lint：`All checks passed!`；
- mypy：`Success: no issues found in 146 source files`；
- Architecture、Table Ownership、Secret Scan、Docs、Contract generate/check compatibility 全部成功；
- Alembic `upgrade head` / `check`、`downgrade base → upgrade head`、Stage 5C revision round-trip 全部成功。

验证结束后：

- PR #68 已 `closed`、`merged=false`；
- 3 个 marker 已全部从验证分支删除；
- `compare main@0d7e242c... → verify branch@02e56112...` 显示 `files=[]`，即最终文件树与 main 无差异；
- 原整改分支 `fix/stage1-stage7-shared-baseline-ci` 在 PR #67 合并后已由仓库自动删除。

## RVC 项目索引验证

- 在 corrective PR head 上由 GitHub-hosted runner 执行仓库自带 `rvc.py discover --root .` 生成 `.reliable-vibe-coding/project-context.json`；不是手工伪造哈希。
- 临时生成/修订 Workflow 在用途完成后均已删除，未进入最终 `main`。

## TikHub 在线验证边界

- TikHub 正式 Operation/Mapper/Runner 与脱敏真实响应 fixture 回归由现有 CI 覆盖。
- 本轮没有执行付费/外部真实 TikHub 在线调用：当前用于仓库读写的 GitHub connector 没有可安全注入 Secret 的 workflow-dispatch 输入，本轮没有把真实 key 写入代码、Workflow、日志或 PR。

# 文档影响

已完成语义检查与同步：Architecture/Workflow 保持真实 `platform/` 目录；固定 Provider Platform Contract 恢复一致；TikHub 调试 README 同步 `.dev + 300s + core/operations + 北京时间 +0800`；被批量替换误改的历史归档 Change 恢复为当时事实；RVC 项目索引按当前仓库重新生成。根 `AGENTS.md` 本轮未修改。

# 交付

- PR #65：已合并，merge commit=`0446b4a2bda3160f61a88d9ed662040f46ee2ac9`。
- corrective PR #67：已合并，最终 head=`6e84a8566d3431da15c83d02b4ae45cf8f9a498c`，merge commit=`0d7e242c0e0a8871830a22974f20aa3f5a902f7b`。
- post-merge 验证 PR #68：已关闭、未合并；12/12 正式 workflow success；验证 marker 已删除。
- 原 corrective 分支：PR #67 合并后已自动删除。
- P1 PR #66：本 Change 未操作、未混入；后续 P1 收口应以新的 `main` 共享基线为起点重新同步事实。
- 发布：本 Change 不部署生产。

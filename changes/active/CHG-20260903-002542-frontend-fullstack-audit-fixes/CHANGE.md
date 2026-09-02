---
schema: coding-change/v1
id: CHG-20260903-002542-frontend-fullstack-audit-fixes
title: 修复前端全栈接线审计发现的分页、轮询与状态一致性缺陷
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/310-frontend-fullstack-audit
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - tests
affected_paths:
  - frontend/package-lock.json
  - frontend/src/features/admin-configuration/
  - frontend/src/features/import-batches/
  - frontend/src/features/identity/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - changes/active/CHG-20260903-002542-frontend-fullstack-audit-fixes/CHANGE.md
contracts: []
data_changes: []
---

# 目标

修复 Issue #310 已确认的五类前端接线、分页、轮询与状态一致性缺陷，继续复用当前 generated client 和既有后端 Contract，不扩大 API、数据库、Runtime 或业务语义范围。

# 成功标准

- [x] 管理员词包车型关联在车型总数超过 200 时完整读取车型目录，避免 replace 保存因前端截断丢失既有关联。
- [x] 管理员配置、数据导入和辅助补采在词包超过单页 100 条时仍能完整发现启用词包。
- [x] 新建辅助补采遍历全部历史 Import Batch Cursor 页，不再只读取首批 100 条。
- [x] 声音广场已加载多页且存在活跃后台 Job 时，轮询不折叠已加载窗口、不丢失后续页选择；人工复核后的刷新同样保持当前窗口。
- [x] 当前 Principal 未读通知超过 50 条时，标记已读后的角标最终以服务端全量 `unread_count` 为准。
- [x] 已有 Analysis Scheme Draft 的名称不再表现为可编辑但无法保存；从 published/历史版本创建新草稿时仍可设置名称。
- [x] 未修改 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Runtime、采集/导入/AI/导出业务语义；`frontend/package.json` 与直接依赖版本保持不变。
- [x] 仅在既有 semver 范围内将传递依赖 `fast-uri` 从 3.1.5 更新为 3.1.7，完整 high dependency audit 恢复为 0 vulnerability。
- [x] Targeted/全量 Vitest、Browser Mock、lint、typecheck、build、依赖安全审计和 Runtime Acceptance 均已取得新鲜通过证据；最终 Ready HEAD 继续由永久 PR CI/Runtime/Completion Gate 复核。
- [x] 独立 Review 发现的函数级中文说明缺口已修复，并重新通过 lint、typecheck 和 Vitest 78/78。

# 范围

- Admin Configuration：完整车型/词包目录读取与 Scheme Draft 名称只读语义。
- Import / Supplement：完整启用词包目录与 Import Batch Cursor 候选读取。
- Identity：通知已读后服务端全量未读数同步。
- Voice Plaza：已加载 Cursor 窗口刷新、Analysis/Export Job 轮询职责拆分和复核后刷新。
- 回归测试、安全锁文件补丁与本次持久 Change 治理。

# 非目标

- 不新增或修改后端 endpoint、Pydantic HTTP Contract、OpenAPI 或 generated client。
- 不修改 PostgreSQL Schema/Migration 或历史数据。
- 不升级 Vue、TypeScript、Python、PostgreSQL、直接 npm/uv 依赖或 Runtime。
- 不修改 TikHub/LLM Provider 行为，不做无关 UI 重构或视觉重设计。

# 必须保持不变

- 继续使用 Pydantic → OpenAPI → Orval generated client 的现有 API 链路，不手写平行 API/Response Contract。
- 车型与词包分页只按真实 `offset/limit/total`；Import Batch 只按真实 Cursor 契约。
- Keyword Pack ↔ Vehicle replace 语义不变；通过完整加载候选避免截断误删。
- Analysis Scheme Update Draft Contract 不新增 `name`；已有 Draft 名称只读，新建 Draft 命名能力保留。
- 通知 mark-read 仍只作用于当前 Principal Inbox；服务端 `unread_count` 是全量最终事实。
- Voice Plaza 用户主动查询仍从第一页开始；后台状态刷新不得破坏已加载窗口。
- `frontend/package.json` 不变；依赖调整仅限 lockfile 中 `fast-uri` 安全补丁。

# 关键实现决策

- 管理员车型/词包 API wrapper 在内部按 offset/total 聚合全部页，保持现有 ListResponse 形状。
- 启用词包按 offset/total 聚合；辅助补采历史 Batch 按 Cursor 遍历并防重复 Cursor。
- 通知 mark-read 先应用 `changed_count` 退化值，再重新读取服务端通知列表，以返回的全量 `unread_count` 收敛最终状态。
- Voice Plaza 通过 `refreshLoadedWindow()` 从第一页沿 Cursor 读取到原已加载规模或数据终点，刷新内容状态并保留仍存在的选择；纯 Export Job 不触发内容列表重载，Analysis Run 才刷新内容窗口。
- Existing Scheme Draft 名称通过前端只读语义与后端 Update Contract 对齐，不扩大 Contract。
- 首次 RED 被新出现的 `fast-uri` High advisory 在测试执行前阻断，因此未伪报 RED；先用 lockfile-only 补丁恢复安全门禁，再取得有效业务 RED。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | >200 车型时完整读取候选，避免 replace 关联因截断丢失 | issues/310 | satisfied | `frontend/src/features/admin-configuration/api.ts`; `frontend/tests/frontend-audit-regressions.spec.ts` 201 车型回归 |
| R2 | >100 词包及多页历史 Batch 在相关候选中完整可发现 | issues/310 | satisfied | `frontend/src/features/admin-configuration/api.ts`; `frontend/src/features/import-batches/api.ts`; `frontend/src/features/import-batches/store.ts`; 101 词包与 Cursor 回归 |
| R3 | 声音广场多页 + 活跃 Job 轮询不折叠列表或丢选择 | issues/310 | satisfied | `frontend/src/features/voice-plaza/store.ts`; 多页 + later-page selection 回归；Browser Mock 全量通过 |
| R4 | >50 未读时已读操作后角标仍以服务端全量未读数为准 | issues/310 | satisfied | `frontend/src/features/identity/store.ts`; 80→79 回归；identity stateful server-snapshot test |
| R5 | Existing Scheme Draft 名称不再假可编辑，新建 Scheme 命名能力保留 | issues/310 | satisfied | `AdminConfigurationPage.vue`; Scheme readonly 回归；现有新建路径保持 |
| R6 | 不改变 Contract/Schema/Runtime/直接依赖/业务语义，并取得与最终 diff 风险匹配的黑盒、构建、运行时与独立 Review 证据 | issues/310 | satisfied | PR diff 仅 frontend/lock/tests/Change；Vitest 78/78；Browser Mock 46/46；Vite build；Runtime Acceptance；独立 Review Finding 已修复 |
| R7 | 恢复 High dependency audit，且不扩大依赖升级范围 | issues/310 | satisfied | `frontend/package-lock.json` 仅传递 `fast-uri 3.1.5 → 3.1.7`; `package.json` 未变；production/full high audit 均 0 vulnerability |

# Validation Matrix

| 验证层 | 判定 | Evidence / 依据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | 有效 RED 后全量 Vitest 17 files / 78 tests 全绿；直接覆盖 201 车型、101 词包、Batch Cursor、多页轮询、80→79 未读和 Scheme readonly |
| 接口 / Contract | not_applicable | 最终 diff 不修改后端 Contract、OpenAPI 或 generated client；所有新调用仍经现有 generated client，typecheck 通过；没有独立 public Contract 变更风险 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 最终 diff 无 backend/service/repository/SQL/Schema/Migration 变化，也不改变服务器事务或持久化规则；仓库 CI 风险分类器据此跳过 PostgreSQL Integration |
| 用户 / Workflow Acceptance | required | 永久 Playwright Browser Mock Acceptance 46/46；页面/交互广覆盖由 Browser 层承担，本次边界另有直接 Vitest 回归 |
| 跨组件 Golden Path | not_applicable | 最终实现不改前后端 Contract、服务器路由、数据库、Worker 或跨组件接线；仓库 CI 风险分类器据此跳过 Real Full-stack Golden Path，不用 Mock 冒充真实链路 |
| 外部依赖 Probe | not_applicable | 不修改 TikHub/LLM Provider API、字段、分页或当前供应方能力，不需要外部付费/网络 Probe |
| Build / Package / Runtime | required | npm production/full high audit 0 vulnerability；lint 0 warning；typecheck 通过；Vite build 成功；Runtime Acceptance canonical Compose、持久化/恢复、Windows overlay 通过 |
| Docs / Governance / Other | required | Issue #310；本 Change；Completion Audit；独立两阶段 Review；PR 永久 CI/Runtime/Completion Gate；merge 后 main fresh CI、Change archive、Issue closure、branch cleanup 由 Post-Merge Finalization 执行 |

# Completion Audit

- [x] upstream_re_read：重新读取更新后的 Issue #310、项目 `AGENTS.md`、Blueprint、当前前端实现、generated client 使用边界、测试和永久 CI；没有以本 Change 自身反推需求。
- [x] change_coverage：从 Issue #310 独立重建五类缺陷、必须保持不变项和安全门禁前置，R1-R7 均有实现与证据，没有 requirement omission。
- [x] reverse_audit：复核“页面/Store → generated client → 既有后端 Contract”方向；最终 diff 不改变服务器边界；所有本次确认的固定 limit 候选读取已按真实 offset/total 或 Cursor 改为完整分页，后台 Job 刷新与用户主动查询职责分离。
- [x] unresolved_cleared：Traceability 无 `not_satisfied`；required 验证层已有匹配证据；PostgreSQL/Real Full-stack/Provider/Contract 层均基于最终 diff 和仓库风险分类有明确 `not_applicable` 依据；已知 Review Finding 已修复并 re-review。

# 验证证据

## RED

- 初始新增 6 个边界回归后，第一次 CI 因新出现的 `fast-uri 3.1.5` High advisory 在测试执行前中止，因此不计为业务 RED。
- lockfile-only 安全补丁后重新执行：既有 72 个测试继续通过，新加 6 个回归全部因旧行为失败，形成有效 RED。

## GREEN

- 本地/runner Frontend Green：npm ci；production/full high audit 0 vulnerability；ESLint 0 warning；typecheck 通过；Vitest 17 files / 78 tests 全部通过。
- 永久 PR CI（生产修复 HEAD）：Vitest 78/78；Vite build 成功；Playwright Browser Mock 46/46；CI Gate success。
- Runtime Acceptance：canonical Compose topology/startup/security/persistence/recovery、repository-relative host-root smoke、Windows overlay storage/startup/permissions/host visibility/restart persistence 均 success。
- 独立 Review 发现“部分修改的内部/helper 函数缺中文函数级职责说明”，修复后重新运行 lint、typecheck、Vitest 78/78 全部成功。
- 当前 `ready_for_review` HEAD 仍需由永久 PR CI/Runtime/Completion Gate 取得 final-head fresh 结果；该结果属于 PR merge 门禁，不通过则不得合并。

# Review

## Review A1：上游要求 → Change

- PASS：Issue #310 已重新读取并按当前风险验证规则校正；五类缺陷、不变项、黑盒/构建/运行时证据要求均已映射。
- PASS：没有把 PostgreSQL/Real Full-stack 机械当成所有前端-only变更的必跑层；`not_applicable` 有最终 diff 与仓库风险分类器双重依据。

## Review A2：Change → 实现 / 测试 / 文档

- PASS：R1-R7 均有对应实现和可观察回归；public Contract/Schema/Runtime/直接依赖不变。
- PASS：Browser Mock、build、runtime 与 unit/component 证据没有互相冒充。

## Code Quality Review

- 原 Finding：修改的 `markRead()`、`loadCreationOptions()`、Voice Plaza 人工复核 helper 缺少当前项目要求的中文函数级说明。
- 处理：已补齐职责说明并重新 Green；未降低 lint/test 标准。
- 当前结论：NO_FINDINGS_WITHIN_SCOPE；等待最终 Ready HEAD 永久门禁确认。

# Post-Merge Finalization（合并后执行）

- [ ] 确认真实 merge commit 与 main HEAD。
- [ ] 取得 merge 后 main fresh CI/Runtime/适用 Completion Gate。
- [ ] 将本 Change 更新为 `done` 并移动到 `changes/archive/2026-09/`，通过独立 governance PR 合入。
- [ ] 重新读取 Issue #310 执行 Closure Audit，并以 `completed` 关闭。
- [ ] 清理当前任务已合并分支和归档分支。

# 文档影响

- Blueprint、README、API/Schema 文档无需同步：本次没有改变长期架构、操作方式、公开 Contract、Schema 或部署方式。
- 持久事实变化仅为缺陷修复行为、回归证据和依赖安全锁文件，分别由测试、Issue/Change 与 lockfile 承载。

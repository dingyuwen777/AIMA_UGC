---
schema: rvc-change/v1
id: CHG-20260824-excel-import-submit-state
title: 修复 Excel 导入按钮假忙碌与失败反馈
level: L2
status: done
owner: aima
branch: docs/archive-excel-import-submit-state
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on:
  - CHG-20260824-multi-keyword-pack-entrypoints
affected_areas:
  - frontend
  - docs
affected_paths:
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportUploadDialog.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue
  - frontend/tests/import-batches-store.spec.ts
  - frontend/e2e/excel-import-submit-state.spec.ts
  - docs/blueprint/04_后端任务API与前端.md
contracts: []
data_changes: []
---

# 目标

修复采集运行中心 Excel 导入弹窗把“不可提交”错误表现成“系统正在忙”的问题，并让真实上传中的状态与请求失败结果对用户可见且可恢复。

# 成功标准

- [x] 未选择文件、未选择关键词包、词包加载中或无可用词包时，“开始导入”不可提交，鼠标使用 `not-allowed`，不显示忙碌转圈。
- [x] 只有真实 Excel 创建请求进行中时，按钮才表达 busy 状态并显示“正在创建…”；请求成功或失败后 busy 状态都会复位。
- [x] Excel 创建请求失败时，错误直接显示在导入弹窗内，并保留统一错误 Contract 的 `request_id`。
- [x] 现有 Excel multipart、Keyword Pack 多选、Import Job、后端 Contract、Worker 和数据库语义保持不变。

# 范围与非目标

范围：Excel 导入弹窗提交资格、disabled/busy 视觉与可访问语义、弹窗内错误反馈、Store 失败收尾回归测试、Browser Mock Acceptance，以及完成审计发现的 Excel Import multipart Blueprint 漂移同步。

非目标：不修改 Excel 上传 API、OpenAPI/generated client、后端 XLSX 校验、Artifact、Import Job、Worker、数据库、去重/过滤逻辑；不新增上传进度、请求超时或取消上传；不修改 TikHub 补采。

# 必须保持不变

- `POST /api/v1/import-batches` 继续提交 `file + keyword_pack_ids[]`。
- 多关键词包并集 OR 语义不变。
- Store 继续复用现有 `uploadImportBatch()`，不建立第二套请求实现。
- 不升级 Vue、Pinia、Playwright、Vitest 或其他依赖。

# 关键决策

1. 普通 disabled 与真实 busy 分离：未满足提交前置条件使用 `not-allowed`；只有 `uploading=true` 的实际请求阶段使用 `aria-busy=true`、`正在创建…` 与 `cursor: progress`。
2. 弹窗内以单一 `canSubmit` 统一约束：文件存在、至少一个关键词包、词包加载完成、当前不在上传中。
3. 保留 Store 既有 `try/finally`；生产 Store 不修改，只用回归测试证明失败后 `uploading=false`。
4. 请求错误复用既有 `store.error` 并在弹窗内显示，不建立第二错误状态源。
5. Blueprint 仅同步现有机器事实：一个 `file` + 1—20 个不重复 `keyword_pack_ids`，不借机改变接口。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 未实际导入时悬停“开始导入”不能表现为一直转圈 | user:2026-08-24-excel-import-spinner | satisfied | `ImportUploadDialog.vue` 以 `canSubmit` 控制未就绪 disabled，并将普通 disabled cursor 改为 `not-allowed`；Final Ready CI 的 `excel-import-submit-state.spec.ts` 通过。 |
| R2 | 点击开始导入后的 busy 状态只对应真实请求，且请求结束后可恢复 | user:2026-08-24-excel-import-spinner | satisfied | 真实请求期间 `aria-busy=true`/`正在创建…`/`cursor: progress`；Store 回归证明失败后 `uploading=false`；Final Ready 38/38 Vitest、17/17 Playwright 通过。 |
| R3 | 错误不能被弹窗遮罩隐藏 | frontend/README.md | satisfied | `CollectionRuntimePage.vue` 将现有 `store.error` 传入弹窗，弹窗以 `role=alert` 展示；503 Browser Mock 验证 detail 与 `request_id`。 |
| R4 | 不改变 Excel Import HTTP/Job/Worker/数据库业务链 | docs/blueprint/04_后端任务API与前端.md | satisfied | Implementation PR #199 无 backend、Migration、Contract、generated client、依赖或锁文件变更；Final Ready Contract、Stage 3A Database、Stage 8F Full-stack 全绿。 |
| R5 | Blueprint 与当前 Excel Import multipart 机器事实一致 | AGENTS.md | satisfied | `bootstrap/api.py` 当前要求一个 `file` + 1—20 个不重复 `keyword_pack_ids`；Blueprint 已同步该现状，Final Ready docs check 通过。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | Final Ready CI `32694494577` / Stage 1 `97333982368`：17/17 Playwright；新增 2 个 Excel 状态用例覆盖未就绪非 busy、真实 POST busy、503 后恢复与错误可见。 |
| Backend/API/PostgreSQL Integration | not_applicable | 无服务器规则/数据库/Job/Worker 改动；额外回归的 Stage 3A Database 与 Import HTTP/Worker integration 全绿。 |
| Contract / Generated Client | not_applicable | 无 Contract/generated 变更；Final Ready OpenAPI/Orval 重新生成、generated diff 与 compatibility 通过。 |
| Real Full-stack Golden Path | not_applicable | 用户可见缺陷为前端状态表达，未改变前后端接线；额外回归 Stage 8F Full-stack `32694494592` 成功。 |
| Real Provider Probe | not_applicable | 与 TikHub/LLM Provider 无关。 |
| Docs / Governance / Other | required | Final Ready Completion Gate `32694494542`、CI docs/Secret/architecture checks、两阶段 Review 均通过。 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取用户要求、`AGENTS.md`、Skill、`frontend/README.md`、Blueprint 04、FastAPI Import route 与 Import Service。
- [x] change_coverage：覆盖“未导入悬停也转圈”和“点击后一直转圈”的提交资格、真实 busy、失败收尾与错误可见性。
- [x] reverse_audit：前端资格与后端 `file + 1—20 keyword_pack_ids` 能力对齐；202 后 Worker 异步继续但按钮 busy 只绑定 HTTP 创建请求；失败保留 `request_id`。
- [x] unresolved_cleared：R1—R5 全部 satisfied；required Validation Matrix 均有证据。

# TDD 与验证证据

## Red

CI run `32693502524` / Stage 1 job `97331290030`：修正测试自身定位器后，15 个既有 E2E 通过、2 个新增 E2E 因真实产品行为失败：未选择文件时按钮实际仍 enabled；真实上传请求期间缺少 `aria-busy=true`。

## Final Ready

Final Ready HEAD：`41a9ac9ddb14e421a58b70b7dbbc579e0c59ef21`。

11 个永久 workflow 全部 success：

- Change Completion Gate `32694494542`
- CI `32694494577`
- Windows Docker Desktop Compose Compatibility `32694494533`
- Internal V1-A `32694494519`
- Stage 8F Full-stack `32694494592`
- Local Dev Bootstrap `32694494557`
- Stage 6 Xiaohongshu `32694494576`
- Stage 7 Plan Occurrence `32694494543`
- Stage 7 Keyword Packs `32694494560`
- Stage 7 Scheduler Runtime `32694494594`
- Stage 7 Provider Config `32694494613`

Final Ready CI Stage 1 job `97333982368`：Ruff format 471 files、Ruff lint、MyPy 237 source files、backend unit 615 passed、contracts 74 passed、API 30 passed；frontend lint/typecheck、38/38 Vitest、Vite 8.2.1 build、17/17 Playwright 全部通过；npm audit production/全量均 0 vulnerabilities；OpenAPI/Orval、generated drift/compatibility、architecture/table ownership/Secret/docs、Wheel build/import 全部通过。

# Review

## Requirement Review

通过。实现逐项覆盖用户两类症状，且没有将前端状态 Bug 扩大为 API、数据库、Worker 或 Provider 改造。完成审计发现的 Blueprint 漂移也只做现状同步。

## Code Quality / Compatibility Review

通过，无未解决 Serious/Important finding。最终 PR diff 只有 2 个生产 Vue 文件、2 个测试文件、1 个 Blueprint 和 Change；生产 Store、后端、Contract、Migration、generated client、依赖与锁文件均未改。PR review threads/comments 均无未解决项。

# 文档影响

- 已同步 `docs/blueprint/04_后端任务API与前端.md` 的 Excel Import multipart 现状。
- `frontend/README.md` 无需修改：Page/Component 负责 Loading/Error、Store 管理共享状态的职责边界未变化。

# 兼容、部署与回滚

- 无 Schema/Migration、API Contract、依赖或运行时版本变化。
- 多词包 OR、Import Job/Worker、数据库、去重/入库逻辑不变。
- 未执行生产部署。
- 回滚只需回退 Implementation PR #199 的前端状态展示、回归测试与 Blueprint 同步，不涉及数据迁移。

# Git / 交付

- Implementation branch: `fix/excel-import-submit-state`
- Implementation PR: #199
- Final Ready HEAD: `41a9ac9ddb14e421a58b70b7dbbc579e0c59ef21`
- Implementation merge commit: `cb4751496fa8873b39e9a22af4d64d391b102659`
- Final Ready PR synthetic merge commit: `1e702311e608270f4204d237de2656405f84103d`
- GitHub compare `1e702311...` → `cb475149...` 返回 `files: []`，证明实际 merge commit 与通过 11 个永久 workflow 的 PR merge tree 无文件差异。
- Archive branch: `docs/archive-excel-import-submit-state`
- PR #199 已按正常 merge 合入 `main`；本文件通过独立归档 PR 从 `changes/active/` 移入 `changes/archive/2026-08/`，归档 PR 自身仍需通过现有永久 CI 后正常合并。

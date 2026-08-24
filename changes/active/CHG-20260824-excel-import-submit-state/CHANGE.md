---
schema: rvc-change/v1
id: CHG-20260824-excel-import-submit-state
title: 修复 Excel 导入按钮假忙碌与失败反馈
level: L2
status: ready_for_review
owner: aima
branch: fix/excel-import-submit-state
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

# 范围

- Excel 导入弹窗的提交资格、disabled/busy 视觉语义和可访问状态。
- 页面向弹窗传递现有 Store 错误。
- Store 上传失败后的 busy 复位回归测试。
- Browser Mock Acceptance 覆盖未就绪、真实提交中和失败后的用户可见状态。
- 将 Blueprint 中已经落后于当前机器实现的 Excel Import multipart 描述同步为现状。

# 非目标

- 不修改 Excel 上传 API、OpenAPI/generated client 或 multipart 字段。
- 不修改后端 XLSX 校验、Artifact、Import Job、Worker、数据库或去重/过滤逻辑。
- 不新增上传进度百分比、请求超时策略或取消上传机制。
- 不修改 TikHub 补采交互。

# 必须保持不变

- `POST /api/v1/import-batches` 继续提交 `file + keyword_pack_ids[]`。
- 多关键词包并集 OR 语义不变。
- Store 继续通过现有 `uploadImportBatch()` 调 generated client，不建立第二套请求实现。
- 不升级 Vue、Pinia、Playwright、Vitest 或其他依赖。

# 关键决策

1. 根因分为“状态语义”和“错误反馈”两层处理：disabled 不再统一使用 `cursor: wait`；只有 `uploading=true` 的真实请求阶段才表达 busy。
2. 提交资格在弹窗内用单一 `canSubmit` 计算，要求文件、至少一个关键词包、词包已加载且当前不在上传中；不把未满足前置条件伪装成运行中。
3. 保留 Store 现有 `try/finally` 作为 busy 状态收尾机制，不改生产 Store；新增回归测试证明失败路径恢复 `uploading=false`。
4. 请求错误复用现有 `store.error`，只增加弹窗内展示，不建立第二套错误状态源。
5. 完成审计发现 Blueprint 仍写“只接受一个 file”，而当前 FastAPI 已要求一个 `file` + 1—20 个不重复 `keyword_pack_ids`；只同步该现状描述，不借机修改接口或业务。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 未实际导入时悬停“开始导入”不能表现为一直转圈 | user:2026-08-24-excel-import-spinner | satisfied | `ImportUploadDialog.vue` 用 `canSubmit` 控制未就绪 disabled，并将普通 disabled cursor 改为 `not-allowed`；CI run 32694005239 / Stage 1 job 97332660320 中 `excel-import-submit-state.spec.ts` 通过。 |
| R2 | 点击开始导入后的 busy 状态只对应真实请求，且请求结束后可恢复 | user:2026-08-24-excel-import-spinner | satisfied | `ImportUploadDialog.vue` 仅以 `uploading` 设置 `aria-busy=true`/`正在创建…`/`cursor: progress`；`import-batches-store.spec.ts` 证明失败后 `uploading=false`；同一 Green job 中 38/38 Vitest 与 17/17 Playwright 通过。 |
| R3 | 前端组件应正确表达 Loading / Error / Empty / Data，错误不能被弹窗遮罩隐藏 | frontend/README.md | satisfied | `CollectionRuntimePage.vue` 将现有 `store.error` 传入弹窗，`ImportUploadDialog.vue` 以 `role=alert` 显示；Browser Mock 503 用例验证 detail 与 `request_id` 均可见。 |
| R4 | 不改变 Excel Import HTTP/Job/Worker/数据库业务链 | docs/blueprint/04_后端任务API与前端.md | satisfied | PR #199 diff 无 backend、Migration、Contract、generated client、依赖或锁文件变更；CI run 32694005239 的 Contract 生成/漂移/兼容检查、Stage 3A Database 与 Stage 8F Full-stack Acceptance 均通过。 |
| R5 | 正式 Blueprint 必须与当前 Excel Import multipart 机器事实一致 | AGENTS.md | satisfied | `backend/src/aima_ugc/bootstrap/api.py` 当前要求一个 `file` + 1—20 个不重复 `keyword_pack_ids`；`docs/blueprint/04_后端任务API与前端.md` 已只同步这一现状。c8597ed8 对应 CI run 32694301543 的 Backend and repository checks 已通过文档检查。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | CI run 32694005239 / job 97332660320：17/17 Playwright 通过；新增 2 个用例分别覆盖“未选择文件/词包时 disabled 非 busy”和“真实 POST 期间 busy、503 后恢复并在弹窗显示 detail + request_id”。 |
| Backend/API/PostgreSQL Integration | not_applicable | 本次未修改服务器规则、数据库、Job/Worker 或持久化；作为额外回归，run 32694005239 的 Stage 3A Database 全绿，包含 Stage 8B Import HTTP/Worker integration。 |
| Contract / Generated Client | not_applicable | 本次未修改 Pydantic/OpenAPI/generated client；作为额外回归，run 32694005239 的 OpenAPI/Orval 重新生成、`git diff --exit-code` 与兼容检查通过。 |
| Real Full-stack Golden Path | not_applicable | 用户可见缺陷是前端状态表达，未改变真实前后端接线；额外回归的 Stage 8F Full-stack Acceptance run 32694301482 通过。 |
| Real Provider Probe | not_applicable | 本次不涉及 TikHub 或任何外部 Provider 当前事实。 |
| Docs / Governance / Other | required | c8597ed8 的 CI run 32694301543 已通过 Backend and repository checks（含文档入口/链接检查）；PR diff 已人工复核为 2 个生产 Vue 文件、2 个测试文件、1 个 Blueprint 和本 Change，无无关业务改动。 |

# Completion Audit

- [x] upstream_re_read：重新读取本轮用户要求、`AGENTS.md`、`frontend/README.md`、`docs/blueprint/04_后端任务API与前端.md`、当前 FastAPI Import route 和 Import Service，从上游事实独立重建完成定义。
- [x] change_coverage：用户的“未导入仅悬停也转圈”和“点击后一直转圈”均拆解为提交资格、真实 busy、失败收尾与错误可见性；没有把当前 Change 自身当作需求全集。
- [x] reverse_audit：后端真实能力要求 `file + 1—20 keyword_pack_ids`，前端 `canSubmit` 与之对齐；HTTP 创建请求结束后 busy 结束，202 后由既有 Job/Worker 异步继续，前端不把 Worker 生命周期伪装为按钮加载；失败保留 `request_id`；Provider 边界不适用。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied` 或无依据延期项；Validation Matrix 的 required/not_applicable 已按实际边界复核。

# 任务

- [x] 调查当前实现、PR #185 相关改动和上游事实源。
- [x] 先建立 Browser 失败用例并取得因产品行为失败的 Red 证据。
- [x] 建立并维护 Validation Matrix。
- [x] 完成最小前端实现，不修改后端 Contract/Worker/数据库。
- [x] 增加 Store 失败收尾回归测试，并修正测试自身 mock 问题，不改生产逻辑规避测试失败。
- [x] 同步完成审计发现的 Excel Import multipart Blueprint 漂移。
- [x] 取得 Green、构建、Contract、数据库和永久 workflow 新鲜证据。
- [x] 完成 Requirement Traceability、Completion Audit 和两阶段人工差异复核。

# 验证

## Red

- CI run `32693502524` / Stage 1 job `97331290030`：修正测试定位器后，15 个既有 E2E 通过、2 个新增 E2E 因真实产品行为失败：
  - 未选择文件时“开始导入”实际仍为 enabled；
  - 真实上传请求进行中按钮缺少 `aria-busy=true`。
- 更早一次第二用例失败包含测试定位器随按钮文案变化而失效的问题；该测试缺陷先被修正，再使用上述 run 作为有效 Red 证据。

## Green

- CI run `32694005239` / Stage 1 job `97332660320`：
  - `npm --prefix frontend run lint`：退出成功；
  - `npm --prefix frontend run typecheck`：TS7 + Vue typecheck 退出成功；
  - `npm --prefix frontend run test -- --run`：9 个 Test Files、38/38 tests 通过；
  - `npm --prefix frontend run build`：Vite 8.2.1，107 modules transformed，构建成功；
  - `npm --prefix frontend run test:e2e`：17/17 Playwright 通过，其中新增 Excel 状态用例 2/2 通过；
  - `npm audit`（production 与全量）：0 vulnerabilities；
  - OpenAPI/Orval 生成、generated diff 与 Contract compatibility：通过；
  - Ruff format 471 files、Ruff lint、MyPy 237 source files：通过；
  - backend unit 615 passed（1 个既有 zipfile warning）、contracts 74 passed、API 30 passed（1 个既有 Starlette/httpx deprecation warning）；
  - architecture/table ownership/Secret/docs checks 与 Wheel build/import：通过。
- 同一 `e0fdb155` HEAD 的永久 workflows：CI、Stage 6、Stage 7 Keyword Packs/Scheduler/Plan Occurrence/Provider Config、Stage 8F Full-stack、Local Dev Bootstrap、Windows Docker Desktop Compose、Internal V1-A 均成功。
- Blueprint 同步提交 `c8597ed8` 后，CI run `32694301543` 已完成并通过 Backend and repository checks（包含 docs check）；Stage 6、Stage 7、Stage 8F、Local Dev、Windows Compose 等对应永久 workflow 也已成功。

# 文档影响

- `docs/blueprint/04_后端任务API与前端.md`：完成审计发现其 Excel Import 段落仍停留在旧的“multipart 只有 file”描述；已按当前 `bootstrap/api.py` 与 `import_http.py` 同步为一个 `file` + 1—20 个不重复 `keyword_pack_ids`，并说明词包快照与异步 Worker 语义。
- `frontend/README.md`：无需修改。其 Page/Component 负责 Loading/Error、Store 负责共享 loading/error 的职责定义没有变化，本次实现正沿用该边界。

# 交付

- Branch：`fix/excel-import-submit-state`。
- PR：#199，当前为 Draft；只有 Change Completion Gate 与永久 CI 满足仓库门禁后才转换为 Ready。
- 关键实现/验证 HEAD：`e0fdb155ec4ea558cb79712ea402516654ffa0a3`；Blueprint 同步 HEAD：`c8597ed8c4874aa324c3dd336b379598d11b1dbf`。
- Migration：无。
- 依赖：无新增、无升级、无降级。
- 部署：未执行生产部署；本次只完成代码修复与仓库集成。
- 回滚：若需回滚，仅回退 PR #199 的前端状态展示、回归测试与 Blueprint 同步，不涉及数据库或数据迁移。

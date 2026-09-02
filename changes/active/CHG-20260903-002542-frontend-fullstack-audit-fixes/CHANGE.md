---
schema: coding-change/v1
id: CHG-20260903-002542-frontend-fullstack-audit-fixes
title: 修复前端全栈接线审计发现的分页、轮询与状态一致性缺陷
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/310-frontend-fullstack-audit
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - full-stack
  - tests
affected_paths:
  - frontend/package-lock.json
  - frontend/src/features/admin-configuration/
  - frontend/src/features/import-batches/
  - frontend/src/features/identity/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - changes/active/CHG-20260903-002542-frontend-fullstack-audit-fixes/CHANGE.md
contracts: []
data_changes: []
---

# 目标

系统修复 Issue #310 中由前端全栈接线审计确认的分页、轮询与状态一致性缺陷，使所有当前已实现页面继续使用真实后端 Contract，并在大目录、长通知队列、Cursor 多页与后台任务同时存在时保持正确行为。

# 成功标准

- [ ] 管理员词包车型关联在车型总数超过 200 时仍完整读取目录，保存 replace 关联不会因未加载车型而丢失既有关联。
- [ ] 管理员配置、数据导入和辅助补采所需词包在超过单页 100 条时仍可完整发现。
- [ ] 新建辅助补采可遍历全部历史 Import Batch Cursor 页，不再只看到首批 100 条。
- [ ] 声音广场已加载多页且存在活跃 Analysis/Export Job 时，自动轮询不折叠已加载窗口、不丢失后续页选择；人工复核后的数据刷新也保持当前已加载窗口。
- [ ] 当前 Principal 未读通知超过 50 条时，标记已读后的角标继续以服务端全量 unread_count 为准。
- [ ] 已有 Analysis Scheme Draft 的名称不再表现为可编辑但无法保存；基于 published/历史版本新建草稿时仍可设置新 Scheme 名称。
- [ ] 不修改 HTTP Contract、OpenAPI/generated client、数据库 Schema/Migration、Runtime、采集/导入/AI/导出业务语义；直接依赖和框架版本保持不变。
- [ ] 恢复现有前端安全门禁：仅将受 2026-08-23 High advisories 影响的传递依赖 `fast-uri` 从 3.1.5 更新到当前既有 semver 约束解析出的安全 v3 补丁版，完整 `npm audit --audit-level=high` 为 0。
- [ ] Targeted 单元、Browser Mock、Backend/API/PostgreSQL、Real Full-stack Golden Path、lint/typecheck/build 与仓库 CI/Runtime 均取得新鲜通过证据。

# 范围

- 修复 Admin Configuration 的完整车型/词包目录读取与 Scheme 名称编辑语义。
- 修复 Collection Runtime / Data Import / TikHub Supplement 的完整词包和 Import Batch 候选读取。
- 修复 Identity Store 的通知已读后全量未读计数同步。
- 修复 Voice Plaza 的 Cursor 已加载窗口刷新、后台 Job 轮询和复核后刷新。
- 增加直接回归、Browser Mock 与适当的真实 full-stack 验收覆盖。
- 处理本次新鲜 CI 在执行 RED 测试前暴露的 `fast-uri <=3.1.5` High 安全门禁阻塞；仅允许 lockfile 内传递补丁更新。

# 非目标

- 不新增或修改后端 endpoint。
- 不改变 Pydantic HTTP Contract、OpenAPI 或 generated client。
- 不修改 PostgreSQL Schema/Migration 或历史数据。
- 不升级 Vue、TypeScript、Python、PostgreSQL、任何直接 npm/uv 依赖或 Runtime；`fast-uri` 的传递补丁更新是恢复已有 High audit 门禁的唯一例外。
- 不修改 TikHub Provider 行为，不做无关 UI 重构或视觉重设计。

# 必须保持不变

- 继续使用 Pydantic → OpenAPI → Orval generated client 的唯一 API 链路，页面不得手写平行 API/Response Contract。
- 车型与词包分页只按后端真实 `offset/limit/total` 契约；Import Batch 只按真实 Cursor 契约，不虚构页码。
- Keyword Pack ↔ Vehicle replace 语义不改变；修复必须通过完整读取现有集合避免前端截断造成误删。
- Analysis Scheme Update Draft Contract 不新增 `name`；已有 Draft 名称按当前后端语义只读，published/历史版本创建新草稿的名称输入行为保持。
- 通知 mark-read 仍只允许当前 Principal 自己的 Inbox；服务端 `unread_count` 是全量事实。
- Voice Plaza 手工查询仍以第一页作为新查询起点；后台刷新不得破坏已经加载的 Cursor 窗口。
- `frontend/package.json` 与所有直接依赖版本保持不变；只接受 npm 在现有 `fast-uri` v3 semver 范围内生成的 lockfile 补丁，且补丁后完整 high audit 必须为 0。

# 关键决策

- 不通过扩大后端 Contract 修复前端缺陷：车型/词包完整读取复用现有 offset/total，Import Batch 复用现有 Cursor。
- 管理员目录 API wrapper 返回与现有调用方相同的 ListResponse，只把内部读取从单页改为完整分页，避免页面层重复拼装。
- Import Batch 辅助补采候选在 Store 内按 Cursor 遍历所有页并过滤合法 succeeded Batch；显式 selectedBatchId 继续保留详情回退路径。
- 通知标记已读先应用 changed_count 的本地退化值，再重新读取通知列表，以服务端全量 `unread_count` 作为最终事实；重读失败时保留安全退化状态和错误反馈。
- Voice Plaza 新增“刷新当前已加载 Cursor 窗口”能力：从第一页重新获取并沿 Cursor 读取到原已加载规模或数据终点，更新内容状态同时保留仍存在的后续页选择；用户主动新查询继续使用现有第一页 `refresh()`。
- 后台轮询只有活跃 Analysis Run 才需要刷新内容窗口；纯 Export Job 只刷新导出与 Run 状态，避免无意义内容查询。
- 首次 RED CI 被 2026-08-23 新发布的 `fast-uri` High advisories 阻断，未执行任何回归测试，因此不计为 RED；使用临时分支限定 runner 让 npm 在原 `^3.0.1` 约束下更新 lockfile，实际解析 `fast-uri 3.1.7`，完整 audit 返回 0，临时 workflow 已删除。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | >200 车型时管理员关联保存不丢既有关联 | https://github.com/dingyuwen777/AIMA_UGC/issues/310 | not_satisfied | 待实现与 201 车型回归 |
| R2 | >100 词包及多页历史 Batch 在相关候选中完整可发现 | https://github.com/dingyuwen777/AIMA_UGC/issues/310 | not_satisfied | 待 offset/Cursor 回归 |
| R3 | 声音广场多页 + 活跃 Job 轮询不折叠列表或丢选择 | https://github.com/dingyuwen777/AIMA_UGC/issues/310 | not_satisfied | 待 Cursor 窗口回归与 Browser Mock |
| R4 | >50 未读时已读操作后角标仍等于数据库全量未读数 | https://github.com/dingyuwen777/AIMA_UGC/issues/310 | not_satisfied | 待 80→79 回归与后端现有 Contract 复核 |
| R5 | 已有 Scheme Draft 名称不再假可编辑，新建 Scheme 名称能力保持 | https://github.com/dingyuwen777/AIMA_UGC/issues/310 | not_satisfied | 待 UI/黑盒回归 |
| R6 | 不修改 Contract/Schema/直接依赖/业务语义，并完成系统黑盒与真实全栈验证后合并 main | https://github.com/dingyuwen777/AIMA_UGC/issues/310 | not_satisfied | 待 diff、CI、Review、PR/main fresh 证据 |
| R7 | 恢复现有 High dependency audit 门禁且不扩大依赖升级范围 | 2026-09-03 PR CI #3708 + GitHub fast-uri advisories | satisfied | `frontend/package-lock.json` 仅传递 `fast-uri 3.1.5 → 3.1.7`；临时 runner `npm audit --audit-level=high` = 0；直接 manifest 未变 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 计划证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Vitest：201 车型、101 词包、Batch Cursor、多页轮询、80→79 未读、Scheme 只读语义 |
| 接口 / Contract | required | generated client/后端 Contract 新鲜复核；最终 diff 不修改 contracts/openapi/generated |
| 集成 / Persistence / Runtime Dependency | required | 运行现有 Backend/API/PostgreSQL Integration，确认 replace、通知全量 COUNT、Cursor 等服务器语义未回归 |
| 用户 / Workflow Acceptance | required | Playwright Browser Mock 覆盖多页目录/通知/声音广场轮询及 Scheme 交互 |
| 跨组件 Golden Path | required | Real Full-stack：至少执行 Admin/Vehicle/Pack/Import/Voice/Export/Notification/Scheme 现有关键路径，并补本次必要断言 |
| 外部依赖 Probe | not_applicable | 本次不修改 TikHub/LLM Provider API、字段映射或真实供应方能力，不需要产生外部费用的探测 |
| Build / Package / Runtime | required | frontend npm high audit、lint、typecheck、Vitest、Vite build、Playwright；仓库 Runtime Acceptance |
| Docs / Governance / Other | required | Issue #310、Change、Requirement Traceability、Completion Audit、Review、PR、main fresh CI/Runtime、归档与 Issue 关闭 |

# 完成审计

- [ ] upstream_re_read：最终 GREEN 后重新读取 Issue #310、相关前端实现、后端 Contract/Repository、测试与 CI。
- [ ] change_coverage：逐项从 Issue #310 重建 R1-R7，确认没有遗漏已审计问题或安全门禁前置。
- [ ] reverse_audit：执行“前端动作 → generated API → 后端实现”和“后端能力 → 前端入口”双向复核，并检查所有有限目录的分页行为。
- [ ] unresolved_cleared：所有 not_satisfied 清零，所有 required Validation 层有新鲜证据，未验证项明确处理。

# 任务

- [x] 冻结当前 main、读取项目规则与 canonical Agent_Skills Source Mode 规则。
- [x] 建立 Issue #310 与 L2 任务计划/验证矩阵。
- [x] 编写可执行 RED 回归覆盖已确认缺陷。
- [x] 处理阻断 RED 执行的新鲜传递依赖 High advisory；没有把安全审计失败伪装成业务 RED。
- [ ] 验证 RED 由目标旧行为导致，而非测试环境或 Mock 错误。
- [ ] 完成最小实现，不修改公共 Contract/Schema/直接依赖。
- [ ] 运行 targeted 单元和静态检查并修复回归。
- [ ] 增加并运行 Browser Mock 黑盒功能测试。
- [ ] 运行 Backend/API/PostgreSQL 与 Real Full-stack Golden Path。
- [ ] 完成 Completion Audit、独立两阶段 Review 与 PR 门禁。
- [ ] 合并 main，运行 main fresh CI/Runtime/Completion，归档 Change、关闭 Issue、清理已合并分支。

# 验证

## RED 计划

- `frontend/tests/frontend-audit-regressions.spec.ts`：直接锁定全部已确认边界。
- 首次 PR CI 在 `npm ci` 后被新发布的 `fast-uri <=3.1.5` High advisory 阻断，生产依赖 audit 为 0、完整 audit 为 1 high，测试未执行，因此不是有效 RED。
- `fast-uri` lockfile 补丁完成后重新运行 CI；必须观察到新增回归因当前旧实现失败，才作为正式 RED。

## GREEN 计划

- Targeted Vitest：新回归 + identity/import/voice/admin 相关既有测试。
- Frontend 全量：high audit、lint、typecheck、Vitest、build。
- Browser Mock：现有全量 + 本次新增用户工作流。
- Backend/API/PostgreSQL：仓库永久集成层。
- Real Full-stack Golden Path：现有 `frontend/e2e-fullstack`，并补本次需要的真实页面断言。
- GitHub Actions：PR head 和 main fresh 的 CI、Runtime Acceptance、Change Completion Gate。

## 新鲜证据

- 安全前置：原 lock `fast-uri 3.1.5`；PR CI #3708 在完整 `npm audit --audit-level=high` 报 1 high 后停止，测试未执行。
- 临时 lock runner：`npm update fast-uri --package-lock-only --ignore-scripts` 在原 semver 下解析 3.1.7；随后完整 `npm audit --audit-level=high` 输出 `found 0 vulnerabilities`，仅 `frontend/package-lock.json` 有 diff 后由 bot 提交 `4a715a4c4283d1d74055651d2d930a04e36b7d37`。
- RED / GREEN / PR / main fresh：待后续执行后填写。

# 文档影响

- 产品架构、HTTP Contract、Schema 和部署语义预期不变，因此不计划修改 Blueprint/Appendix；若实现调查发现描述性文档与修复后的真实行为冲突，再做最小同步。
- 本 Change、Issue #310、测试和最终 PR 承担本次缺陷修复的需求与验证追溯。
- 传递依赖安全补丁仅记录在本 Change 和锁文件，不改变用户可见产品/部署文档。

# 交付

- 分支：`fix/310-frontend-fullstack-audit`
- Issue：#310
- Commit：RED `c74da04f6c637629388ebb03505c7dd45c6402b8`；安全 lock 补丁 `4a715a4c4283d1d74055651d2d930a04e36b7d37`
- PR：#311（Draft / RED 阶段）
- 合并：待验证与 Review 后执行
- 发布：不适用；本任务只合并主分支，不触发 Release/生产部署

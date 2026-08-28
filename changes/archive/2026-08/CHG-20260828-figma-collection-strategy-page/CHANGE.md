---
schema: rvc-change/v1
id: "CHG-20260828-figma-collection-strategy-page"
title: "采集策略正式 Figma 页面实现"
level: L2
status: done
owner: "chatgpt"
branch: "feature/figma-collection-strategy-page"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "frontend"
affected_paths:
  - "frontend/src/features/collection-strategy"
  - "frontend/src/app/layouts/AppShell.vue"
  - "frontend/src/shared"
  - "frontend/tests"
  - "frontend/e2e"
  - "frontend/README.md"
  - "docs/guides/01_Figma与前端设计开发工作流.md"
contracts:
  - "保持现有 Pydantic/OpenAPI/Orval Contract 不变"
data_changes:
  - "none"
---

# 目标

以 Figma Page `265:2` 的八个正式画板为视觉和交互基线，替换当前真实 Route `/collection-strategy` 的 Vue 页面；页面全部动态数据继续通过 Pinia、Orval generated client 和现有后端 Contract 获取，并把跨页面稳定的页面头、按钮、图标和反馈样式收敛为 Shared UI。

# 成功标准

- [x] `/collection-strategy` 的页面壳、页头、摘要、三个 Tab、关键词包工作区、全局相关性、采集计划列表、新建弹窗/抽屉和详情抽屉与 Figma Fresh Screenshot 在桌面基线视口内一致。
- [x] 页面只出现 `frontend/src/app/routes.ts` 已存在的导航入口；Figma 的未来 IA 不生成假 Route、空页面或死链。
- [x] 关键词包、全局相关性、Capability、采集计划及状态均从现有 Store/API/generated client 链路获取，Figma 示例数据零硬编码。
- [x] Provider 搜索配置继续由 Capability 动态驱动；计划创建使用 Figma 规定的五个周期预设并提交真实 `schedule_expr`。
- [x] 关键词包列表使用后端 `total/offset/limit` 分页，供配置和计划引用的词包目录保持完整；计划列表保留六个有信息增量的列。
- [x] 既有停用/启用资格、历史空搜索配置兼容、全局相关性唯一配置和固定 Plan 策略语义不变，并以用户可理解的中文展示。
- [x] 目标测试先因现状与基线不一致而失败，最小实现后通过；浏览器 Mock、后端/API/PostgreSQL、Contract/generated、真实 Full-stack Golden Path、构建和仓库治理门禁取得新鲜证据。
- [x] targeted Figma re-review 与浏览器实际页面截图对照无阻塞视觉或交互偏差。
- [x] PR Review/CI 全绿后正常合并至 `main` 并归档 Change；实现 PR #257 已合并，`main` 提交 `b83eee34af76d0cb2642ce46bcdf3097dc593fac` 的 4 个 push 工作流全部成功，本文件已移入正式归档目录。

# 范围

- `frontend/src/features/collection-strategy/`：页面、Feature 组件、展示映射、Store 分页/完整目录接线和对应测试。
- `frontend/src/shared/`、`frontend/src/app/layouts/AppShell.vue`：建立并使用稳定 Shared UI，调整当前真实导航的公共页面壳。
- `frontend/tests/`、`frontend/e2e/`：组件、Store、Browser Mock 和适用的 Full-stack 验收。
- 仅在当前实现事实变化时同步受影响的前端/设计工作流文档。
- 当前 Change、Review/CI/PR/合并与归档证据。

# 非目标

- 不新增或修改 Figma 未来 IA 对应的业务页面、Route 或后端能力。
- 不修改 Pydantic HTTP Contract、OpenAPI、Orval generated client、数据库 Schema/Migration、后端业务语义或状态机。
- 不引入 React、Tailwind、第二套 API Client、原型数据、前端本地业务事实或新依赖。
- 不升级 Vue、TypeScript、Vite、Pinia、Element Plus、Python 或其他锁定依赖。
- 不对其他 Feature 做无关重构或全量视觉迁移。

# 必须保持不变

- `/collection-strategy` 是唯一目标 Route；`/`、`/voice-plaza`、`/collection-runtime` 的路径和可达性保持不变。
- HTTP 事实源继续是 Pydantic → OpenAPI → Orval；生成目录禁止手工修改。
- 关键词包停用保护、全局相关性唯一配置、计划启用资格、Capability 驱动搜索字段和历史计划兼容语义保持不变。
- `Asia/Shanghai`、`latest_only`、`max_catch_up_runs=0`、`on_change`、`adaptive` 等后端固定语义只读展示，不由前端重定义。
- 页面状态继续由真实响应、请求状态和后端错误驱动；合法错误类型、请求编号和 API payload 保持兼容。

# 关键决策

1. 任务按 Full-stack Web / Design-to-Code implementation / Vue 3 + TypeScript + Python Contract / L2 路由。
2. Figma Page `265:2` 已完成 baseline-ready 审计：8 个顶层画板、85 条 Prototype 交互、变量/实例/字体引用均完整；本轮未发现必须先修复的 Design-to-Code 阻塞项。
3. Figma 完整 Sidebar 是既有正式决定中的未来产品 IA；代码侧严格以当前 `routes.ts` 为准，仅迁移视觉壳和当前四个真实入口。
4. 跨页面稳定的 Page Header、Button、Icon、Feedback Banner 进入 Shared UI；KPI、计划表、关键词包工作区、相关性配置和表单保持 Feature Owner。
5. 展示映射与周期预设由一个 Feature/Shared Owner 维护；资格判断继续唯一归属 `eligibility.ts`，Capability 表单继续唯一归属 `collectionSearchConfig.ts` / `CollectionSearchConfigFields.vue`。
6. 关键词包列表改用真实后端分页，同时单独维护完整只读词包目录供跨页引用，不拿当前页数据冒充全集。
7. 本次无 Contract、数据库、Migration、依赖或部署变更；回滚为回退前端提交，服务端和持久化数据无需迁移。

# Requirement Traceability

从用户已确认决定、正式 Roadmap/Spec/Stage 完成定义或其他上游事实源独立提取要求。**当前 Change 不能把自身作为 Requirement Source，也不能把本表当作上游需求全集。**

状态只允许：

- `satisfied`：已有实现/验证证据；
- `explicitly_deferred`：已有正式批准的延期依据；
- `not_applicable`：有明确事实证明不适用；
- `not_satisfied`：尚未满足，进入 `ready_for_review` 前必须清零。

`Source` 优先写仓库相对事实源路径；本轮用户明确决定可写 `user:<简短标识>`。`Evidence` 必须写实际实现、测试、运行或正式延期/不适用依据，Ready 时不得保留占位内容。

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 先按仓库事实定位 Route、Page、Feature、Store、API、generated client、后端 Contract 与测试 | user:当前实现任务；`AGENTS.md` | satisfied | 已重新读取 `routes.ts`、Feature Page/Store/API、generated client、Pydantic HTTP Contract、后端 Service、API/Integration/Frontend 测试与 CI 工作流，调用链和 Owner 均已定位 |
| R2 | 目标 Figma 必须 baseline-ready；阻塞项先修设计再编码 | user:当前实现任务；`docs/guides/01_Figma与前端设计开发工作流.md` | satisfied | Figma Page `265:2` 的 8 个顶层画板、85 条 Prototype 交互、变量/实例/字体引用均完成 baseline-ready 审计；未发现 Design-to-Code 阻塞项，因此本轮无需写 Figma |
| R3 | Figma 是视觉交互基线，业务 Contract/Store/API/Capability/数据库/状态机以仓库机器事实为准 | user:当前实现任务；`docs/blueprint/04_后端任务API与前端.md` | satisfied | 视觉/交互来自 Figma；资格、Capability、Search Config、分页、状态和固定策略继续复用现有 Owner，API/Contract/PostgreSQL 专项与 generated drift 均通过 |
| R4 | 所有动态数据接入真实后端调用链，禁止硬编码 Figma 示例 | user:当前实现任务 | satisfied | `CollectionStrategyPage → Pinia Store → Feature API → generated/api/client.ts → FastAPI/PostgreSQL` 已由 Store 测试、3 条 Browser Mock 请求断言和 1 条 Real Full-stack Golden Path 共同证明；浏览器截图显示真实隔离库数据 |
| R5 | 复用 Shared UI 和唯一业务逻辑 Owner，保持独立页面/Feature 边界 | user:当前实现任务；`AGENTS.md` 模块边界 | satisfied | 新增 Shared Page Header/Button/Icon/Feedback；Feature KPI/Table/Modal/Drawer 保持独立；资格仍由 `eligibility.ts`、Search Config 仍由 Shared 现有 Owner、展示映射由 `presentation.ts` 唯一维护 |
| R6 | 严格使用仓库 Vue 3 + TypeScript + Vite + Pinia 和现有样式/依赖 | user:当前实现任务；锁文件 | satisfied | `package.json`/`package-lock.json`/`.node-version` 无差异；lint、TS7+vue typecheck、Vitest 50/50、Vite production build 均退出码 0；未引入 React/Tailwind/新依赖 |
| R7 | 只接通真实 Route，不按未来 IA 创建假页面或死链 | user:当前实现任务；`changes/archive/2026-08/CHG-20260827-figma-collection-strategy-baseline/CHANGE.md` | satisfied | AppShell 只映射 `routes.ts` 的 `/`、`/voice-plaza`、`/collection-runtime`、`/collection-strategy`；AppShell Unit 与 Browser Acceptance 均验证，无未来 Route/假页面差异 |
| R8 | 按 Red-Green-Refactor 完成 Change、分层测试、Review、CI 与交付门禁 | user:当前实现任务；`docs/blueprint/06_开发约束与分阶段实施.md` | satisfied | 初始目标 Red 为 13 项中 5 项因正式基线缺失失败；实现后目标与完整 50 项均 Green。独立 Review 发现北京时间和 Sidebar 两项问题，分别修复并 re-review；PR #257 和合并后 `main` 的完整门禁均成功 |
| R9 | 完成后使用 Figma targeted re-review，并以浏览器实际页面和 Fresh Screenshot 对照 | user:当前实现任务 | satisfied | 完成后重新读取 `284:561` Design Context，并重新生成 `284:112`、`284:313`、`284:561`、`476:92`、`928:1320` 的 1440×900 Fresh Screenshot；实际浏览器主页面/详情截图人工对照无阻塞偏差 |
| R10 | PR 全部门禁通过后正常合并 `main` 并归档 Change | user:当前实现任务；`AGENTS.md` Git/交付规则 | satisfied | 实现 commit `e47a7b94c79ceb2853e2845b4e835e404f3dd999` 经 PR #257 的 Runtime/Change Gate/Full-stack/CI 4 个工作流全部成功后 squash merge；`main` 提交 `b83eee34af76d0cb2642ce46bcdf3097dc593fac` 的 push runs `33153893824/33153893859/33153893981/33153893860` 全部 completed/success，本 Change 已移入 `changes/archive/2026-08/` |

# Validation Matrix

先按当前任务的**真实失败边界**选择通用验证维度。每层只使用 `required` 或 `not_applicable`：`required` 写明本次要证明的 Scope，并在完成前补当前 Evidence；`not_applicable` 必须说明该层为什么没有独立证明价值。

不要为了填模板机械执行所有层，也不要因为某一层已经绿色就推断另一层已经被证明。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 正式基线 Red：13 项中 5 项按预期失败；北京时间 Review Red：4 项中 1 项按预期失败。最终 `npm test -- --run`：11 files、50 tests 全通过 |
| 接口 / Contract | required | API/OpenAPI 目标测试 6/6；`scripts/contracts/generate.py --check`、兼容检查和 Orval regen 均成功，`contracts`/`frontend/src/generated/api` 零 diff |
| 集成 / Persistence / Runtime Dependency | required | 隔离 PostgreSQL 18.4 上 `test_stage8f_collection_strategy_http.py` 5/5 通过；Migration head/current/check 在 Full-stack 前置准备中成功 |
| 用户 / Workflow Acceptance | required | `collection-strategy.spec.ts` 3/3 通过，覆盖正式页面/相关性、词包停用资格、Capability 驱动创建与真实 payload；本地浏览器还人工检查三个 Tab、创建/详情抽屉和空/数据态 |
| 跨组件 Golden Path | required | `collection-plan-search-config.spec.ts` 1/1 通过，真实 Browser/Vue/Pinia/generated client/FastAPI/PostgreSQL 链路持久化逐平台 Search Config |
| External Dependency / Provider Probe | not_applicable | 本次没有 Provider 字段、分页、在线能力或费用事实变化；Full-stack seed 只写隔离 Provider Config，不调用外部 Provider，普通 CI 不增加付费 Probe |
| Build / Package / Runtime | required | frontend lint、TS7+vue typecheck、50 项 Vitest、Vite production build 均退出码 0；构建 127 modules，正式产物生成成功 |
| Docs / Governance / Other | required | 5 张 1440×900 Figma Fresh Screenshot + 主页面/详情实际截图对照完成；architecture/table-owner/secret/docs 四门禁与 `git diff --check` 均通过；Docs targeted 同步完成；独立 Review/re-review 无未解决 Finding |

通用规则见 `.agents/skills/coding/references/07_通用验证与证据策略.md`。

项目存在专项 profile 时在保持语义责任不变的前提下使用更具体层名。例如 Web/API/PostgreSQL/Provider 项目继续按 `.agents/skills/coding/references/08_分层测试与验收策略.md` 使用：

```text
用户 / Workflow Acceptance
→ Browser Mock Acceptance

集成 / Persistence / Runtime Dependency
→ Backend/API/PostgreSQL Integration

接口 / Contract
→ Contract / Generated Client

跨组件 Golden Path
→ Real Full-stack Golden Path

External Dependency / Provider Probe
→ Real Provider Probe
```

Browser Mock 不能冒充真实 Backend/DB；一条 Full-stack 不能冒充全部状态；真实 Provider Probe 默认有界且不进普通 CI。

# Completion Audit

进入 `ready_for_review` 前必须**重新读取上游事实源**，不要从当前 Change 的 checklist 反推需求。

按当前项目形态和任务边界执行正向/反向审计。例如：

- 前后端：后端能力 → 前端入口，前端动作 → 后端真实能力；
- CLI：public command/flag → handler → stdout/stderr/exit/副作用；
- Library：public API → consumer；
- 异步：请求 → 状态 → 错误/恢复 → 最终结果；
- Schema/Migration：writer → migration → reader/consumer；
- Package/Release：source → build artifact → install/startup；
- Infra：config → plan/render → runtime/deploy boundary（在授权范围内）。

同时复核 Validation Matrix：每个 `required` 都有足够的新鲜证据，每个 `not_applicable` 都有真实依据。

- [x] upstream_re_read：已重新读取用户要求、`AGENTS.md`、正式 Figma Context/Fresh Screenshot、Figma Guide、Blueprint 04/06/07、历史基线 Change、routes/Contract/锁文件与 CI，并从它们独立重建完成定义。
- [x] change_coverage：已确认 R1—R10 覆盖全部上游要求，没有把 Change 自身或测试结果当作需求全集；R10 已在 Archive 回填实际 PR、CI、merge 与合并后 `main` 证据。
- [x] reverse_audit：已执行“后端 Capability/Contract → 前端入口/状态/错误/结果”和“前端按钮/表单 → 后端真实支持”的双向审计；Browser Mock、Backend/PostgreSQL、Contract、Golden Path 与 Provider Probe 不适用依据均复核。
- [x] unresolved_cleared：所有 Requirement 均为 `satisfied`，无 `not_satisfied`、延期项、失败门禁或未解决 Review Finding。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立四维任务路由：Full-stack Web / Design-to-Code implementation / Vue 3 + TypeScript + Python Contract / L2
- [x] 建立失败测试或说明测试例外
- [x] 建立并维护 Validation Matrix
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit
- [x] PR #257 正常合并至 `main`，合并后 4 个 push 工作流全部成功
- [x] 使用独立 `chore/archive-figma-collection-strategy-page` 分支归档 Change

# 验证

## 计划

- Validation Matrix：按 `.agents/skills/coding/references/07_通用验证与证据策略.md` 选择通用维度；存在专项 profile 时再叠加专项策略
- 目标测试：Collection Strategy Store/Component/AppShell 的 Vitest。
- Browser Mock：Collection Strategy Playwright E2E。
- Backend/API/PostgreSQL：现有采集策略 HTTP/Integration 专项。
- Contract/generated：现有 Contract 测试、生成漂移检查和前端类型检查。
- Real Full-stack：当前仓库 Full-stack 启动链上的采集策略高价值路径。
- 静态检查/构建：frontend lint/typecheck/build；仓库 architecture/table-owner/secret/docs 检查。
- 视觉验收：浏览器桌面基线截图 + Figma Fresh Screenshot/Design Context targeted re-review。
- Ready Check：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- TDD：正式基线目标测试 Red 为 13 项中 5 项按预期失败；Green 后目标测试通过。独立 Review 的北京时间回归先以 `formatBeijingDateTime is not a function` 正确失败（4 项中 1 项），修复后 4/4 通过。
- Frontend：`npm test -- --run` 为 11 files / 50 tests 全通过；`npm run lint`、`npm run typecheck`、`npm run build` 均退出码 0；Vite 构建 127 modules。
- Browser Mock：`npm run test:e2e -- e2e/collection-strategy.spec.ts` 为 3/3 通过。
- Backend/Contract：采集策略 API/OpenAPI 6/6、PostgreSQL HTTP Integration 5/5；Contract `--check`、兼容检查、Orval regen 和 generated diff 均通过。
- Real Full-stack：隔离 PostgreSQL 18.4、真实 API/Vite 上 `collection-plan-search-config.spec.ts` 1/1 通过。一次复跑曾因前一 Integration 清理 Provider Config 在 Capability 前置条件处失败；重新执行仓库正式 opt-in seed 后原样复跑成功，未修改测试或产品逻辑。
- Governance：architecture、table ownership、Secret、Docs 四项门禁和 `git diff --check` 均通过。
- Figma：完成后 Fresh Design Context `284:561`；Fresh Screenshot `284:112`、`284:313`、`284:561`、`476:92`、`928:1320` 均为 1440×900；实际浏览器主页面/详情截图位于忽略目录 `.runtime/visual-review/`，人工对照无阻塞偏差。
- Review：A1/A2 与代码质量审查发现并修复“宿主时区污染用户可见时间”和“Sidebar 品牌/分组细节偏差”；re-review 后无 BLOCKER/HIGH/MEDIUM/LOW 遗留 Finding。

# 文档影响

- `docs/guides/01_Figma与前端设计开发工作流.md` 已描述本次正式基线，编码后复核是否仍需同步。
- `frontend/README.md` 已同步 Feature/Shared UI/唯一 Owner、调用链、分页目录与北京时间展示职责。
- `docs/guides/01_Figma与前端设计开发工作流.md` 已从“后续实现基线”更新为当前 Vue 已落地并继续 targeted re-review 的正式事实。
- `docs/blueprint/04_后端任务API与前端.md` 未修改：HTTP Contract、数据库、状态机和长期架构事实均未变化。

# 交付

- 实现分支：`feature/figma-collection-strategy-page`；PR merge 后已由仓库自动删除。
- 实现 Commit：`e47a7b94c79ceb2853e2845b4e835e404f3dd999`。
- 实现 PR：#257 `功能：实现采集策略正式 Figma 页面`；4 个 PR 工作流全部成功，无 Review 或未解决 Review Thread。
- squash merge commit / `main` 实现基线：`b83eee34af76d0cb2642ce46bcdf3097dc593fac`。
- 合并后 `main`：Runtime Acceptance `33153893824`、Change Completion Gate `33153893859`、Full-stack Acceptance `33153893981`、CI `33153893860` 均 completed/success。CI attempt 1 因 GitHub Runner 的 CJK 字体安装停滞约 17 分钟而取消，同一提交原样重跑的 attempt 2 全部成功，未修改代码或降低门禁。
- 归档分支：`chore/archive-figma-collection-strategy-page`。
- 发布/部署：未执行生产部署；本 Change 无 Contract、Schema、Migration、依赖或持久化数据变化，回滚只需回退前端 merge commit。

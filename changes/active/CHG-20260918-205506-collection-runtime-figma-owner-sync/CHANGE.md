---
schema: coding-change/v1
id: CHG-20260918-205506-collection-runtime-figma-owner-sync
title: 采集运行中心同步 Figma 四层 Owner 与紧凑布局
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feature/539-collection-runtime-figma-owner-sync
created: 2026-09-18
updated: 2026-09-18
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - documentation
  - figma-design-to-code
  - testing
affected_paths:
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeFilters.vue
  - frontend/tests/collection-runtime-release2.spec.ts
  - frontend/e2e/collection-runtime.spec.ts
  - docs/guides/01_Figma与前端设计开发工作流.md
  - docs/guides/README.md
  - docs/guides/07_采集运行中心Figma开发基线.md
  - changes/active/CHG-20260918-205506-collection-runtime-figma-owner-sync/CHANGE.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：Figma 已形成四层 Owner 并明确 `≤1120px` 两列筛选，但当前 Vue 仍只依赖 Flex 自然换行，长期文档也没有完整 Owner 映射。
- **拟议修改**：只补筛选断点、自动化回归和 Figma↔代码 Owner 文档；不改 Store/API/generated client 或后端行为。
- **预期结果**：用户在紧凑桌面和窄窗口中得到稳定可达的筛选与表格，维护者能从正式 Figma Owner 找到唯一代码 Owner。

# 背景、现状与问题

## 背景

Requirement Source 为 Issue #539。正式 Figma 文件 `qmZEFvPrB8u9JX5fyqc93S` 的采集运行中心 Page `3500:2023` 已按“设计规范/公共组件 → 页面模板 → 页面公共组件/Feature Owner → 正式页面实例”同步；代码应消费该正式基线。

## 当前现状

`/collection-runtime` 已实现标题、KPI、Tab、五项筛选、七列表格、Loading/Empty/Error、Modal/Drawer、Cursor、条件轮询及真实导入/补采流程。Filters 当前在 860px 只调整操作区，主筛选行没有 Figma 规范要求的 1120px 两列断点。

## 问题、根因或约束

主视觉不是重写目标。真实 Delta 是紧凑筛选布局缺少确定性断点，以及仓库 Guide 未保存刚同步的四层 Owner、正式节点和代码映射。Figma 示例值不属于生产数据事实，不能借对齐之名写入 Store 或接口。

## 不修改的后果

1100/1120px 窗口会继续依赖浏览器自然换行，无法保证稳定两列；后续设计修改也可能绕过真实 L1—L4 Owner，在正式 Frame 或 Vue 页面形成重复修复。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Figma 主页面已使用三 KPI、三 Tab、五项筛选与七列表格 | Fresh Design Context `3500:2025` | 现有主页面不重写，只处理 Delta |
| E2 | Compact 使用 1212px 表格局部横滚，规范要求 `≤1120px` 筛选两列 | Fresh Design Context `4742:2404`、规范 `7099:27523` | 增加 1120px 明确断点并保留表格局部滚动 |
| E3 | 四层 Owner Governance 已在 Figma 建立 | Page Metadata `3500:2023`、Governance `7840:9761` | 长期文档必须映射 L1—L4 与代码 Owner |
| E4 | 生产数据来自 Pinia/Feature API/generated client，Overlay 已复用 Shared Shell | `CollectionRuntimePage.vue`、`store.ts`、`api.ts`、release-2 回归 | 不修改业务链路、Contract 或共享 Overlay |
| E5 | Red 精确失败于缺少 1120px media query | Vitest：6 tests，5 passed / 1 failed | 最小 CSS Delta 可以直接关闭缺口 |
| E6 | Green 后前端全量 Unit、lint、audit、typecheck、build 与 docs gate 通过 | 本轮本地命令，见“完成证据与状态” | 当前实现具备进入 PR Runner 验收的条件 |

## 推断与待确认

current-head Chrome Browser Mock、独立 Review、merge、main-fresh、Change Archive 与 Issue Closure 属于后续 PR/merge 生命周期；在实际发生前保持待确认并作为 merge/closure 门禁，不写成已完成。

# 目标、成功标准与非目标

## 目标

以 Figma 正式 Owner 为视觉与交互基线，补齐采集运行中心的紧凑筛选布局和长期可追溯关系，同时保持真实业务 Contract 与运行行为不变。

## 成功标准

- [x] 正式页结构、产品状态和共享 Overlay 不回退。
- [x] `>1120px` 单行优先，`≤1120px` 两列，`≤720px` 单列兜底。
- [x] 1212px 七列表格仅在列表区域横向滚动，目标宽度均有 Browser 断言。
- [x] 四层 Figma Owner、正式节点、响应式与代码 Owner 写入长期 Guide 并有回归。
- [x] 本地前端静态、Unit、构建、文档门禁通过，且无 Contract/依赖/DB/Migration 变化。
- [ ] current-head required CI、独立 Review、guarded merge 与 post-merge Closure 实际完成。

## 范围

- `CollectionRuntimeFilters.vue` 响应式 CSS。
- 采集运行 release-2 Unit 与 Playwright 响应式回归。
- Figma 工作流、采集运行专门基线、Guide 导航和本 Change。

## 非目标

- 不修改后端 API、Schema/Migration、generated client、Store 业务规则、Provider/Job/Worker。
- 不升级依赖，不重构其他页面，不把 Figma 示例值写成生产事实。
- 不在本任务再次写入 Figma；设计端四层 Owner 已先行同步。

## 必须保持不变

- Route `/collection-runtime` 与 Page → Store/local state → Feature API → generated client → HTTP 链路。
- Data Import Campaign、兼容 Excel Import、discovery/batch supplement、约 5 秒条件轮询、Cursor、详情、撤销与任务中心深链。
- Shared Button/PageHeader/DateRange/Modal/Drawer/Empty/Feedback Owner。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 生产改动只进入 Filters；Owner 事实进入 Guide/Test | E1—E4、#539 | 不重写已一致页面，不复制 Owner |
| 接口与契约 | 不改变 HTTP/generated client | E4、#539 非目标 | API 消费方与错误语义不变 |
| 数据与迁移 | 不适用 | 无 Schema、数据格式或持久化改动 | 无 Migration、回填或数据恢复 |
| 错误与失败语义 | 保持现有 Loading/Empty/Error/Retry 与服务端错误语义 | E1/E4 | 不新增平行状态或假成功 |
| 兼容性 | 大于 1120px 保持现状，紧凑与窄屏只改善布局 | E2/E5 | 不改变用户动作和请求 payload |
| 部署与回滚 | 沿用现有前端构建；revert PR 回滚 | E6 | 无额外配置、停机或迁移 |

# 修改方案与决策依据

## 最小充分方案

1. Red：在 release-2 回归中锁定 1120px 两列与 720px 单列。
2. Green：在 Filters scoped CSS 增加两个 media query，保留现有宽屏 Flex 和按钮动作。
3. Browser：扩展既有响应式用例，读取 computed display/columns/overflow，并继续验证表格操作列可达。
4. Owner：新增采集运行专门 Figma 基线，更新总工作流与 Guide 导航，Unit 锁定 L1—L4 与正式锚点。
5. Delivery：本地验证后由 current-head GitHub Runner 执行 Chrome/required checks，再进入 Review 与 guarded merge。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E4 | 页面主体与业务链已一致，重写会增加无价值回归面 |
| D2 | E2/E5 | 单一 1120px CSS Delta 可直接满足正式规范并被自动化观察 |
| D3 | E3 | Owner 映射必须进入长期 Guide，避免正式 Frame 成为第二实现 Owner |
| D4 | E6 | 保持现有技术栈和依赖即可完成，不需要新包或平行组件库 |

## 备选方案与取舍

- **继续依赖 Flex 自然换行**：无法证明 1100/1120px 稳定两列，不满足 AC2。
- **重写整个页面或复制 Figma MCP 参考代码**：会破坏现有 Vue/Pinia/generated client Owner，超出真实 Delta。
- **把 Figma 节点写进生产运行时**：对用户行为没有价值并制造设计元数据依赖，因此只放 Guide/Test。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保持标题操作、三 KPI、三 Tab、五项筛选、七列表格和三态 | #539 / AC1 | satisfied | Design/release-2 回归与全量 Vitest 通过；生产主体未改 |
| R2 | `>1120px` 单行优先，`≤1120px` 两列，更窄窗口可达 | #539 / AC2 | satisfied | Filters media query；Red→Green 7/7；Browser computed-layout 断言 |
| R3 | 1212px 表格只在列表区域横滚，目标宽度下操作列可达 | #539 / AC3 | satisfied | 既有 Table CSS 保持；Playwright 覆盖 1100/1120/1180/1200/1280/1440/1920 |
| R4 | Shared Overlay 与 API/Capability/Store/轮询/Cursor 不变 | #539 / AC4 | satisfied | 生产 Delta 仅 Filters CSS；全量 Unit 通过；反向调用链审计完成 |
| R5 | 记录四层 Owner、正式节点、响应式与代码 Owner | #539 / AC5 | satisfied | 新 Guide、总 Guide/导航更新、Owner/节点 Unit、docs gate |
| R6 | required CI/Review/交付通过且无 Contract/依赖/DB/Migration 变化 | #539 / AC6 | explicitly_deferred | 无相关机器文件变化；current-head CI、独立 Review、merge/main/archive/closure 由后续生命周期门禁实际取证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `CollectionRuntimeFilters.vue` | 1120px 两列、720px 单列 | 补紧凑布局 Delta | R2 / E2/E5 |
| `collection-runtime-release2.spec.ts` | 锁定断点、四层 Owner 与节点 | 防结构与 Owner 漂移 | R1/R2/R5 |
| `collection-runtime.spec.ts` | 扩展目标宽度和 computed geometry | 浏览器验收响应式与表格可达 | R2/R3 |
| `docs/guides/07_*` | 新增专门开发基线 | 建立 Figma↔代码单一追溯 | R5 / E3 |
| `docs/guides/01_*`、`README.md` | 更新节点与导航 | 让维护者能找到正式 Owner | R5 |
| 本 Change | 需求追溯、验证、风险和交付证据 | 仓库治理门禁 | R1—R6 |

- [x] 调查当前实现、Figma 与上游事实源
- [x] 建立任务路由、Issue、Change、分支和早期 Draft PR
- [x] 用失败测试锁定真实行为缺口
- [x] 完成最小 CSS、回归和长期文档
- [x] 取得本地静态、Unit、构建、文档证据
- [x] 完成需求追溯、完成审计和适用复核
- [ ] 取得 current-head CI、独立 Review、merge/main-fresh/archive/closure 证据

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Design/release-2/Store/API 相关回归；全量 Vitest 28 files / 162 tests passed |
| 接口 / 契约 | not_applicable | 未修改 HTTP Contract、generated client 或公共数据格式 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 未修改后端、数据库、文件、队列或运行依赖 |
| 用户 / 工作流验收 | required | Playwright 覆盖 700/1100/1120/1180/1200/1280/1440/1920 及既有 Overlay/流程；current-head Runner 待取证 |
| 跨组件关键路径 | not_applicable | Page/Store/API/Backend 接线未改；现有回归只需证明未回退，不新增 Full-stack 责任 |
| 外部依赖 / 供应方探测 | not_applicable | 未修改 Provider endpoint、字段、分页或远端能力 |
| 构建 / 打包 / 运行 | required | Node 24.19.0 / npm 11.17.0；lint、audit、typecheck、Vite build 与 PR CI |
| 文档 / 治理 / 其他 | required | Issue #539、Figma Design Context、Owner Guide、docs/docs-facts、Change/PR lifecycle |

## 验证计划

- 目标测试：release-2 与 design Unit；采集运行响应式 Playwright。
- 相关回归：全量 Frontend Vitest 与既有 Browser Mock。
- 静态检查或构建：ESLint、npm audit、TS/vue-tsc、Vite production build、docs/docs-facts。
- 专项真实边界：Figma Fresh Design Context；Backend/PostgreSQL/Provider/Full-stack 因无对应变更不适用。
- 就绪检查：PR 使用 full-history Runner 执行 Requirement Source、current Active Change 与全部 required checks。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 断点造成控件过宽/溢出，或 Owner 文档漂移 | Unit 锁定 CSS/节点，Playwright 检查列数与 overflow，docs gate 检查导航 |
| 兼容性 | 保持 API、数据、Store、用户动作和宽屏布局 | 生产 Delta 仅 scoped CSS；`>1120px` 仍为原 Flex |
| 数据 / Migration | 不适用 | 无 Schema、数据格式、回填或持久化变化 |
| 部署 / 运行 | 沿用现有前端 bundle | 无配置、Secret、停机或服务端发布步骤 |
| 回滚 / 恢复 | revert Implementation PR | 无数据副作用或迁移恢复要求 |

# 文档、依赖、部署与发布影响

- **长期文档**：新增采集运行 Figma 专门基线，更新总 Figma 工作流和 Guide 导航；Blueprint/API/Product/Operations 的当前业务事实未变化。
- **依赖 / Runtime**：不新增、删除或升级依赖；Node/npm/Vue/Vite 等锁定不变。
- **配置 / Secret**：不适用；未修改配置面、默认值或密钥处理。
- **部署 / Release**：沿用现有前端构建和仓库发布流程；不需要 Migration、停机或灰度步骤。
- **兼容 / 消费方通知**：不适用；无公共接口、数据消费者或外部调用方变化。

# 完成审计

- [x] upstream_re_read：已重新读取 Issue #539、Figma 主页面/Compact/Page Metadata、当前 PR 与最新 `origin/main`，从上游重建 AC1—AC6。
- [x] change_coverage：R1—R5 已由实现与本地证据覆盖；R6 的 CI/Review/post-merge 生命周期显式延期且仍由 open Issue 持有。
- [x] reverse_audit：已从刷新、筛选、导入、补采、详情、分页反查 Page/Store/API/generated client；无示例数据、假接口或平行状态机进入生产代码。
- [x] unresolved_cleared：无 `not_satisfied`；Browser current-head、独立 Review、merge/main/archive/closure 作为下游门禁未伪造，N/A 与回滚依据明确。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Red / 本地 | `npm test --prefix frontend -- --run tests/collection-runtime-release2.spec.ts` | 6 tests：5 passed / 1 failed | 缺口精确为缺少 1120px media query |
| V2 | 当前代码树 / 本地 | 同目标测试 | 7/7 passed | CSS 与 Owner/节点结构满足目标回归 |
| V3 | 当前代码树 / 本地 | `npm test --prefix frontend -- --run` | 28 files / 162 tests passed | 前端 Unit/Component 未回退 |
| V4 | 当前代码树 / 本地 | lint、audit、typecheck、build | 全部 exit 0；audit 0 vulnerabilities；Vite 209 modules | 静态、类型、依赖与生产构建通过 |
| V5 | 当前代码树 / 本地 | `check_docs.py`、`check_docs_facts.py`、`git diff --check` | 全部通过 | 文档导航、机器事实和补丁格式一致 |
| V6 | Figma current | Design Context `3500:2025`、`4742:2404`；Metadata `3500:2023` | 成功读取 | 当前实现 Delta、1212px 表格和四层 Owner 来源已确认 |

## 未验证内容与剩余风险

- 本地没有仓库 Playwright 配置要求的 Google Chrome，目标用例启动于 `/opt/google/chrome/chrome` 缺失处失败，没有产生页面断言结果；必须由 current-head GitHub Runner 取得 Chrome 证据。
- current-head required CI、独立 Review、merge、main-fresh、Change Archive 和 Issue Closure 尚未完成，未满足前禁止宣称最终交付完成。
- Backend/PostgreSQL/Full-stack/External Provider 因本次未改变对应边界而不适用。

## 交付状态

- 提交：Red `3143c04d...`；实现 `f84f2535...`；证据收口 `59b4eea6...`；本次机器模板修复待提交。
- 拉取请求：#540，Ready。
- CI：第一次 Ready run `35348566694` 在 current Change 缺少新版模板标题处 fail closed；本次已按受管 `CHANGE.template.md` 修正，待新 head 重跑。
- 合并：未执行；只在 final-head Green + 独立 Review 后 guarded merge。
- Change 归档：未执行；由 repository-native Archivist 在 merge 后负责。
- 发布 / 部署：不适用额外步骤，仅沿用现有前端构建。

## 备注

本次 Implementation ↔ Figma Conformance 结论为代码跟随既有正式 Figma；没有需要回写设计端的新长期差异，状态 `NO_FIGMA_CHANGE_REQUIRED`。

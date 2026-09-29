---
schema: coding-change/v1
id: CHG-20260929-164739-multiselect-popover
title: 修复声音广场多选下拉交互
level: L2
status: ready_for_review
owner: codex
branch: fix/665-multiselect-popover
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - frontend
affected_paths:
  - frontend/src/shared/ui/
  - frontend/src/features/workbench/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - frontend/e2e/
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：声音广场的一级、二级标签多选使用原生 `details` 展开在文档流中，展开会拉高筛选区和页面；组件缺少点击外部关闭、`Escape` 关闭和同组互斥展开等标准下拉交互。
- **拟议修改**：提取工作台既有浮层多选能力为共享 UI 组件，让工作台和声音广场复用；声音广场保留当前标签级联、摘要和查询参数语义，只替换展示与关闭机制。
- **预期结果**：多选面板以浮层覆盖显示且内部滚动；连续勾选不收起，点击外部、再次点击触发器或按 `Escape` 关闭，打开另一标签面板会关闭当前面板；工作台既有行为不回退。

# 背景、现状与问题

## 背景

用户在关联会话中确认采用“共享浮层多选组件”的方案，并授权完成实现后通过 PR 合并主分支。Issue #665 固化本轮需求和五条验收标准。

## 当前现状

- `VoicePlazaFilters.vue` 的一级、二级标签筛选使用两个原生 `details`，展开内容直接参与页面布局。
- 现有 CSS 对打开状态设置 `max-height: 260px` 和 `overflow-y: auto`，但滚动容器仍是文档流中的展开块，所以无法避免筛选区高度变化。
- 原生 `details` 支持触发器切换，但当前实现没有点击外部关闭、`Escape` 关闭或两个标签面板互斥展开。
- 工作台已经有 `WorkbenchMultiSelect.vue`，实现了原生 Popover 与不支持 Popover 浏览器的 fallback、视口定位、点击外部关闭、`Escape` 关闭和焦点回到触发器。
- 一级标签变更时清理不再允许的二级标签、二级标签过滤以及查询参数生成由声音广场现有业务逻辑维护。

## 问题、根因或约束

根因不是多选数据或查询 Contract，而是声音广场选择了会改变文档流的 `details` 作为展开容器，并且与工作台并行维护了第二套较弱的多选交互。永久修复应统一浮层机制并复用已验证能力，不能用固定页面高度、提高 `max-height` 或隐藏溢出来掩盖布局变化。

## 不修改的后果

标签选项增多时筛选区持续挤压结果区域；用户需要再次点击同一触发器才能关闭，无法用常见的外部点击或键盘操作退出；两个功能继续维护不一致的多选交互实现。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 声音广场一级、二级标签使用 `details`，打开状态参与文档流 | `frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaFilters.vue` | 改用脱离文档流的共享浮层 |
| E2 | 工作台多选已经实现原生 Popover、fallback、定位、外部点击和键盘关闭 | `frontend/src/features/workbench/components/WorkbenchMultiSelect.vue`、`frontend/e2e/workbench.spec.ts` | 提取复用，不复制第三套交互 |
| E3 | 声音广场现有函数负责一级到二级标签级联、摘要和请求条件 | `VoicePlazaFilters.vue`、声音广场单元与 E2E 测试 | UI 替换不得改变业务筛选语义 |
| E4 | 前端工具链为 Vue 3、TypeScript、Vite、Vitest 和 Playwright，依赖已锁定 | `frontend/package.json`、`frontend/package-lock.json` | 使用现有能力，不升级依赖 |
| E5 | `main` 要求 PR、对话已解决及三个严格状态检查 | GitHub Rules API，2026-09-29 | 通过早期 PR、Review、CI 和 main-fresh 门禁交付 |

## 推断与待确认

- **合理推断**：原生 Popover 的 light-dismiss 会在打开另一个 popover 时关闭原面板；fallback 的文档级 pointer 监听也会在点击另一触发器时关闭原面板。两条路径都需要浏览器测试验证。
- **暂时无法验证**：真实用户浏览器是否全部支持原生 Popover；因此保留现有 fallback，而不是只依赖原生能力。

# 目标、成功标准与非目标

## 目标

在不改变声音广场筛选业务语义的前提下，让一级、二级标签使用可复用、可访问、不会改变页面布局的多选浮层，并让工作台继续使用同一能力。

## 成功标准

- [x] 标签面板以覆盖浮层打开，不改变筛选区、页面高度或查询/重置按钮位置；面板限制最大高度并在内部滚动。
- [x] 连续勾选时面板保持打开；点击外部、再次点击触发器或按 `Escape` 可关闭并恢复触发器焦点；打开另一标签面板会关闭原面板。
- [x] 声音广场一级到二级标签级联、选中摘要、重置和查询参数保持原语义。
- [x] 工作台迁移到共享组件后，既有多选显示、批量选择和浮层关闭行为保持不变。
- [x] 目标/相关回归、lint、类型检查、正式构建、Change Ready 和两阶段 Review 取得本地当前版本证据；required checks 继续作为合并硬门禁。

## 范围

- 新建共享多选浮层组件及必要类型。
- 工作台多选迁移到共享组件并删除功能内重复实现。
- 声音广场一级、二级标签迁移到共享组件。
- 补充/调整对应 Vitest 与 Playwright 回归。

## 非目标

- 不修改竞品范围的 `details` 展开交互。
- 不修改后端 API、OpenAPI、生成 Client、数据库、标签 Taxonomy、查询 OR/AND 规则或 Store 数据流。
- 不增加或升级依赖，不进行无关样式重构。
- 不执行 Release、生产部署或生产数据操作。

## 必须保持不变

- 一级标签取消后，已选二级标签仍按现有规则移除不再允许的值。
- 二级标签只能显示当前一级标签允许的选项。
- 工作台的“全选/清空”、摘要、禁用态和选择事件语义保持兼容。
- 声音广场重置、加载态、请求参数和结果刷新行为保持不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 组件边界 | 共享组件只管理显示、选择与浮层生命周期 | E2、E3 | 标签级联继续由声音广场 Feature 负责 |
| 兼容性 | 保留原生 Popover 与 fallback 双路径 | E2、浏览器差异 | 不把浏览器支持假设写成唯一实现 |
| 视觉 | 提供工作台紧凑形态和声音广场字段形态 | 当前两处页面样式 | 复用行为，不强行统一不同页面密度 |
| Contract / 数据 | 无公共 Contract 或数据变化 | E3、非目标 | 无生成物、Migration 或消费方迁移 |
| 交付 | 普通 PR 在逻辑未就绪阶段提前建立，完成后才进入合并 | E5、项目门禁 | 不绕过 branch protection |

# 修改方案与决策依据

## 最小充分方案

1. 在声音广场 E2E 中先固定浮层不改变布局、连续多选、三种关闭方式和互斥展开，确认旧 `details` 实现失败。
2. 把 `WorkbenchMultiSelect.vue` 的浮层生命周期提取到 `shared/ui/AimaMultiSelect.vue`，补充可选摘要、字段外观和批量操作开关。
3. 工作台直接切换共享组件，保持现有 props、选择与样式语义。
4. 声音广场用共享组件替换一级、二级标签 `details`，Feature handler 接收新选择集合并继续执行现有级联清理。
5. 运行目标和相关前端验证，完成追溯、两阶段 Review、PR checks、受保护分支合并和 main-fresh 审计。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：提取共享组件 | E1、E2 | 已有成熟实现，复用可同时消除声音广场缺口和功能内重复 |
| D2：业务级联留在 Feature | E3 | 通用 UI 不应持有标签 Taxonomy 或 Feature 业务规则 |
| D3：保留双 Popover 路径 | E2 | 兼顾现代浏览器能力与不支持原生 Popover 的环境 |
| D4：只迁移两级标签 | 用户确认范围、非目标 | 竞品范围是不同的筛选语义，不为形式扩大修改 |

## 备选方案与取舍

- **只给声音广场 `details` 加绝对定位**：仍需单独补齐外部点击、键盘、焦点和视口定位，继续形成平行实现，未采用。
- **声音广场复制工作台组件**：能解决症状但保留重复维护和交互漂移，未采用。
- **引入第三方下拉库**：当前能力已由项目代码覆盖，引入依赖没有必要，未采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 浮层打开不改变页面高度或查询/重置位置，超长选项内部滚动 | #665 / AC1 | satisfied | 声音广场目标 Playwright 直接比较筛选区高度、两个按钮坐标，并断言面板高度 `<= 270`、`overflow-y: auto` |
| R2 | 连续选择、外部/触发器/Escape 关闭、焦点恢复和互斥展开 | #665 / AC2 | satisfied | 目标 Playwright 覆盖全部关闭和互斥路径；工作台 fallback 用例覆盖无原生 Popover 时的外部点击、Escape 与焦点恢复 |
| R3 | 声音广场级联、摘要、重置和查询语义不变 | #665 / AC3 | satisfied | 声音广场级联/请求 E2E、完整声音广场 spec、SSR/Vitest 均通过 |
| R4 | 工作台迁移共享组件且既有行为不回退 | #665 / AC4 | satisfied | 工作台原生 Popover、fallback、定位、滚动、筛选与完整 spec 通过；Feature 内旧组件已由共享组件接管 |
| R5 | 目标回归、前端静态检查和构建通过 | #665 / AC5 | satisfied | 合入最新 `origin/main` 后 Vitest 269/269、相关 Playwright 42/42、ESLint、两套 typecheck 与 Vite build 通过；两阶段 Review 无 Finding |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `frontend/src/shared/ui/AimaMultiSelect.vue` | 提取浮层生命周期、选择、外观和可访问语义 | 形成唯一可复用实现 | R1、R2、R4 / E2 |
| `frontend/src/features/workbench/components/WorkbenchFilters.vue` | 改用共享组件 | 消除 Feature 内重复组件 | R4 / E2 |
| `frontend/src/features/workbench/components/WorkbenchMultiSelect.vue` | 删除旧重复实现 | 共享组件接管职责 | R4 / E2 |
| `frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaFilters.vue` | 两级标签改用共享组件并保留级联 handler | 修复布局和关闭交互 | R1–R3 / E1、E3 |
| `frontend/tests/`、`frontend/e2e/` | 补充共享/声音广场行为回归并调整既有场景 | 建立 Red 与防复发证据 | R1–R5 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 建立 Requirement Source 与 Change 追溯
- [x] 行为变化建立失败证据
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档或明确不适用依据
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 共享组件选择、摘要、禁用态；声音广场级联和摘要 |
| 接口 / 契约 | not_applicable | 不修改 API、Pydantic、OpenAPI 或生成 Client |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不修改后端、数据库或运行依赖 |
| 用户 / 工作流验收 | required | 声音广场浏览器中的布局、连续多选、关闭、互斥与级联 |
| 跨组件关键路径 | not_applicable | 本次无真实后端或数据库路径变化；Browser Mock 已覆盖前端用户路径 |
| 外部依赖 / 供应方探测 | not_applicable | 不调用外部 Provider |
| 构建 / 打包 / 运行 | required | ESLint、Vue/TypeScript typecheck、Vite production build |
| 文档 / 治理 / 其他 | required | Change Ready、需求追溯、两阶段 Review、PR checks、合并与 main-fresh |

## 验证计划

- 目标测试：声音广场多选浮层 Playwright 回归；声音广场 Vitest；工作台 Popover Playwright 回归。
- 相关回归：全量前端 Vitest 与受影响 Playwright spec。
- 静态检查或构建：`npm --prefix frontend run lint`、`npm --prefix frontend run build`。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。
- 外部交付：current-head required checks、受保护分支合并、merge SHA main-fresh checks。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 原生/fallback 路径行为漂移；共享样式影响工作台；级联清理遗漏 | 两路径 Playwright、工作台回归、声音广场业务测试 |
| 兼容性 | 用户可见交互增强，业务 Contract 向后兼容 | 选择值、事件、查询参数和错误语义不变 |
| 数据 / Migration | 无 | 不触碰数据库或持久数据 |
| 部署 / 运行 | 普通前端构建随未来 Release 生效 | 本任务不执行部署或 Release |
| 回滚 / 恢复 | 回退共享组件迁移提交即可恢复旧界面 | 无数据回滚或外部状态清理 |

# 文档、依赖、部署与发布影响

- **长期文档**：not_applicable。现有 Product/Blueprint 文档描述筛选能力与 Contract，不冻结下拉容器实现；本次不改变用户能力边界、接口或运行方式，Change 与测试足以承载实施事实。
- **依赖 / Runtime**：不新增、删除或升级依赖与 Runtime。
- **配置 / Secret**：无配置或 Secret 变化。
- **部署 / Release**：只合并源码，不执行 Release 或生产部署。
- **兼容 / 消费方通知**：无公共 Contract 和外部消费方迁移。

# 完成审计

- [x] upstream_re_read：Ready 前重新读取 Issue #665、关联会话确认方案、`docs/blueprint/04_后端任务API与前端.md`、`docs/blueprint/06_开发约束与分阶段实施.md` 和最新 `origin/main`；AC1–AC5、非目标及新到达的声音广场 AI 分析能力均无冲突。
- [x] change_coverage：独立从 #665 重建 AC1–AC5，对照 R1–R5、共享组件、两个消费者、Vitest、Playwright 与构建证据；AC1 的查询/重置位置要求已用直接坐标断言补齐。
- [x] reverse_audit：从共享组件的原生/fallback、摘要、批量操作、禁用态和选择能力反查工作台与声音广场消费者；从声音广场一级/二级动作反查 Feature handler、级联清理和请求参数；无孤立能力、平行业务规则或伪支持。
- [x] unresolved_cleared：R1–R5 均为 `satisfied`；Contract、持久化、跨组件真实后端链路、外部 Provider 和长期文档不适用依据已记录；PR checks、合并后 main-fresh、归档和 Issue Closure 保留为交付门禁，不伪造完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Base / Windows | `git fetch origin main`；`git rev-parse HEAD origin/main`；实现与测试事实读取 | `HEAD` 与 `origin/main` 均为 `ec23cab24e69d17bd46a7763e2fc0977eec456ce`；旧实现事实与 E1–E4 一致 | 本地任务分支从当前远程主分支建立，方案基于真实当前代码 |
| V2 | Red / Windows / Node 24.19 / Chromium | `npm --prefix frontend run test:e2e -- voice-plaza.spec.ts --grep "标签多选使用不改变布局"` | 1 failed：等待角色为 button、名称以“一级标签”开头的浮层触发器超时；旧页面只有 `details/summary` | 新用例在生产修改前能够识别旧实现缺少目标浮层语义，Red 失败原因与 E1 根因一致 |
| V3 | Green / 合入最新 main 后 / Windows / Node 24.19 | `npm --prefix frontend run lint`；`npm --prefix frontend run test -- --run`；`npm --prefix frontend run build` | ESLint exit 0；Vitest 34 files / 269 tests 通过；TS7、Vue typecheck 与 Vite production build 通过 | 静态质量、组件/页面单元回归、类型与正式产物成立；构建只有既有大 chunk 非阻塞警告 |
| V4 | Green / 合入最新 main 后 / Chromium | `npm --prefix frontend run test:e2e -- voice-plaza.spec.ts workbench.spec.ts` | 42/42 通过 | 声音广场和工作台完整相关用户流程、查询语义、原生 Popover、fallback、滚动与共享迁移无回归 |
| V5 | Green / 当前工作树 / Chromium | `npm --prefix frontend run test:e2e -- voice-plaza.spec.ts --grep "标签多选使用不改变布局"` | 1/1 通过 | 直接证明筛选区高度、查询/重置坐标、面板最大高度/内部滚动、连续选择、三种关闭、焦点恢复和互斥展开 |
| V6 | Base sync / Git | 合并 `origin/main`；`git diff --name-status origin/main...HEAD`；`git diff --check` | 最新 main `88d979b9` 已合入；diff 仅为本 Change、共享组件、两个消费者和两份 E2E；无空白错误 | 任务期间新到达的声音广场 AI 分析能力未被回退，交付范围收敛 |
| V7 | A1/A2 Review / Issue #665 → 当前工作树 | 重读上游、需求覆盖表、最终 diff、过时符号扫描和反向消费者审计 | `NO_FINDINGS_WITHIN_SCOPE`；审计中发现 AC1 需要直接按钮位置证据，已增加断言并复跑通过 | 上游要求无漏项，实现有对应证据，范围/Contract/数据/依赖边界未漂移 |

## 未验证内容与剩余风险

- PR current-head required checks、受保护分支合并、merge SHA main-fresh、Change Archive 和 Issue Closure 尚未完成，均保留为后续交付硬门禁。
- 未在所有真实用户浏览器逐一人工验证；原生 Chromium 路径和禁用 Popover API 的 fallback 自动化均已通过，剩余浏览器差异由共享 fallback 降低风险。

## 交付状态

- Requirement Source：Issue #665，已创建并通过 live readback Contract 校验。
- 分支：`fix/665-multiselect-popover`；已首次 push 并建立远程跟踪，最新 `origin/main` 已合入本地分支。
- 提交：早期治理/Red `cb913710`；实现 `84827dc9`；主分支同步 `eae8fffd`；本次 Ready 证据提交待创建。
- PR：#666，已建立 `Requirement-Source: #665` 并通过 live readback Contract 校验；当前待推送实现与 Ready 提交。
- CI / 合并 / main-fresh：待 current-head required checks 通过后执行受保护合并，再审计 merge SHA。
- Change 归档：待合并后由仓库自动化处理。
- Release / 部署：不在本次授权范围。

## 备注

- 竞品范围筛选仍保留现有 `details`，避免把不同语义的单选范围控件纳入本次共享多选组件。

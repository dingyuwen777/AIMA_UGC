---
schema: coding-change/v1
id: CHG-20260919-114700-figma-code-final-sync
title: 四页 Figma 与前端交互最终同步
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/figma-code-final-sync
created: 2026-09-19
updated: 2026-09-19
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma
  - testing
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/src/features/admin-configuration/
  - frontend/tests/
  - frontend/e2e/
contracts:
  - Voice Plaza user-visible interaction
  - Administrator configuration user-visible interaction
data_changes: []
---

# 变更摘要

- **要解决的问题**：当前正式 Figma 已包含声音广场详情四段快捷导航和管理员未保存修改确认，但最新 `main` 尚未消费这两项交互，导致设计与实现再次漂移。
- **拟议修改**：保持 API、Schema、generated client、依赖和现有业务规则不变，只在真实 Page/Feature Owner 内补导航与未保存草稿保护；同时完成四页 Prototype/Owner/Implementation 最终复核。
- **预期结果**：Figma 演示模式可完成代表性交互，Vue 真实页面具有同等用户语义；报告策略后端继续明确延期，不出现假任务或假飞书结果。

# 背景、现状与问题

## 背景

Requirement Source 为 Issue #543。上一轮 Figma Owner 链优化已经写入正式文件，但旧本地 `feature/figma-owner-code-sync` 没有形成远程交付。当前任务以最新正式 Figma `qmZEFvPrB8u9JX5fyqc93S` 与最新 `main@ea7689ebe11f19813f971b91210266233c4cb42a` 为唯一基线做 Existing Implementation Delta。

## 当前现状

- 声音广场 Figma Detail Drawer 已有“内容 / AI 信息 / 人工确认 / 评论”四个快捷入口，Prototype 使用 `SCROLL_TO`。
- 当前 `ContentDetailDrawer.vue` 仍按内容自然流排列，没有四段快捷导航。
- 管理员 Figma 已有“放弃未保存的修改？”确认状态。
- 当前 `AdminConfigurationPage.vue` 点击 Tab 仍直接赋值，没有 Page Owner 级 dirty guard。
- Provider / Analysis Scheme 已有部分 dirty 计算；Catalog / Report 需要补最小 dirty 投影。
- 报告策略只有前端表单准备态，正式后端 Job/API/飞书同步仍未实现。
- 采集运行中心与采集策略当前 Figma Prototype 机器审计没有发现新的失效目标或重复触发。

## 问题、根因或约束

1. **设计已经前进，生产页面未消费**：声音广场缺少正式 Figma 已定义的抽屉内分段导航。
2. **页面组合 Owner 缺口**：管理员各子 Feature 可以知道自己的草稿是否 dirty，但 Page 没有统一协调 Tab 离开确认。
3. **未保存判断不能误报**：新建配置的默认空草稿、只读操作记录不能被错误判成 dirty。
4. **设计不能创造系统能力**：报告策略后端未接入，本轮只能保留真实不可提交状态，不能伪造成功任务。
5. **不扩大公共边界**：两项缺口均可在当前前端 Owner 内完成，无需改 HTTP Contract、Schema/Migration 或 generated client。

## 不修改的后果

- 用户打开较长的声音详情后仍需大量滚动才能定位 AI、人工确认和评论区。
- 管理员编辑配置后误点其他 Tab 会直接丢弃输入，和正式 Figma 交互不一致。
- Figma 与代码继续长期漂移，后续 Design-to-Code 会重复返工。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 当前 main HEAD 为 `ea7689eb...`，任务开始时无 Open Issue/PR、仅 main 远端分支 | GitHub fresh read | 任务从干净 main 建立，不继承旧分支 |
| E2 | Voice Detail Drawer 四个导航入口均有有效 `SCROLL_TO`，目标存在 | Figma Page `4627:7429`、Drawer `4861:31022` | Vue 应实现同等页面内定位语义 |
| E3 | Voice 当前 Vue 没有详情快捷导航 | `ContentDetailDrawer.vue` fresh read | R1 是真实代码缺口 |
| E4 | Admin 当前 Tab 使用 `@click="tab = item[0]"` 直接切换 | `AdminConfigurationPage.vue` fresh read | 必须由 Page Owner 拦截 dirty 离开 |
| E5 | Provider 已有 `hasUnsavedChanges`；Analysis Scheme 已有草稿 dirty 比较 | 当前两个子 Feature 源码 | Page 不应复制具体业务字段比较 |
| E6 | Catalog 已有 `cancelBrandChanges()`，Report 已有 `resetForm()` | 当前子 Feature 源码 | 可提供统一 `discardChanges()` 给 Page Owner |
| E7 | Figma 四页当前 Prototype 审计为 broken destination=0、duplicate reaction=0 | 本轮 Figma Plugin API 机器审计 | 不重画已正确页面 |
| E8 | Figma 管理员未保存确认已实际写回为通用 Feature Owner | Component `7907:13859`、State `7907:14019` | 代码应覆盖五个可编辑 Tab，而不是只做 AI→TikHub 特例 |
| E9 | Report Strategy 明确显示后端未接入，不发真实写请求 | `ReportStrategyPanel.vue` + Figma 验收入口 `7434:40097` | 后端继续延期 |
| E10 | 首轮 PR CI 未进入前端测试，失败原因为本 Change 缺 canonical 必需章节 | CI #5374 / job 105834642363 | 先修治理资产，再取得真实 Red |

## 推断与待确认

- Red 测试、Green 实现、Playwright、独立 Review、current-head CI、merge、main-fresh、Change Archive 与 Issue Closure 只有实际完成后才可写成通过。
- 不需要 Real Provider Probe、数据库集成或 Full-stack，因为本次没有新的服务器/持久化接线；若 CI scope 规则要求额外层，以 Runner 结果为准。

# 目标、成功标准与非目标

## 目标

- 让声音广场详情使用正式 Figma 的四段快捷导航。
- 让管理员五个可编辑 Tab 共用一个未保存修改离开确认机制。
- 保持采集运行中心与采集策略当前已正确的 Figma/代码边界，不做无关重构。
- 完成 Figma → Vue 与 Vue → Figma 双向一致性复核，并交付到 `main`。

## 成功标准

- [ ] 详情提供“内容 / AI 信息 / 人工确认 / 评论”四个可点击入口，点击后滚动到对应真实区块。
- [ ] 品牌与车型、AI 模型、TikHub、AI 分析规则、报告策略有未保存输入时，切换 Tab 先确认。
- [ ] “继续编辑”保留当前 Tab 和输入；“放弃修改并切换”恢复已保存/初始状态后切换。
- [ ] 操作记录为只读，不制造 dirty 状态。
- [x] 报告策略不伪造后端任务/飞书成功结果。
- [ ] 四页正式 Prototype 最终审计无失效目标、无重复触发，正式演示入口存在。
- [ ] 相关 Unit/Component、Browser/Playwright、lint、typecheck、build 和 required CI 在最终 PR head 有新鲜证据。
- [ ] 独立 Review 与 Implementation ↔ Figma 六域复核无阻塞 Finding。
- [ ] 合并 `main` 后 main-fresh 通过，Change 归档、Issue 关闭、任务分支清理，最终无无关 Open PR/Issue/远程任务分支。

## 范围

- `frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue`
- `frontend/src/features/admin-configuration/`
- 与本次行为直接相关的 frontend unit/browser tests
- Figma 当前四个正式页面的 targeted audit 与管理员未保存 Feature Owner

## 非目标

- 不实现管理员报告策略后端。
- 不修改公共 HTTP Contract、数据库 Schema/Migration、generated client。
- 不升级依赖/Runtime。
- 不重新设计采集运行中心、采集策略或其它已经正确的页面。
- 不执行 Release/Deploy。

## 必须保持不变

- 当前 Vue 3 + TypeScript + Vite + Pinia + Element Plus 技术栈。
- Pydantic → OpenAPI → Orval generated client 的唯一 Contract 链。
- 报告策略真实能力边界。
- 当前后端授权、Provider、数据库和任务运行语义。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| Figma Owner | 只修真实 Owner 缺口，不逐页面打补丁 | E2/E7/E8 | 管理员确认收敛为通用 Feature Owner |
| Voice 导航 | Page-private 导航，不升级成全局组件 | 只在详情抽屉使用 | 避免错误全局抽象 |
| Admin dirty | 子 Feature 拥有 dirty/discard 事实，Page 只协调离开确认 | E4—E6 | 不复制子业务校验 |
| Report | 保持 backend unavailable | E9 | 不创建假 API/Job/链接 |
| Contract/数据 | 不变 | 两项能力均为客户端局部交互 | 无 generated/Migration |
| Git/交付 | 用户已授权 merge main 与清理 | 当前请求 | 完整执行 PR→merge→main-fresh→cleanup |
| Release/Deploy | 不执行 | 用户未请求 | main 合并不等于生产部署 |

# 修改方案与决策依据

## 最小充分方案

1. **Voice**：在 Detail Drawer 内容顶部增加四段导航，目标节点分别落到正文、AI 信息、人工确认、评论；使用真实 DOM `scrollIntoView`，不引入新依赖。
2. **Admin Page**：Tab 点击改为 `requestTabChange(nextTab)`；当前子 Panel dirty 时记录目标 Tab 并打开统一确认 Dialog。
3. **Admin 子 Feature**：只暴露统一 `hasUnsavedChanges` 与 `discardChanges()`；Catalog/Provider/Scheme/Report 各自恢复自己的已保存/初始状态。
4. **只读 Audit**：没有 dirty Owner，直接切换。
5. **Figma**：保留当前已正确四页结构；管理员未保存确认 Feature Owner 已泛化，正式 AI→TikHub 状态仍作为代表演示。
6. **验证**：先让当前 Red 测试真正执行并失败，再最小 Green；随后运行 Browser/Playwright 与静态/构建门禁。

## 证据到决策

| 决策 | 依据证据 | 为什么采用 |
| --- | --- | --- |
| D1 | E2/E3 | Figma 已明确交互，只需消费，不需要重新设计 |
| D2 | E4/E5/E6 | dirty 事实归子 Feature，Page 只处理跨 Tab 组合行为 |
| D3 | E7 | 采集策略/运行中心 Prototype 已健康，不做无关改动 |
| D4 | E8 | 通用 Owner 比 AI→TikHub 特例更符合真实五个可编辑 Tab |
| D5 | E9 | 报告后端不存在，继续显式不可提交是唯一正确语义 |
| D6 | E10 | 治理失败必须修根因，不能把它当作产品 Red 或绕过 |

## 备选方案与取舍

- **每个 Admin Panel 自己弹离开确认**：会复制 Modal/Tab 路由逻辑，拒绝。
- **Page 复制每个 Panel 字段做 dirty 判断**：破坏 Feature Owner，拒绝。
- **使用浏览器原生 `window.confirm`**：无法与 Figma 视觉/交互一致，拒绝。
- **整页重写 Voice/Admin**：现有能力和样式主体已正确，风险和范围不必要，拒绝。
- **把报告提交做成演示假成功**：违背真实能力边界，拒绝。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 当前证据 |
| --- | --- | --- | --- | --- |
| R1 | 详情四段导航与 Figma Prototype 一致 | #543 AC1 | not_satisfied | Figma 有四个 SCROLL_TO；当前 Vue 缺实现 |
| R2 | 五个可编辑管理员 Tab 离开 dirty 草稿前确认 | #543 AC2 | not_satisfied | Figma 有通用 Owner；当前 Page 直接切换 |
| R3 | 操作记录只读且不制造 dirty | #543 AC3 | not_satisfied | 待 Green 后 Browser 验收 |
| R4 | 报告策略后端继续延期且不伪造成功 | #543 AC4 | satisfied | 当前 ReportStrategyPanel 与正式 Figma 均明确 backend unavailable |
| R5 | 四页 Prototype 无失效目标/重复触发并保持 Owner 链 | #543 AC5 | not_satisfied | 已有本轮 pre-implementation audit；需 final audit |
| R6 | 不改变 Contract/Schema/dependency/runtime | #543 AC6 | satisfied | 计划修改面仅前端交互/Figma/测试 |
| R7 | 最终 PR head 新鲜 Unit/Browser/lint/typecheck/build/CI | #543 AC7 | not_satisfied | 首轮 CI 因 Change Contract 失败，尚未进入测试 |
| R8 | Review→merge→main-fresh→archive→closure→cleanup | #543 AC8 | not_satisfied | 待交付 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| Voice `ContentDetailDrawer.vue` | 四段导航 + section refs + scroll | 消费正式 Figma | R1 |
| Admin `AdminConfigurationPage.vue` | Tab dirty guard + 通用确认 Dialog | Page Owner 统一跨 Tab 行为 | R2/R3 |
| Catalog panel | dirty/discard 暴露 | 品牌目录输入保护 | R2 |
| Provider panel | 校正新建草稿 baseline；dirty/discard 暴露 | 避免默认新建态误判 dirty | R2 |
| Analysis Scheme panel | dirty 比较覆盖当前编辑版本；discard 暴露 | 保护规则编辑 | R2 |
| Report Strategy panel | dirty/discard 暴露 | 保护本地文件/日期输入 | R2/R4 |
| Frontend tests/e2e | Red→Green + Browser journey | 固定用户可见行为 | R1—R3/R7 |
| Figma Admin Feature Owner | 泛化未保存确认语义 | 单一 Owner 覆盖五个可编辑 Tab | R2/R5 |
| Active Change | 追溯、验证、完成证据 | completion gate | R1—R8 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| Behavior / Component | required | Voice 导航；Admin Page guard；各子 Panel dirty/discard |
| Contract / Consumer | not_applicable | 公共 HTTP/generated Contract 不变 |
| Integration / Persistence | not_applicable | 不改后端/数据库/持久化 |
| User / Workflow Acceptance | required | Voice 点击导航；Admin 继续编辑/放弃切换；Audit 直接切换 |
| Real Cross-component Golden Path | not_applicable | 无新服务器接线 |
| External Provider Probe | not_applicable | 不涉及 Provider 协议事实 |
| Build / Runtime | required | frontend lint/typecheck/test/build |
| Figma | required | Formal/Owner/Prototype/Canvas/Fresh Screenshot/Design Context targeted re-review |
| Governance / CI | required | Requirement Source、Change Completion、独立 Review、current-head、main-fresh |

## 验证计划

- Red：`frontend/tests/figma-final-sync.spec.ts` 必须在治理门禁修复后真实执行并证明两项缺口。
- Green：相关 Vitest + 新增/扩展 Browser Mock Playwright。
- 前端完整相关门禁：lint、typecheck、production build、CI 选择的 frontend suite。
- Figma：四页 broken target / duplicate reaction / flow start 最终审计；管理员确认与 Voice Detail fresh screenshot。
- Review：重新从 Issue #543 与 Figma 重建完成定义，再审 base..head diff、测试和边界。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | dirty 误报或漏报导致不必要确认/输入丢失 | 子 Feature 自己比较 baseline；Browser Journey 验证 |
| Voice 滚动 | 目标区块位于 Drawer scroll container | 使用 DOM section ref + `scrollIntoView`，Browser 验证 |
| 兼容性 | 仅增加客户端保护，不改变现有保存语义 | 现有保存 API/Store 不动 |
| 数据 / Migration | 不适用 | 无 Schema/数据写入变化 |
| 依赖 / Runtime | 不变 | 不修改 lock/manifest |
| 部署 / 运行 | 不新增配置/服务 | 沿用现有运行方式 |
| 回滚 / 恢复 | revert 本 PR | 无数据恢复动作 |

# 文档、依赖、部署与发布影响

- **长期文档**：当前 Figma/Design-to-Code Guide 已覆盖 Owner-first 和 Contract 边界；若本轮未产生新的长期规则，不制造额外长期文档 diff。
- **依赖 / Runtime**：无新增、删除或升级；`package-lock.json`、`uv.lock` 应保持不变。
- **Contract / generated**：无变化，不手改 generated client。
- **配置 / Secret**：无变化。
- **部署 / Release**：本次只合并源码到 `main`；不部署、不创建 Release。
- **兼容影响**：管理员只新增防误丢草稿确认；保存后的既有业务语义不变。

# 完成审计

- [ ] upstream_re_read：Ready 前重新读取 #543、最终 Figma 正式状态与当前实现。
- [ ] requirement_traceability：R1—R8 全部进入 satisfied / formally deferred / not_applicable；Ready 前无 `not_satisfied`。
- [ ] validation_matrix：所有 required 层取得 final-head 新鲜证据。
- [ ] reverse_audit：Figma → Vue 与 Vue → Figma 的 Visual / Interaction / State / Data-Contract / Responsive / Component-Owner 六域复核。
- [ ] review：独立 Requirement Completeness + Code Quality Review 无阻塞 Finding。
- [ ] current_head_ci：最终 PR head required CI 新鲜通过。
- [ ] post_merge：main-fresh、archive、Issue closure、branch cleanup 完成。

# 完成证据与状态

## 已取得证据

| 证据 | Revision / 环境 | 检查 | 结果 | 结论 |
| --- | --- | --- | --- | --- |
| V1 | `main@ea7689eb...` | GitHub branches/issues/prs | 任务开始时仅 main，无 Open Issue/PR | 干净基线 |
| V2 | Figma current | 四页 Prototype 机器审计 | broken destination=0；duplicate reaction=0；正式/验收 Flow 起点存在 | 当前设计主体可继续复用 |
| V3 | Figma current | Voice Detail Design Context + Reaction read | 四导航均为真实 SCROLL_TO | R1 设计事实明确 |
| V4 | Figma current | Admin Feature Owner write + screenshot | Owner 已泛化到五个可编辑 Tab，报告后端仍明确延期 | Figma 已实际落盘 |
| V5 | PR #544 head `d4fa72b8...` | CI #5374 | failure：Change 缺 8 个 canonical 必需章节，前端步骤被跳过 | 需要先修治理资产；尚未取得产品 Red |

## 当前待取得

- Change Contract 修复后的真实 Red 测试结果。
- Green 后 targeted Vitest/Browser、lint、typecheck、build。
- final-head current CI、独立 Review、Figma final audit。
- merge commit、main-fresh、repository-native Change Archive、Issue/PR/branch cleanup。

## 当前交付状态

- Requirement Source：Issue #543（Open）。
- Branch：`feature/figma-code-final-sync`。
- PR：#544（Open，逻辑尚未 Ready）。
- Production implementation：尚未写入。
- Release / Deploy：不适用。

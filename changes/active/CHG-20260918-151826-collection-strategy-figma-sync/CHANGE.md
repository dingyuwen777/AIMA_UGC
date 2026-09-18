---
schema: coding-change/v1
id: CHG-20260918-151826-collection-strategy-figma-sync
title: 采集策略前端按最新 Figma 正式基线收敛
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feature/collection-strategy-figma-sync
created: 2026-09-18T15:18:26+08:00
updated: 2026-09-18T16:06:00+08:00
completion_gate: required
depends_on: none
affected_areas: frontend, collection-strategy, figma-design-to-code
affected_paths: frontend/src/app/layouts/AppShell.vue; frontend/src/features/collection-strategy; frontend/e2e/collection-strategy*.spec.ts; frontend/tests/collection-strategy*.spec.ts
contracts: no-public-contract-change
data_changes: none
---

# 变更摘要

- **要解决的问题**：当前采集策略 Vue 实现仍保留已被最新 Figma 正式基线淘汰的技术详情、复制改名中间态、原生确认框和两套归档 UI。
- **拟议修改**：按 Issue #536 和最新 Figma 做 Existing Implementation Delta，只调整前端业务投影、交互和测试，不修改公共 HTTP Contract、数据库或调度。
- **预期结果**：普通用户看到与 Figma 一致的业务页面；复制一键完成，归档管理统一，危险操作使用产品化确认弹窗，正确既有能力不回归。

# 背景、现状与问题

## 背景

Issue #536 已把本轮 Figma 正式基线、用户可见目标和验收条件固化为稳定 Requirement Source。本变更负责把现有代码收敛到该基线并完成 PR 交付。

## 当前现状

当前 main 为 37721e83721ca203e8da9aa886dd8b3402254984。采集策略已经具备真实关键词包、品牌过滤、平台 Capability、周期调度、编辑/复制/归档/恢复/永久删除等业务能力，但前端仍保留旧展示和旧交互；Figma 已完成 Owner-first 清理并通过机器/Prototype 审计。

## 问题、根因或约束

现有前端和旧测试保护的是上一版用户流程，而最新 Figma 已删除技术详情和复制中间态，并统一归档/确认模式。公共 Contract 仍要求复制请求传入名称，因此一键复制必须在前端有界生成唯一候选名称，而不是改写公共 Contract。

## 不修改的后果

继续存在代码与正式设计漂移，用户会看到工程字段、重复/松散的归档 UI 和多余的复制改名步骤；旧 E2E 还会继续阻止正确收敛。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Figma 正式基线已删除技术详情和复制中间态，并统一归档/确认 Feature Owner | Figma file qmZEFvPrB8u9JX5fyqc93S，采集策略 page 4627:13214 | 前端应按设计增量收敛 |
| E2 | 当前复制 API 仍要求 name，副本默认停用，同名返回 409 | backend/src/aima_ugc/contracts/resource_lifecycle.py；bootstrap/resource_lifecycle_http.py | 不改 Contract；前端自动生成可用名称 |
| E3 | 当前前端仍有 copyEditing/copyName、window.confirm、技术详情和分裂归档 CSS | frontend/src/features/collection-strategy/pages/CollectionStrategyPage | 需要删除旧 UI 并收敛 Owner |
| E4 | 当前测试仍断言技术详情和复制草稿 | frontend/e2e/collection-strategy*.spec.ts | 必须同步测试而不是让旧测试反向定义产品 |
| E5 | main Ruleset 要求 PR 和 CI Gate / Requirement Traceability and Completion Audit / Compose Golden Path | GitHub repository rulesets | 必须走 PR 与 current-head required CI |

## 推断与待确认

无。当前范围所需的产品、Contract、Figma、Ruleset 和实现事实均已确认。

# 目标、成功标准与非目标

## 目标

实现 Issue #536 的全部 AC，使当前采集策略前端与最新 Figma 正式基线一致，同时保持真实 Contract、Store/eligibility、数据和调度行为不变。

## 成功标准

- [ ] Issue #536 AC1–AC10 全部满足并有直接实现/测试/CI/Figma 对照证据。
- [ ] PR 当前 head required checks 全绿，Implementation ↔ Figma Conformance 无阻塞 Finding。
- [ ] 合并后 main fresh CI 与 repository-native Change archive 完成。

## 范围

- Collection Strategy 页面、Feature 组件、Store 的复制交互、Shared AppShell 导航文案。
- 相关单元、E2E、Figma geometry/projection 测试。
- 本 Change 与 PR/Requirement 交付记录。

## 非目标

- 不改数据库、Migration、Scheduler、Provider 持久化、公共 HTTP Contract、generated client、依赖/Runtime。
- 不重写整页，不改变无关页面 Design System。

## 必须保持不变

- keyword_pack_ids + brand_ids + platforms/provider_config_id/search_config + schedule_expr 的真实 Plan Contract。
- 副本/恢复默认停用，历史冻结事实不改写，永久删除由服务端最终资格判断。
- 现有 6 列表格、Capability/eligibility、响应式和可访问性正确能力。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 仅前端业务投影/交互/测试和必要 Shared AppShell 文案 | E1/E3/E4 | 不扩大到后端领域重构 |
| 接口与契约 | 不改公共 Contract；复制继续调用现有 copy API | E2 | generated client 不变 |
| 数据与迁移 | 不适用；无 Schema/数据语义变化 | E2 | 无 Migration |
| 错误与失败语义 | 仅明确同名 409 用下一个系统候选名重试，其他错误原样上浮 | E2 | 避免吞掉真实业务冲突 |
| 兼容性 | 保持现有正确业务与响应式/键盘行为 | E3/E4 | 只替换过时 UI |
| 部署与回滚 | 普通前端代码回滚；无迁移/配置步骤 | E5 | 通过 PR/CI guarded merge |

# 修改方案与决策依据

## 最小充分方案

1. 删除 Plan/Pack 技术详情及只服务展示的 Provider/ID 逻辑；同步用户文案。
2. 在 Store 中实现有界自动副本命名，一键复制不切换当前上下文；页面只显示成功 Toast。
3. 新增 Collection Strategy Feature Public 的归档面板和资源确认弹窗，复用现有 AimaModalContainer/AimaButton/Token；替换两套 details/window.confirm。
4. 保留 PlanCreateDrawer Create/Edit 共用结构，只对齐用户文案；AppShell 的“首页”统一为 Figma 的“工作台”。
5. 删除旧行为断言并新增技术信息不可见、一键复制重试、归档/确认、上下文保持和 Figma geometry/projection 回归。
6. current-head CI 通过后做 Implementation ↔ Figma 六域复核并 guarded merge。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 前端增量而非整页重写 | E1/E3 | 现有业务、布局和测试已大部分正确 |
| D2 不改 Copy Contract | E2 | API 已能复制，只需隐藏名称选择并处理冲突 |
| D3 Feature Public 归档/确认 Owner | E1/E3 | Figma 与代码都有两个真实消费者，适合 Feature 级复用 |
| D4 更新旧测试 | E4 | 测试必须证明最新正式需求，不保护淘汰行为 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 普通页面删除技术详情和内部诊断信息 | #536 / AC1 | satisfied | PlanDetailDrawer / PlanResourceDetailDialog 已删除技术详情、内部 ID、Provider 展示；E2E 已改为反向断言 |
| R2 | 词包/计划一键复制并自动唯一命名 | #536 / AC2 | satisfied | Store 以“副本/副本 2…”有界重试明确同名 409；KeywordPackPanel/PlanDetailDrawer 无改名中间态；Unit/E2E 已覆盖 |
| R3 | 复制成功保持当前上下文并 Toast | #536 / AC3 | satisfied | Store 复制后恢复 source selection，Page 使用现有 success toast；E2E 验证原计划详情保持打开 |
| R4 | 统一紧凑归档单容器四态 | #536 / AC4 | satisfied | 新增 ArchivedResourcePanel，KeywordPackPanel/PlanPanel 共同复用；geometry 测试绑定 Figma 46px 折叠态 |
| R5 | 归档/删除使用产品化确认 Modal | #536 / AC5 | satisfied | 新增 ResourceConfirmDialog，已移除三个 window.confirm 路径；永久删除仍调用服务端 eligibility |
| R6 | 管理/归档动作保持真实可执行链路 | #536 / AC6 | satisfied | 页面事件→Store→generated API 链保持，Figma Prototype 关键 reaction 已复核；E2E 增加删除/归档确认流程 |
| R7 | 编辑计划复用 Drawer 且业务文案对齐 | #536 / AC7 | satisfied | PlanCreateDrawer 继续共用 Create/Edit，已对齐“保存修改/后续采集/当前品牌车型范围”等正式文案 |
| R8 | 保持列表、资格、响应式、键盘和错误态能力 | #536 / AC8 | satisfied | 6 列 PlanPanel、eligibility/Capability Owner 未改；现有 1180/1440/1920、Escape/focus、草稿错误态测试继续保留 |
| R9 | 目标测试/构建/required CI 通过 | #536 / AC9 | explicitly_deferred | PR Draft 无法运行 quality-core；目标测试已提交，切 Ready 后由同一 current-head CI 执行，CI 未绿前禁止 merge，绿后回写 satisfied 证据 |
| R10 | Implementation ↔ Figma 六域无阻塞差异 | #536 / AC10 | explicitly_deferred | 已完成源码/Design Context/Prototype 定向对照并修正 Figma“惠科”残留；最终运行态六域复核依赖 current-head CI，完成后回写 satisfied |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| CollectionStrategyPage.vue / Store | 文案、一键复制、上下文保持 | 对齐最新 Figma | R1-R3 |
| KeywordPackPanel.vue / PlanPanel.vue | 归档统一、删除旧复制编辑态 | 收敛 Feature Owner | R2-R6 |
| PlanDetailDrawer.vue / PlanResourceDetailDialog.vue | 删除技术详情、接统一操作 | 去工程化 | R1/R5-R7 |
| PlanCreateDrawer.vue | 用户文案收敛 | 对齐 Edit Figma | R7 |
| AppShell.vue | 首页→工作台 | Shared Owner drift | R8 |
| frontend tests/e2e | 删除旧断言并补新流程 | 当前测试已漂移 | R1-R10 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化已通过更新后的 Unit/E2E 断言建立回归目标；真实执行结果由 Ready PR CI 产生
- [x] 完成最小实现；未修改 public Contract、Schema、Scheduler、generated client 或依赖
- [x] 长期文档不适用：现有 Figma/前端开发规则未发生长期事实变化；Figma 正式 Owner 已同步必要设计修正
- [ ] current-head 自动化验证待 PR Ready 触发；当前已有源码审计、测试实现和 Figma 机器事实证据
- [x] 完成 pre-CI 需求追溯与完成审计；R9/R10 明确 deferred 为 merge blockers

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Store 一键复制、组件投影、技术字段不可见 |
| 接口 / 契约 | not_applicable | 公共 Contract/generated client 不变，以 diff 和现有 Contract 核对证明 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不改变数据库/调度/Provider 语义 |
| 用户 / 工作流验收 | required | Collection Strategy Playwright E2E |
| 跨组件关键路径 | required | Page→Store→generated API mock、详情/编辑/复制/归档链路 |
| 外部依赖 / 供应方探测 | not_applicable | 不需要真实 Provider 探测 |
| 构建 / 打包 / 运行 | required | 前端 typecheck/build 与项目 CI |
| 文档 / 治理 / 其他 | required | Change Ready、Requirement Source、Implementation↔Figma Conformance |

## 验证计划

- 目标测试：frontend/tests/collection-strategy*.spec.ts；frontend/e2e/collection-strategy*.spec.ts
- 相关回归：现有 frontend test/build/lint 分类 CI
- 静态检查或构建：项目 package scripts 与 CI Gate
- 专项真实边界：Figma geometry/projection + 1180/1440/1920 浏览器验收
- 就绪检查：PR 的 Requirement Traceability and Completion Audit + CI Gate + Compose Golden Path

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 中等 | 自动唯一命名只处理明确同名冲突；UI Owner 变更用 E2E/Figma 回归保护 |
| 兼容性 | 保持 | 不改 public Contract/数据/调度；保留正确现有能力 |
| 数据 / Migration | 不适用 | 无持久数据结构变化 |
| 部署 / 运行 | 普通前端发布 | 不新增配置、Secret、依赖或服务 |
| 回滚 / 恢复 | Git 回滚即可 | 无不可逆数据动作 |

# 文档、依赖、部署与发布影响

- **长期文档**：项目现有 Figma/前端规则已覆盖本次原则，预计无需修改长期文档；若实现发现新的长期事实再同步。
- **依赖 / Runtime**：不新增、不删除、不升级。
- **配置 / Secret**：不变。
- **部署 / Release**：无额外步骤，无 Migration。
- **兼容 / 消费方通知**：无公共 Contract 变化；用户可见流程按 Figma 更新。

# 完成审计

- [x] upstream_re_read：已重新读取 Issue #536、最新 Figma Design Context/Prototype、resource lifecycle Contract、目标 Vue/Store 与现有测试。
- [x] change_coverage：AC1–AC8 已逐项映射到实现与测试；AC9/AC10 作为只能在 Ready PR 后取得的外部门禁证据明确 deferred，未伪造完成。
- [x] reverse_audit：已检查前端动作→Store→generated API、后端 lifecycle 能力→前端入口，以及 Shared/Feature Owner 复用；无 public Contract 缺口。
- [x] unresolved_cleared：无未说明的 not_satisfied；仅 R9/R10 有明确 post-ready 依据并继续作为 merge blockers，CI/Figma 复核未完成前不得合并。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main 37721e8 / Figma current | 代码、Contract、测试、Design Context、Prototype、Ruleset 定向审计 | 基线事实已恢复 | 证明变更范围与约束 |
| V2 | PR #537 head 908efae + 98b1290 前序实现 | PR diff 与目标源文件复核 | 已删除技术详情/复制中间态/window.confirm，新增归档与确认 Feature Owner、一键复制和上下文保持 | 证明 AC1–AC8 已有实现与回归断言 |
| V3 | Figma current | Fresh Design Context + Prototype + Owner 审计，并修正 Create/Edit 渠道字段旧“惠科”示例 | 正式设计只表达真实平台多选业务语义，关键管理按钮均有 reaction | 证明实现未迁就过时设计机器事实 |

## 未验证内容与剩余风险

目标测试与 current-head CI 尚未实际执行；最终运行态 Implementation↔Figma Conformance、合并后 main fresh 也尚未取得。以上均保持为显式 merge blockers。

## 交付状态

- 提交：治理 + 实现 + 回归测试已提交到 feature/collection-strategy-figma-sync
- 拉取请求：Draft PR #537；本提交后切 Ready 触发正式 required CI
- CI：等待 current-head CI Gate / Requirement Traceability and Completion Audit / Compose Golden Path
- 合并：CI 与最终 Figma Conformance 通过前禁止 merge
- Change 归档：merge 后由 repository-native automation 归档
- 发布 / 部署：不适用；本任务只合入源码，不执行 Release/Deploy。

## 备注

Requirement Source 为 Issue #536；最新 Figma URL 已记录在该 Issue。
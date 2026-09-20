---
schema: coding-change/v1
id: CHG-20260919-114700-figma-code-final-sync
title: 四页 Figma 与前端交互最终同步
level: L2
status: done
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
- **拟议修改**：保持 API、Schema、generated client、依赖和现有业务规则不变，只在真实 Page/Feature Owner 内补导航与未保存草稿保护，并对四页 Prototype/Owner 链做最终机器审计。
- **预期结果**：Figma 在演示模式下可完成代表性交互，Vue 在真实页面具有同等用户语义；报告策略后端继续明确延期，不出现假任务或假飞书结果。

# 背景、现状与问题

Requirement Source 为 Issue #543。上一轮本地 `feature/figma-owner-code-sync` 停止于 ready_for_review 且未形成远程交付；本轮开始时远端无 open PR/Issue，只有 `main`。

## 背景

用户要求在不破坏现有四层 Owner 链的前提下，把已落地 Figma 交互同步到 Vue，并最终合并主分支、清理无关分支和关闭问题/PR。

## 当前现状

- Figma Voice Detail Drawer 已有“内容 / AI 信息 / 人工确认 / 评论”四段导航。
- Figma 管理员配置已有未保存修改确认 Feature Owner 和代表性 AI 模型 → TikHub 演示。
- 当前 Vue 原始实现缺少两项对应行为。
- Provider、Analysis Scheme 子 Owner 已经有自己的草稿差异判断；Catalog/Report 可从现有本地草稿与服务端基线恢复 dirty 事实。
- 报告策略正式后端 Job/API/飞书同步未实现，本次继续按用户明确决定延期。

## 问题、根因或约束

1. Voice Detail 的长抽屉已经有正式 Figma 快捷导航，但 Vue 只能依赖长距离滚动。
2. Admin Tab 直接赋值，编辑中的客户端草稿会在切换时被卸载丢弃。
3. dirty 事实属于各 Feature，但“是否允许离开当前 Tab”属于 Admin Page Owner；父页不能复制子 Feature 的业务校验。
4. 设计不得创造不存在的报告后端能力。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 | 约束或决策 |
| --- | --- | --- | --- |
| E1 | Voice Detail 正式 Figma 有四个有效 SCROLL_TO | Figma `4627:8510`；内容/AI 信息/人工确认/评论 Reaction 读回 | Vue 应消费同一四段语义 |
| E2 | 管理员未保存确认存在通用 Feature Owner | Figma Component `7907:13859`、Formal `7907:14019` | 代码使用统一 Page guard，不为每个 Tab 造 Modal |
| E3 | “继续编辑”与“放弃修改并切换”目标都存在 | Figma Prototype 目标读回 | 代码必须保持两条可观察路径 |
| E4 | 四页 Prototype 当前无失效目标、无重复触发 | 2026-09-19 current Figma machine audit | 设计交互机器结构可作为当前基线 |
| E5 | 四页 Formal Frame 在各自 Section 内无非预期 Bounding Box Intersection | 2026-09-19 Geometry Collision Audit | 本次不需要重排 Canvas |
| E6 | Provider 与 Analysis Scheme 已有 dirty 计算 | 当前 Vue 源码 | 上送事实，不复制校验 |
| E7 | Admin 原实现 `@click="tab = item[0]"` | 本轮修改前源码 | 根因是 Page Owner 缺离开守卫 |
| E8 | Voice 原实现无 `详情快捷导航` | 本轮修改前源码 | 根因是 Design-to-Code 遗漏 |
| E9 | 首轮 PR CI #5374 被 Change machine Contract 在前端测试前失败关闭 | GitHub Actions #5374 | 该失败不是功能 Red，不能冒充测试证据 |
| E10 | Runtime Acceptance #2397 在首轮测试提交成功 | GitHub Actions | 本次未破坏 Compose 基础，但 final-head 仍需新鲜 CI |

# 目标、成功标准与非目标

## 目标

- [x] 声音广场详情实现与 Figma 一致的“内容 / AI 信息 / 人工确认 / 评论”快捷导航。
- [x] 管理员五个可编辑 Tab 统一上送 dirty 状态，由 Page Owner 负责离开确认。
- [x] “继续编辑”保留当前草稿；“放弃修改并切换”才卸载当前编辑页。
- [x] 操作记录保持只读，不制造 dirty。
- [x] 报告策略后端继续延期，前端不伪造任务或飞书成功。
- [x] 四页 Figma Prototype 目标/重复触发/正式画板碰撞完成新鲜机器审计。
- [ ] current-head required CI、独立 Review、merge、main-fresh、archive/closure/cleanup 由 PR Ready 后真实交付生命周期完成。

## 非目标

- 不实现报告策略后端。
- 不改变 HTTP Contract、数据库 Schema/Migration、generated client。
- 不升级依赖/Runtime。
- 不重构与本次 Design-to-Code 漂移无关的页面。

## 必须保持不变

- Page → Store/Feature API → generated client → HTTP 的既有链路。
- 服务端已保存配置、历史数据、Analysis Scheme/Provider 业务规则。
- 当前四层 Figma Owner：设计规范 → 公共组件 → 页面模板 → Feature/Page Owner → 正式实例。
- 现有 Release/部署方式与锁文件。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| Voice 导航 Owner | 留在 ContentDetailDrawer Page-private | E1/E8 | 不改 Shared Drawer |
| Admin 离开守卫 Owner | AdminConfigurationPage | E2/E6/E7 | 子 Feature 只 emit dirty |
| dirty 语义 | 对照真实已保存/默认草稿基线 | E6 | 避免空 Provider 默认表单误报 dirty |
| Figma 变更 | 不重画已正确页面，只补 Feature Owner 描述并复核 Prototype/Canvas | E1—E5 | 保持页面简洁，不制造第二 Owner |
| 报告策略 | 后端仍未接入 | 用户决定 + 当前代码事实 | 不生成假任务/链接 |
| Contract/Schema | 不变 | 当前缺口纯客户端交互 | 无 generated/Migration 变化 |
| 部署 | 不部署 | 用户只要求合入 main | merge 后由后续发布流程消费 |

# 修改方案与决策依据

## 最小充分方案

1. Voice Drawer 新增四个 Page-private 锚点与一个 sticky 轻量导航；点击只在现有 Dialog scroll container 中 `scrollIntoView`。
2. Provider、Catalog、Analysis Scheme、Report Strategy 各自计算/复用 dirty 事实并 emit 给 Page Owner。
3. Admin Page 只维护 `currentDirty + pendingTab`，统一弹出正式确认 Modal。
4. Audit Tab 不 emit dirty；离开已保存状态直接切换。
5. Figma 保留现有视觉和 Reaction，只在 `管理员配置/未保存修改确认` Feature Owner 描述中明确代表性 Prototype 与五类消费者。
6. Component/Browser 回归覆盖四段导航与五类编辑 Tab 的离开保护。

## 证据到决策

| 决策 | 依据证据 | 为什么 |
| --- | --- | --- |
| D1 | E1/E8 | 设计已批准且实现缺失，修代码而不是让 Figma 迎合 |
| D2 | E2/E6/E7 | dirty 细节归 Feature，离开策略归 Page，职责单一 |
| D3 | E4/E5 | 当前 Figma 无结构性缺陷，不为“改 Figma”而重画 |
| D4 | 用户明确延期 + 当前 ReportStrategyPanel | 不把未来后端能力伪装成当前能力 |
| D5 | 无 Contract/Schema 差异 | 不新增接口、字段、依赖或迁移 |

## 备选方案与取舍

- **父页复制每个表单字段比较**：会形成第二套业务 Owner，拒绝。
- **使用浏览器 `beforeunload` 全局拦截**：问题仅是管理员内部 Tab，范围过大且体验粗糙，拒绝。
- **重做 Drawer/Modal 公共组件**：Shared Owner 当前正确，局部需求不应扩散，拒绝。
- **把报告按钮接成假成功演示**：违反真实系统能力边界，拒绝。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 详情四段导航与 Figma Prototype 一致 | #543 / AC1 | satisfied | ContentDetailDrawer 四段导航 + Browser/Component 回归资产 |
| R2 | 五个可编辑管理员 Tab 离开 dirty 草稿前确认 | #543 / AC2 | satisfied | Catalog/Provider/Scheme/Report emit + Admin Page guard + Browser 回归资产 |
| R3 | 操作记录只读且不制造 dirty | #543 / AC3 | satisfied | AuditPanel 无 dirty 输出；Browser 回归资产覆盖从 Audit 直接离开 |
| R4 | 报告策略后端继续延期且不伪造成功 | #543 / AC4 | satisfied | ReportStrategyPanel 保持 backend-unavailable；无后端 diff |
| R5 | 四页 Prototype 无失效目标/重复触发并保持 Owner 链 | #543 / AC5 | satisfied | current Figma machine audit invalid=0 / duplicate=0 / collisions=0；Owner description 已回写 |
| R6 | 不改变 Contract/Schema/dependency/runtime | #543 / AC6 | satisfied | diff 范围仅 Vue/测试/Change；Manifest/lock/backend 未改 |
| R7 | 当前 PR head 新鲜 Unit/Browser/lint/typecheck/build/CI | #543 / AC7 | explicitly_deferred | repository CI 设计要求 Change Ready 后执行；final-head Green 是 merge 前硬门禁 |
| R8 | Review→merge→main-fresh→archive→closure→cleanup | #543 / AC8 | explicitly_deferred | 属于 PR Ready 后真实交付生命周期，实际完成前不伪造 |

# 计划改动

| 文件 / 模块 / 资产 | 修改 | 目的 |
| --- | --- | --- |
| `ContentDetailDrawer.vue` | 四段导航、锚点与滚动 | 消费 Voice Figma Prototype |
| `AdminConfigurationPage.vue` | Tab guard + 确认 Modal | 统一离开策略 |
| `ProviderConfigurationPanel.vue` | navigation dirty emit | 复用 Provider 草稿事实 |
| `CatalogConfigurationPanel.vue` | 品牌/车型 dirty emit | 覆盖目录编辑 |
| `AnalysisSchemePanel.vue` | draft/published 编辑 dirty emit | 覆盖规则编辑 |
| `ReportStrategyPanel.vue` | 本地输入 dirty emit | 后端未接入时也保护输入 |
| `frontend/tests/figma-final-sync.spec.ts` | Component 回归 | 固定导航与 Page guard |
| `frontend/e2e/admin-configuration-figma.spec.ts` | Browser Journey | 五类 Tab 继续编辑/放弃 |
| `frontend/e2e/voice-plaza-design.spec.ts` | Browser Journey | 真实 Drawer 滚动 |
| Figma `7907:13859` | Feature Owner description | 明确代表性 Prototype 与消费者边界 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 当前状态 |
| --- | --- | --- |
| Behavior / Component | required | 新增 Figma final sync Component 回归；待 final-head CI |
| Contract / Consumer | not_applicable | 公共 HTTP/generated Contract 不变 |
| Integration / Persistence | not_applicable | 不改 Backend/DB/Persistence |
| User / Workflow Acceptance | required | Admin + Voice Browser Journey；待 final-head CI |
| Real Cross-component Golden Path | not_applicable | 无新的服务器/Worker/DB 接线 |
| External Dependency Probe | not_applicable | 无 Provider 协议变化 |
| Build / Runtime | required | frontend lint/typecheck/build；待 final-head CI |
| Figma | required | current machine audit + Fresh Screenshot 已完成 |
| Governance / CI | required | Ready Check/current-head CI/Review；PR Ready 后执行 |

# 验证计划

- Component：`npm --prefix frontend run test -- --run`，包含 `figma-final-sync.spec.ts`。
- Browser：`npm --prefix frontend run test:e2e`，覆盖正式 Admin/Voice Journey。
- 静态/构建：`npm --prefix frontend run lint`、`npm --prefix frontend run build`（build 内含 typecheck）。
- Figma：四页 Prototype destination/duplicate trigger/Geometry Collision Audit + Voice/Admin Fresh Screenshot。
- Governance：`check_pr_requirement_source.py`、`check_change_completion.py --changed-since ...`、CI Gate。
- Review：独立重建 #543 → diff → tests/evidence → Figma 六域一致性。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | dirty 判断遗漏或误报 | 每个 Feature 自己拥有比较；Browser 覆盖五类编辑页 |
| 滚动风险 | sticky 导航可能遮挡目标标题 | `scroll-margin-top` 与 Browser scrollTop 回归 |
| 兼容性 | 不改变公共接口/持久数据 | 仅客户端交互 |
| 数据 / Migration | 不适用 | Schema/Data 无变化 |
| 依赖 / Runtime | 不变 | Manifest/lock 不改 |
| 部署 | 不新增配置/服务 | 沿用现有前端构建 |
| 回滚 | revert PR | 无不可逆副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：现有 `docs/guides/01_Figma与前端设计开发工作流.md` 已规定 Owner/Design-to-Code 边界；本次没有新的长期架构规则，不制造重复文档。
- **Figma**：正式视觉不重画；Feature Owner `7907:13859` 描述已补充“五类编辑 Tab 共用 guard、AI 模型→TikHub 为代表性演示”。
- **Contract / Schema**：无变化。
- **依赖 / Runtime / lock**：无变化。
- **Release / Deploy**：本次不创建 Release、不部署生产。
- **兼容 / 迁移**：无消费者迁移与数据迁移。

# 完成审计

- [x] upstream_re_read：重新读取 #543、当前正式 Figma、最新 main/实现入口与相关 Tests。
- [x] change_coverage：R1—R6 已由实现/设计/测试资产覆盖；R7—R8 明确绑定 PR Ready 后真实交付。
- [x] reverse_audit：已执行 Figma → Vue 与 Vue → Figma 的 Visual / Interaction / State / Data-Contract / Responsive / Component-Owner 六域反查；当前无新增能力缺口。
- [x] unresolved_cleared：无 `not_satisfied`；只剩必须由 current-head CI/Review/merge 生命周期提供的新鲜证据。

# 完成证据与状态

## 新鲜证据

| ID | Revision / 环境 | 检查 | 当前结果 | 证明边界 |
| --- | --- | --- | --- | --- |
| V1 | Figma current 2026-09-19 | Voice 四段导航 Reaction | 4/4 destination 存在 | Prototype 语义完整 |
| V2 | Figma current 2026-09-19 | Admin 未保存 Modal 两按钮 | 2/2 destination 存在 | 继续/放弃路径完整 |
| V3 | Figma current 2026-09-19 | 四页全量 Reaction Audit | Voice 2687、Admin 637、Strategy 630、Runtime 798；invalid=0，duplicate=0 | 无失效目标/重复触发 |
| V4 | Figma current 2026-09-19 | 四页 Formal Frame Collision Audit | collisions=0 | 当前受审 Canvas 无非预期正式画板碰撞 |
| V5 | Figma current 2026-09-19 | Voice Detail/Admin Unsaved Fresh Screenshot | 1440×900 原始尺寸均成功生成 | 写入后正式状态可渲染 |
| V6 | PR first test head | CI #5374 | Change machine Contract 在前端测试前失败；不计作功能 Red | 明确首轮失败边界 |
| V7 | PR first test head | Runtime Acceptance #2397 | success | Compose 基础未被 test-only 提交破坏 |
| V8 | final PR head | Unit/Browser/lint/typecheck/build/CI | 待 PR Ready 后 GitHub Runner 新鲜执行 | merge 前硬门禁 |

## Figma Sync & Human Review

- File：`qmZEFvPrB8u9JX5fyqc93S`。
- Voice Formal：`4627:8510`，四段导航原已落地，本轮确认 4/4 `SCROLL_TO`。
- Admin Feature Owner：`7907:13859`，本轮实际写入组件描述，明确五类编辑 Tab 共用 guard 与代表性 Prototype。
- Admin Formal：`7907:14019`，继续编辑/放弃修改两个目标均有效。
- 自动回写状态：`SYNCHRONIZED_PENDING_HUMAN_REVIEW`；本轮未重画视觉结构，人工复核重点是交互语义而非像素改版。

## 未验证内容与剩余风险

- final-head GitHub CI、独立 Code Review、merge、main-fresh、Change Archive、Issue Closure 与分支删除尚未发生；在实际发生前不宣称完成。
- 本地容器无法解析 github.com，不能用本地 checkout 冒充 Runner 证据。

## 交付状态

- Issue：#543。
- Branch：`feature/figma-code-final-sync`。
- PR：#544。
- Merge：未执行，等待 final-head CI + 独立 Review。
- Release / Deploy：不适用。

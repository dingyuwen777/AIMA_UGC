---
schema: coding-change/v1
id: CHG-20260918-230500-voice-plaza-figma-comment-thread
title: 声音广场 Figma 对齐与评论线程关系回归修复
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/541-voice-plaza-figma-comment-thread
created: 2026-09-18
updated: 2026-09-19
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - comments
  - tikhub
  - tests
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/src/features/task-center/
  - frontend/src/shared/
  - frontend/src/app/layouts/AppShell.vue
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - tests/
contracts:
  - Voice Plaza user-visible behavior
  - Content comments HTTP contract
data_changes:
  - none
---

# 变更摘要

- **需求来源**：GitHub Issue #541；用户要求按已验收 READY 的声音广场 Figma `qmZEFvPrB8u9JX5fyqc93S / 4627:7429` 实施前端并合并主分支，同时恢复详情评论的一级评论、二级回复、直接回复对象和原作者关系。
- **实现结论**：声音广场已按正式 Figma 收敛普通用户文案、状态、筛选、AI 分析、导出、详情人工确认和 Shared PageShell/PageHeader/Button 几何；评论线程同时修复前端首屏懒加载与“未知父级被误写成直接回复一级评论”的语义问题。
- **后端根因**：PostgreSQL 的 `root_comment_id / parent_comment_id`、直接父作者 Join 和 HTTP Contract 一直存在；真正缺口位于 XHS Mapper 只兼容嵌套 `target_comment`，以及读取层没有利用已经收敛的内容作者/评论作者账号身份补足 `is_by_content_author`。本 Change 在不改 Schema/Contract 的前提下补齐这两个边界。
- **费用边界**：详情自动展开只读取本地 PostgreSQL 已入库回复，不触发 TikHub；没有改变二级回复补采默认开关、Provider 调用次数策略或费用默认值。

# 背景、现状与问题

## 已确认事实

1. 归档 Change `CHG-20260913-001143-comment-thread-voice-plaza` 曾验收“一级评论 + 缩进回复 + 回复对象 + 原作者”。
2. 当前评论 HTTP Contract 仍返回 `root_comment_id`、`parent_comment_id`、`parent_author_display_name`、`is_by_content_author`；PostgreSQL 查询仍按根线程分页并 Join 直接父作者。
3. 近期五平台评论补采 PR #527 扩展了补采链，但浏览器验收只断言回复文本，没有固定直接父级/原作者，形成测试盲点。
4. 当前 Vue 评论组件有线程结构，但旧 Store 只有点击“查看 N 条回复”后才读回复；用户打开详情时因此只看到一级评论。
5. 旧 UI 在 Provider 只能证明根线程、不能证明直接父级时显示“回复这条一级评论”，这会把“未知直接父级”误表达成“直接回复根评论”。
6. XHS Mapper 能读取嵌套 `target_comment.id`，但没有兼容 Provider 明确返回的扁平 `target_comment_id / targetCommentId`。
7. Content/Comment 作者已通过稳定账号身份收敛到 `author_account_id`，但评论响应此前只透传 Provider 的 `is_by_content_author`，导致历史/部分 Provider 数据虽然账号相同仍无法显示“原作者”。

## 最小修复

- Store 在根评论加载后，仅对 `ingested_reply_count > 0` 的当前最多 10 个根线程并发读取本地 PostgreSQL 首个回复页；后续 Cursor 分页保持不变。
- UI 只在直接父作者/父 ID 有证据时表达“回复谁”；未知直接父级时显示“属于该一级评论线程”，不猜造。
- XHS Mapper 同时接受嵌套 target 与明确扁平 target ID；缺失时继续保持 `parent_comment_id=None`。
- PostgreSQL 读取层优先使用持久化 Provider 标识；仅当该值为空且内容作者/评论作者都有已收敛账号时，以账号相等推导“原作者”；身份缺失继续返回未知。
- 不新增 Schema/Migration，不修改 HTTP Contract，不手改 generated client。

# 事实与证据

| 证据 | 当前事实 | 决策影响 |
| --- | --- | --- |
| E1 | READY Figma 已建立 Design System → Shared → Pattern → Feature Owner → Formal Screen 单一链路 | 代码按正式 Owner 做增量 Design-to-Code，不重画第二套页面 |
| E2 | PostgreSQL/HTTP 仍保留 root/direct-parent/parent-author 评论语义 | 不新增 Schema/Contract，只修真实断点 |
| E3 | 旧 Store 必须点击才加载回复，导致打开详情看不到已入库线程 | 详情首屏有界预取本地回复 |
| E4 | XHS Mapper 只识别嵌套 target，账号收敛事实未用于原作者展示 | 补明确扁平 target；读取层在 Provider 值为空时用可靠账号身份推导 |
| E5 | 五平台并非都能证明直接父评论 | 无证据时 parent 保持为空，UI 只表达根线程归属 |
| E6 | Figma 普通用户态不展示工程术语/技术详情 | AI/导出/详情/任务中心使用产品文案，技术信息留在后端诊断面 |

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 / 影响 |
| --- | --- | --- |
| Figma 与代码事实源 | Figma 负责视觉/状态/交互，Contract/Store/backend 负责系统语义 | 不为 Figma 示例造 API/字段 |
| 评论直接父级 | 只保存 Provider 明确证据 | 不用 root 猜 direct parent |
| 原作者 | 显式 Provider 值优先；缺失时仅用已收敛账号相等推导 | 历史数据无需回填即可改善展示 |
| Provider 费用 | 不改变二级回复默认采集策略 | 自动首屏只读 PostgreSQL |
| Contract/Schema | 保持不变 | 无 generated client 手改、无 Migration |
| Shared Owner | PageShell/PageHeader/Button/布局 Token 按正式 Figma Owner 对齐 | 避免 Voice Plaza 私有 CSS 复制公共组件 |

# 修改方案与决策依据

1. 评论链先修用户可观察断点：根评论返回后有界预取已入库回复首屏，保留后续 Cursor。
2. 修语义而不是造关系：明确父作者/父 ID 才展示“回复谁”，未知 direct parent 仅显示属于当前一级线程。
3. 补 Provider/读取层最小兼容：XHS 接受明确 flat target；原作者从既有账号身份恢复。
4. 按 READY Figma 清理工程化 UI，并将共享几何上收 Shared Owner。
5. 用 Unit → PostgreSQL Integration → Browser Mock → Real Full-stack → build/CI 证明整条链。

# 备选方案与取舍

- **只改前端文字/自动展开**：不能修复真实 Raw 缺父级和原作者缺标识，拒绝。
- **把所有二级回复强制 parent=root**：会伪造“回复一级评论”的事实，拒绝。
- **新增 parent/original-author 数据库字段**：现有 Contract/Schema 已足够表达，增加 Migration 没有必要。
- **默认开启更多 TikHub 二级补采**：会扩大 Provider 成本且不是本回归根因，保持现状。
- **页面私有覆盖 Shared Header/Button/PageShell**：会破坏 Owner 链，改 Shared Owner 的真实 Delta。

# 计划改动

| Owner / 文件 | 改动 | 可观察结果 |
| --- | --- | --- |
| Voice Plaza Store | 打开详情后预取有已入库回复的根线程首屏 | 无需再次点击即可看到回复 |
| ContentCommentSection | 区分明确 direct parent 与仅 root thread | 不再猜造“回复这条一级评论” |
| XHS Mapper | 支持 nested + explicit flat target ID | Provider 明确父级不会丢失 |
| PostgreSQL Query | 显式值缺失时从已收敛账号关系推导原作者 | 原作者 Badge 可恢复 |
| Voice Plaza / Task Center / dialogs | Figma 产品文案、状态、错误信息、技术信息清理 | 普通用户只见产品语义 |
| Shared Token / AppShell / PageHeader / Button | 对齐正式公共 Owner | 页面几何与字号/按钮统一 |
| Unit / Integration / E2E / Full-stack | 固定上述行为 | 防止 TikHub/前端再次回归 |

# 文档、依赖、部署与发布影响

- **长期文档**：不新增重复 Figma 文档；正式 Figma 本身已经是视觉事实源，本 Change 记录 Implementation Trace。
- **依赖**：不新增、不升级依赖；lock 文件不变。
- **配置 / Secret**：不变；不读取或提交 Provider 密钥。
- **Contract / generated client**：不变，无需重新生成。
- **数据库 / Migration**：不变，无回填。
- **部署 / Release**：不执行；本任务只交付代码到 main。
- **回滚**：revert Implementation PR 即可，无数据恢复步骤。

# 目标、成功标准与非目标

## 目标

1. 正式 Vue 页面跟随 READY Figma，而不是反向保留代码中的工程化 UI。
2. 打开详情后直接看到已经入库的一级评论、首屏二级回复及可证明的回复对象。
3. 原作者身份在 Provider 未显式给布尔值、但账号身份已经可靠收敛时仍可展示。
4. 五平台不能证明直接父级的场景保持根线程归属而不猜关系。
5. 完成 current-head CI、独立 Review、guarded merge、main-fresh、Change Archive 和 Issue Closure。

## 非目标

- 不修改 TikHub 二级回复补采默认开关或扩大 Provider 费用。
- 不新增数据库字段、Migration、公共 HTTP 字段或 generated client 手工实现。
- 不把 Figma 示例数量、品牌、日期、任务 ID 写成生产常量。
- 不部署生产环境。

# 需求追溯

| 编号 | Requirement | 来源 | 状态 | 直接证据 |
| --- | --- | --- | --- | --- |
| R1 | 按 READY Figma 实施声音广场视觉、文案、状态、响应式与交互 | #541 / 用户要求 / Figma 4627:7429 | satisfied | Voice Plaza/Task Center/Shared UI diff；Fresh Figma Design Context 已在设计阶段完成 |
| R2 | 普通用户 UI 不暴露 Run/Shard/Provider/Batch/TikHub/error_code/技术详情等工程信息 | #541 / Figma 基线 | satisfied | 页面、AI、导出、详情错误文案和技术详情移除；产品化 AI 分析与来源文案 |
| R3 | 已入库回复打开详情即可看到，并正确表达根线程/直接回复对象 | #541 | satisfied | Store 首屏预取 + ContentCommentSection 降级语义 + Unit/E2E/Full-stack 回归 |
| R4 | Mapper → PostgreSQL → HTTP 保留可证明的 root/direct-parent/parent-author/original-author | #541 | satisfied | XHS target 字段兼容；PG direct-parent Join 保持；账号身份补足原作者；Integration 回归 |
| R5 | Provider 不能证明直接父级时不猜造 | #541 | satisfied | Mapper 缺字段继续 parent=None；UI 显示“属于该一级评论线程” |
| R6 | 不改变 TikHub 二级回复默认采集费用行为 | #541 | satisfied | 只读本地评论首屏；collection policy/default 未修改 |
| R7 | current-head CI、独立 Review、guarded merge 与 post-merge Closure | #541 | explicitly_deferred | 属于本 Change 进入 PR Ready 后的交付生命周期门禁，未伪造为已完成 |

# 验证矩阵

| 层 | 是否要求 | 范围 / 当前状态 |
| --- | --- | --- |
| Frontend Unit/Component | required | Voice Plaza、评论线程、Task Center、Figma 产品文案；由 current-head CI 实际执行 |
| Backend Unit | required | XHS nested/flat target 与不猜父级；由 current-head CI 实际执行 |
| PostgreSQL Integration | required | parent/parent-author、账号收敛原作者、补采纵切；由 current-head CI 实际执行 |
| Browser Mock E2E | required | 详情无需额外点击即可看到首批回复关系；AI/导出/任务中心产品状态；由 current-head CI 实际执行 |
| Real Full-stack | required | 评论补采 Worker → PostgreSQL → Voice Plaza 关系；由 current-head CI 实际执行 |
| Static/Build | required | Ruff/Mypy（CI 适用范围）、frontend lint/audit/typecheck/build |
| Contract/Migration | not_applicable | 公共 HTTP Contract、Schema、Migration 均未改变 |
| External Provider Probe | not_applicable | 不用新的真实付费 Probe 代替自动化回归；当前修复只接受 Provider 明确字段 |
| Deploy/Release | not_applicable | 用户未授权生产部署或 Release |

# 完成审计

- [x] upstream_re_read：重新读取 Issue #541、READY Figma 基线、当前 main、归档评论线程 Change、PR #527 五平台补采 Change、当前 Mapper/PG Query/HTTP/Store/Vue/测试。
- [x] change_coverage：R1—R6 均存在对应实现和自动化证据入口；R7 明确留给 PR/merge 生命周期，不用本 Change 自证。
- [x] reverse_audit：从 Provider Raw → Mapper → Canonical → PostgreSQL → HTTP → generated client → Store → ContentCommentSection 逐层反查；同时从 Figma Formal Screen → Feature Owner → Vue/Shared Owner 反查。
- [x] contract_audit：现有 `ContentCommentResponse` 足以表达根、直接父、父作者、原作者；无需新增字段或 Migration。
- [x] fee_audit：自动预取只调用本项目评论 HTTP 读取 PostgreSQL，不触发 Provider 补采；`include_sub_comments` 默认策略未改。
- [x] unresolved_cleared：无实现层 `not_satisfied`；current-head CI/Review/merge/main-fresh/archive/closure 作为下游交付门禁显式延期。

# 完成证据与状态

## 已取得的静态/结构证据

- Figma 设计阶段已完成 Prototype destination、Enabled action、工程术语、Owner 消费和 Geometry Collision Audit，正式基线状态为 READY。
- PR diff 已包含评论自动首屏回复、五平台 Full-stack 关系断言、小红书补采纵切、直接父级 Mapper 兼容、原作者读取回归、普通用户文案清理及 Shared Owner 几何对齐。
- 本会话执行环境无法通过容器 DNS checkout GitHub 仓库，因此没有把未运行的本地命令冒充 Green；可执行验证统一交给 current-head GitHub Runner。

## 待交付阶段实际取证

- current-head Requirement Traceability / static / frontend / PostgreSQL / Full-stack required checks。
- 独立 Review / re-review。
- guarded merge 到 main。
- Implementation merge 后 main-fresh CI。
- repository-native Change Archive。
- Issue #541 Acceptance/Closure。
- 不执行生产部署。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 |
| --- | --- |
| 主要风险 | 自动首屏回复增加最多当前 10 个根线程的本地评论读取；不产生 Provider 调用。 |
| 直接父级兼容 | 只接受 Provider 明确 nested/flat target；未知继续为空。 |
| 原作者兼容 | Provider 显式值优先；仅显式值缺失且两个账号身份均已收敛时推导相等关系。 |
| API / Schema | 不变。 |
| 数据迁移 | 不适用；历史已入库数据可直接从账号关系获得原作者显示改善。 |
| 依赖 | 不新增、不升级。 |
| 回滚 | revert Implementation PR；无数据迁移和不可逆副作用。 |

# 交付状态

- Requirement Source：Issue #541。
- Branch：`feature/541-voice-plaza-figma-comment-thread`。
- PR：#542，当前仍为 Draft；本 Change 已达到 `ready_for_review`，下一步转换 PR Ready 触发 current-head required CI。
- Merge / main-fresh / archive / closure：尚未执行，必须以实际平台证据为准。

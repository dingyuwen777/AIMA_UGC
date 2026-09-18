---
schema: coding-change/v1
id: CHG-20260918-230500-voice-plaza-figma-comment-thread
title: 声音广场 Figma 对齐与评论线程关系回归修复
level: L3
status: active
owner: dingyuwen777
branch: feature/541-voice-plaza-figma-comment-thread
created: 2026-09-18
updated: 2026-09-18
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
  - frontend/src/shared/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - backend/src/aima_ugc/adapters/providers/tikhub/mappers/
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - tests/
contracts:
  - Voice Plaza user-visible behavior
  - Content comments HTTP contract
data_changes:
  - none
---

# 变更摘要

- **需求来源**：GitHub Issue #541；用户要求按已验收 READY 的声音广场 Figma `qmZEFvPrB8u9JX5fyqc93S / 4627:7429` 实施前端并合并主分支，同时恢复详情评论的一级评论、二级回复和直接回复对象关系。
- **当前判断**：评论读取 Contract、PostgreSQL 查询和 Vue 线程渲染代码仍保留 `root_comment_id` / `parent_comment_id` / `parent_author_display_name`，且与 2026-09-13 已验证实现基本一致；最近五平台补采改动的全栈验收只断言回复文本，没有固定“回复谁”的关系。当前需要同时修复用户可见的懒加载体验并补跨层回归，继续排查真实采集数据是否丢直接父级。
- **设计边界**：Figma 负责布局、视觉、文案、状态与交互；真实 API / Store / generated client / PostgreSQL / Provider 语义继续以当前代码 Contract 为准。不得为复制示例数据发明接口或字段。

# 已确认事实与根因假设

1. 归档 Change `CHG-20260913-001143-comment-thread-voice-plaza` 明确验收过“根评论 + 缩进回复 + 回复对象 + 原作者”。
2. 当前 `content_queries.py` 的评论分页/父作者 Join 与上述已验收版本相同；HTTP Contract 仍返回根评论、直接父评论和父作者。
3. 当前 `ContentCommentSection.vue` 仍能渲染“回复 <父作者> / 回复该线程中的评论 / 回复这条一级评论”，但 Store 只在用户点击“查看 N 条回复”后请求回复。
4. PR #527 的五平台浏览器全栈覆盖回复文本，但没有断言直接父级关系，因此数据链关系回归存在测试盲点。
5. TikHub 各平台并非都能证明直接父评论：能够证明时必须保存；只能证明根线程时应降级，禁止猜造。
6. 辅助补采 UI 的“二级回复”默认关闭在 PR #527 之前就已存在；本 Change 不静默改成默认开启，避免未经决定扩大 Provider 费用。

# Requirement Traceability

| ID | Requirement | 来源 | 初始状态 | 计划证据 |
| --- | --- | --- | --- | --- |
| R1 | 按 READY Figma 实施声音广场视觉、文案、状态、响应式与交互 | #541 / 用户本轮要求 | not_satisfied | Design-to-Code diff + 浏览器回归 |
| R2 | 普通用户 UI 不暴露工程术语与技术详情 | #541 / Figma 基线 | not_satisfied | Vue 组件 + E2E |
| R3 | 已入库回复在详情中直接表达所属一级评论和可证明的回复对象 | #541 | not_satisfied | Store/组件/E2E |
| R4 | Mapper → PostgreSQL → HTTP 保留 root/direct-parent/parent-author | #541 | not_satisfied | 小红书纵切集成回归 |
| R5 | 五平台真实限制下不猜造直接父级 | #541 | not_satisfied | Mapper/组件降级测试 |
| R6 | 不改变 TikHub 二级回复默认采集费用行为 | #541 | satisfied | 代码审计 |
| R7 | PR current-head CI、Review、合并后 main fresh 验证通过 | #541 | not_satisfied | GitHub Checks / main SHA |

# 实施计划

1. 先增加评论关系回归测试，复现“必须点击才看到回复关系”和五平台全栈关系断言缺失。
2. 修声音广场 Store，在详情根评论返回后，对已入库回复数大于 0 的根评论有界预取首个回复页；保留后续分页按钮。
3. 若纵切测试证明 Mapper/持久化关系丢失，再只修真实根因；不对 Provider 未提供的直接父级做推断。
4. 按 Figma Owner 映射调整 Voice Plaza 页面、筛选、详情、AI 分析、导出及必要 Shared UI；移除普通用户工程细节，保持真实 Store/API/生成 Client 不变。
5. 执行目标测试、Lint/Typecheck/Build、两阶段 Review、PR Required Checks；通过后合并 main 并做 fresh-main 验证。

# 验证矩阵

| 层 | 要求 |
| --- | --- |
| Frontend unit/component | required：评论关系、自动首屏回复、Figma 产品文案 |
| Backend integration | required：小红书回复的 root/parent/parent-author 从 Mapper 入库到 Query |
| Browser mock E2E | required：打开详情无需额外点击即可看到首批回复关系 |
| Full-stack | required：补采 Worker → PostgreSQL → Voice Plaza 断言回复关系 |
| Static/build | required：frontend lint/typecheck/build；Python Ruff/Mypy 按受影响范围 |
| Review/CI | required：两阶段 Review + PR current-head + merge 后 main fresh |

# 风险与边界

- 不改 Schema/Migration，除非新增失败测试证明当前字段无法表达真实 Provider 关系。
- 不手改 generated client；Contract 未变时不重新生成。
- 不修改 TikHub 二级回复默认开关，不把测试 Fixture 当 Provider 全量事实。
- Figma 示例行数、数字、时间、品牌等不写成生产常量。
- 不部署生产环境。

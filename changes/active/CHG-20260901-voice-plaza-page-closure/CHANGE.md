---
schema: coding-change/v1
id: CHG-20260901-voice-plaza-page-closure
title: 声音广场页面动作与 VP5 验收收口
level: L2
status: in_progress
owner: codex
branch: main
created: 2026-09-01
updated: 2026-09-02
completion_gate: required
depends_on:
  - CHG-20260901-voice-plaza-taxonomy-filters
affected_areas:
  - frontend
  - content
  - analysis
  - reporting
  - figma-design-to-code
  - documentation
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/src/shared/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - tests/integration/content/
  - docs/
contracts: []
data_changes: []
---

# 背景与现状

声音广场已经具有列表/详情、Cursor、人工相关性复核、Analysis Run 预检/创建/进度/取消/历史，以及 selected/page/query Excel Export 和 Artifact 下载。本 Change 实施 VP3—VP5：以当前 Figma CURRENT 基线复核并补齐缺口，不重建第二套 Store/API/数据源，不改变已有公共 Contract 或异步语义。

# 目标

- 列表/详情完整展示 `voice_type`、全部标签、AI current/stale 与人工相关性来源。
- Normal/Loading/Empty/Error/Partial/Stale/AI 未配置及动作运行/失败状态可验收。
- 人工复核、Analysis Run、Export/Download 的选择、Hash、取消和错误 `request_id` 与真实后端一致。
- 完成 Browser Mock、Backend/PostgreSQL、Contract、少量 Full-stack、Build 和 Figma Conformance。

# 范围与非目标

Included：现有 Voice Plaza 页面、组件、Store/API 的定向补缺，现有后端能力回归，Figma CURRENT 节点与 VP5 完成定义审计。

Excluded：新 Schema/Migration、管理员配置页、车型、总数页码、第三方状态、自定义导出列、消息中心、外部 Provider Probe、无关重构和依赖升级。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 以当前 Figma CURRENT 列表/状态/详情/弹窗为正式基线 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3923:556-558 | satisfied | 复核 Normal/Loading/Empty/Error/Detail/Analysis/Export CURRENT 节点；八个筛选行和 Contract Note 已同步 |
| R2 | 展示 voice_type、完整标签、相关性来源和 AI current/stale | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | Table/Detail 组件与 Unit/Browser 回归覆盖 `voice_type`、全部有序标签及人工覆盖来源 |
| R3 | Normal/Loading/Empty/Error/Partial/Stale/AI 未配置可验收 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | 相关 Unit 与完整 42 条 Browser Mock Acceptance 通过 |
| R4 | Cursor 加载更多，不虚构总数/页码 | AGENTS.md | satisfied | 保留 `has_more/next_cursor`；页面与 Figma CURRENT 仅提供“加载更多” |
| R5 | 人工相关性复核保留 AI 原判与 request_id 错误反馈 | backend/src/aima_ugc/contracts/http.py | satisfied | API/Browser 回归通过，人工覆盖继续与 AI 原结果分离 |
| R6 | Analysis Run 保持 1—1000 选择、预检 Hash、创建、进度、取消和历史 | backend/src/aima_ugc/contracts/http.py | satisfied | 未改变既有 Contract/Store；Unit/Browser/Contract 回归通过 |
| R7 | Export 保持 selected/page/query、记录、Artifact 下载与权限边界 | backend/src/aima_ugc/contracts/http.py | satisfied | 未改变既有 Contract/Store；Browser 覆盖创建、历史、空查询禁用和保留期提示 |
| R8 | Future Backlog 保留在设计，不在生产页面伪实现 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3923:559 | satisfied | 反向能力审计未发现 Future 控件进入生产代码 |

# Validation Matrix

| 验证层 | 要求 | 计划证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Voice Plaza 与 Shared UI 目标测试 |
| Contract / Generated | required regression | 现有 Content/Analysis/Export 与新增 Taxonomy 漂移检查 |
| Backend/API/PostgreSQL | required | 查询、人工复核、Run、Export 生产调用链 |
| Browser Mock Acceptance | required | 全筛选、全部页面状态和动作反馈 |
| Real Full-stack Golden Path | required | 列表筛选及一个 Analysis/Export 关键路径 |
| External Provider Probe | not_applicable | 不改变 TikHub/LLM Provider 当前事实 |
| Build / Runtime | required | Frontend typecheck/test/build 与 API runtime |
| Docs / Governance / Figma | required | 六域 Conformance、完成定义、Ready Check 和质量门禁 |

# 实施步骤

- [x] 复核当前列表/详情/状态/动作与 Figma CURRENT 节点。
- [x] 为确认缺口建立 Red，最小修改 Feature/Shared Owner。
- [ ] 补齐 Browser Mock 与真实 Full-stack Golden Path。
- [x] 重新读取上游并执行正反向能力审计。
- [ ] 完成两阶段 Review、文档同步和全部 required 新鲜验证。

# Completion Audit

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [ ] unresolved_cleared

# 当前验证边界

Unit/Component、Contract/generated、完整 Browser Mock、Build、Figma Conformance 与文档/治理门禁已有本轮证据。Docker Desktop Linux Engine 未响应且本机没有 PostgreSQL/API 监听，因此 Backend/PostgreSQL Integration 与 Real Full-stack Golden Path 仍未验证；Change 继续保持 `in_progress`，不把 Browser Mock 写成真实全栈证明。

# 独立 Review 记录

以 base/current-base `4115e94df5d1bc46aa5ca28068c993424469ed57` 上的未提交 working tree 执行 Standard Review，并与依赖 Change 的 L3 Deep Review 联合审计。Figma CURRENT 八个列表态、详情、Analysis Preview、Export 状态与生产页面做正反向对照；代码范围内未发现新的 Finding。由于真实 PostgreSQL/Full-stack 未运行，Review 结论仍是“实现范围无 Finding、交付证据阻塞”，不是完整 VP5 PASS。

# 兼容、部署与回滚

本 Change 默认不改变公共 Contract、Schema、Migration 或依赖。页面可随应用版本回滚；不能删除历史 Content/Analysis/Review/Export 事实。若实现调查发现必须改变公共语义，先升级为 L3 或拆出独立 Change。

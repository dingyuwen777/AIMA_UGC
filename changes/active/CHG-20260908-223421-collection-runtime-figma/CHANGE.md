---
schema: coding-change/v1
id: CHG-20260908-223421-collection-runtime-figma
title: 采集运行中心 Figma 补齐与增量实施
level: L2
status: implementing
owner: codex
branch: feature/collection-runtime-figma-20260908
created: 2026-09-08
updated: 2026-09-08
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - collection
  - ingestion
affected_paths:
  - frontend/src/features/import-batches/
  - frontend/tests/
  - frontend/e2e/
  - docs/product/
  - docs/appendix/
contracts: []
data_changes: []
---

# 目标与边界

依据 Issue #391，先补齐采集运行中心关键 Figma 画板，再在现有 Vue 页面和子组件中增量实施；总体页面结构、公共侧栏、视觉层级不变，必要可用性修正同步到 Figma。用户已授权完整交付并在验收通过后合并 main。初始 main 为 87ff0ffad99299843d4ef3c44d2195a3cdd8aeac。

保留现有 Vue/Pinia/Feature API/生成 Client/Contract/持久 Job、所有合法输入和后台行为；无新依赖、公开 Contract、数据库或迁移变化，不部署、不进行真实付费 Provider 调用。用户原有 docs/guides/01_Figma与前端设计开发工作流.md 修改排除在本次提交外。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 补车型、逐平台参数及两种补采来源画板 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC1 | not_satisfied | 已定位正式画板及公共组件 Owner |
| R2 | 导入详情、冲突明细、现有撤销完整表达 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC2 | not_satisfied | 已确认 conflicts API/Store 与现有撤销服务 |
| R3 | 页面和浮层增量对齐 Figma，修正示例与说明 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC3 | not_satisfied | 已读取正式主页面 Design Context |
| R4 | 多尺寸表格和弹层操作可达 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC4 | not_satisfied | 基线已复现 1180/1280 详情按钮裁切 |
| R5 | 筛选确认、类型筛选、轮询分页和请求竞争正确 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC5 | not_satisfied | 基线已复现 40→20 与草稿筛选提交 |
| R6 | 保留既有业务与错误恢复，补真实冲突消费 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC6 | not_satisfied | 初始既有 10 项 Browser Mock 通过 |
| R7 | 分层验证、构建、设计对照与 CI | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC7 | not_satisfied | 按下方矩阵执行 |
| R8 | 双向 Figma 同步、审查及正式交付 | https://github.com/dingyuwen777/AIMA_UGC/issues/391 / AC8 | not_satisfied | 交付流程已获授权，未开始 Ready 判定 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Store 筛选/分页/迟到响应及组件状态回归 |
| 接口 / Contract | required | 保持现有 generated Client，生成漂移检查 |
| Backend/API/PostgreSQL | required | 复用当前导入与补采服务器边界，针对受影响消费的既有集成 |
| Browser Mock Acceptance | required | 车型/参数/来源/详情/冲突/撤销、错误与多尺寸几何 |
| Real Full-stack Golden Path | required | 使用隔离数据库完成少量真实 UI→API 导入/详情消费流程 |
| External Provider Probe | not_applicable | 本次不改变外部 Adapter/请求协议，不需付费调用 |
| Build / Runtime | required | 前端 lint/typecheck/test/build，正常页面运行 |
| Docs / Governance / Other | required | 定向产品文档、Figma 状态和设计对照、Completion/CI |

# 实施计划

1. Figma 既有表单/详情公共组件 → 补最小缺口并保持页面外形 → 实例、滚动、状态、截图复核。
2. 既有 Page/Filters/Table/Detail 与 Store → 差异驱动实现与缺陷修复 → Red/Green 回归和 Browser Mock。
3. 真实前后端关键流程与正式构建 → 验证接线和兼容 → 对照 Figma 当前画板。
4. 文档/审查/PR/CI → 同步必要设计差异 → guarded merge 与 main 验证、项目自动归档和收尾。

# 兼容、部署与回滚

只调整已有前端消费者和布局，不改变后端持久化、来源身份或撤销语义。保留 Route、API 与依赖版本。无需数据迁移；回滚本次前端提交恢复旧界面，数据继续由现有服务维护。实际生产部署不属于本次授权范围。

# Completion Audit

- [ ] upstream_re_read：Ready 前重读 Issue #391 和正式 Figma。
- [ ] change_coverage：逐项核验上游 AC，不以本 Change 自证。
- [ ] reverse_audit：后端能力→前端入口、前端动作→真实服务、列表→详情→结果完整。
- [ ] unresolved_cleared：所有实现与验证缺口完成后再进入 Ready。

# 初始证据与当前状态

2026-09-08 基线只读审查：既有 collection-runtime/data-import-policy Browser Mock 10 passed；四种宽度探针确认 1180/1280 操作裁切；40 条加载后轮询回到 20 条并提交草稿 search。当前 Figma 正式入口 3500:2025，Page 3500:2023；行为说明 4908:22991，响应式说明 4764:8874。

当前仍为实施中。首个提交用于追溯和早期 PR，不表示逻辑就绪；完成要求全部满足后再申请 Ready、合并和收尾。

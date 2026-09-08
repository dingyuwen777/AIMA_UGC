---
schema: coding-change/v1
id: CHG-20260908-192203-voice-plaza-figma
title: 声音广场 Figma 实施与全量排序
level: L3
status: implementing
owner: codex
branch: feat/voice-plaza-figma-20260908
created: 2026-09-08
updated: 2026-09-08
completion_gate: required
depends_on: []
affected_areas:
  - content
  - vehicles
  - frontend
affected_paths:
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - frontend/
  - migrations/
  - contracts/
  - tests/
  - docs/
contracts:
  - ContentListQuery
  - ContentListItemResponse
  - VehicleModelResponse
data_changes:
  - vehicle_models
---

# 目标与边界

上游需求为 Issue #389 和用户 2026-09-08 的按 Figma 直接实施决定。保留现有 Vue/Pinia/生成 Client/Service/Job 架构及锁定版本，增量实现后端排序、车型分组、声音广场界面和公共外壳。不得用示例数据或只对当前页排序代替真实能力；不部署、不合并。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 粉丝数和发布时间全量排序、空值置后、Cursor 绑定并兼容旧调用 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 | not_satisfied | 已新增失败的排序和 Cursor 测试 |
| R2 | 复用管理员车型目录并补 Figma 系列分组 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 | not_satisfied | 尚未实现 |
| R3 | 声音广场与无顶栏公共布局符合 Figma，保留现有业务与错误恢复 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 | not_satisfied | 前轮已完成有界差异审查 |
| R4 | 有数据页面跨 1180 至 2560 宽度无异常留白、裁切，操作可达 | https://github.com/dingyuwen777/AIMA_UGC/issues/389 | not_satisfied | 等待实际实现后验收 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Cursor、筛选、选择、弹层与目录 |
| 接口 / Contract | required | OpenAPI/生成 Client 与排序参数 |
| Backend/API/PostgreSQL | required | 排序/空值/同值/分页、车型持久关系 |
| Browser Mock Acceptance | required | 正常/加载/空/错、编辑/任务/导出与多尺寸 |
| Real Full-stack Golden Path | required | 管理车型与内容列表真实读写接线 |
| External Provider Probe | not_applicable | 复用落库数据和既有业务；不需要付费外部调用 |
| Build / Runtime | required | 类型检查和正式前端构建 |
| Docs / Governance / Other | required | 当前行为、兼容和交付记录 |

# 实施计划

1. Contract/查询/Cursor → 全量排序 → 单元与 PostgreSQL 边界验证。
2. 车型目录/Migration/管理入口 → 真实系列数据 → 目录和内容消费集成验证。
3. AppShell/声音广场组件与 Store → Figma 运行效果 → 目标浏览器行为和截图。
4. 生成物/文档/构建 → 兼容与完成复核 → 汇总新鲜证据。

# 兼容、部署与回滚

旧调用不传排序保留 coalesce(published_at,last_seen_at) 降序；新页面显式发布时间排序。新 Cursor 绑定排序，旧 Cursor 在原查询和有效期内继续可读。车型增量可空字段不要求修改既有 ID；先执行 Migration 后部署新代码，回滚先回旧代码，保留新字段数据。

# Completion Audit

- [ ] upstream_re_read：完成前重读 Issue 与用户目标。
- [ ] change_coverage：逐项核对实现、测试和文档。
- [ ] reverse_audit：检查已有能力未丢失，页面动作有真实支持。
- [ ] unresolved_cleared：全部必需项满足后才进入 Ready。

# 验证记录

- 初始 Red：tests/unit/content/test_content_cursor.py，4 failed / 1 passed。新增字段与排序身份尚不支持，失败符合预期；原签名防篡改用例通过。

---
schema: coding-change/v1
id: CHG-20260902-u5-product-capabilities
title: U5 可用状态、计数、导出列与站内通知
level: L3
status: in_progress
owner: codex
branch: main
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: [CHG-20260902-u2-content-vehicle-evidence, CHG-20260902-u3-admin-identity-config, CHG-20260902-u4-analysis-scheme]
affected_areas: [content, reporting, notification, identity, api, contracts, frontend, documentation]
affected_paths:
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/reporting/
  - backend/src/aima_ugc/modules/notification/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/product.py
  - backend/src/aima_ugc/contracts/http.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/voice-plaza/
  - frontend/src/app/layouts/AppShell.vue
  - tests/
  - docs/
contracts:
  - Content availability projection/observations
  - Content count summary
  - Versioned export column catalog and request snapshot
  - Principal inbox/read state
data_changes:
  - content_availability_observations
  - reporting_data_exports.columns
  - notification_events
  - notification_inbox_items
---

# 背景、目标与边界

U5 增加四个独立 Owner 的能力，不建万能任务表：Content 保存追加式第三方可用状态观察和查询 Count；Reporting 冻结安全列目录；Notification 从业务终态投影 Principal Inbox。Job/Content/Artifact 仍是业务事实源。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 只有 Provider 明确证据判定 confirmed；技术失败为 unknown/suspected | user:2026-09-02-recommended-decisions | satisfied | 追加观察与规范化状态 |
| R2 | 本地历史、Raw、Analysis 与证据长期保留 | user:2026-09-02-recommended-decisions | satisfied | 无级联删除能力 |
| R3 | Cursor 不变；有界范围 exact，大范围 estimated/none | user:2026-09-02-recommended-decisions | satisfied | 独立 Count Contract |
| R4 | 导出列使用后端白名单和版本，禁止任意数据库字段 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | column catalog + frozen snapshot |
| R5 | 通知按 Principal 建立 Inbox，不替代 Job/Artifact 权限 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | 事件与已读状态分离 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 可用状态归一化、count mode、列白名单、已读状态 |
| 接口 / Contract | required | 四组 additive API 与 generated client |
| Backend/API/PostgreSQL | required | 观察历史、Count、导出快照、Inbox 权限/幂等 |
| Browser Mock Acceptance | required | 状态/计数/列选择/消息中心工作流 |
| Real Full-stack Golden Path | required | 导出终态→通知→下载入口 |
| External Provider Probe | not_applicable | 未改变 Provider operation；不为状态模型额外付费调用 |
| Build / Runtime | required | 后端/Worker/frontend 构建 |
| Docs / Governance / Other | required | Owner、安全、保留和回滚同步 |

# Completion Audit

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [ ] unresolved_cleared

当前未清零项：Contract、列白名单、前端交互和静态 Schema 已验证，但 Availability/Count/Export Snapshot/Inbox 的真实 PostgreSQL Integration、Migration 与导出终态 Full-stack 仍受本机 Docker/PostgreSQL 不可用阻塞；逐 Provider 自动观察、生产估算源和个人列 Profile 按路线延期。本 Change 保持 `in_progress`。

# 本轮验证证据

- API/Contract/Unit 受支持范围：`866 passed, 8 skipped, 0 failed`；生成后 Contract 专项 `101 passed`；
- `unavailable_confirmed` 的 Provider 证据指针、截断 exact→none、列白名单/版本和 Principal Inbox 隔离已由 Contract/API/静态 Schema 测试覆盖；
- 声音广场 Count/Availability/导出列和 AppShell 通知入口已反向审计，前端 ESLint/typecheck、`67 passed` 与 production build 通过；
- 导出终态→通知→下载、Availability 历史和 Count 查询的真实数据库路径仍未运行，不能标记 Ready。

---
schema: coding-change/v1
id: CHG-20260902-u3-admin-identity-config
title: U3 Principal 权限与管理员配置中心
level: L3
status: done
owner: codex
branch: test/294-vp5-u1-u5-runtime-validation
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on:
  - CHG-20260902-u1-vehicle-catalog
affected_areas:
  - identity
  - system
  - vehicles
  - analysis
  - api
  - contracts
  - frontend
  - figma-design-to-code
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/identity/
  - backend/src/aima_ugc/modules/system/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/contracts/http.py
  - frontend/src/app/
  - frontend/src/features/admin-configuration/
  - tests/
  - docs/
contracts:
  - Principal/AuthContext
  - Current principal projection
  - Administrator authorization errors
data_changes: []
---

# 背景、目标与边界

第一版建立 Provider-neutral Principal/AuthContext 和后端管理员守卫，角色仅为 `administrator` 与 `user`。飞书只预留 Identity Adapter Port，用户后续单独接入；本 Change 不伪造飞书登录成功、不实现本地账号密码。开发运行使用显式 development identity 配置，生产仍不得宣称已有企业认证。

管理员配置中心提供车型/词包与 Analysis Scheme 的真实入口、权限态和审计历史，不在声音广场混入配置编辑器。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 身份源预留飞书，第一版不实际接入 | user:2026-09-02-identity-decision | satisfied | Provider-neutral Port + Feishu placeholder boundary |
| R2 | 角色仅管理员和普通用户 | user:2026-09-02-role-decision | satisfied | 后端角色枚举和路由守卫 |
| R3 | 第一版不强制双人审批 | user:2026-09-02-approval-decision | satisfied | publish 不要求第二 Principal |
| R4 | 发布、回滚和配置修改必须审计 | user:2026-09-02-approval-decision | satisfied | 同事务追加 audit_events |
| R5 | 管理员配置是独立页面，不与声音广场混合 | docs/roadmap/04_业务目录内容查询与AI配置中心实施路线.md | satisfied | 独立 Route/Feature/Figma Section |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Principal、角色、Route guard、权限态 |
| 接口 / Contract | required | me/403/Error Contract/generated client |
| Backend/API/PostgreSQL | required | 管理员守卫与审计原子性 |
| Browser Mock Acceptance | required | 管理员/普通用户页面与动作 |
| Real Full-stack Golden Path | required | development Principal→管理员配置→审计 |
| External Provider Probe | not_applicable | 飞书尚未接入，不能伪造 Probe |
| Build / Runtime | required | API/frontend build |
| Docs / Governance / Figma | required | Figma READY/Conformance 与认证边界说明 |

# Completion Audit

- [x] upstream_re_read：已重新读取角色、飞书预留、审计决定、正式路线、实现与最终验证事实。
- [x] change_coverage：Principal、两类角色、后端权限、管理员页面、审计和 Figma 基线均有证据。
- [x] reverse_audit：已从管理员与普通用户入口反查后端守卫、事务审计和真实全栈结果。
- [x] unresolved_cleared：飞书真实认证按确认范围延期，其余 Required 项均已满足，无 `not_satisfied`。

当前无语义未决项：本地 required 验证与独立 Review 已完成，飞书真实认证按已确认范围延期。

# 本轮验证证据

- API/Contract/Unit 受支持范围：`866 passed, 8 skipped, 0 failed`；普通用户对车型、Scheme、词包、相关性和采集计划写操作的后端 403 已覆盖；
- 管理员独立路由、普通用户导航隐藏、Principal Inbox 和配置四个 Tab 已反向审计，前端 ESLint/typecheck、`67 passed`、production build 通过；
- Figma 管理员车型、Scheme、状态板节点及 37 个公共组件实例已完成结构/溢出/字体/复用 QA，状态记录在 `figma-state.json`；
- 飞书只有 Provider-neutral Adapter Port，没有虚构登录、回调、Session 或生产认证；PostgreSQL 管理操作审计事务已通过 Integration，管理员创建车型→读取审计已通过 Real Full-stack。

# 交付完成证据

- PR #289 已把 U1–U5 前端与文档接线合并到 `main`（merge commit `b5622e2308193da4bb6878672944f38938bf46d5`）；PR #295 又完成恢复验证与基线修复（merge commit `f60f598c84e0696873cc01fc30f4d817ed51ae52`）；
- `main` 的 CI run #33589659720 与 Runtime Acceptance run #33589659537 均成功，覆盖产品、PostgreSQL、真实浏览器和 Compose 门禁；
- 本 Change 的实现、验证、Review、合并与 main 新鲜验证已闭环，因此转为 `done` 并归档。

---
schema: coding-change/v1
id: CHG-20260930-170805-frontend-transitive-security
title: 更新前端传递依赖安全补丁版本
level: L2
status: done
owner: assistant
branch: fix/frontend-transitive-security
created: 2026-09-30 17:08:05 +08:00
updated: 2026-09-30
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - dependency-security
  - testing
affected_paths:
  - frontend/package-lock.json
contracts: []
data_changes: []
---

# 变更摘要

PR #680 的 current-head CI 因 npm 新增高危公告失败。建立独立安全修复，只把当前锁文件中的五个传递依赖解析更新到现有版本范围允许的安全补丁，不修改直接依赖声明或产品代码。

# 背景、现状与问题

`main@784306e3` 的 `frontend/package-lock.json` 解析到 `brace-expansion` 2.1.4 / 5.0.9、`fast-uri` 3.1.7 和 `markdown-it` 14.3.0。GitHub Advisory 于 2026-09-29 更新后，正式 `npm audit --audit-level=high` 报 1 high / 2 moderate，阻断所有触发完整前端审计的 PR。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 影响 |
| --- | --- | --- | --- |
| E1 | `brace-expansion` 当前版本命中 High DoS 公告 | GHSA-qhr7-859c-m2p7；PR #680 job 109814876260 | required audit 失败 |
| E2 | `fast-uri` 3.1.7 命中 URL host 规范化公告 | GHSA-hrr3-gc8f-f4qj | 需要更新到 3.1.8 |
| E3 | `markdown-it` 14.3.0 命中 linkify 二次复杂度公告 | GHSA-253c-mchw-3w2r | 需要更新到安全 14.x 补丁 |
| E4 | npm dry-run 只更新五个传递解析，不增删包或修改直接依赖 | `npm audit fix --dry-run --json` | 可使用锁文件最小修复 |

# 目标、成功标准与非目标

- [x] 只调整传递依赖补丁解析，不修改 `frontend/package.json`。
- [x] `npm ci` 后 audit 无 high/critical，三个当前公告全部清零。
- [x] 前端 lint、单元、类型/构建和 E2E 保持通过。
- [ ] 经独立 Review、PR required checks、精确 head 合并和 main-fresh 收口。

非目标：直接依赖、Node/npm、Python、框架升级；产品代码、Contract、Schema/Migration、部署或生产数据修改。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 施工单元 | 使用独立 Issue #681、Change、分支和 PR | 项目依赖升级规则 | 不污染 #679 / PR #680 的功能追溯 |
| 更新范围 | 只接受 npm dry-run 列出的补丁解析 | E1-E4 | 不升级直接依赖或新增包 |
| 安全门槛 | 至少 high/critical 清零，同时记录全部三个公告结果 | #681 AC2 | 不通过 audit 绕过或忽略公告 |
| 兼容验证 | 干净安装、前端全套验证和正式 CI | #681 AC3-AC4 | 证明工具链行为未回归 |

# 修改方案与决策依据

使用锁定 npm 执行 `npm audit fix --package-lock-only`，检查 diff 只含预期五个传递依赖版本与 integrity 更新。随后用 `npm ci` 重建干净依赖，执行 audit、lint、Vitest、typecheck/build 和 Playwright。任何直接依赖、包数量或非锁文件变化都视为范围外并停止。

## 备选方案与取舍

- 忽略 audit 或使用管理员 bypass：拒绝，违反 required check 与安全门禁。
- 在 PR #680 中直接改锁文件：拒绝，混合内容打标与依赖升级追溯。
- 升级 Orval、TypeDoc、ESLint 或 Vue 工具链：拒绝，超出补丁修复所需范围。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 五个传递解析更新到 npm 当前建议的安全补丁，直接依赖不变 | #681#AC1 | satisfied | 锁文件 diff 仅包含 `brace-expansion` 2.1.4→2.1.7（两处）、5.0.9→5.0.12、`fast-uri` 3.1.7→3.1.8、`markdown-it` 14.3.0→14.3.2；`frontend/package.json` 无差异 |
| R2 | audit 无 high/critical，三个公告清零 | #681#AC2 | satisfied | 干净 `npm ci` 审计 392 个包并报告 0 vulnerabilities；随后 `npm audit --audit-level=high` 报 0 vulnerabilities |
| R3 | 前端静态、单元、构建和 E2E 通过 | #681#AC3 | satisfied | ESLint 通过；Vitest 36 files / 271 tests 通过；Vue/TypeScript typecheck 与 Vite build 通过；Playwright 170 tests 通过 |
| R4 | Review、required CI、合并、main-fresh、归档和 Closure | #681#AC4 | explicitly_deferred | 实现后完成 Review；PR/merge 后证据按生命周期取得，不豁免任何门禁 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| `frontend/package-lock.json` | 更新五个传递依赖解析与对应 integrity | 清除当前三个安全公告 | R1-R2 |
| 本 Change | 冻结证据、验证和交付边界 | 满足独立依赖升级追溯 | R1-R4 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 依赖安全 | required | 干净 `npm ci`；`npm audit --audit-level=high`；完整 audit 摘要 |
| 前端单元 | required | ESLint；Vitest 全量 |
| 构建 | required | TypeScript/Vue typecheck；Vite production build |
| 用户工作流 | required | Playwright E2E 全量 |
| 后端 / 数据 | not_applicable | 不修改后端、Contract、Schema/Migration 或数据 |
| 治理 / 交付 | required | Change Ready、独立 Review、PR current-head CI、guarded merge、main-fresh、原生归档、Issue Closure |

# 风险、兼容性、迁移与回滚

风险仅在传递补丁与现有前端工具链兼容性；通过干净安装和全套前端验证控制。无公共 Contract、数据或部署变化。回滚时恢复安全 PR 的锁文件提交；回滚会重新暴露已确认公告，因此只能作为异常定位手段，不能作为长期状态。

# 文档、依赖、部署与发布影响

- **文档**：安全事实由 #681 与本 Change 维护；不改产品文档。
- **依赖**：只更新锁文件中的传递补丁解析；直接依赖清单不变。
- **部署 / Release**：不执行部署或 Release；后续构建会使用新锁文件。
- **数据 / Migration**：不适用。

# 完成审计

- [x] upstream_re_read：已重读 #681、PR #680 audit 日志、当前 package manifest/lock 和三个 GitHub Advisory。
- [x] change_coverage：AC1-AC4 已映射到锁文件、安全审计、全套前端验证和交付生命周期。
- [x] reverse_audit：从三个告警反查五个锁文件节点与上游依赖链；没有直接依赖或产品运行时代码修改需求。
- [x] unresolved_cleared：R1-R3 已完成；R4 的 PR/merge 后证据按生命周期明确延期，不存在未说明的 `not_satisfied` 要求。

# 完成证据与状态

已完成锁文件最小安全更新和本地验证：

- `npm audit fix --package-lock-only` 只改动五个预期传递依赖解析，`frontend/package.json` 保持不变；
- 干净 `npm ci` 安装 391 个包、审计 392 个包，报告 `found 0 vulnerabilities`；
- `npm audit --audit-level=high` 报告 `found 0 vulnerabilities`；
- ESLint 通过；Vitest 36 个测试文件、271 个测试通过；
- Vue/TypeScript 类型检查和 Vite production build 通过；
- Playwright 全量 170 个测试通过，用时 2.5 分钟。

当前已具备独立 Review 条件；PR current-head CI、guarded merge、main-fresh、归档与 Issue Closure 继续按 R4 的交付生命周期取得证据。

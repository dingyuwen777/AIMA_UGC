---
schema: coding-change/v1
id: CHG-20260923-092000-actions-hygiene-targeted-pagination
title: Actions Hygiene 改为 stale Workflow ID 定向分页
level: L3
status: in_progress
owner: dingyuwen777
branch: fix/actions-hygiene-targeted-pagination
created: 2026-09-23
updated: 2026-09-23
completion_gate: required
depends_on:
  - CHG-20260923-063501-actions-hygiene
  - CHG-20260923-171000-actions-history-cleanup
affected_areas:
  - ci
  - github-actions
  - maintenance
affected_paths:
  - scripts/quality/actions_hygiene.py
  - tests/unit/test_actions_hygiene.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts:
  - GitHub Actions Hygiene
data_changes: []
---

# 变更摘要

- **要解决的问题**：#576 已把长期 Actions Hygiene 合入 main，但 main-fresh 首次真实执行发现当前实现每次完整扫描仓库 3.6 万级 Actions runs 两次，重复引入 #573 已经实测淘汰的高成本方案。
- **拟议修改**：复用 #573 已验证模型：完整分页 repository workflow records，只对 stale workflow ID 定向分页 runs；无 stale record 的普通 main push 不再读取全仓 runs。
- **预期结果**：保持 #575 的全部安全边界，同时把正常运行成本从 O(全仓历史 runs) 收敛为 O(workflow records + stale workflow runs)。

# 背景、现状与问题

## 背景

Requirement Source：Issue #575。PR #576 已合并长期 Hygiene，但 #573 的归档 Change 已明确记录：AIMA repository metadata 当时已有 36,626 条 Actions runs，全量 runs paginate 的 Ready CI 曾“长时间无删除进展”，随后改用 stale workflow ID 定向分页才成功删除 323 条旧 runs。

## 当前现状

- 当前 repository Actions runs total_count 再次确认约 36,369。
- #576 main-fresh CI #5523 的产品 Gate 均 Green，但 Actions Hygiene 长时间停留在 Reconcile obsolete workflow history。
- 原实现每次 main push 调用全仓 runs 分页两次，即使当前没有 stale Workflow 也支付相同成本。
- #573 已提供平台事实：repository workflows API 可枚举 deleted/stale workflow records，并可按 workflow ID 定向查询 runs。

## 问题、根因或约束

安全判定正确不等于长期实现可接受。对 3 万级历史每个 main push 做两次全量分页会消耗大量 GitHub REST 配额和 Runner 时间，也与上游已验证经验冲突。

## 不修改的后果

每次 main push 都可能额外发起数百次 Actions runs API 请求；仓库历史越长，Hygiene 越慢，最终可能命中 rate limit 或长期占用 Runner。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 决策 |
| --- | --- | --- | --- |
| E1 | 当前约 36,369 Actions runs | Actions runs metadata | 禁止 normal push 全仓分页 |
| E2 | #573 已淘汰全仓 runs paginate | 归档 V5/V6 | 复用成熟定向模型 |
| E3 | deleted workflow 可按 workflow ID 查询 runs | #573 V7 | stale workflow ID 是稳定定向 Owner |
| E4 | #576 产品/Runtime pre-merge CI Green | CI #5522 / Runtime #2528 | 性能纠正不需要改变产品 Gate |

## 推断与待确认

- 待 current-head CI 证明新的定向算法、Ruff、unit/contract 全 Green。
- 待 main-fresh 证明干净基线时 Actions Hygiene 快速完成，输出 candidates=0 或只处理真实 stale workflow IDs。

# 目标、成功标准与非目标

## 目标

保留长期自动清理能力，同时消除每次 main push 对全仓历史 runs 的扫描。

## 成功标准

- [ ] AC1：只完整分页 repository workflow records，不调用全仓 actions/runs 列表接口。
- [ ] AC2：current path 与 PR-only/main-history 保护规则保持。
- [ ] AC3：仅对 stale workflow ID 定向完整分页 runs。
- [ ] AC4：stale workflow 有 active run 时整条跳过；completed-only 才删除。
- [ ] AC5：删除后逐 stale workflow ID 读取 total_count；404 视为 retired=0，非零硬失败。
- [ ] AC6：429/5xx/network 才是 temporary exit 75；权限/结构/历史/readback 仍硬失败。
- [ ] AC7：AIMA 仍只有 6 个长期 Workflow，CI job-level actions:write 结构不变。
- [ ] AC8：Review、CI、merge、main-fresh、archive、#575 closure 完整闭环。

## 范围

仅 Actions Hygiene 脚本、专属测试和 Blueprint 性能/生命周期事实。

## 非目标

- 不修改 6 个正式 Workflow 职责。
- 不修改产品、数据库、API、部署或 Release。
- 不新增外部服务、状态数据库或第 7 个 Workflow。

## 必须保持不变

main-only + CI Gate、job-level actions:write、current/main-history/active-run 安全边界保持。

# 约束与意图决策

| 维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 候选来源 | repository workflow records | E2/E3 | 小集合 |
| run 快照 | 只按 stale workflow ID 分页 | E1-E3 | 成本与 stale 数量相关 |
| 404 | deleted workflow retired 视为 0 | #573 V8/V9 | 幂等 |
| 临时失败 | 只限 429/5xx/network | #575 安全边界 | 不吞权限/逻辑缺陷 |
| 回滚 | 可回滚代码；已删 run 不可恢复 | GitHub 平台事实 | 保守删除 |

# 修改方案与决策依据

## 最小充分方案

1. list_repository_workflows 完整分页 workflows endpoint。
2. current path + first-parent main history 选择 stale records。
3. list_workflow_runs 只按 stale workflow ID 分页；无 stale record 时不访问任何 runs 列表。
4. active preflight 后只删除 completed stale runs。
5. workflow_run_count 逐 ID fresh readback；404=retired=0，remaining>0 硬失败。
6. tests 明确断言请求包含 actions/workflows/<id>/runs，且不包含全仓 actions/runs? 列表扫描。
7. main-fresh 验证真实 GitHub API。

## 证据到决策

| 决策 | 证据 | 原因 |
| --- | --- | --- |
| D1 定向 workflow ID | #573 V6/V7 | 已在同仓实测有效 |
| D2 不做全仓 readback | E1 | 全仓历史会持续增长 |
| D3 保留 first-parent main history | #575 | 继续保护 PR-only workflow |
| D4 hard/transient 分流 | #575 | maintenance 波动不等于逻辑缺陷 |

<!-- governance:required-for=L3 -->
## 备选方案与取舍

- 继续全仓分页：已被 #573 和 #5523 真实证据否决。
- 固定 stale ID allowlist：不能自动覆盖未来删除。
- 外部状态库：过度工程。
- 定时批处理：不能解决每次 workflow deletion 的自动收尾。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 禁止全仓 runs 扫描 | 本 Change AC1 | not_satisfied | 待 current-head tests |
| R2 | stale workflow 定向分页 | AC2-AC5 | not_satisfied | 待 tests |
| R3 | 错误语义保持严格 | AC6 | not_satisfied | 待 tests |
| R4 | Workflow 结构不变 | AC7 | satisfied | 不修改 ci.yml |
| R5 | 完整交付 | AC8 | not_satisfied | downstream |

# 计划改动

| 文件 | 修改 | 原因 |
| --- | --- | --- |
| scripts/quality/actions_hygiene.py | stale workflow ID 定向 API | 性能与 API 配额 |
| tests/unit/test_actions_hygiene.py | 定向端点与安全回归 | 防止退化 |
| docs/blueprint/06_开发约束与分阶段实施.md | 记录 3 万级历史约束 | 长期事实 |

- [x] 调查当前实现和事实源
- [x] 建立验证矩阵
- [x] 建立性能失败证据
- [x] 完成最小实现
- [x] 同步长期文档
- [ ] 取得 current-head 验证证据
- [ ] 完成需求追溯和完成审计

# 验证矩阵

| 层 | 是否要求 | 范围 |
| --- | --- | --- |
| unit | required | stale selection / targeted endpoint / delete/readback |
| contract | required | 禁止 global runs scan |
| CI | required | Ruff + unit + existing AIMA gates |
| real API | required | main-fresh Actions Hygiene |
| product build | not_applicable | 无产品变化 |
| docs/governance | required | Blueprint + Change |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 |
| --- | --- |
| 主要风险 | workflow records API 若漏掉仍有历史 run 的 deleted workflow，会推迟清理；平台已有 #573 同仓证据支持当前语义 |
| 兼容性 | #575 全部安全边界保留 |
| Migration | 不适用 |
| 回滚 | 代码可回滚；run 删除不可恢复 |

# 文档、依赖、部署与发布影响

- 无新增依赖、Secret、Schema 或 Release 变化。
- Blueprint 只更新当前项目 CI 事实。
- 仍复用现有 CI，不新增长期 Workflow。

# 完成审计

- [ ] upstream_re_read：Ready 前重读 #575、#573 archive、#576 archive、current main。
- [ ] change_coverage：AC1-AC7 current-head 清零；AC8 downstream。
- [ ] reverse_audit：workflow records → main history → stale IDs → targeted runs → DELETE → per-ID readback。
- [ ] unresolved_cleared：性能和安全 Finding 清零。

# 完成证据与状态

## 新鲜证据

| 证据 | 环境 | 结果 | 证明 |
| --- | --- | --- | --- |
| V1 | current AIMA metadata | total_count≈36,369 | 全仓扫描成本高 |
| V2 | #573 archive V5-V9 | targeted workflow ID Green | 上游成熟方案 |
| V3 | #576 main-fresh #5523 | product gates Green，Hygiene 长时间 running | 当前实现真实性能问题 |

## 未验证内容与剩余风险

待 current-head CI 与修复后 main-fresh。

## 交付状态

- Branch：fix/actions-hygiene-targeted-pagination
- PR：未创建
- Merge：未执行
- Issue #575：保持 open

## 备注

本 Change 是 #575 同一需求的性能/治理纠正，不新建重复 Issue。
---
schema: coding-change/v1
id: CHG-20260923-091500-actions-hygiene-scale
title: Actions Hygiene 定向扫描优化
level: L3
status: in_progress
owner: dingyuwen777
branch: maintenance/actions-hygiene-scale
created: 2026-09-23
updated: 2026-09-23
completion_gate: required
depends_on:
  - CHG-20260923-063501-actions-hygiene
affected_areas:
  - ci
  - github-actions
  - maintenance
affected_paths:
  - scripts/quality/actions_hygiene.py
  - tests/unit/test_actions_hygiene.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts:
  - GitHub Actions Hygiene v2
data_changes: []
---

# 变更摘要

- **问题**：首版长期 Hygiene 在 AIMA 36,369 条 Actions runs 上执行仓库级双扫描，main-fresh 清理 Job 长时间占用 Runner，不适合作为每次 main push 的长期能力。
- **修改**：改为先读取 repository workflow records，选出 current main 已不存在且 first-parent 历史真实拥有过的 stale workflow ID，再仅分页这些 workflow ID 的 runs；删除后逐 workflow ID 读取 total_count 做 fresh readback。
- **预期结果**：保持原安全边界，但正常干净基线只读取少量 workflow records，不扫描 3.6 万条正式历史。

# 背景、现状与问题

Requirement Source：Issue #575。PR #576 已把首版能力合并到 main，并通过 PR CI/Runtime Acceptance；首次 main-fresh 真实运行显示 Actions Hygiene 在 36,369 条历史 runs 上执行全量扫描，性能明显不可接受。PR #573 的一次性清理已经验证：GitHub repository workflows API 会暴露带历史 runs 的 deleted workflow record，可按 workflow ID 定向读取 runs，清空后 404/total_count=0 可作为退休/清零语义。

# 事实与证据

| 证据 | 事实 | 决策 |
| --- | --- | --- |
| E1 | AIMA Actions runs total_count=36,369 | 不允许每次 main push 全量双扫描 |
| E2 | PR #573 真实删除 323 stale runs | workflow ID 定向算法已经过仓库真实验证 |
| E3 | 当前 main 6 个 Workflow 均有效 | current path 继续绝对保护 |
| E4 | #576 main-fresh Core/Runtime Green，但 Hygiene 长时间运行 | 性能是当前唯一未闭环问题 |

# 目标与成功标准

- [ ] AC1：不再访问 repo-wide /actions/runs 分页接口做全量扫描。
- [ ] AC2：先枚举 repository workflows；current path 绝对保护，PR-only/non-main-history 继续跳过。
- [ ] AC3：只对 stale workflow ID 定向分页 runs；任一 active run 仍整条 workflow 跳过。
- [ ] AC4：DELETE 后逐 stale workflow ID fresh readback；404 视为 retired/0，非 404 错误保持原临时/硬失败语义。
- [ ] AC5：干净基线输出 candidate=0 / targeted_runs=0 / remaining=0，并在合理时间内结束。
- [ ] AC6：CI Job 权限、main-only、CI Gate dependency、6 个正式 Workflow 数量保持不变。
- [ ] AC7：current-head CI/Review/merge/main-fresh/archive/#575 closure 完整闭环。

# 非目标

- 不改变 #576 已建立的权限和触发边界。
- 不新增 Workflow、Secret、定时任务或外部服务。
- 不清理当前 6 个 Workflow 的历史 runs。
- 不改变产品、数据库、API 或部署逻辑。

# 修改方案

1. 用 repository workflows API 枚举 workflow records。
2. 对 record path 做 current paths + first-parent main history 双判定。
3. 仅针对 stale workflow ID 调用 workflow-specific runs endpoint。
4. active preflight 不变；只删除 completed。
5. 删除后按 workflow ID 查询 total_count；404=retired/0。
6. 测试明确断言“禁止回退到 repo-wide actions/runs 扫描”。

# 需求追溯

| 编号 | 要求 | 状态 |
| --- | --- | --- |
| R1 | 定向 workflow-record 枚举 | not_satisfied |
| R2 | current/main-history 安全边界保持 | not_satisfied |
| R3 | stale workflow ID 定向 runs | not_satisfied |
| R4 | active skip / fresh per-ID readback | not_satisfied |
| R5 | 不改变 CI 权限/触发/Workflow 数量 | not_satisfied |
| R6 | 真实 main-fresh 快速完成 | not_satisfied |
| R7 | 完整交付 | downstream |

# 验证矩阵

- unit：current/stale/PR-only/active/completed。
- API contract：repository workflows endpoint、workflow-id runs endpoint、404 retired。
- regression：禁止 repo-wide /actions/runs? 分页。
- CI：AIMA full required CI + Runtime Acceptance。
- main-fresh：Actions Hygiene success，读取 JSON 结果并验证 candidate/targeted/deleted/remaining。

# 风险与回滚

删除 Actions runs 不可逆，因此只优化发现路径，不放宽任何删除条件。代码可 revert；已经删除的 run 不可恢复。API/历史/返回格式异常继续 fail closed，仅 429/5xx/临时网络错误允许 exit 75 后 warning 重试。

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 完成证据与状态

## 新鲜证据

- V1：AIMA Actions API total_count=36,369，首版全量扫描规模不合格。
- V2：PR #573 历史证据证明 stale workflow ID 定向查询/删除/404 retired 可用。

## 交付状态

- PR：未创建
- CI：未执行
- merge/main-fresh/archive/closure：未执行

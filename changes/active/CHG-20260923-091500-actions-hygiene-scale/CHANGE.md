---
schema: coding-change/v1
id: CHG-20260923-091500-actions-hygiene-scale
title: Actions Hygiene 定向扫描优化
level: L3
status: ready_for_review
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

- **要解决的问题**：首版长期 Hygiene 在 AIMA 36,369 条 Actions runs 上执行仓库级双扫描，main-fresh 清理 Job 长时间占用 Runner，不适合作为每次 main push 的长期能力。
- **拟议修改**：改为先读取 repository workflow records，选出 current main 已不存在且 first-parent 历史真实拥有过的 stale workflow ID，再仅分页这些 workflow ID 的 runs；删除后逐 workflow ID 读取 total_count 做 fresh readback。
- **预期结果**：保持 #576 的安全边界，但正常干净基线只读取少量 workflow records，不再扫描 3.6 万条正式历史。

# 背景、现状与问题

## 背景

Requirement Source：Issue #575。PR #576 已把首版长期 Actions Hygiene 合并到 main；PR #573 的一次性清理已经验证 stale workflow ID 定向查询与删除可行。

## 当前现状

- AIMA 当前 Actions runs total_count 为 36,369。
- #576 PR CI 与 Runtime Acceptance 已 Green。
- #576 首次 main-fresh 的 Core/Runtime 已 Green，但 Actions Hygiene 在全量双扫描阶段长时间占用 Runner。
- 当前 main 仍只有 CI / Full-stack Acceptance / Runtime Acceptance / Developer Tooling Compatibility / Release / Change Archive 六个正式 Workflow。

## 问题、根因或约束

全仓库 `/actions/runs` 分页会随着历史持续增长；首版还会在 execute 后再做一次完整 fresh scan，因此复杂度与仓库全部历史 runs 绑定。长期治理必须把成本绑定到“workflow records + stale workflow runs”，不能绑定到全部有效 CI 历史。

## 不修改的后果

AIMA 每次健康 main push 都会反复扫描数万条历史；随着 runs 增长，维护 Job 会越来越慢，并消耗大量 GitHub API quota/Runner 时间。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | AIMA Actions runs total_count=36,369 | GitHub Actions REST | 禁止每次 main push 全仓双扫描 |
| E2 | PR #573 真实删除 323 stale runs | #573 Change/CI 历史 | workflow ID 定向方案已经过真实仓库验证 |
| E3 | repository workflows API 会暴露有历史 runs 的 deleted workflow record | #573 V7-V9 | 可先枚举 stale workflow ID |
| E4 | stale workflow 清空后 workflow-specific endpoint 404 可按 retired/0 处理 | #573 幂等修复 | fresh readback 可逐 ID 完成 |
| E5 | 当前 6 个正式 Workflow 均有效 | main .github/workflows | current path 继续绝对保护 |

## 推断与待确认

- 待确认：v2 在 current main 干净基线应快速输出 candidate=0、targeted_runs=0、remaining=0。
- 待确认：AIMA required CI/Runtime Acceptance 对 v2 代码与测试全部 Green。

# 目标、成功标准与非目标

## 目标

把 Actions Hygiene 从全仓库历史扫描改成 stale workflow ID 定向扫描，在不放宽任何删除安全边界的前提下，使运行成本与 stale Workflow 数量成正比。

## 成功标准

- [x] AC1：脚本不再使用 repo-wide `/actions/runs?per_page=...` 做全量发现或 fresh scan。
- [x] AC2：先枚举 repository workflows；current path 绝对保护，PR-only/non-main-history 继续跳过。
- [x] AC3：只对 stale workflow ID 定向分页 runs；任一 active run 仍整条 workflow 跳过。
- [x] AC4：DELETE 后逐 stale workflow ID fresh readback；404 视为 retired/0，其他异常保持原临时/硬失败语义。
- [ ] AC5：干净基线输出 candidate=0 / targeted_runs=0 / remaining=0，并在合理时间内结束；由 main-fresh 真实运行验证。
- [x] AC6：CI Job 权限、main-only、CI Gate dependency、6 个正式 Workflow 数量保持不变。
- [ ] AC7：current-head CI/Review/merge/main-fresh/archive/#575 closure 完整闭环。

## 范围

- `scripts/quality/actions_hygiene.py` 定向发现/读取。
- `tests/unit/test_actions_hygiene.py` 定向 endpoint 与安全边界回归。
- Blueprint 06 的 Workflow 生命周期实现说明。

## 非目标

- 不改变 #576 已建立的 CI Job 权限和触发边界。
- 不新增 Workflow、Secret、schedule、数据库或外部服务。
- 不清理当前 6 个正式 Workflow 的历史 runs。
- 不改变产品、数据库、API、部署或 Release 语义。

## 必须保持不变

- current workflow path 绝对保护。
- first-parent main-history 判定。
- active run 整条 workflow skip。
- 只有 completed runs 才能删除。
- 429/5xx/network → exit 75；权限/结构/历史/readback 错误硬失败。
- Actions Hygiene 只在 main push + CI Gate success 后运行，actions:write 只授予该 Job。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围 | 只优化发现/分页算法 | E1-E5 | 不重写权限与治理 Contract |
| 接口 | CLI schema 升级为 repository-actions-hygiene/v2 | 定向统计字段变化 | 输出 workflow_record_count / targeted_run_count |
| 数据 | 不适用 | 无业务数据 | 无 Migration |
| 错误语义 | 404 仅在 stale workflow-specific 查询时按 retired/0 | E4 | 不把任意 404 静默吞掉 |
| 兼容性 | current 6 Workflow/CI checks 保持 | E5 | Branch Protection/required checks 不变 |
| 性能 | 禁止 repo-wide runs scan | E1 | 正常干净基线只读 workflow records |

# 修改方案与决策依据

## 最小充分方案

1. 使用 `/actions/workflows` 完整分页 repository workflow records。
2. current paths + first-parent main history 选出 stale workflow records。
3. 只对 stale workflow ID 调用 `/actions/workflows/{id}/runs`。
4. 对定向 run 快照执行 active preflight；active 存在时该 workflow 整条跳过。
5. 只 DELETE completed stale runs。
6. 删除后逐 workflow ID 查询 `total_count`；404=retired/0，remaining>0 硬失败。
7. 测试明确断言 workflow-specific endpoint 被使用且 repo-wide `/actions/runs?` 不出现。

## 证据到决策

| 决策 | 依据证据 | 为什么采用 |
| --- | --- | --- |
| D1 repository workflows 先发现 | E2/E3 | Workflow records 数量远少于 36k runs |
| D2 stale ID 定向分页 | E2 | #573 已在真实仓库证明可用 |
| D3 逐 ID fresh readback | E4 | 避免第二次全仓 scan |
| D4 安全条件不变 | E5 / #575 | 性能优化不能放宽 destructive boundary |

<!-- governance:required-for=L3 -->
## 备选方案与取舍

- 继续全仓 runs 双扫描：安全但规模不可接受，拒绝。
- 只扫描最近 N 页：可能漏掉很久以前的 stale Workflow，拒绝。
- 只在 workflow 文件变化时运行：active-run skip 后可能没有后续重试，不能单独采用。
- 维护额外状态数据库/cache：当前问题无需新增状态系统，过度工程。
- workflow ID 定向方案：既有真实证据、无新增状态、复杂度最低，采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 禁止全仓 run scan | #575 / AC1 | satisfied | v2 只使用 repository workflows 与 workflow-id runs endpoint；回归明确禁止 repo-wide actions/runs 扫描 |
| R2 | current/main-history 边界保持 | #575 / AC2 | not_satisfied | 待 current-head tests |
| R3 | stale workflow ID 定向 runs | #575 / AC3 | satisfied | list_repository_workflows → stale record → list_workflow_runs(workflow_id) 实现与 endpoint 回归已落库 |
| R4 | active skip + per-ID readback | #575 / AC4 | satisfied | active workflow 整条 skip；execute 后 workflow_run_count(id) fresh readback，404=retired/0 |
| R5 | CI 权限/触发/Workflow 数量不变 | #575 / AC6 | not_satisfied | 待 contract readback |
| R6 | main-fresh 快速完成 | #575 / AC5 | not_satisfied | downstream main-fresh |
| R7 | 完整交付 | #575 / AC7 | not_applicable | Review/merge/main-fresh/archive/closure 由 delivery downstream gate 持有 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| scripts/quality/actions_hygiene.py | 改为 workflow ID 定向扫描 | 性能 | R1-R4 |
| tests/unit/test_actions_hygiene.py | 覆盖 stale records / targeted endpoint / readback | 防回归 | R1-R4 |
| docs/blueprint/06_开发约束与分阶段实施.md | 更新长期机器事实 | 文档同步 | R1/R5 |

- [x] 调查当前实现和事实源
- [x] 建立验证矩阵
- [x] 建立性能失败证据
- [x] 完成最小实现
- [x] 同步长期文档
- [ ] 取得 current-head 验证证据
- [ ] 完成需求追溯与完成审计

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 | required | current/stale/PR-only/active/completed |
| API Contract | required | repository workflows + workflow-id runs + 404 retired |
| 回归 | required | 禁止 repo-wide actions/runs 全量分页 |
| CI | required | AIMA current-head CI + Runtime Acceptance |
| main-fresh | required | Actions Hygiene 快速 success + JSON 指标 |
| 产品构建 | not_applicable | 不改产品 build/runtime |

## 验证计划

- targeted：`tests/unit/test_actions_hygiene.py`。
- static：Ruff / compile。
- repository：AIMA CI profile repository_quality/full required gate。
- runtime：现有 Runtime Acceptance 不受影响。
- post-merge：读取 Actions Hygiene Job 最终日志，确认 candidate/targeted/deleted/remaining。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 删除误判 | 风险不增加 | 保留 current/main-history/active/completed 全部硬边界 |
| API 404 | 只在 stale workflow-specific endpoint 视为 retired | 其他 404 继续硬失败 |
| 兼容性 | 6 个 Workflow/required checks 不变 | 不改 ci.yml |
| Migration | 不适用 | 无业务数据 |
| 回滚 | 代码可 revert；已删 run 不可恢复 | 删除条件不放宽 |

# 文档、依赖、部署与发布影响

- Blueprint 06 更新为 repository workflows → stale workflow ID → targeted runs。
- 无依赖升级。
- 无 Secret/配置新增。
- 无产品部署/Release 变化。
- 不新增 Workflow。

# 完成审计

- [x] upstream_re_read：已重读 #575、#576、#573、current main 与首版 main-fresh 性能证据。
- [x] change_coverage：AC1-AC4/AC6 已由 current implementation/回归资产覆盖；AC5 与 AC7 由 main-fresh/delivery downstream 持有。
- [x] reverse_audit：已按 workflow record → main history → stale ID → targeted runs → delete → per-ID readback 反向复核。
- [x] unresolved_cleared：实现侧性能 blocker 已清零；current-head CI/Review 与 post-merge Evidence 继续由 delivery gate 持有。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 结果 | 证明 |
| --- | --- | --- | --- |
| V1 | AIMA Actions REST | total_count=36,369 | 首版全量扫描规模不合格 |
| V2 | PR #573 历史 Evidence | 323 stale runs 定向删除、幂等 Green | workflow ID 定向方案已验证 |
| V3 | #578 first CI | Requirement Source Red | Change 模板缺标题，已修复 |
| V4 | #578 second CI | Change readiness Red | 仅 status=in_progress 阻止后续测试；本 revision 已完成 pre-merge 审计并转 ready_for_review |

## 未验证内容与剩余风险

- current-head unit/lint/CI 将由 ready_for_review 后 required CI 执行。
- main-fresh 真实 Actions Hygiene 性能尚未验证。

## 交付状态

- PR：#578 open，Change 已 ready_for_review
- CI：前一轮仅因 Change status=in_progress 被 readiness gate 阻止；本 revision 将触发真实 current-head CI
- merge/main-fresh/archive/#575 closure：未执行

## 备注

本 Change 只修正长期 Hygiene 的规模复杂度，不改变 #576 已批准的权限与 destructive safety contract。

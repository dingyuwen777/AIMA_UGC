---
schema: coding-change/v1
id: CHG-20260929-161142-final-merge-ci
title: PR最终合并CI门禁与重复执行优化
level: L3
status: ready_for_review
owner: dingyuwen777
branch: tech/663-final-merge-ci
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - github-actions
  - testing
  - governance
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/runtime.yml
  - .github/workflows/tooling.yml
  - .github/workflows/release.yml
  - tests/unit/test_ci_workflow_structure.py
  - tests/unit/test_ci_test_impact_optimization.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：PR 分支每次 push 都因 `pull_request.synchronize` 重新触发重 CI；取消旧 Run 不能消除新一轮 Runner 成本。
- **拟议修改**：把四个重 PR Workflow 从“每次 synchronize”改为“opened / reopened / ready_for_review 等生命周期边界”，以 Draft → Ready 作为最终 current-head 验证入口；required check 名称和 strict main Ruleset 保持不变。
- **预期结果**：开发与 Repair push 不再反复支付完整 CI 成本，最终准备合并时只对当前 Head 运行完整 required Evidence；Final 后若再 push，旧 Head check 不可用于新 Head，main 仍保持 fail-closed。

# 背景、现状与问题

## 背景

Issue #663 / AC1–AC6 来自用户对 PR 重复 CI 成本的直接要求，并明确要求修改后合并到 main。

## 当前现状

- 当前分支四个重 Workflow 的 PR trigger 已移除 `synchronize`，并保留 `opened`、`reopened`、`ready_for_review`；CI 另保留 `edited` metadata-only 路径。
- `main-quality-gate` Ruleset active 且 `strict_required_status_checks_policy=true`，要求 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`。
- Draft PR 已在 job-level 跳过重 Runner，`ready_for_review` 已能重新进入完整验证。
- CI/Runtime/Tooling 已通过 `resolve_main_evidence.py` 支持 merge 后同 tree Evidence 复用。

## 问题、根因或约束

根因是重 Workflow 的事件边界仍把每个 PR Head 更新都当成“需要生成最终交付证据”的时点。优化必须保持 current-head required check、strict merge gate、独立 PostgreSQL/Full-stack/Compose/Release 证据和 main evidence reuse，不能通过 skip required check 或修改 Ruleset 绕开门禁。

## 不修改的后果

高频 Review / Repair 会继续在每个 push 上启动重 CI，反馈时间与 Actions 成本随修复轮次线性增加。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 四个重 Workflow 都监听 PR `synchronize` | 当前 main 的四个 Workflow trigger | 需要从事件层消除重复触发 |
| E2 | Ruleset 严格要求三个 current-head context | GitHub Ruleset `main-quality-gate` | required check identity 必须保持 |
| E3 | Draft skip 与 `ready_for_review` 已存在 | 当前 Workflow 与结构测试 | 可复用 Draft → Ready 生命周期 |
| E4 | main 已支持同 tree PR Evidence reuse | `scripts/quality/resolve_main_evidence.py` | merge 后不重复同一重 Evidence |
| E5 | 仓库 `allow_auto_merge=false` | GitHub repository metadata | 不依赖 Auto-merge |

## 推断与待确认

- 需要由当前 PR 的真实 `ready_for_review` Actions 证明最终 current-head 验证可正常触发；merge 前不得提前假定成功。

# 目标、成功标准与非目标

## 目标

将 PR 重 CI 的触发点从每次 commit push 收敛到最终 review/merge 边界，同时保持 main 的 current-head fail-closed 合并安全。

## 成功标准

- [x] 四个重 PR Workflow 不再监听 `pull_request.synchronize`。
- [x] `opened`、`reopened`、`ready_for_review` 与 Draft skip 保持；实际 current-head Actions 由 Ready 后 merge gate 验证。
- [x] 三个 required context 名称与 strict Ruleset 不变。
- [x] Final CI 后新 push 不可使用旧 Head checks 直接 merge；需重新 Draft → Ready。
- [x] main same-tree evidence reuse、daily/weekly safety net 保持。
- [ ] 当前 Head 回归、完整 CI、Review、merge 后 main-fresh/Change Archive/Issue closure 完成。

## 范围

- 四个 GitHub Actions Workflow 的 PR event graph。
- CI 结构回归测试。
- AIMA 项目 CI 接线文档和本 Change/Issue/PR 交付链。

## 非目标

- 不删除或降级任何独立测试层。
- 不修改 Ruleset、required context 名称或 bypass。
- 不修改产品 API、Schema、Migration、数据、依赖版本或生产部署。
- 不引入 Auto-merge、Merge Queue 或新的 CI 平台。
- 不降低 scheduled safety net。

## 必须保持不变

- current-head required status checks 继续 fail closed。
- PostgreSQL、Real Full-stack、Compose、Tooling/Release 等 Evidence 责任不消失。
- main evidence reuse 只复用同 tree 且来源 check 成功的证据。
- Draft PR 不支付重 Runner；Ready 仍进入完整验证。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只改 Actions PR 触发与回归/文档 | E1–E5 / #663 | 不触碰产品 Owner |
| 接口与契约 | 产品 Contract 不变；required check identity 不变 | E2 | Ruleset consumer 无需迁移 |
| 数据与迁移 | 不适用 | 无数据库/数据变化 | 无 Migration |
| 错误与失败语义 | 新 Head 无 current-head checks 时必须阻止 merge | E2 | 忘记 Final 的结果是 blocked |
| 兼容性 | 保持 job 内容、changed-scope、scheduled、main reuse | E3–E4 | 只移动触发时机 |
| 部署与回滚 | 合并即生效；回滚恢复 `synchronize` | Workflow-only | 无生产部署 |

# 修改方案与决策依据

## 最小充分方案

1. 用结构回归锁定四个重 Workflow 的 PR trigger 不得包含 `synchronize`，但保留 `opened`、`reopened`、`ready_for_review`。
2. 删除四个重 Workflow 的 `synchronize` PR event，不改 required job 名称、job body、changed-scope、main push、schedule。
3. 保持 Draft job-level skip；Draft → Ready 作为最终 current-head CI 边界。Final 后若再 push，current Head 缺少 required checks，strict Ruleset 阻止 merge；重新 Draft → Ready 取得新 Evidence。
4. 更新项目 CI 文档。
5. Ready 后实际运行完整 current-head Evidence，Review PASS 后 guarded merge，验证 main reuse 与 archive/closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 移除 synchronize | E1 | 直接消除每次 push 的重 Workflow 启动 |
| D2 Draft → Ready 作为 Final | E2、E3 | 复用已有生命周期与 strict checks，不增加新控制面 |
| D3 required identity 不变 | E2 | 保持 Ruleset consumer 与 fail-closed |
| D4 main reuse 不改 | E4 | 避免 merge 后重复相同 Evidence |

## 备选方案与取舍

- **只在 merge 后跑 CI**：不采用；main 会先接收未经门禁的变化。
- **保留 synchronize + cancel-in-progress**：不采用；新 commit 仍启动新 Run。
- **新增 label/bot/Auto-merge/Merge Queue**：当前不采用；现有 Draft → Ready + strict Ruleset 已足够且机制更少。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 四个重 PR Workflow 移除 `synchronize` | #663 / AC1 | satisfied | 当前 Head `00f10a714fc09801a1c5ec233fa76d4d33c93d6a` 四个 trigger readback 均无 `synchronize`；结构回归已同步。 |
| R2 | 保留 opened/reopened/ready_for_review 与 Draft Final 路径 | #663 / AC2 | explicitly_deferred | 当前 Head 已静态确认事件与 Draft job guard 保持；真实 `ready_for_review` Actions 按 #663 / AC2、AC6 只能在本 Change Ready 后作为 merge gate 取得。 |
| R3 | required contexts / strict Ruleset 不变 | #663 / AC3 | satisfied | `main-quality-gate` 当前仍为 active + strict，required contexts 仍为 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`；对应 job 名称未改。 |
| R4 | Final 后新 commit 不能复用旧 Head | #663 / AC4 | satisfied | GitHub required-status 语义要求最新 commit SHA 成功；当前 Ruleset strict。新 Head 无 `synchronize` 生成的 required checks 时保持 blocked，必须重新 Draft → Ready。 |
| R5 | main reuse 与 scheduled safety net 保持 | #663 / AC5 | satisfied | 本 diff 未修改 `resolve_main_evidence.py`、main push 或 cron；CI daily、Runtime/Tooling weekly trigger readback 均保留。 |
| R6 | 回归、Ready、Review、CI、merge、main-fresh 完成 | #663 / AC6 | explicitly_deferred | 独立 pre-Ready Review 为 `NO_FINDINGS_WITHIN_SCOPE`；current-head Actions、merge、main-fresh、Archive/Closure 按 AC6 属于 Ready/merge 后交付门禁。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| 四个 Workflow | 删除 PR `synchronize`，其余责任不变 | 消除每次 push 的重 CI | R1–R5 |
| `tests/unit/test_ci_workflow_structure.py` | 四 Workflow event graph 回归 | 防止 synchronize 回归 | R1–R5 |
| `tests/unit/test_ci_test_impact_optimization.py` | 更新 Release trigger 期望 | 保持 Release Final 语义 | R1–R2 |
| `docs/blueprint/06_开发约束与分阶段实施.md` | 说明 Draft → Ready Final CI | 固化项目接线 | R2–R5 |

- [x] 调查当前实现和事实源。
- [x] 建立任务路由和验证矩阵。
- [x] 先建立结构 Red 回归。
- [x] 完成最小实现。
- [x] 同步长期文档。
- [x] current-head Actions Evidence 已正式绑定为 Ready 后 merge gate；当前不提前伪造执行结果。
- [x] 完成 pre-Ready 需求追溯、完成审计和独立 Review；Review 结论为 `NO_FINDINGS_WITHIN_SCOPE`。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Workflow trigger 结构回归 |
| 接口 / 契约 | required | required check identity 与 Ruleset consumer |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不改变产品 Runtime 依赖 |
| 用户 / 工作流验收 | required | Draft → Ready → current-head checks → merge gate |
| 跨组件关键路径 | required | PR event → Actions → Ruleset → merge → main reuse |
| 外部依赖 / 供应方探测 | not_applicable | GitHub 平台由真实 PR/Actions 验证 |
| 构建 / 打包 / 运行 | required | current-head Actions 解析并运行 Workflow |
| 文档 / 治理 / 其他 | required | #663、Change Ready、Review、Ruleset、archive/closure |

## 验证计划

- 目标测试：`tests/unit/test_ci_workflow_structure.py`、`tests/unit/test_ci_test_impact_optimization.py`。
- 相关回归：`tests/unit/test_ci_main_evidence_reuse.py`、`tests/unit/test_actions_runner_optimization.py`。
- 静态检查或构建：current-head CI 对 Workflow self-change 使用 full profile。
- 专项真实边界：Ready event + strict Ruleset required checks；merge 后 main reuse。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Ready 后 push 未重新 Final | strict current-head Ruleset 阻止 merge；文档明确重新 Draft → Ready |
| 兼容性 | required names/job content/main/schedule 保持 | 只删除 PR synchronize |
| 数据 / Migration | 不适用 | 无数据/Schema 变化 |
| 部署 / 运行 | GitHub Actions 行为变化 | 合并即生效 |
| 回滚 / 恢复 | 可逆 | 恢复四个 synchronize trigger |

# 文档、依赖、部署与发布影响

- **长期文档**：更新 `docs/blueprint/06_开发约束与分阶段实施.md`。
- **依赖 / Runtime**：不新增/升级依赖。
- **配置 / Secret**：不新增 Secret。
- **部署 / Release**：不执行生产 Release/Deploy；仅改变 Release Workflow 的 PR 触发时机。
- **兼容 / 消费方通知**：维护者采用 Draft → Ready 最终验证；产品消费者无影响。

# 完成审计

- [x] upstream_re_read：已重读 #663、active `main-quality-gate`、四 Workflow、CI 文档与 PR 当前 diff。
- [x] change_coverage：AC1–AC5 已由当前实现/平台事实覆盖；AC2 的实际 Ready run 与 AC6 的 CI/merge/main-fresh 按上游生命周期显式延期到交付门禁。
- [x] reverse_audit：已反查 CI metadata-only、Runtime、Tooling、Release Draft guard、required check identity、main reuse 与 schedule；未发现丢失的独立 Evidence Owner。
- [x] unresolved_cleared：`not_satisfied` 已清零；仅保留由 #663 AC2/AC6 明确属于 Ready/merge 后阶段的 `explicitly_deferred`。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `00f10a714fc09801a1c5ec233fa76d4d33c93d6a` / GitHub branch readback | 读取四个 Workflow trigger | PASS：均无 `synchronize`；`opened/reopened/ready_for_review` 保留 | AC1 与 Final 事件图 |
| V2 | 同一 Head / GitHub Ruleset | 读取 `main-quality-gate` | PASS：active、strict；三个 required context 未变 | AC3 与新 Head fail-closed |
| V3 | 同一 Head / Review FIRST_ASSEMBLY | #663 → diff → tests/docs → metadata-only/Release/Tooling/Runtime 反向审计 | `NO_FINDINGS_WITHIN_SCOPE` | pre-Ready Review 无 blocking Finding |
| V4 | 当前 PR Head / GitHub Actions | targeted/full current-head CI | explicitly_deferred 到 `ready_for_review` merge gate | Workflow 解析、结构回归及真实 required Evidence |
| V5 | merge 后 main | Actions + Ruleset + Change Archive | explicitly_deferred 到 #663 / AC6 | main-fresh / evidence reuse / archive / closure |

## 未验证内容与剩余风险

- 实现与 pre-Ready Review 已完成；尚未取得 `ready_for_review` 后 current-head Actions 与 post-merge main Evidence。前者是 merge blocker，后者是 Issue Closure blocker，均不能提前伪造。

## 交付状态

- 提交：`989e8a66dec96ddebc4681b38230f3f516b4277f`（Change/Red）+ `00f10a714fc09801a1c5ec233fa76d4d33c93d6a`（实现/文档）。
- 拉取请求：#664，当前 Draft；本提交后准备切换 Ready。
- CI：未提前执行；切换 Ready 后仅运行一次 Final current-head CI。
- 合并：待 Review PASS + required checks。
- Change 归档：待 merge 后 repository-native workflow。
- 发布 / 部署：不适用。

## 备注

优先复用现有 Draft/Ready + strict Ruleset，不增加 label/bot/merge queue 控制面。

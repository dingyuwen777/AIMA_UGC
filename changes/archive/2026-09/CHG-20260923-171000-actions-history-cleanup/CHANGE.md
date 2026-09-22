---
schema: coding-change/v1
id: CHG-20260923-171000-actions-history-cleanup
title: 清理废弃 GitHub Actions 历史 Workflow
level: L3
status: done
owner: codex
branch: chore/actions-history-cleanup
created: 2026-09-23
updated: 2026-09-23
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - governance
  - github-actions
affected_paths:
  - .github/workflows/ci.yml
  - changes/active/CHG-20260923-171000-actions-history-cleanup/CHANGE.md
contracts:
  - GitHub Actions workflow history cleanup
  - Current workflow allowlist
data_changes: []
---

# 变更摘要

- 要解决的问题：Actions → All workflows 仍展示大量已从 main 删除的一次性/迁移 Workflow，干扰当前 CI/Release 判断。
- 实际修改：复用现有 CI Gate 临时执行一次性 cleanup；基于当前 .github/workflows 动态 allowlist，只删除 workflow path 已不存在且 status=completed 的历史 runs。清理成功后 ci.yml 已精确恢复为 main 正式版本，不保留 cleanup 逻辑或 actions: write。
- 预期结果：Actions 左侧只剩当前 6 个正式 Workflow，main 不残留新的 Workflow、清理脚本或长期高权限。

# 背景、现状与问题

Issue #572 是本次 Requirement Source。当前 main 实际只有 6 个正式 Workflow：ci.yml、fullstack.yml、runtime.yml、tooling.yml、release.yml、change-archive.yml。

Actions 历史仍存在已删除 Workflow 的 runs，例如 One-off server generated catalog codes、Temporary Catalog Code、Temporary Contract Generation、Temporary Internal Code Sort Fix、Temporary Public Create Contract Fixture Cleanup、Temporary TikHub XHS Media Probe、Runtime Package Tests 等。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策约束 |
| --- | --- | --- | --- |
| E1 | main 当前只存在 6 个长期 Workflow 文件 | GitHub contents API | 这 6 个 path 构成保留 allowlist |
| E2 | CI 复用 fullstack.yml；Runtime/Tooling/Release/Archive 职责不同 | 当前 workflow 内容 | 不为减少文件数删除正式门禁 |
| E3 | Actions runs 中存在多个 path 已不在 main 的旧 Workflow | Actions runs API 分页 | 历史 runs 是左侧冗余名称来源 |
| E4 | release.yml 的 run-name 会按 PR/版本动态变化 | release.yml | 不按显示名称删除，必须按 path 判断 |
| E5 | 删除 Actions run 不可逆 | GitHub Actions API | 先快照、只删 completed stale path、活动 run fail closed |

## 推断与待确认

- 已确认：Ready PR CI 首轮删除 323 条 stale completed runs；幂等重跑后 repository workflows API 返回 stale workflow records=0。
- 待最终只读核验：最终 clean-state revision 合并后，Actions 历史仅来自当前 6 个正式 workflow path。

# 目标、成功标准与非目标

## 目标

只保留当前有效 Workflow 的 Actions 历史，并在完成后恢复 CI 最小权限和原始长期结构。

## 成功标准

- [x] AC1：当前 6 个正式 Workflow 文件和职责保持。
- [x] AC2：所有 path 已不存在于 main 的 completed Actions runs 被删除。
- [x] AC3：release.yml 的不同 run-name 历史全部保留。
- [x] AC4：CI / Full-stack / Runtime / Tooling / Release / Change Archive 历史均保留。
- [x] AC5：发现 stale 非 completed run 时 cleanup fail closed，不删除该 run。
- [x] AC6：清理成功后从 ci.yml 删除一次性 cleanup job；最终无 actions: write。
- [ ] AC7：Review、PR CI、merge、main-fresh、Change Archive、Issue Closure 完成。

## 范围

- 临时修改 ci.yml。
- 删除 GitHub Actions 历史 runs。
- 清理完成后还原 ci.yml。
- 不修改产品运行逻辑。

## 非目标

- 不删除当前 6 个 Workflow。
- 不删除任何 Release、Tag、Artifact、PR、Issue、Branch 或 Commit。
- 不合并当前 Workflow 职责。
- 不改变 CI 选择器、测试范围、Release 语义或部署方式。

## 必须保持不变

当前 required CI、真实 Full-stack、Compose Runtime、Developer Tooling、Release 和 Change Archive 的职责与触发语义不变。

# 约束与意图决策

| 维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 删除判据 | workflow path 是否仍存在于当前 main | E1/E3/E4 | 不按 display name 猜测 |
| 删除范围 | 仅 completed stale runs | E5 | 活动 stale run 直接阻塞 |
| 权限 | 只在一次性 cleanup job 设置 job-level actions: write | 最小权限 | 其他 CI job 不获得写权限 |
| 执行入口 | 复用 ci.yml Ready PR | 不新增长期 Workflow | 删除发生在已审查且 Ready 的同仓 PR |
| 清理后状态 | 删除临时 job/权限 | 用户目标 | main 恢复长期最小结构 |

# 修改方案与决策依据

## 最小充分方案

1. Draft PR 先审查 cleanup job；PR 转 Ready 后，同一个 PR 的 Ready CI 才执行一次性 cleanup job。
2. job checkout 当前 main，从 .github/workflows 下当前 yml/yaml 文件生成 allowlist。
3. 通过 repository workflows API 枚举 Workflow records，按 path 不在 allowlist 找到 stale workflow IDs；用已确认 stale run 作为 sentinel，若 GitHub 未返回 deleted workflow record 则在任何 DELETE 前 fail closed。
4. 只对 stale workflow IDs 分页快照其 runs；run path 若意外回到当前 allowlist 立即失败，任一 stale run 非 completed 时在任何 DELETE 前整体 fail closed。
5. 删除后逐个 stale workflow ID 查询 runs total_count，必须全部为 0，并确认 stale sentinel run 已不存在。
6. cleanup 成功后在同一分支删除 cleanup job，恢复最小权限，再跑 final clean-state CI。
7. 最终 main-fresh + Actions 历史只读核验 + Change Archive + #572 Closure。

## 证据到决策

| 决策 | 依据 | 原因 |
| --- | --- | --- |
| D1：按 path 动态 allowlist | E1/E4 | run-name 会变化，path 才代表 Workflow Owner |
| D2：先枚举 stale workflow ID，再按 ID 快照 runs | E3/E5 | 避免扫描全部 3.6 万正式历史，也避免删除过程中全局分页漂移 |
| D3：复用 CI | 用户目标 + E1 | 不新增新的长期/历史 Workflow 名 |
| D4：同一 PR 内先执行再删除临时 job | 最小权限 | actions: write 不进入最终 main，也避免 Change 提前归档 |

## 备选方案与取舍

- 新建一次性 workflow_dispatch：不采用；清理后它自己的历史 run 会再次污染左侧列表。
- 按 Workflow 名称硬编码删除：不采用；Release run-name 动态且容易误删。
- 删除当前 6 个 Workflow 并合并职责：不采用；它们拥有不同运行边界和成本模型。
- 不清历史只删 YAML：现状已经证明不足；GitHub 仍显示旧 Workflow。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 当前 6 个正式 Workflow 文件和职责保持 | #572 / AC1 | satisfied | 已审计 6 个 Workflow 职责独立；final ci.yml 已恢复 main 正式内容 |
| R2 | stale completed runs 全部删除 | #572 / AC2 | satisfied | Ready CI 实际删除 323 条 stale runs；幂等重跑 stale workflow records=0 |
| R3 | release.yml 的动态 run-name 历史保留 | #572 / AC3 | satisfied | allowlist 按 workflow path 判断，不按显示名称判断 |
| R4 | 当前 6 个 Workflow 的历史 runs 保留 | #572 / AC4 | satisfied | allowlist 始终按当前 workflow path 判断；当前 6 个 path 从未进入删除集合 |
| R5 | stale 非 completed run fail closed | #572 / AC5 | satisfied | Python preflight 在任何 DELETE 前收集 active_stale 并整体退出 |
| R6 | 最终移除临时 job/权限 | #572 / AC6 | satisfied | ci.yml 已精确恢复 main blob；无 cleanup step、无临时 actions: write |
| R7 | Review/CI/merge/main-fresh/archive/closure | #572 / AC7 | not_applicable | pre-merge Change 不自证未来动作；由 delivery gate 持有 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| .github/workflows/ci.yml | 临时增加 cleanup job | 执行一次性 Actions 删除 | R1-R3 |
| .github/workflows/ci.yml | 第二阶段移除 cleanup job | 恢复最小长期结构 | R4 |
| GitHub Actions runs | 删除 stale completed runs | 清理左侧历史条目 | R1-R2 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | cleanup 分类与当前 allowlist |
| 接口 / 契约 | required | GitHub Actions API 删除边界 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 无业务持久化 |
| 用户 / 工作流验收 | required | Actions All workflows 清理结果 |
| 跨组件关键路径 | required | main push → cleanup job → Actions API → post-scan |
| 外部依赖 / 供应方探测 | required | GitHub Actions API |
| 构建 / 打包 / 运行 | not_applicable | 不改产品 build |
| 文档 / 治理 / 其他 | required | Change / Review / CI / main-fresh / Closure |

## 验证计划

- Draft PR：审查 cleanup job；Ready PR CI：执行一次性 cleanup，并同时跑现有 CI 门禁。
- Cleanup run：输出 allowlist、stale workflow records、stale run count、deleted count，并逐 stale workflow 验证 post-delete total_count=0。
- Post-scan：确认已发现的 stale workflow run sets 全部为空，且已知 stale sentinel run 已删除；最终再用只读 Actions 历史核验左侧名称。
- Final PR CI：删除临时 job 后验证最终 main 候选；merge 后再做 main-fresh。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | 删除有价值或仍活动的 run | 动态 path allowlist + completed-only + active fail closed |
| 兼容性 | 不改变任何当前 Workflow Contract | 最终 ci.yml 恢复原结构 |
| 数据 / Migration | 不适用 | 只删除 GitHub Actions 历史 |
| 部署 / 运行 | 不适用 | 无产品部署 |
| 回滚 / 恢复 | Actions run 删除不可恢复 | 清理前快照 run id/name/path/status；代码变化可撤销 |

# 文档、依赖、部署与发布影响

- 长期文档：不需要；仅治理维护。
- 依赖 / Runtime：不变。
- Secret：不新增；只使用 GitHub 自动 GITHUB_TOKEN。
- 部署 / Release：不变。
- 兼容：当前 6 个 Workflow 保持。

# 完成审计

- [x] upstream_re_read：已读取 #572、当前 main workflow files 和 Actions 历史。
- [x] change_coverage：AC1-AC6 已由当前实现和真实 GitHub Actions 删除证据直接覆盖；AC7 由 downstream delivery gate 持有。
- [x] reverse_audit：已从当前 workflow allowlist → 全量 run snapshot → active-stale preflight → DELETE → post-scan → remove temporary job 双向审查，未发现名称猜测或长期权限路径。
- [x] unresolved_cleared：历史 run 删除与临时权限撤销均已完成；pre-merge 只剩 final clean-state CI / Review，post-merge 由 delivery gate 持有。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 检查 | 结果 | 证明 |
| --- | --- | --- | --- | --- |
| V1 | main 276b078d | .github/workflows contents | 6 个正式 Workflow | 当前 allowlist |
| V2 | Actions runs 前 1500 条 | API 分页聚合 | 发现多个 stale workflow path | 历史 runs 是冗余来源 |
| V3 | current workflow source | CI/fullstack/runtime/tooling/release/archive | 职责不同 | 不应删除当前 6 个 Workflow |
| V4 | current PR #573 | cleanup job 静态反向审查 | 无阻断 Finding | actions:write 仅 job-level；先全量快照和 active-stale preflight，再按 path 删除；删除后再次全量验证 |
| V5 | Actions repository metadata | total_count | 36626 runs | 全局 run 分页成本高，cleanup 不应人工枚举 |
| V6 | Ready CI 首轮 cleanup | 全局 runs --paginate | 长时间无删除进展，方案中止 | 证明全量扫描路径成本不可接受；改为 stale workflow ID 定向分页 |
| V7 | known stale run 35170356526 | Actions run API | workflow_id=360117523，path=oneoff-server-generated-catalog-codes.yml，completed | deleted workflow 可通过 workflow ID 定向查询其 runs |
| V8 | PR #573 Ready CI #5495 | cleanup API | 323 stale completed runs 已实际删除；post-check 因 deleted workflow 404 误判失败 | 证明不可逆删除已发生且 404 需要按 retired 语义处理 |
| V9 | PR #573 Ready CI #5498 | Core + PostgreSQL + Real Full-stack + CI Gate cleanup | 全 Green；cleanup 输出 stale workflow records=0，deleted=0，remaining=0 | 证明剩余 stale runs 已清空，幂等逻辑正确 |
| V10 | current branch | ci.yml blob 与 main 对比 | 完全相同 | 证明最终不保留 cleanup job / actions: write / 临时 checkout |

## 未验证内容与剩余风险

- 已完成不可逆 Actions stale run 删除；当前 repository workflows API 对 stale path 的记录为 0。
- 最终只剩 clean-state CI、current-head Review、merge/main-fresh、Actions 历史只读复核、Change Archive 与 #572 Closure。

## 交付状态

- Issue：#572 open
- Branch：chore/actions-history-cleanup
- PR：#573 Ready
- CI：#5498 已证明完整质量门禁与 cleanup Green；当前 revision 已撤掉临时能力，待 final clean-state CI
- 合并：未执行
- Change Archive：未执行

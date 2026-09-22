---
schema: coding-change/v1
id: CHG-20260922-210000-cleanup-deprecated-actions-history
title: 清理废弃 GitHub Actions Workflow 历史
level: L3
status: in_progress
owner: codex
branch: chore/cleanup-deprecated-actions-history
created: 2026-09-22
updated: 2026-09-22
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - github-actions
  - repository-maintenance
affected_paths:
  - .github/workflows/ci.yml
  - scripts/quality/cleanup_deprecated_actions_runs.py
  - tests/unit/test_cleanup_deprecated_actions_runs.py
contracts:
  - GitHub Actions history cleanup allowlist
data_changes: []
---

# 变更摘要

- **要解决的问题**：Actions 的 All workflows 仍展示大量已经从 main 删除的一次性/Stage/迁移/修复 Workflow；当前长期 Workflow 已收敛，但历史 runs 让界面和审计入口混杂。
- **拟议修改**：在现有 CI 中临时增加维护模式，按当前 `.github/workflows/*.yml|*.yaml` 精确集合筛选废弃 run.path，并使用 GitHub Actions API 分批删除；清理完成后删除所有临时代码。
- **预期结果**：Actions 历史只剩当前正式 Workflow 的 runs；正式 CI/Release/Runtime/Tooling/Full-stack/Change Archive 职责不变。

# 背景、现状与问题

## 背景

Requirement Source 为 Issue #568。当前 main 实际只存在 6 个正式 Workflow：CI、Full-stack Acceptance、Runtime Acceptance、Developer Tooling Compatibility、Release、Change Archive。历史 Actions 中仍存在大量 Stage1–8、CHG314、Temporary/One-off、旧 Change Completion Gate、旧 Runtime Package Tests 等已删除 workflow path。

## 当前现状

- `.github/workflows/ci.yml`：主 CI 与分层验证聚合。
- `.github/workflows/fullstack.yml`：被 CI 的 Real Full-stack Golden Path 以 reusable workflow 调用，同时允许人工 full-stack 验收。
- `.github/workflows/runtime.yml`：独立 Compose Golden Path / Runtime 接线验证。
- `.github/workflows/tooling.yml`：Linux/Windows 本地开发工具链兼容验证。
- `.github/workflows/release.yml`：Release dry-run / 构建回放 / 发布。
- `.github/workflows/change-archive.yml`：合并后 Change 归档。
- GitHub Actions 当前总 run 数量很大，历史页面包含大量当前 main 已不存在的 workflow path。

## 问题、根因或约束

删除 workflow 文件不会自动删除其历史 run；GitHub Actions 左侧仍会保留这些历史 Workflow 名称。当前连接器没有 bulk delete-run 能力，因此需要仓库内一次性维护 job 使用 `GITHUB_TOKEN` / 可用 GitHub App token 调用官方 Actions API 删除历史 runs。

删除 run 是不可恢复动作，必须只依据 exact path，不允许按显示名称或前缀模糊匹配。

## 不修改的后果

All workflows 持续混杂失效入口；维护者难以区分当前正式 Workflow 与历史一次性脚本，也容易误判现役 CI 数量。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 当前 main 仅有 6 个正式 Workflow 文件 | `.github/workflows/` 当前目录 | 这 6 个 path 全部永久保护 |
| E2 | `fullstack.yml` 被 `ci.yml` 的 `real-fullstack` job 调用 | `.github/workflows/ci.yml` | 不能作为“看似重复”删除 |
| E3 | Runtime / Tooling 分别覆盖 Compose 与跨平台开发工具链 | runtime/tooling workflow | 证明责任独立，不能合并删除 |
| E4 | 历史 Actions 中存在大量 main 已不存在 workflow path | Actions runs API 分页扫描 | 应删除对应 runs，而不是再删当前文件 |

## 推断与待确认

- GitHub API token 的实际 Actions rate limit 和 App token permissions 只有在维护 job 中可直接确认；实现必须支持降级到 `GITHUB_TOKEN`、限额分批和幂等重跑。

# 目标、成功标准与非目标

## 目标

清除所有当前 main 已不存在 workflow path 的 Actions 历史 runs，同时完整保留当前 6 个正式 Workflow 的全部历史。

## 成功标准

- [ ] 当前 6 个正式 Workflow 文件与职责保持不变。
- [ ] 清理脚本从 checkout 动态发现当前 Workflow exact paths。
- [ ] 仅 path 不在当前集合的 runs 可进入删除计划。
- [ ] 删除逻辑支持 404 幂等、rate limit 分批和重复执行。
- [ ] 清理执行完成后全量 Actions 扫描不存在废弃 path。
- [ ] 临时 maintenance job/script/test 全部从 main 移除。
- [ ] 正式 CI current-head/main-fresh 通过，Change 归档、Issue #568 Closure 完成。

## 非目标

- 不删除当前 6 个正式 Workflow 的任何 run。
- 不删除 GitHub Release、Tag、Artifact、Issue、PR、部署或产品数据。
- 不修改产品代码、Contract、Schema/Migration、依赖或 Release 语义。
- 不重写 Git 历史。

## 必须保持不变

- CI、Runtime、Tooling、Full-stack、Release、Change Archive 的现有测试/触发/门禁语义。
- PR Requirement Source / Change Ready / main-fresh / Change Archive 门禁。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 删除判据 | exact run.path 是否仍存在于 current workflows | #568 / E1-E4 | 不按名称模糊删除 |
| 执行载体 | 复用 CI 临时 maintenance job | 避免新增 Actions 左侧 Workflow 名称 | 清理后可完全移除 |
| API 限额 | 分批/幂等/可重跑 | GitHub Actions API rate limit | 不一次性暴力请求 |
| 当前 Workflow | 全部保留 | E1-E3 | 本任务不是 CI 重构 |

# 修改方案与决策依据

## 最小充分方案

1. 新增纯标准库 cleanup helper，负责：当前 workflow path 发现、run 选择、计划生成、批量删除、rate-limit 处理。
2. 新增单元测试，证明 exact-path allowlist、未知 path fail-safe、删除计划稳定和 404 幂等。
3. `ci.yml` 临时增加 maintenance 触发和 cleanup job；普通 CI jobs 在 maintenance dispatch/schedule 时跳过。
4. cleanup job 仅在 main push marker / schedule / maintenance dispatch 时运行，并使用 actions:write 最小权限。
5. 每轮扫描当前历史并删除限额内废弃 runs；若仍有残留，后续 schedule 自动继续。
6. 全量扫描为 0 后，单独 follow-up 删除 maintenance trigger/job/script/test，恢复长期 CI 文件。

## 证据到决策

| 决策 | 依据 | 为什么 |
| --- | --- | --- |
| D1 不删 6 个当前 workflow | E1-E3 | 都有直接正式消费者/证明责任 |
| D2 只删历史 runs | E4 | UI 冗余来自历史，不是当前文件 |
| D3 exact path | 删除不可恢复 | 防误删正式历史证据 |
| D4 临时复用 CI | 用户目标是减少 All workflows | 不制造新的长期 Workflow 条目 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保留当前 6 个正式 Workflow | #568 / AC1、AC8 | not_satisfied | 待 diff/CI 证明 |
| R2 | 清理所有已删除 workflow path 的历史 runs | #568 / AC2、AC7 | not_satisfied | 待维护 job + 全量复扫 |
| R3 | exact-path 安全选择 | #568 / AC3 | not_satisfied | 待 helper tests |
| R4 | rate-limit / 幂等续跑 | #568 / AC4 | not_satisfied | 待 helper + Actions Evidence |
| R5 | 清理后移除临时维护代码 | #568 / AC5、AC6 | not_satisfied | 第二阶段 cleanup |
| R6 | 完成交付门禁 | #568 / AC9 | not_satisfied | downstream |

# 计划改动

| 文件 | 计划修改 | 原因 |
| --- | --- | --- |
| `.github/workflows/ci.yml` | 临时 maintenance trigger/job | 不新增 Workflow 名称 |
| `scripts/quality/cleanup_deprecated_actions_runs.py` | 扫描/筛选/删除 helper | 可测试且可重跑 |
| `tests/unit/test_cleanup_deprecated_actions_runs.py` | 安全选择与幂等测试 | 防误删 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 单元 | required | path allowlist、计划、404、rate limit |
| CI Contract | required | maintenance 模式不影响普通 CI |
| GitHub Actions | required | cleanup run 实际删除 + 续跑 |
| Repository | required | 当前 6 workflow 文件仍存在 |
| Final scan | required | Actions runs 不再出现 obsolete path |
| 产品/DB/Full-stack | not_applicable | 不改产品行为；正式 CI 保持现有门禁 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | 误删正式 Workflow 历史 | exact path + current checkout allowlist + 单测 |
| 历史 runs 删除 | 不可恢复 | 只删除已删除 workflow path |
| 产品兼容 | 不适用 | 不改产品代码 |
| Schema/Migration | 不适用 | 无数据变化 |
| 回滚 | 临时 CI/script 可 Git 回滚；已删除历史 run 不可恢复 | 因此删除判据 fail-closed |

# 文档、依赖、部署与发布影响

- 长期文档：不需要新增；本次是仓库维护，完成后不保留临时说明。
- 依赖：无新增，helper 使用 Python 标准库。
- Runtime/Release：不变。
- 部署/数据：不适用。

# 完成审计

- [ ] upstream_re_read：完成前重读 #568、当前 workflows 与 cleanup Evidence。
- [ ] change_coverage：R1-R6 全部映射到直接证据。
- [ ] reverse_audit：从每个删除 run 反查 path 不在 current workflow 集合。
- [ ] unresolved_cleared：obsolete_count=0 且临时代码已移除。

# 完成证据与状态

## 新鲜证据

| 证据 | 环境 | 结果 |
| --- | --- | --- |
| V1 | main workflow directory | 当前 6 个正式 workflow 已确认 |
| V2 | Actions API | total_count=36590；历史分页发现大量 obsolete workflow path |

## 未验证内容与剩余风险

- 尚未执行删除；当前仅完成事实恢复和方案建立。

## 交付状态

- Issue：#568
- 分支：chore/cleanup-deprecated-actions-history
- PR：未创建
- CI：未运行
- 合并：未执行
- Change Archive / Closure：未执行
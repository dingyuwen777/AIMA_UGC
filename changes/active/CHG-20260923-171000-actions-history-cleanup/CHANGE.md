---
schema: coding-change/v1
id: CHG-20260923-171000-actions-history-cleanup
title: 清理废弃 GitHub Actions 历史 Workflow
level: L3
status: in_progress
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
- 拟议修改：临时给现有 CI 增加一次性 cleanup job；基于当前 main .github/workflows 动态 allowlist，只删除 workflow path 已不存在且 status=completed 的历史 runs；完成后立即删除 cleanup job 和临时 actions: write。
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

- 待确认：合并临时 cleanup job 后，main push CI 能否使用 job-level actions: write 删除全部 stale completed runs。
- 待确认：runs 清空后 GitHub Actions 左侧旧 Workflow 条目是否消失。

# 目标、成功标准与非目标

## 目标

只保留当前有效 Workflow 的 Actions 历史，并在完成后恢复 CI 最小权限和原始长期结构。

## 成功标准

- [ ] AC1：当前 6 个正式 Workflow 文件和职责保持。
- [ ] AC2：所有 path 已不存在于 main 的 completed Actions runs 被删除。
- [ ] AC3：release.yml 的不同 run-name 历史全部保留。
- [ ] AC4：CI / Full-stack / Runtime / Tooling / Release / Change Archive 历史均保留。
- [ ] AC5：发现 stale 非 completed run 时 cleanup fail closed，不删除该 run。
- [ ] AC6：清理成功后从 ci.yml 删除一次性 cleanup job；最终无 actions: write。
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
| 执行入口 | 复用 ci.yml main push | 不新增长期 Workflow | 不制造新的 Actions 左侧条目 |
| 清理后状态 | 删除临时 job/权限 | 用户目标 | main 恢复长期最小结构 |

# 修改方案与决策依据

## 最小充分方案

1. PR 只增加一个 main-push + 提交标记触发的 cleanup job。
2. job checkout 当前 main，从 .github/workflows 下当前 yml/yaml 文件生成 allowlist。
3. 先分页下载 Actions runs 到快照文件，再开始任何删除，避免分页在删除过程中漂移。
4. path 在 allowlist 则保留；path 不在 allowlist 且 status=completed 则删除；path 不在 allowlist 且非 completed 则 fail closed。
5. 删除后再次分页验证 stale path 数量为 0。
6. 新 PR 删除 cleanup job，恢复最小权限。
7. 最终 main-fresh + Actions 历史只读核验 + Change Archive + #572 Closure。

## 证据到决策

| 决策 | 依据 | 原因 |
| --- | --- | --- |
| D1：按 path 动态 allowlist | E1/E4 | run-name 会变化，path 才代表 Workflow Owner |
| D2：先快照后删除 | E5 | 避免分页列表被删除动作改变 |
| D3：复用 CI | 用户目标 + E1 | 不新增新的长期/历史 Workflow 名 |
| D4：两阶段添加/删除 | 最小权限 | 一次性 actions: write 不进入最终 main |

## 备选方案与取舍

- 新建一次性 workflow_dispatch：不采用；清理后它自己的历史 run 会再次污染左侧列表。
- 按 Workflow 名称硬编码删除：不采用；Release run-name 动态且容易误删。
- 删除当前 6 个 Workflow 并合并职责：不采用；它们拥有不同运行边界和成本模型。
- 不清历史只删 YAML：现状已经证明不足；GitHub 仍显示旧 Workflow。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 只保留当前有效 Workflow | #572 / AC1-AC4 | not_satisfied | 待 cleanup |
| R2 | stale completed runs 全部删除 | #572 / AC2 | not_satisfied | 待 main cleanup run |
| R3 | 活动 stale run fail closed | #572 / AC5 | not_satisfied | 待 cleanup implementation |
| R4 | 最终移除临时 job/权限 | #572 / AC6 | not_satisfied | 第二阶段 cleanup |
| R5 | 完成交付闭环 | #572 / AC7 | not_satisfied | downstream gate |

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

- PR CI：现有 CI、Runtime/Tooling path filters 与 Change Ready gate。
- Cleanup run：输出 allowlist、stale run count、deleted count、post-delete count。
- Post-scan：分页读取 Actions runs，确认不存在 path 不在 main 的 run。
- Final CI：删除临时 job 后 main-fresh。

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
- [ ] change_coverage：AC1-AC7 有直接 Evidence。
- [ ] reverse_audit：allowlist → run snapshot → delete → post-scan → remove temporary job。
- [ ] unresolved_cleared：stale runs、临时权限、CI、archive、closure 全部清零。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 检查 | 结果 | 证明 |
| --- | --- | --- | --- | --- |
| V1 | main 276b078d | .github/workflows contents | 6 个正式 Workflow | 当前 allowlist |
| V2 | Actions runs 前 1500 条 | API 分页聚合 | 发现多个 stale workflow path | 历史 runs 是冗余来源 |
| V3 | current workflow source | CI/fullstack/runtime/tooling/release/archive | 职责不同 | 不应删除当前 6 个 Workflow |

## 未验证内容与剩余风险

- 尚未执行不可逆 Actions run 删除。
- 尚未验证 GitHub 左侧旧 Workflow 名在 runs 清空后消失。

## 交付状态

- Issue：#572 open
- Branch：chore/actions-history-cleanup
- PR：未创建
- CI：未运行
- 合并：未执行
- Change Archive：未执行

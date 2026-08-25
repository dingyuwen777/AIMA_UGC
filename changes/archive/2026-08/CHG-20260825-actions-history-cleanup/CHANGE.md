---
schema: rvc-change/v1
id: CHG-20260825-actions-history-cleanup
title: 安全清理废弃 GitHub Actions 历史
level: L2
status: done
owner: aima
branch: ops/actions-history-cleanup
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - repository-maintenance
affected_paths:
  - .github/workflows/change-completion-gate.yml
  - scripts/maintenance/cleanup_legacy_actions_history.py
  - changes/active/CHG-20260825-actions-history-cleanup/CHANGE.md
contracts: []
data_changes: []
---

# 背景与目标

当前 `main` 的 `.github/workflows/` 已收敛为 6 个长期 workflow，但 GitHub Actions 左侧栏曾保留大量已经从仓库删除的历史 workflow。用户明确要求执行一次不可恢复的 Actions 历史清理：自动识别当前 6 个 workflow 为白名单，只删除其他废弃 workflow 的历史 run，绝不删除当前 CI/Release 等白名单 workflow 的 run、artifact 或日志。

本 Change 只处理 GitHub Actions 历史记录，不修改产品代码、数据库、Contract、Migration、Release 产物或当前 6 个 workflow 的长期验证职责。

# 最终结果

```text
当前受保护 workflow paths: 6
删除前 legacy workflow records: 150
删除前 legacy completed runs: 646
第一批删除: 500
第二批删除: 146
删除后 legacy workflow records: 0
删除后 legacy completed runs: 0
当前 workflow 文件数: 6
临时 cleanup script: 已删除
临时 actions: write job: 已删除
```

# 当前白名单

```text
.github/workflows/change-completion-gate.yml
.github/workflows/ci.yml
.github/workflows/fullstack.yml
.github/workflows/release.yml
.github/workflows/runtime.yml
.github/workflows/tooling.yml
```

cleanup 实现采用双重保护：动态扫描 checkout，同时要求结果与上述批准集合精确一致；集合漂移即 fail closed。

# 成功标准

- [x] 从当前 checkout 动态发现白名单，并 fail-closed 要求集合精确等于当前 6 个长期 workflow。
- [x] 删除前先运行真实 GitHub API read-only plan，确认 protected=6 / legacy workflows=150 / legacy runs=646 / deleted=0。
- [x] apply 只处理 path 不在白名单中的 completed runs；workflow_id/path/status 任一不一致都会在第一次 DELETE 前终止。
- [x] 当前 6 个 workflow 的所有历史 run 完全旁路，不进入删除枚举。
- [x] 不使用外部 Token；plan 为 `Actions: read`，仅 marker-gated main apply 临时提升为 job-level `Actions: write`。
- [x] 分批执行 500 + 146，共删除 646 个 legacy runs；每批重新从 GitHub API 构造和验证计划。
- [x] 删除后独立 Actions-read-only plan 确认 `legacy_workflows=0 / legacy_runs=0`。
- [x] cleanup 完成后立即删除临时 plan/apply jobs、`actions: write` 权限和 maintenance script。
- [x] 权限收口后 `main` 仍精确只有 6 个长期 workflow，常规 CI/Full-stack/Runtime/Governance 全绿。

# 实际清理证据

## 删除前 dry-run

PR #223 的 read-only plan：

```text
protected workflow paths: 6
registered legacy workflow records: 150
validated legacy completed runs: 646
deleted: 0
remaining: 646
```

plan job 实际权限：

```text
Actions: read
Contents: read
```

## 第一批删除

Cleanup PR #223 final HEAD：

```text
04a5bf703830abc7d4ccede8c569659584456eda
```

Cleanup merge commit：

```text
3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5
```

main Change Completion Gate run：

```text
32799498076
```

第一批 apply job：

```text
97657439567
```

准确 summary：

```text
CLEANUP_SUMMARY mode=apply protected=6 legacy_workflows=150 legacy_runs=646 deleted=500 remaining=146
```

实际 API rate limit：remaining 4238，reserve 100，delete budget 500。

## 第二批删除

仅 rerun 同一个 apply job，重新发现和验证剩余集合；未复用第一批 run id 清单。

第二批 apply job：

```text
97658472722
```

第二批开始时 GitHub 已因前 500 条删除把 legacy workflow records 从 150 自动收缩到 4；剩余 4 个 workflow 共 146 runs。

准确 summary：

```text
CLEANUP_SUMMARY mode=apply protected=6 legacy_workflows=4 legacy_runs=146 deleted=146 remaining=0
```

两批合计删除：

```text
500 + 146 = 646 legacy workflow runs
```

## 删除后独立只读复核

重新执行 read-only plan：

```text
job 97658818312
Actions: read
Contents: read
```

最终 summary：

```text
CLEANUP_SUMMARY mode=plan protected=6 legacy_workflows=0 legacy_runs=0 deleted=0 remaining=0
```

因此本次不仅清零了 646 个 legacy runs，原 150 个废弃 workflow registry records 也随最后一个 run 删除而从 GitHub Actions 注册表消失。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 自动识别当前 6 个 workflow 为白名单 | user:2026-08-25-actions-history-cleanup | satisfied | dry-run、两批 apply、zero-plan 均输出 protected=6；post-removal main `.github/workflows/` 也精确为 6 个文件 |
| R2 | 只删除其他已废弃 workflow 的历史 runs | user:2026-08-25-actions-history-cleanup | satisfied | `97657439567` 删除 500，`97658472722` 删除 146；`97658818312` 最终 legacy_runs=0 |
| R3 | 绝不碰当前 CI/Release 等白名单历史 | user:2026-08-25-actions-history-cleanup | satisfied | protected workflow runs 完全不进入 legacy 枚举；self-test 覆盖 protected path/id/path/status fail-closed；6 个长期 workflow 在 cleanup 后仍正常运行 |
| R4 | 不暴露 Token，使用受限仓库凭据 | AGENTS.md | satisfied | plan 为 Actions read；apply 仅临时 Actions write + Contents read；Token 未打印、未持久化，随后高权限 job 已删除 |
| R5 | 不新增长期 ghost workflow，并移除一次性维护能力 | user:2026-08-25-actions-history-cleanup | satisfied | 全程未新增 workflow 文件；cleanup 复用 Change Completion Gate；PR #224 已移除 plan/apply job、actions: write 和临时脚本 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | cleanup 不修改产品 UI；cleanup merge 与权限收口 merge 后主 CI 的 Browser Mock 均成功 |
| Backend/API/PostgreSQL Integration | not_applicable | cleanup 不修改后端/数据库；两次 post-merge PostgreSQL Integration 均成功 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | cleanup 不修改产品链路；cleanup merge 和权限收口 merge 后 Full-stack 均成功 |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | dry-run、500+146 apply、zero-plan、cleanup PR/main CI、removal PR/main CI、最终 6 workflow/脚本 404/无 actions:write 均有新鲜证据 |

# 安全设计与实际证明

1. **动态发现 + 精确集合**：避免临时或新 workflow 被自动误纳入保护/删除集合。
2. **完整计划后再删除**：所有 legacy workflow/run 在第一条 DELETE 前完成分页与一致性校验。
3. **白名单完全旁路**：当前 6 个 workflow 不调用 legacy run 枚举，因此其历史不可能进入候选集合。
4. **逐条二次断言**：每条不可逆 DELETE 前再次核验 workflow_id/path/status/protected invariants。
5. **最小权限**：PR 计划阶段实际 `Actions: read`；仅 main marker apply 临时 `Actions: write`。
6. **分批 + rate-limit**：每批最多 500，并保留至少 100 API 请求余量；第二批重新发现后仅删除 146。
7. **独立 zero-plan**：最终不是依据删除 job 自报成功，而是另一个 read-only job 得到 0/0。
8. **高权限立即撤销**：完成后 PR #224 恢复 governance-only Change Completion Gate 并删除临时 script。

# Completion Audit

- [x] upstream_re_read：最终再次核对用户“当前 6 个 workflow 为白名单，只删其他废弃 runs，绝不碰当前历史”的要求和仓库治理规则。
- [x] change_coverage：全部用户要求具有真实 GitHub API/Actions 运行证据，不以 UI 是否即时刷新作为唯一依据。
- [x] reverse_audit：逐个删除对象必须反向归属 legacy workflow；每个 protected path 反向确认不进入枚举；权限从 plan/read → apply/write → removal/no-write 完整闭环。
- [x] unresolved_cleared：legacy workflows/runs 已为 0/0，一次性维护能力已从 main 撤销，post-removal main 门禁全绿，无未满足项。

# A1 / A2 与代码质量 Review

## A1：上游要求 → Change

通过。没有把授权扩大成“删除仓库所有旧 Actions history”，没有删除当前 workflow 的早期合法历史；只处理 path 不在当前 6 个白名单中的 legacy workflow runs。

## A2：Change → GitHub 实际状态

通过：

```text
删除前 150 workflows / 646 runs
→ -500
→ -146
→ 删除后 0 workflows / 0 runs
→ removal PR 移除 actions:write / maintenance script
→ main 仍只有 6 个长期 workflows
```

## 代码质量与安全 Review

通过。开发时 Ruff formatter/import 规则曾暴露机械格式问题，修复未改变删除语义；cleanup final PR HEAD、cleanup merge main、removal PR HEAD、removal merge main 均有新鲜 CI 证据。

# Cleanup 实现交付

Cleanup PR：

```text
#223 安全清理废弃 GitHub Actions 历史
Final HEAD: 04a5bf703830abc7d4ccede8c569659584456eda
Merge: 3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5
```

Cleanup merge 后 main：

```text
CI                      32799498119 success
Full-stack Acceptance   32799498083 success
Runtime Acceptance      32799498173 success
Change Completion Gate  32799498076 success
```

# 权限收口交付

Removal PR：

```text
#224 移除一次性 Actions 历史清理机制
Final HEAD: 2dc2ba7caa4071932e2bc8f29df20e1e700d1da4
Merge: 73027fe300e86d29b5864a0b90d1b7ec82669961
```

Removal merge 后 main：

```text
CI                      32800526971 success
Full-stack Acceptance   32800526941 success
Runtime Acceptance      32800526975 success
Change Completion Gate  32800526951 success
```

最终机器事实：

- `.github/workflows/` 精确 6 个文件；
- `scripts/maintenance/cleanup_legacy_actions_history.py` 不存在；
- `change-completion-gate.yml` 只有 `ready-check`，顶层仅 `contents: read`，不存在 `actions: write`；
- cleanup 完成后的独立 read-only plan 已确认 Actions registry `legacy_workflows=0 / legacy_runs=0`。

# 不可逆性与回滚

- 已删除的 646 个 legacy Actions runs、其日志和 artifacts 不可恢复，这是用户明确授权的一次性清理。
- 当前 6 个 workflow 的历史未进入删除计划。
- 一次性 cleanup 代码和高权限已完全移除，不存在后续自动删除行为。

# Git / 归档

- Cleanup branch: `ops/actions-history-cleanup`
- Cleanup PR: #223，已合并
- Removal branch: `ops/remove-actions-history-cleanup`
- Removal PR: #224，已合并
- Archive branch: `archive/actions-history-cleanup`
- Archive: 本文件由独立归档 PR 从 `changes/active/` 移入 `changes/archive/2026-08/`；归档 PR/merge 状态由 GitHub 历史记录

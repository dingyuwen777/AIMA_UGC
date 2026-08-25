---
schema: rvc-change/v1
id: CHG-20260825-actions-history-cleanup
title: 安全清理废弃 GitHub Actions 历史
level: L2
status: ready_for_review
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

# 成功标准

- [x] 从当前 checkout 的 `.github/workflows/*.yml|*.yaml` 动态发现白名单，并 fail-closed 要求集合精确等于当前 6 个长期 workflow。
- [x] PR 先执行 read-only dry-run，列出保护 workflow、legacy workflow 和可删除 completed run 数量，不做删除。
- [x] apply 模式只处理 workflow path 不在白名单中的 completed runs；任一 run 的 workflow_id/path/status 与计划不一致时，在删除开始前失败。
- [x] 当前 6 个 workflow 的所有历史 run 均不进入删除计划。
- [x] 删除使用当前仓库 `GITHUB_TOKEN` 的 job-level `actions: write`，不引入或打印外部 Token；PR plan 实际权限仅为 `Actions: read / Contents: read`。
- [x] 单次 apply 有删除上限和 API rate-limit 保护；646 个 legacy runs 分两批 500 + 146 完成删除。
- [x] 删除完成后的独立只读 plan 确认 `legacy_workflows=0 / legacy_runs=0`。
- [x] 一次性 `actions: write` job 已从 removal 分支删除，临时 maintenance 脚本已删除；待 removal PR 合并后 `main` 恢复为仅 6 个长期 workflow 且无临时高权限清理能力。

# 白名单

当前唯一受保护 workflow 路径：

```text
.github/workflows/change-completion-gate.yml
.github/workflows/ci.yml
.github/workflows/fullstack.yml
.github/workflows/release.yml
.github/workflows/runtime.yml
.github/workflows/tooling.yml
```

cleanup 实现同时采用：

```text
checkout 动态发现
+
精确集合断言
```

只要当前 `.github/workflows/` 与上述集合不完全一致，就 fail closed，中止计划和删除。

# 实际清理结果

## 1. 删除前只读计划

PR #223 的只读 plan：

```text
protected workflow paths: 6
registered legacy workflow records: 150
validated legacy completed runs: 646
deleted: 0
remaining: 646
```

PR plan job 的 `GITHUB_TOKEN` 权限为：

```text
Actions: read
Contents: read
```

因此删除前的真实 API 枚举没有任何写权限。

## 2. 第一批不可逆删除

实现 PR #223 merge commit：

```text
3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5
```

main `Change Completion Gate` run：

```text
32799498076
```

第一批 apply job：

```text
97657439567
```

实际日志：

```text
GITHUB_TOKEN Permissions
Actions: write
Contents: read

protected=6
legacy_workflows=150
legacy_runs=646
GitHub core API remaining=4238
rate-limit reserve=100
delete_budget=500
deleted=500
remaining=146
```

准确 summary：

```text
CLEANUP_SUMMARY mode=apply protected=6 legacy_workflows=150 legacy_runs=646 deleted=500 remaining=146
```

## 3. 第二批不可逆删除

只 rerun 同一个 apply job，不创建新 workflow，也不复用旧 run id 清单。第二次运行重新从 GitHub API 完整发现和验证剩余集合。

第二批 apply job：

```text
97658472722
```

重新发现：

```text
protected=6
legacy_workflows=4
legacy_runs=146
GitHub core API remaining=3704
rate-limit reserve=100
delete_budget=146
deleted=146
remaining=0
```

准确 summary：

```text
CLEANUP_SUMMARY mode=apply protected=6 legacy_workflows=4 legacy_runs=146 deleted=146 remaining=0
```

两批合计删除：

```text
500 + 146 = 646 legacy workflow runs
```

GitHub 在某个 legacy workflow 的最后一个历史 run 被删除后同步移除了其 Actions registry record，因此第二批开始时 legacy workflow record 已由 150 自动下降为 4。

## 4. 删除后独立只读复核

删除完成后重新执行只读 plan job：

```text
97658818312
```

该 job 权限重新降回：

```text
Actions: read
Contents: read
```

最终真实 API 结果：

```text
protected workflow paths: 6
registered legacy workflow records: 0
validated legacy completed runs: 0
deleted: 0
remaining: 0
```

准确 summary：

```text
CLEANUP_SUMMARY mode=plan protected=6 legacy_workflows=0 legacy_runs=0 deleted=0 remaining=0
```

这证明此次清理不仅删除了 646 个 legacy runs，也使原 150 个废弃 Actions workflow registry records 全部消失。

# 范围

- 临时在现有 `change-completion-gate.yml` 中增加 read-only plan job 和 marker-gated apply job。
- 临时增加 `scripts/maintenance/cleanup_legacy_actions_history.py`，负责白名单发现、Actions API 分页、计划校验、rate-limit 保护和分批删除。
- cleanup 完成后立即通过独立 removal PR 删除两个临时 job 和 maintenance 脚本。
- 最终独立归档本 Change。

# 非目标

- 不删除当前 6 个 workflow 的任何历史 run。
- 不删除 GitHub Release、Tag、PR、Commit、Issue 或仓库文件历史。
- 不改变 `ci.yml`、`fullstack.yml`、`runtime.yml`、`tooling.yml`、`release.yml` 的长期职责。
- 不保留长期 Actions history cleanup 功能；这是一次性仓库维护操作。

# 必须保持不变

- 当前 6 个 workflow 的 path/history 为保护对象。
- `release.yml` 历史不得删除。
- `ci.yml`、`fullstack.yml`、`runtime.yml`、`tooling.yml`、`change-completion-gate.yml` 的既有历史不得删除。
- cleanup 完成后仓库不保留 `actions: write` maintenance job。
- cleanup 完成后不新增第 7 个 workflow。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 自动识别当前 6 个 workflow 为白名单 | user:2026-08-25-actions-history-cleanup | satisfied | PR dry-run 与两批 apply 均实际输出 6 个受保护路径；最终只读 plan `97658818312` 再次确认 protected=6 |
| R2 | 只删除其他已废弃 workflow 的历史 runs | user:2026-08-25-actions-history-cleanup | satisfied | 第一批 `97657439567` 删除 500，第二批 `97658472722` 删除 146；最终只读 plan legacy_runs=0 |
| R3 | 绝不碰当前 CI/Release 等白名单历史 | user:2026-08-25-actions-history-cleanup | satisfied | 白名单 workflow 从不调用 legacy `list_runs()`；self-test 覆盖 protected path/id/path/status fail-closed；最终 protected=6 且 registry 正常存在 |
| R4 | 不暴露 Token，使用受限仓库凭据 | AGENTS.md | satisfied | plan 实际权限 Actions read；apply 两批实际权限仅 Actions write + Contents read；Token 全程 masked，未写文件或日志 |
| R5 | 不新增长期 ghost workflow，并在完成后移除临时高权限机制 | user:2026-08-25-actions-history-cleanup | satisfied | 从未新增 workflow 文件；cleanup 复用现有 Change Completion Gate；`ops/remove-actions-history-cleanup` 已恢复原 governance-only workflow 并删除临时脚本 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | cleanup 不修改产品 UI/浏览器行为；但 merge 后主 CI 的 Browser Mock 仍成功 |
| Backend/API/PostgreSQL Integration | not_applicable | cleanup 不修改后端/数据库行为；merge 后 PostgreSQL Integration 仍成功 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | cleanup 逻辑不需要 Full-stack 证明；实现 merge 后 Full-stack run `32799498083` 仍 success |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | 两批 apply `97657439567` / `97658472722` success；独立只读 zero-plan `97658818312` success；main CI `32799498119`、Runtime `32799498173`、Full-stack `32799498083`、Completion Gate `32799498076` success；removal PR 待验证 |

# 安全设计与实际证明

1. **双重白名单**：动态扫描 checkout，并要求精确等于批准的 6 个路径。实际三阶段（plan/apply/zero-plan）均通过。
2. **先计划后删除**：全部 legacy workflow/run 先分页和验证，再做第一条 DELETE。实际首次验证 150 workflow / 646 run 无冲突。
3. **白名单完全旁路**：protected workflow 不枚举其 runs，因此当前 CI/Release history 不可能进入删除计划。
4. **删除前二次断言**：每条 DELETE 前再次调用 `validate_legacy_run()`。
5. **最小权限**：plan 为 Actions read；仅 marker-gated main apply 为 Actions write。实际 GitHub Runner 权限日志与设计一致。
6. **分批 + rate-limit**：第一批上限 500、预留 100 API 请求；第二批重新发现后仅删除剩余 146。
7. **删除后独立验证**：Actions read-only plan 返回 `legacy_workflows=0 / legacy_runs=0`。
8. **立即移除能力**：removal 分支已删除一次性 `actions: write` job 和 maintenance script，不把仓库维护操作变成长期开口。

# Completion Audit

- [x] upstream_re_read：重新读取用户“当前 6 个 workflow 为白名单、只删其他废弃 runs、绝不碰当前历史”的明确要求，以及当前 `AGENTS.md` / Reliable Vibe Coding 交付约束。
- [x] change_coverage：R1-R5 全部具有真实 GitHub API / Actions 运行证据；不是根据 Actions UI 外观推断完成。
- [x] reverse_audit：从每个实际删除 run 反向验证 legacy workflow_id/path/status；从每个 protected path 反向确认完全不进入删除枚举；从 cleanup job 权限反向确认 only-main/marker/write 边界。
- [x] unresolved_cleared：646 个 legacy runs 已删除，独立只读复核为 0/0；当前不存在业务或 cleanup 语义未满足项。剩余仅是 removal PR、post-merge 验证和 Change archive 的交付机械步骤。

# A1 / A2 与代码质量 Review

## A1：上游要求 → 当前 Change

通过。用户三个核心不可替代条件全部满足：

```text
当前 6 个 workflow 自动形成保护集合
只删除其他 legacy workflow runs
绝不删除当前 CI/Release 等保护历史
```

没有扩大为“删除所有旧 Actions history”，也没有把当前白名单历史按时间截断。

## A2：当前 Change → 实际 GitHub 状态

通过：

```text
删除前：150 legacy workflows / 646 legacy runs
第一批：-500
第二批：-146
删除后：0 legacy workflows / 0 legacy runs
保护集合：始终 6
```

不是仅以 apply job success 作为结论，另外执行了 Actions-read-only 的独立 post-cleanup plan。

## 代码质量与安全 Review

通过，未发现未解决的重要问题。实际开发过程中出现的 Ruff formatter/import 规则失败均只做机械格式修复，没有改变删除语义。最终候选 HEAD `04a5bf703830abc7d4ccede8c569659584456eda` 的 CI、Full-stack、Runtime、Change Completion Gate 全部 success。

高风险点均有明确控制：

- 不接受白名单漂移；
- 不删除非 completed run；
- 不接受 workflow_id/path mismatch；
- 不枚举 protected workflow runs；
- 不持久化 Token；
- 不创建第 7 个 cleanup workflow；
- 不永久保留 `actions: write` job。

# 主分支验证

实现 merge：

```text
PR #223
Final HEAD: 04a5bf703830abc7d4ccede8c569659584456eda
Merge commit: 3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5
```

merge 后主分支：

```text
CI                    32799498119 success
Full-stack Acceptance 32799498083 success
Runtime Acceptance    32799498173 success
Change Completion Gate 32799498076 success
```

CI 内 Repository Quality、PostgreSQL Integration、CI Gate 均 success。

# Removal / 权限收口

当前 removal 分支：

```text
ops/remove-actions-history-cleanup
```

已执行：

- `change-completion-gate.yml` 恢复 governance-only 内容；
- 删除 `legacy-actions-cleanup-plan`；
- 删除 `legacy-actions-cleanup-apply`；
- 因此删除临时 job-level `actions: write`；
- 删除 `scripts/maintenance/cleanup_legacy_actions_history.py`；
- 保持当前 6 个 workflow 文件不变。

待 removal PR 最新 HEAD CI 成功后合并；合并后再次核对 `main` 无临时清理权限/脚本且 workflow registry 仍只有 6 个，再独立归档本 Change。

# 回滚与不可逆性

- 已删除的 646 个 legacy Actions runs、其日志和 artifacts 不可恢复，这是用户明确授权的不可逆操作。
- 当前 6 个 workflow 的历史未进入删除计划。
- 临时仓库代码/Workflow 权限机制可通过 removal PR 完全移除；删除历史本身不存在代码回滚。

# Git / 交付

- Cleanup branch: `ops/actions-history-cleanup`
- Cleanup PR: #223 `安全清理废弃 GitHub Actions 历史`，已合并
- Cleanup final PR HEAD: `04a5bf703830abc7d4ccede8c569659584456eda`
- Cleanup merge commit: `3591c1fbdbfdb50a65c6da3e773fe6e12b1246d5`
- First apply job: `97657439567`，deleted 500 / remaining 146
- Second apply job: `97658472722`，deleted 146 / remaining 0
- Independent read-only zero verification: `97658818312`，legacy_workflows=0 / legacy_runs=0
- Removal branch: `ops/remove-actions-history-cleanup`
- Removal PR: 待创建
- Archive: removal merge + post-merge validation 后执行独立归档 PR

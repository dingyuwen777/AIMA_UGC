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

当前 `main` 的 `.github/workflows/` 已收敛为 6 个长期 workflow，但 GitHub Actions 左侧栏仍显示大量已经从仓库删除的历史 workflow。用户明确要求执行一次不可恢复的 Actions 历史清理：自动识别当前 6 个 workflow 为白名单，只删除其他废弃 workflow 的历史 run，绝不删除当前 CI/Release 等白名单 workflow 的 run、artifact 或日志。

本 Change 只处理 GitHub Actions 历史记录，不修改产品代码、数据库、Contract、Migration、Release 产物或当前 6 个 workflow 的长期验证职责。

# 成功标准

- [x] 从当前 checkout 的 `.github/workflows/*.yml|*.yaml` 动态发现白名单，并 fail-closed 要求集合精确等于当前 6 个长期 workflow。
- [x] PR 只执行 read-only dry-run，列出保护 workflow、legacy workflow 和可删除 completed run 数量，不做删除。
- [x] apply 模式只处理 workflow path 不在白名单中的 completed runs；任一 run 的 workflow_id/path/status 与计划不一致时，在删除开始前失败。
- [x] 当前 6 个 workflow 的所有历史 run 均不进入删除计划。
- [x] 删除使用当前仓库 `GITHUB_TOKEN` 的 job-level `actions: write`，不引入或打印外部 Token；PR plan 实际权限仅为 `Actions: read / Contents: read`。
- [x] 单次 apply 有删除上限和 API rate-limit 保护；遗留数量过大时通过同一白名单 workflow job 分批继续，不创建第 7 个 workflow。
- [ ] legacy runs 清零或达到 GitHub API 可清理的事实边界后，删除临时 cleanup job/script，并再次确认当前 `.github/workflows/` 仍只有 6 个长期 workflow。

# 当前 dry-run 事实

PR #223，HEAD `812672be20dcafc7d9b8ab1716f51d7f7c5be6b4` 的 `Change Completion Gate` run `32798721779` 中：

```text
Legacy Actions history cleanup plan
→ self-test: success
→ token permissions: Actions read / Contents read
→ protected workflow paths: 6
→ registered legacy workflow records: 150
→ validated legacy completed runs: 646
→ deleted: 0
→ remaining: 646
```

脚本在输出删除计划前已经完整分页并验证所有 legacy run；未发现 `workflow_id`、path 或 status 冲突，也未发现任何白名单 path 进入 legacy 计划。因此预计 apply 需要两批：首批最多 500，第二批约 146；每一批都会重新从 API 发现和验证剩余计划，而不是复用旧 run id 清单。

# 范围

- 在现有 `change-completion-gate.yml` 中临时增加：PR 只读 plan job，以及仅特定 main merge marker 才执行的 apply job。
- 增加临时 maintenance 脚本，负责白名单发现、Actions API 分页、计划校验、rate-limit 保护和分批删除。
- 完成后通过独立清理 PR 移除临时 job/script，并归档本 Change。

# 非目标

- 不删除当前 6 个 workflow 的任何历史 run。
- 不删除 GitHub Release、Tag、PR、Commit、Issue 或仓库文件历史。
- 不改变 `ci.yml`、`fullstack.yml`、`runtime.yml`、`tooling.yml`、`release.yml` 的长期职责。
- 不尝试绕过 GitHub Actions API 对 ghost workflow UI 的平台级限制；如果某个 legacy workflow 已无 run 但 UI 仍显示，则记录为 GitHub 后端残留。

# 必须保持不变

当前白名单必须精确为：

```text
.github/workflows/change-completion-gate.yml
.github/workflows/ci.yml
.github/workflows/fullstack.yml
.github/workflows/release.yml
.github/workflows/runtime.yml
.github/workflows/tooling.yml
```

任何集合漂移都必须中止 cleanup，而不是自动扩大或缩小白名单。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 自动识别当前 6 个 workflow 为白名单 | user:2026-08-25-actions-history-cleanup | satisfied | PR #223 dry-run run `32798721779` 实际发现并输出 6 个受保护路径，且与当前 `.github/workflows/` 精确一致 |
| R2 | 删除能力只作用于其他已废弃 workflow 的历史 runs | user:2026-08-25-actions-history-cleanup | satisfied | dry-run 完整验证 150 个 legacy workflow records / 646 个 completed runs；apply 复用同一 `collect_cleanup_plan()` 并在首个 DELETE 前完成全部校验 |
| R3 | 绝不碰当前 CI/Release 等白名单历史 | user:2026-08-25-actions-history-cleanup | satisfied | self-test 覆盖 protected path、workflow_id/path mismatch、non-completed run 全部 fail-closed；生产 dry-run 中白名单 workflow runs 完全不枚举 |
| R4 | 不暴露 Token，使用受限仓库凭据 | AGENTS.md | satisfied | PR plan job 日志显示 `Actions: read / Contents: read`；apply 权限仅在带唯一 marker 的 main push job 提升为 job-level `actions: write`，日志不会输出 Token |
| R5 | 不新增长期 ghost workflow | user:2026-08-25-actions-history-cleanup | satisfied | 没有新增 `.github/workflows/*.yml`；plan/apply 都临时挂在现有白名单 `change-completion-gate.yml` 下，完成后移除临时 job/script |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI/浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端或数据库行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | 不修改真实产品链路 |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | cleanup self-test + PR read-only plan `32798721779` 已成功；main apply summary、post-cleanup plan、临时机制移除将在 merge 后补齐，Change 保持 Active 直到完成 |

# 安全设计

1. **双重白名单**：脚本动态扫描 checkout，同时要求扫描结果与当前 6 个预期路径完全一致；不一致立即失败。
2. **先计划后删除**：完整分页获取 workflow 与 legacy run；所有 run 必须满足 `workflow_id` 一致、规范化 path 等于 legacy workflow path、`status=completed`，否则整个 apply 在第一次 DELETE 前失败。
3. **当前历史完全旁路**：白名单 workflow 不枚举、不删除其 runs；即使 GitHub 返回多个相同受保护 path 的 workflow record，也全部保护。
4. **最小权限**：PR plan job 只有 `actions: read`；main apply job 才有 `actions: write`，且只在 merge commit 含唯一 `[actions-history-cleanup]` marker 时运行。
5. **分批删除**：单次最多 500 个 run；执行前读取 rate limit，并保留至少 100 次 API 请求余量。
6. **无新 workflow 文件**：复用当前白名单中的 `change-completion-gate.yml`，完成后删除临时 job/script。

# Completion Audit

- [x] upstream_re_read：重新读取本轮用户要求、当前 main `AGENTS.md`、Reliable Vibe Coding Skill、Change Management 与 Verification Review；完成定义仍是“当前 6 个 path 唯一白名单 + 只删其他 legacy completed runs + 不碰当前历史”。
- [x] change_coverage：R1-R5 全部映射到脚本安全不变量、workflow 权限和 dry-run 证据；没有把 UI 外观变化误当成唯一成功证明。
- [x] reverse_audit：从“每个将删 run → legacy workflow_id/path/status”反向审计，并从“每个当前 workflow path → 不枚举其 runs”反向审计；还检查了 apply 权限只存在于 marker-gated main job。
- [x] unresolved_cleared：Requirement 无 `not_satisfied`；实际不可逆删除作为 merge 后运维步骤尚未执行，因此 Change 继续 Active，不提前标记 `done` 或归档。

# A1 / A2 与代码质量 Review

## A1：上游要求 → 当前 Change

通过。用户要求只有三个核心不可替代条件：当前 6 个 workflow 自动形成白名单、删除其他废弃 workflow runs、绝不触碰当前 CI/Release 历史。Change 已全部覆盖，并额外加入 fail-closed、最小权限、分批/rate-limit 保护，不改变用户语义。

## A2：当前 Change → 实现 / 验证

通过。PR dry-run 使用真实 GitHub Actions API 返回 150 个 legacy workflow records / 646 个 completed runs，self-test 与全量计划校验均成功，且 `deleted=0`。apply 使用同一个计划构造函数，不存在平行的宽松删除逻辑。

## 代码质量 Review

通过，未发现阻塞问题。重点确认：

1. `discover_current_workflow_paths()` 既动态发现又要求集合精确等于批准的 6 个路径，避免误把临时/新 workflow 自动加入白名单。
2. `collect_cleanup_plan()` 在第一次 DELETE 前完成所有 legacy workflows/runs 的分页与校验；遇到 running/queued 或 path/id 异常会整批 abort。
3. `validate_legacy_run()` 在每次不可逆 DELETE 前再次验证关键不变量。
4. 白名单 workflow 不调用 `list_runs()`，因此当前历史不进入删除候选集合。
5. apply 单次最多 500，并读取 rate limit、保留 100 次请求余量；646 条计划可以安全分两批执行。
6. Token 只通过环境变量传给标准库 HTTP client，不打印、不写文件；PR plan job 的实际日志确认只有 Actions read 权限。

# 验证与交付计划

1. Draft PR read-only dry-run：已完成，150 legacy workflows / 646 completed runs / 0 deletes。
2. 当前 Change 已进入 `ready_for_review`；等待最新 HEAD 的永久 CI/Completion Gate 成功后转 PR Ready。
3. 使用带 `[actions-history-cleanup]` 的 merge commit 合并；main apply job 删除首批最多 500。
4. 读取 apply job `CLEANUP_SUMMARY`；若 `remaining > 0`，只 rerun 同一个 apply job，预计第二批约 146。
5. 所有批次完成后，再运行一次只读 plan，要求 `legacy_runs=0`；legacy workflow record 若 run=0 仍存在则记录为 GitHub UI/backend ghost，不再做越权操作。
6. 新建 cleanup-removal PR，删除临时 script/job；验证并合并。
7. 将 Change 状态改为 `done` 并独立归档。

# 回滚与不可逆性

- 已删除的 GitHub Actions runs/artifacts/logs不可恢复，这是用户明确授权的目标；因此 apply 前必须完成全量计划和 fail-closed 校验。
- 仓库代码侧可通过 revert 临时 cleanup workflow/script 变更回滚；它不会恢复已经删除的 Actions 历史。

# Git 状态

- Branch: `ops/actions-history-cleanup`
- PR: #223 `安全清理废弃 GitHub Actions 历史`
- Dry-run HEAD: `812672be20dcafc7d9b8ab1716f51d7f7c5be6b4`
- Dry-run Actions run: `32798721779`
- 当前状态：`ready_for_review`；等待最新 HEAD 新鲜门禁后转 Ready/合并。

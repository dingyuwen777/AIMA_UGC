---
schema: rvc-change/v1
id: CHG-20260825-actions-history-cleanup
title: 安全清理废弃 GitHub Actions 历史
level: L2
status: in_progress
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

- [ ] 从当前 checkout 的 `.github/workflows/*.yml|*.yaml` 动态发现白名单，并 fail-closed 要求集合精确等于当前 6 个长期 workflow。
- [ ] PR 只执行 read-only dry-run，列出保护 workflow、legacy workflow 和可删除 completed run 数量，不做删除。
- [ ] apply 模式只处理 workflow path 不在白名单中的 completed runs；任一 run 的 workflow_id/path/status 与计划不一致时，在删除开始前失败。
- [ ] 当前 6 个 workflow 的所有历史 run 均不进入删除计划。
- [ ] 删除使用当前仓库 `GITHUB_TOKEN` 的 job-level `actions: write`，不引入或打印外部 Token。
- [ ] 单次 apply 有删除上限和 API rate-limit 保护；遗留数量过大时通过同一白名单 workflow job 分批继续，不创建第 7 个 workflow。
- [ ] legacy runs 清零或达到 GitHub API 可清理的事实边界后，删除临时 cleanup job/script，并再次确认当前 `.github/workflows/` 仍只有 6 个长期 workflow。

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
| R1 | 自动识别当前 6 个 workflow 为白名单 | user:2026-08-25-actions-history-cleanup | not_satisfied | 待 PR dry-run 验证 checkout 发现结果 |
| R2 | 只删除其他已废弃 workflow 的历史 runs | user:2026-08-25-actions-history-cleanup | not_satisfied | 待 dry-run/apply 计划证据 |
| R3 | 绝不碰当前 CI/Release 等白名单历史 | user:2026-08-25-actions-history-cleanup | not_satisfied | 待脚本 fail-closed 自测与 dry-run 证据 |
| R4 | 不暴露 Token，使用受限仓库凭据 | AGENTS.md | not_satisfied | 待 workflow permissions 与执行证据 |
| R5 | 不新增长期 ghost workflow，cleanup 完成后恢复 6 个长期入口 | user:2026-08-25-actions-history-cleanup | not_satisfied | 待 cleanup removal PR 与最终目录证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI/浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端或数据库行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | 不修改真实产品链路 |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | cleanup 脚本 self-test、PR read-only plan、main apply summary、post-cleanup workflow/run 复核、临时机制移除 |

# 安全设计

1. **双重白名单**：脚本动态扫描 checkout，同时要求扫描结果与当前 6 个预期路径完全一致；不一致立即失败。
2. **先计划后删除**：完整分页获取 workflow 与 legacy run；所有 run 必须满足 `workflow_id` 一致、规范化 path 等于 legacy workflow path、`status=completed`，否则整个 apply 在第一次 DELETE 前失败。
3. **当前历史完全旁路**：白名单 workflow 不枚举、不删除其 runs；即使 GitHub 返回多个相同受保护 path 的 workflow record，也全部保护。
4. **最小权限**：PR plan job 只有 `actions: read`；main apply job 才有 `actions: write`，且只在 merge commit 含唯一 `[actions-history-cleanup]` marker 时运行。
5. **分批删除**：单次最多 500 个 run；执行前读取 rate limit，并保留至少 100 次 API 请求余量。
6. **无新 workflow 文件**：复用当前白名单中的 `change-completion-gate.yml`，完成后删除临时 job/script。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 验证与交付计划

1. 在 Draft PR 上运行脚本 `--self-test` 与 `--plan`，读取 legacy workflow/run 精确数量。
2. 将本 Change 更新为 `ready_for_review`，记录 dry-run 证据；同一 HEAD 永久 CI 通过后转 Ready。
3. 使用带 `[actions-history-cleanup]` 的 merge commit 合并；main apply job 按批删除。
4. 若 summary 显示 remaining > 0，仅 rerun 同一个 apply job，直到 remaining=0 或出现明确平台边界。
5. 再次 API plan 确认 legacy completed runs 为 0，确认白名单 history 未被删除。
6. 新建 cleanup-removal PR，删除临时 script/job；验证后合并。
7. 将 Change 状态改为 `done` 并独立归档。

# 回滚与不可逆性

- 已删除的 GitHub Actions runs/artifacts/logs不可恢复，这是用户明确授权的目标；因此 apply 前必须完成全量计划和 fail-closed 校验。
- 仓库代码侧可通过 revert 临时 cleanup workflow/script 变更回滚；它不会恢复已经删除的 Actions 历史。

# Git 状态

- Branch: `ops/actions-history-cleanup`
- PR: 待创建
- 当前状态：`in_progress`

---
schema: rvc-change/v1
id: CHG-20260825-release-workflow-publication
title: 系统修复并重构 Release Workflow 发布阶段
level: L3
status: in_progress
owner: aima
branch: fix/release-workflow-publication
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - release
  - deployment
affected_paths:
  - .github/workflows/release.yml
  - tests/unit/test_docker_build_sources.py
  - docs/appendix/11_生产部署与离线Release方案.md
  - docs/roadmap/02_生产上线实施路线.md
  - changes/active/CHG-20260825-release-workflow-publication/CHANGE.md
contracts: []
data_changes: []
---

# 背景与根因

正式 Release #39（run `32803805624`）已经证明候选构建、离线 Bundle、真实 Compose 回放、GHCR Backend/Frontend 推送和 digest 校验全部成功；最终仅在 `Create Git tag and GitHub Release` 失败：

```text
failed to run git: fatal: not a git repository (or any of the parent directories): .git
```

根因是当前 Release 将“只读构建/回放”和“带写权限发布”拆成两个独立 Job，这是正确的最小权限设计；但 `publish-release` Job 不 checkout 源码，最后的 `gh release create` 又没有显式 repository 上下文，GitHub CLI 因而尝试从本地 `.git` 推断仓库并失败。

本 Change 不把两阶段设计退回一个大 Job，也不通过无意义 checkout 掩盖问题，而是把 Release Workflow 重新整理为可读、显式、可验证的两阶段发布流程。

# 目标

1. 修复 #39 的 GitHub Release 创建失败，使 publish Job 完全不依赖本地 `.git`。
2. 保留“构建/验证只读，正式发布才拿写权限”的安全边界。
3. 让 Release Workflow 从上到下可以按业务阶段阅读，不靠历史知识理解。
4. 所有 GitHub CLI 发布操作显式绑定当前仓库，不再依赖隐式 repository 推断。
5. 保留当前手工正式发布、PR 只读 dry-run、离线 Bundle 回放、GHCR digest、Tag/Release 的既有能力。
6. 增加回归测试，防止未来再次把 publish Job 写成依赖 checkout/.git 的隐式行为。

# 非目标

- 不把正式 Release 改成每次 push/main 自动运行。
- 不改变 Backend/Frontend GHCR package 名称。
- 不升级 Python/Node/PostgreSQL/Actions 版本。
- 不新增 PAT、额外 Secret 或第三方发布服务。
- 不在本 Change 实现 SBOM、签名、provenance、协调 Backup/Restore。
- 不改变 canonical `compose.yaml` Runtime 或服务器部署目录。

# 必须保持不变

```text
正式发布
→ 仅 workflow_dispatch 手工触发

PR
→ 仅 Release 相关路径变化时执行 dry-run
→ 无 contents/packages 写权限

阶段 1 build-verify
→ checkout 当前候选 SHA
→ 构建 Linux/AMD64 Backend/Frontend
→ 固定 postgres:18.4
→ 生成 images.tar + manifest + SHA256SUMS + DEPLOY.md
→ 删除本地候选镜像后从 Bundle 重新 load
→ canonical Compose --no-build --pull never 回放

阶段 2 publish-release
→ 只消费阶段 1 已回放候选
→ 仅此 Job 获得 contents:write + packages:write
→ 推送 GHCR 版本/SHA tag
→ 记录真实 digest
→ 创建 Git Tag + GitHub Release + 可下载 Bundle
```

# 方案比较

## 方案 A：只给 publish Job 增加 checkout

优点：改动最少，`gh` 能通过 `.git` 找到仓库。

缺点：publish Job 本来只需要“已验证 artifact + GitHub/GHCR API”，重新 checkout 会把源码工作区变成一个不必要依赖；以后仍可能有其他命令继续依赖隐式 Git context，业务阶段也不够清楚。

结论：不采用。

## 方案 B：只增加 `GH_REPO`

优点：直接修复当前错误，不需要 checkout。

缺点：只补环境变量虽然能修 #39，但现有 workflow 仍把发布上下文、权限边界、阶段含义分散在多处，后续维护者不容易判断哪些操作必须显式 repo、哪些步骤是正式发布 commit point。

结论：作为必要机制，但单独采用不够。

## 方案 C：保留两阶段安全架构，系统整理发布上下文、阶段命名和回归门禁（采用）

- 顶部明确解释两种触发模式与两阶段职责；
- 静态 Release 配置集中到 workflow-level `env`；
- build Job 继续只读；publish Job 继续最小写权限；
- publish Job 明确设置 `GH_REPO=${{ github.repository }}`；
- `gh release view/create` 显式使用 `--repo "${GH_REPO}"`；
- publish Job 不 checkout，并增加显式 repo preflight；
- 发布成功后再读取 GitHub Release/Tag 做最终确认；
- 测试直接约束上述不变量；
- Appendix/Roadmap 同步当前长期流程。

优点：修根因、权限清楚、可读性高、以后不易回归，同时不改变现有业务 Runtime 和正式发布触发语义。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 下次正式 Release 不再因 publish Job 缺少 `.git` 而失败 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 待 workflow 实现与 PR dry-run/CI 验证 |
| R2 | Workflow 要系统、清楚、可由维护者从上到下理解 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 待阶段结构、注释、命名和文档完成 |
| R3 | 正式 Release 只由用户手工触发，普通提交不正式发布 | user:2026-08-25-manual-release-only | not_satisfied | 待确认 `workflow_dispatch` + PR dry-run 触发保持不变 |
| R4 | 保留 Build/Replay → GHCR digest → Tag/Release → Bundle 的长期 Release 能力 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 待 workflow/测试/文档验证 |
| R5 | PR dry-run 不获得正式发布写权限 | docs/appendix/11_生产部署与离线Release方案.md | not_satisfied | 待权限测试验证 |
| R6 | publish Job 不依赖 checkout/.git，GitHub CLI 使用显式仓库上下文 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 待回归测试验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI/浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端/数据库业务行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | 不修改产品 Full-stack 链路；Release 自己执行真实 Compose replay |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | Unit release-workflow invariants + Release PR dry-run + CI/Runtime/Completion Gate；必要时读取正式 Release dry-run logs |

# 实施计划

1. **建立失败回归测试**
   - 修改：`tests/unit/test_docker_build_sources.py`
   - 约束 publish Job 必须显式 `GH_REPO`、`gh release ... --repo`，且不得靠 checkout 取得 `.git`。
   - 先在 Draft PR 观察目标测试因当前实现失败。

2. **重构 Release Workflow 可读结构**
   - 修改：`.github/workflows/release.yml`
   - 集中静态 Release env；增加顶部流程说明；统一阶段/步骤命名；保留两阶段最小权限。
   - publish Job 增加显式仓库上下文与 preflight，不 checkout。

3. **修复正式发布与增加最终验证**
   - `gh release view/create` 全部显式 `--repo`；API URL 使用 `GH_REPO`。
   - GitHub Release 创建后显式验证 Tag、Release、关键资产存在。

4. **同步长期文档**
   - `docs/appendix/11_生产部署与离线Release方案.md` 解释触发方式、两个 Job、权限和发布 commit point。
   - `docs/roadmap/02_生产上线实施路线.md` 只更新与当前 Release 机器事实直接相关的摘要。

5. **验证与交付**
   - 运行目标 Unit、Repository Quality、Release PR dry-run、Runtime/Completion Gate。
   - Completion Audit / A1+A2 Review 后进入 `ready_for_review`，正常合并。
   - 合并后只验证 main；不自动触发正式 v2.0.0 Release，正式版本仍由用户手工 Run workflow。

# 部署、兼容与回滚

- 无 Schema/Migration/业务数据变化。
- 不改变服务器 Runtime、Compose、AIMA_HOST_ROOT 或现有 GHCR package 名称。
- 回滚只需 revert workflow/test/doc 变更；不会删除已存在的 GHCR 镜像。
- #39 已成功写入的 `v2.0.0` GHCR tags 属于未完成正式 GitHub Release 的部分发布状态；本 Change 不主动删除这些 package tags。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# Git 状态

- Branch: `fix/release-workflow-publication`
- PR: 待创建
- Release #39 evidence: run `32803805624`

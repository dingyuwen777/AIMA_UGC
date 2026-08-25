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
  - tests/unit/test_release_workflow.py
  - changes/active/CHG-20260825-release-workflow-publication/CHANGE.md
contracts: []
data_changes: []
---

# 背景与根因

正式 Release #39（run `32803805624`）已经证明候选构建、离线 Bundle、真实 Compose 回放、GHCR Backend/Frontend 推送和 digest 校验全部成功；最终仅在 `Create Git tag and GitHub Release` 失败：

```text
failed to run git: fatal: not a git repository (or any of the parent directories): .git
```

根因是 Release 将“只读构建/回放”和“带写权限发布”拆成两个独立 Job，这是正确的最小权限设计；但 `publish-release` Job 不 checkout 源码，最后的 `gh release create` 又没有显式 repository 上下文，GitHub CLI 因而尝试从本地 `.git` 推断仓库并失败。

用户随后明确补充安全要求：Backend/Frontend GHCR 镜像不得公开。GitHub Container Registry 的 Package visibility 是独立事实，不能因为“首次默认 private”就长期假设现有 Package 一定私有。因此正式流程必须 fail closed 检查实际 Package `visibility=private`，而不是让 workflow 尝试修改 Package visibility。

本 Change 不把两阶段设计退回一个大 Job，也不通过无意义 checkout 掩盖问题，而是把 Release Workflow 整理为可读、显式、可验证的两阶段发布流程。

# 目标

1. 修复 #39 的 GitHub Release 创建失败，使 publish Job 完全不依赖本地 `.git`。
2. 保留“构建/验证只读，正式发布才拿写权限”的安全边界。
3. 让 Release Workflow 从上到下可按业务阶段阅读，不靠历史知识理解。
4. 所有 GitHub CLI 发布操作显式绑定当前仓库，不再依赖隐式 repository 推断。
5. 保留当前手工正式发布、PR 只读 dry-run、离线 Bundle 回放、GHCR digest、Tag/Release 的既有能力。
6. Backend/Frontend GHCR Package 必须保持 `private`；任何非 private 状态在 push 前直接中止。
7. 增加回归测试，防止发布上下文、权限、触发方式和私有镜像门禁回归。

# 非目标

- 不把正式 Release 改成每次 push/main 自动运行。
- 不改变 Backend/Frontend GHCR package 名称。
- 不升级 Python/Node/PostgreSQL/Actions 版本。
- 不新增 PAT、额外 Secret 或第三方发布服务。
- 不自动改变 GHCR Package visibility。
- 不在本 Change 实现 SBOM、签名、provenance、协调 Backup/Restore。
- 不改变 canonical `compose.yaml` Runtime 或服务器部署目录。

# 必须保持不变

```text
正式发布
→ 仅 workflow_dispatch 手工触发

PR
→ 仅 Release 相关路径变化时执行 dry-run
→ 无 contents/packages 写权限

Phase 1 build-verify
→ checkout 当前候选 SHA
→ 只读检查 GitHub/Packages/CI
→ 要求两个 GHCR Package visibility=private
→ 构建 Linux/AMD64 Backend/Frontend
→ 固定 postgres:18.4
→ 生成 images.tar + manifest + SHA256SUMS + DEPLOY.md
→ 删除本地候选镜像后从 Bundle 重新 load
→ canonical Compose --no-build --pull never 回放

Phase 2 publish-release
→ 只消费 Phase 1 已回放候选
→ 不 checkout 源码，不依赖 .git
→ 仅此 Job 获得 contents:write + packages:write
→ push 前再次要求 GHCR Package visibility=private
→ 推送 GHCR 版本/SHA tag并记录 digest
→ 创建 Git Tag + GitHub Release + 可下载 Bundle
→ 发布后重新验证 Tag、Release assets 和 Package 私有性
```

# 方案比较

## 方案 A：只给 publish Job 增加 checkout

优点：改动最少，`gh` 能通过 `.git` 找到仓库。

缺点：publish Job 本来只需要“已验证 artifact + GitHub/GHCR API”，重新 checkout 会制造无意义源码依赖；以后仍可能继续依赖隐式 Git context。

结论：不采用。

## 方案 B：只增加 `GH_REPO`

优点：直接修复当前错误，不需要 checkout。

缺点：只补环境变量虽然能修 #39，但不会解决流程可读性、Package 私有门禁和发布后确认，也无法避免以后同类隐式上下文回归。

结论：作为必要机制，但单独采用不够。

## 方案 C：保留两阶段安全架构，系统整理上下文、私有门禁和最终验证（采用）

- Workflow 顶部直接解释两种触发模式和两个 Phase；
- 静态 Release 配置集中到 workflow-level `env`；
- build Job 继续只读，publish Job 继续最小写权限；
- 两个 Job 的 GitHub CLI 都使用显式 `GH_REPO`；
- PR dry-run 在无 `.git` 临时目录真实执行 `gh repo view <repo>`，证明显式 context 可工作；
- Phase 1 和 Phase 2 均读取 GitHub Package API，要求 Backend/Frontend `visibility=private`；
- publish Job 不 checkout；
- `gh release view/create` 显式 `--repo`；
- 发布成功后验证 Tag target、Release assets 和 Package 私有性；
- Unit 测试直接约束这些不变量。

优点：修根因、权限清楚、镜像隐私 fail closed、流程可读、以后不易回归，同时不改变业务 Runtime 和正式发布触发语义。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 下次正式 Release 不再因 publish Job 缺少 `.git` 而失败 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 已实现显式 `GH_REPO` / `--repo` 和无 `.git` context probe；待最终 CI/Release dry-run |
| R2 | Workflow 要系统、清楚、可由维护者从上到下理解 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 已按触发说明、Phase 1/2、集中 env、语义化 step 整理；待 Review |
| R3 | 正式 Release 只由用户手工触发，普通提交不正式发布 | user:2026-08-25-manual-release-only | not_satisfied | `workflow_dispatch` + Release 相关 PR dry-run；Unit 测试已建立，待 Green |
| R4 | 保留 Build/Replay → GHCR digest → Tag/Release → Bundle 的长期 Release 能力 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 现有链路全部保留；Release PR dry-run 正在验证真实 build/replay |
| R5 | PR dry-run 不获得正式发布写权限 | docs/appendix/11_生产部署与离线Release方案.md | not_satisfied | workflow-level read-only；publish Job marker-gated；待 CI/Release dry-run Green |
| R6 | publish Job 不依赖 checkout/.git，GitHub CLI 使用显式仓库上下文 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | `publish-release` 无 checkout，`GH_REPO` + `--repo`；PR context probe 已 success |
| R7 | Release 不得把 Backend/Frontend 镜像公开 | user:2026-08-25-private-ghcr-only | not_satisfied | Phase 1 `Verify GHCR packages are private` 已在 PR dry-run success；Phase 2 push 前和发布后均 fail closed 复核 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI/浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端/数据库业务行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | 不修改产品 Full-stack 链路；Release 自己执行真实 Compose replay |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | Unit workflow invariants + Release PR dry-run + CI/Runtime/Completion Gate；读取 Release dry-run step 证明 private package/context/build/replay |

# 实施与验证记录

## Red

PR #226 HEAD `157a3a5de8a2f8d42a0534d837d98ca741b19ad9` 先加入回归测试，Repository Quality run `32805012136` 按预期失败：

```text
2 failed, 627 passed
- 缺少 GH_REPO 显式 repository context
- 缺少发布后 GitHub Release/asset 验证
```

这证明测试命中了 #39 的真实缺陷，而不是环境错误。

## Green 实现

当前 workflow 已完成：

- 顶部触发/两阶段职责说明；
- 静态 Release env 集中；
- `build-verify` 只读 + `packages: read`；
- 在无 `.git` 临时目录执行 GitHub CLI 显式 repo probe；
- PR/正式构建前读取 Package API 并要求 `private`；
- `publish-release` 无 checkout；
- `GH_REPO=${{ github.repository }}`；
- `gh release view/create --repo`；
- push 前再次检查 private；
- Release 创建后验证 tag target、4 个资产和 private visibility；
- manifest 正式发布事实记录 `ghcr_visibility=private`。

PR 最新 Release dry-run run `32805434039` 已确认以下前置步骤 success：

```text
Verify GitHub CLI explicit repository context  success
Verify GHCR packages are private                success
Verify Docker toolchain                         success
```

因此当前两个已存在 GHCR Package 的真实 visibility 已由 GitHub Runner + Package API 证明为 `private`，不是根据默认设置推断。

# 文档影响

现有 Roadmap/Appendix 已正确描述“正式 `workflow_dispatch` 手工发布、PR dry-run、两阶段候选回放/GHCR/Tag/Release”的长期边界，本 Change 没有改变这些架构语义。新增的显式 repository context 与 private fail-closed 属于 Release workflow 安全实现细节，已通过 workflow 顶部说明、语义化 step、测试与本 Change 固化，不复制第二套实现说明到长期 Blueprint。

# 部署、兼容与回滚

- 无 Schema/Migration/业务数据变化。
- 不改变服务器 Runtime、Compose、AIMA_HOST_ROOT 或现有 GHCR package 名称。
- 不修改 Package visibility；只读取并要求 `private`。
- 回滚只需 revert workflow/test 变更；不会删除已存在的 GHCR 镜像。
- #39 已成功写入的 `v2.0.0` GHCR tags 属于未完成正式 GitHub Release 的部分发布状态；本 Change 不主动删除这些 package tags。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# Git 状态

- Branch: `fix/release-workflow-publication`
- PR: #226 Draft
- Release #39 evidence: run `32803805624`
- Red CI evidence: run `32805012136`
- Green candidate HEAD: `390c94900181585c31cf6e0a3e2468efbad75683`

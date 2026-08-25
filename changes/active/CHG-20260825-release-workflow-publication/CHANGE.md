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
  - tests/unit/test_release_workflow.py
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

根因是 Release 将“只读构建/回放”和“带写权限发布”拆成两个独立 Job，这是正确的最小权限设计；但 `publish-release` Job 不 checkout 源码，最后的 `gh release create` 又没有显式 repository 上下文，GitHub CLI 因而尝试从本地 `.git` 推断仓库并失败。

用户随后明确了最终发布边界：

```text
AIMA_UGC 源码仓库保持 public
GitHub Release 必须提供可直接下载的完整离线部署包
离线包中继续包含 images.tar（Backend / Frontend / PostgreSQL）
Backend / Frontend GHCR Package 本身继续保持 private
服务器现有 canonical docker compose 启动命令不改变
```

因此“公开 GitHub Release Asset 中包含离线镜像”是已确认交付方式，不再作为阻塞；真正需要 fail closed 的是 GHCR Package visibility，workflow 不负责把 Package 改 public/private，只在 push 前要求两个 Package 实际仍为 `private`。

本 Change 不把两阶段设计退回一个大 Job，也不通过无意义 checkout 掩盖问题，而是把 Release Workflow 整理为可读、显式、可验证的两阶段发布流程。

# 目标

1. 修复 #39 的 GitHub Release 创建失败，使 publish Job 完全不依赖本地 `.git`。
2. 保留“构建/验证只读，正式发布才拿写权限”的安全边界。
3. 让 Release Workflow 从上到下可按业务阶段阅读，不靠历史知识理解。
4. 所有 GitHub CLI 发布操作显式绑定当前仓库，不再依赖隐式 repository 推断。
5. 保留当前手工正式发布、PR 只读 dry-run、离线 Bundle 回放、GHCR digest、Tag/Release 的既有能力。
6. Backend/Frontend GHCR Package 继续保持 `private`；任何非 private 状态在 push 前直接中止。
7. 正式 GitHub Release 继续附带 `AIMA_UGC-vX.Y.Z-deploy.tar.gz`，其中包含 `images.tar`，允许从当前 public 仓库 Release 页面直接下载完整离线镜像。
8. Release 交付方式不得改变服务器现有 canonical `compose.yaml + env.production` 启动命令。
9. 增加回归测试，防止发布上下文、权限、触发方式、GHCR 私有性、离线 Bundle 和服务器启动命令回归。

# 非目标

- 不把正式 Release 改成每次 push/main 自动运行。
- 不改变 Backend/Frontend GHCR package 名称。
- 不把 GHCR Package 改成 public。
- 不把源码仓库改成 private。
- 不改为“服务器在线从 GHCR 拉取镜像”的部署模式。
- 不升级 Python/Node/PostgreSQL/Actions 版本。
- 不新增 PAT、额外 Secret 或第三方发布服务。
- 不自动改变 GHCR Package visibility。
- 不在本 Change 实现 SBOM、签名、provenance、协调 Backup/Restore。
- 不改变 canonical `compose.yaml` Runtime、`AIMA_HOST_ROOT` 或服务器部署目录。

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
→ 推送 GHCR 版本/SHA tag 并记录 digest
→ 重新生成最终离线 tar.gz，其中保留 images.tar
→ 创建 Git Tag + public GitHub Release + 可下载完整离线 Bundle
→ 发布后重新验证 Tag、Release assets 和 GHCR Package 私有性

服务器
→ docker load -i images.tar
→ docker compose --env-file env.production config --quiet
→ docker compose --env-file env.production up -d --no-build --pull never --wait
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

## 方案 C：保留两阶段安全架构，系统整理上下文、私有门禁、离线资产和最终验证（采用）

- Workflow 顶部直接解释两种触发模式和两个 Phase；
- 静态 Release 配置集中到 workflow-level `env`；
- build Job 继续只读，publish Job 继续最小写权限；
- 两个 Job 的 GitHub CLI 都使用显式 `GH_REPO`；
- PR dry-run 在无 `.git` 临时目录真实执行 `gh repo view <repo>`，证明显式 context 可工作；
- Phase 1 和 Phase 2 均读取 GitHub Package API，要求 Backend/Frontend `visibility=private`；
- publish Job 不 checkout；
- `gh release view/create` 显式 `--repo`；
- 正式 Release 继续附带包含 `images.tar` 的完整离线部署包；
- 服务器继续使用同一 canonical Compose Runtime，不引入第二套启动脚本；
- 发布成功后验证 Tag target、Release assets 和 GHCR Package 私有性；
- Unit 测试直接约束这些不变量。

优点：修根因、权限清楚、GHCR 镜像仍私有、Release 离线交付方式明确、流程可读、以后不易回归，同时不改变业务 Runtime 和正式发布触发语义。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 下次正式 Release 不再因 publish Job 缺少 `.git` 而失败 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 已实现显式 `GH_REPO` / `--repo` 和无 `.git` context probe；待最终 CI/Release dry-run |
| R2 | Workflow 要系统、清楚、可由维护者从上到下理解 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | 已按触发说明、Phase 1/2、集中 env、语义化 step 整理；待 Review |
| R3 | 正式 Release 只由用户手工触发，普通提交不正式发布 | user:2026-08-25-manual-release-only | not_satisfied | `workflow_dispatch` + Release 相关 PR dry-run；Unit 测试已建立，待 Green |
| R4 | 保留 Build/Replay → GHCR digest → Tag/Release → Bundle 的长期 Release 能力 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 现有链路全部保留；Release PR dry-run 正在验证真实 build/replay |
| R5 | PR dry-run 不获得正式发布写权限 | docs/appendix/11_生产部署与离线Release方案.md | not_satisfied | workflow-level read-only；publish Job 仅 workflow_dispatch；待 CI/Release dry-run Green |
| R6 | publish Job 不依赖 checkout/.git，GitHub CLI 使用显式仓库上下文 | user:2026-08-25-release-workflow-systematic-fix | not_satisfied | `publish-release` 无 checkout，`GH_REPO` + `--repo`；PR context probe 已 success |
| R7 | Backend/Frontend GHCR Package 继续保持 private | user:2026-08-25-private-ghcr-only | not_satisfied | Phase 1 private check 已由真实 GitHub Package API success；Phase 2 push 前和发布后均 fail closed 复核 |
| R8 | 当前 public 仓库的 GitHub Release 必须可下载完整离线镜像包，包内保留 images.tar | user:2026-08-25-public-release-offline-bundle | not_satisfied | workflow 生成并上传 `${DEPLOY_ARCHIVE}`；新增 Unit 回归测试，待最终 Green |
| R9 | 不影响服务器现有 Docker Compose 启动命令 | user:2026-08-25-preserve-server-compose-command | not_satisfied | Release Bundle 保留 canonical `compose.yaml`，DEPLOY.md 命令保持 `docker compose --env-file env.production up -d --no-build --pull never --wait`；新增 Unit 回归测试，待最终 Green |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI/浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端/数据库业务行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client |
| Real Full-stack Golden Path | not_applicable | 不修改产品 Full-stack 链路；Release 自己执行真实 Compose replay |
| Real Provider Probe | not_applicable | 不修改外部 Provider |
| Docs / Governance / Other | required | Unit workflow invariants + Release PR dry-run + CI/Runtime/Completion Gate；读取 Release dry-run step 证明 package/context/build/replay；验证离线 Bundle 与服务器 Compose 命令不变 |

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
- manifest 正式发布事实记录 `ghcr_visibility=private`；
- GitHub Release 的 `${DEPLOY_ARCHIVE}` 继续包含 `images.tar`；
- Release Bundle 中继续复制 canonical `compose.yaml`，服务器启动命令不变。

Release PR dry-run run `32805434039` 已完整 success，并提供新鲜真实证据：

```text
Verify GitHub CLI explicit repository context  success
Verify GHCR packages are private                success
Build Linux AMD64 application images            success
Replay bundle with no build and no pull         success
Verify deploy archive can be created            success
Report dry-run result                            success
```

Runner 实际返回：

```text
GHCR dingyuwen777/aima-ugc-backend: visibility=private
GHCR dingyuwen777/aima-ugc-frontend: visibility=private
Release dry-run succeeded
No GHCR push, Git Tag, GitHub Release or repository write token was used
```

因此两个 GHCR Package 的真实 visibility 已由 GitHub Runner + Package API 证明为 `private`，不是根据默认设置推断；同时离线 Bundle 已真实完成 build → docker save → 删除本地镜像 → docker load → canonical Compose `--no-build --pull never` 回放。

# 文档影响

现有 Roadmap/Appendix 已明确把 GitHub Release Workflow 定义为“正式手工发布 GHCR digest、Tag、GitHub Release 和可下载 Bundle”，并明确服务器使用 `docker load + canonical Compose --no-build --pull never`。本轮最终决定没有改变该长期架构，只进一步确认：当前 public 仓库 Release Asset 可以公开提供完整离线镜像包，而 Backend/Frontend GHCR Package 本身继续保持 private。该差异已由本 Change、workflow 注释和回归测试固化；不新增第二套部署文档或第二套服务器启动方式。

# 部署、兼容与回滚

- 无 Schema/Migration/业务数据变化。
- 不改变服务器 Runtime、Compose、AIMA_HOST_ROOT 或现有 GHCR package 名称。
- 不修改 GHCR Package visibility；只读取并要求 `private`。
- GitHub Release 继续上传包含 `images.tar` 的公开离线部署 tar.gz，这是用户明确接受的当前交付方式。
- 服务器继续 `docker load -i images.tar` 后执行现有 canonical Compose 命令；无需改部署脚本或 env 格式。
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
- Green Release dry-run evidence: run `32805434039`
- Current candidate HEAD: `0e31d23455f4595eefc6a2fe7043dc5b7f855490`

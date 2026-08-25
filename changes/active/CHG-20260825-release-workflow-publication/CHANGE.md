---
schema: rvc-change/v1
id: CHG-20260825-release-workflow-publication
title: 系统修复并重构 Release Workflow 发布阶段
level: L3
status: ready_for_review
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

正式 Release #39（run `32803805624`）已证明候选构建、离线 Bundle、真实 Compose 回放、GHCR Backend/Frontend 推送和 digest 校验成功；最终只在 `Create Git tag and GitHub Release` 失败：

```text
failed to run git: fatal: not a git repository (or any of the parent directories): .git
```

根因是 Release 正确地把“只读构建/回放”和“带写权限发布”拆成两个独立 Job，但 `publish-release` 不 checkout 源码，原 `gh release create` 又没有显式 repository 上下文，GitHub CLI 因而尝试从本地 `.git` 推断仓库并失败。

本 Change 保留两阶段最小权限设计，不用额外 checkout 掩盖问题，而是让所有 GitHub CLI 发布操作显式绑定仓库，并把 Release Workflow 按长期可读、可验证的阶段重新组织。

# 已确认发布边界

用户确认：

```text
AIMA_UGC 源码仓库保持 public
GitHub Release 提供可直接下载的完整离线部署包
离线包继续包含 images.tar（Backend / Frontend / PostgreSQL）
Backend / Frontend GHCR Package 本身继续保持 private
服务器 canonical docker compose 启动命令不改变
正式 Release 仍只由用户手工 workflow_dispatch 触发
```

因此 public GitHub Release Asset 中包含完整离线镜像是当前明确接受的交付方式；GHCR Package visibility 仍 fail closed 为 `private`，workflow 只检查实际可见性，不修改 Package visibility。

# 目标与成功标准

1. `publish-release` 不依赖本地 `.git`，不再复现 #39 的 repository context 错误。
2. 保留 Phase 1 只读构建/回放、Phase 2 最小写权限发布的安全边界。
3. Workflow 从触发方式、共享配置、Phase 1、Phase 2 到最终验证可以顺序阅读。
4. 正式 Release 继续只允许 `workflow_dispatch`，普通 push 不发布版本；Release 相关 PR 只跑 read-only dry-run。
5. Linux/AMD64 Backend/Frontend + `postgres:18.4` 继续进入 `images.tar`，离线 Bundle 真实执行 `--no-build --pull never` 回放。
6. 正式发布继续推送 GHCR 版本/SHA tag、记录 digest、创建 Git Tag/GitHub Release，并上传可下载完整离线 tar.gz。
7. Backend/Frontend GHCR Package 在构建前、push 前和正式发布后均要求实际 `visibility=private`。
8. 服务器继续使用 bundle 内 canonical `compose.yaml` 和既有 `env.production`；启动命令不改变。
9. 回归测试约束触发、权限、显式仓库上下文、GHCR 私有性、离线资产和服务器启动命令。

# 非目标

- 不把正式 Release 改成 `push: main` 自动发布。
- 不改变 GHCR package 名称或主动修改其 visibility。
- 不把源码仓库改成 private。
- 不改为服务器在线从 GHCR 拉取镜像。
- 不改变 `compose.yaml`、`AIMA_HOST_ROOT`、`env.production` 格式或服务器 Runtime。
- 不升级 Python、Node、PostgreSQL 或 Actions 版本。
- 不新增 PAT、额外 Secret 或第三方发布服务。
- 不在本 Change 引入 SBOM、独立签名/provenance 或协调 Backup/Restore。

# 最终流程

```text
PR（Release 相关路径）
→ Phase 1 build-verify（contents/checks/packages read）
→ 显式 GH_REPO 无 .git context probe
→ GHCR private visibility 检查
→ Linux/AMD64 build
→ images.tar + manifest + SHA256SUMS + DEPLOY.md
→ 删除本地候选镜像
→ docker load
→ canonical Compose --no-build --pull never --wait 回放
→ publish-release 跳过

用户手工 workflow_dispatch
→ 同一 Phase 1 完整构建/回放
→ 校验 main 最新 SHA + CI gates
→ 上传已回放 candidate Artifact
→ Phase 2 publish-release（contents/packages write）
→ 不 checkout，显式 GH_REPO
→ 再校验 main / version / GHCR private
→ 下载并校验 candidate
→ push Backend/Frontend VERSION + SHA tag
→ pull-back + image ID/digest 校验
→ 最终 manifest + 完整离线 tar.gz（保留 images.tar）
→ gh release create --repo ... --target RELEASE_SHA
→ 验证 Tag target、4 个 Release assets、GHCR private visibility
```

服务器离线运行入口保持：

```bash
docker load -i images.tar
docker compose --env-file env.production config --quiet
docker compose --env-file env.production up -d --no-build --pull never --wait
```

# 方案比较

## 方案 A：publish Job 增加 checkout

可以让 `gh` 从 `.git` 推断仓库，但为纯发布 Job 引入无必要源码依赖，也继续保留隐式上下文。未采用。

## 方案 B：只增加 `GH_REPO`

能直接修复 #39，但没有系统整理权限、阶段、Package visibility 和发布后验证。仅作为必要机制，不单独采用。

## 方案 C：两阶段不变 + 显式上下文 + 私有门禁 + 最终验证（采用）

保持现有安全架构，集中静态 Release 配置，显式 `GH_REPO` / `--repo`，Phase 1/2 分工清晰，正式发布前后校验 GHCR 私有性，正式 Release 继续附带完整离线包，并用回归测试固定这些不变量。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正式 Release 不再因 publish Job 缺少 `.git` 而失败 | user:2026-08-25-release-workflow-systematic-fix | satisfied | `publish-release` 无 checkout；显式 `GH_REPO` / `--repo`；Release dry-run `32808909424` 的无 `.git` GitHub CLI context probe success |
| R2 | Workflow 系统、清楚、可从上到下理解 | user:2026-08-25-release-workflow-systematic-fix | satisfied | `.github/workflows/release.yml` 顶部解释两种触发模式；共享 env 集中；Phase 1/2 和步骤使用语义化名称；A2 Review 无阻塞项 |
| R3 | 正式 Release 只手工触发，普通提交不正式发布 | user:2026-08-25-manual-release-only | satisfied | Workflow 只有 `workflow_dispatch` 正式路径和 Release 相关 PR dry-run，无 `push`；`tests/unit/test_release_workflow.py` 随 CI `32808909422` success |
| R4 | 保留 Build/Replay → GHCR digest → Tag/Release → Bundle 长期能力 | docs/roadmap/02_生产上线实施路线.md | satisfied | Workflow 保留全部链路；Release dry-run `32808909424` build/bundle/replay success；正式 Phase 2 只消费已回放 candidate |
| R5 | PR dry-run 不获得正式发布写权限 | docs/appendix/11_生产部署与离线Release方案.md | satisfied | workflow 默认 `contents: read`；build Job 仅 read；write permissions 只在 workflow_dispatch 的 `publish-release`；run `32808909424` publish Job skipped |
| R6 | publish Job 不依赖 checkout/.git，GitHub CLI 显式绑定仓库 | user:2026-08-25-release-workflow-systematic-fix | satisfied | `publish-release` 无 `actions/checkout`；`GH_REPO=${{ github.repository }}`；`gh release view/create --repo`; Unit + real no-.git context probe success |
| R7 | Backend/Frontend GHCR Package 保持 private | user:2026-08-25-private-ghcr-only | satisfied | Release dry-run `32808909424` 通过真实 GitHub Package API 校验两个 package `visibility=private`；正式 Phase 2 push 前与发布后再次 fail closed 校验 |
| R8 | Public 仓库 Release 可下载完整离线镜像包，包内保留 images.tar | user:2026-08-25-public-release-offline-bundle | satisfied | Workflow `docker save` 生成 `release-bundle/images.tar`，最终 `${DEPLOY_ARCHIVE}` 打包整个 bundle 并作为 `gh release create` asset；Unit + Release dry-run `32808909424` success |
| R9 | 不影响服务器现有 Docker Compose 启动命令 | user:2026-08-25-preserve-server-compose-command | satisfied | Bundle 继续复制 canonical `compose.yaml`；DEPLOY.md 保持 `docker load` + `docker compose --env-file env.production ... --no-build --pull never --wait`；Unit、Runtime `32808909407`、Release replay `32808909424` success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI/浏览器行为；CI 中该层仍随 Repository Quality 通过 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端/数据库业务行为；PostgreSQL Integration 仍随 CI `32808909422` success |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client；漂移检查仍随 CI success |
| Real Full-stack Golden Path | not_applicable | 不修改产品 Full-stack 链；永久 Full-stack `32808909417` 仍 success；Release 自身另做真实 Compose replay |
| Real Provider Probe | not_applicable | 不修改外部 Provider，也不需要真实 Provider 费用调用 |
| Docs / Governance / Other | required | CI `32808909422` success；Runtime `32808909407` success；Full-stack `32808909417` success；Release dry-run `32808909424` success；Completion Gate 在 Change 进入 Ready 前仅因 `in_progress` 状态按设计失败 |

# TDD 与验证证据

## Red

PR #226 初始测试 HEAD `157a3a5de8a2f8d42a0534d837d98ca741b19ad9`，CI run `32805012136` 出现预期失败：

```text
2 failed, 627 passed
- 缺少 GH_REPO 显式 repository context
- 缺少发布后 GitHub Release/asset 验证
```

证明回归测试命中 #39 根因。

## Green

当前候选 HEAD：`8bbbfb888019e1be2704aed5ec5ea7a9006582da`。

当前新鲜证据：

```text
CI                                  32808909422  success
Runtime Acceptance                  32808909407  success
Full-stack Acceptance               32808909417  success
Release dry-run for PR #226         32808909424  success
```

Release dry-run 已真实完成：

```text
explicit GitHub repository context  success
GHCR private visibility check       success
Linux/AMD64 Backend/Frontend build  success
postgres:18.4                       success
offline images.tar / manifests      success
remove local tags → docker load     success
canonical Compose replay            success
deploy archive creation             success
PR publish job                      skipped
```

正式 `gh release create` 属于 `workflow_dispatch` 写操作，按用户要求不在 PR 中实际创建正式版本；当前修复通过显式 repo context 的无 `.git` real probe、Unit 不变量和完整 read-only Release dry-run覆盖 #39 根因及正式发布前置链路。

# 文档影响

正式 Roadmap/Appendix 已定义“手工正式发布 → GHCR digest + Tag + GitHub Release + 可下载 Bundle”，并定义服务器 `docker load + canonical Compose --no-build --pull never`。本轮没有改变这些长期部署机器边界，因此不复制第二套部署文档；本 Change 记录新增的可见性决定：public GitHub Release Asset 可包含完整离线镜像，而 GHCR Package 本身继续保持 private。

# Completion Audit

- [x] upstream_re_read — 重新读取用户本轮决定、`AGENTS.md`、Roadmap、Release Appendix、适用 Skill/Completion Gate；独立重建完成定义，包含手工触发、可读两阶段、公开离线 asset、GHCR private、服务器命令不变。
- [x] change_coverage — 对照上游要求逐条检查 R1–R9；未发现遗漏的 Release 触发、权限、资产、Runtime 或可见性要求。
- [x] reverse_audit — 从正式输出反查：GitHub Release asset → 完整 tar.gz → images.tar + canonical compose；服务器启动命令 → bundle 中实际 compose/env；GHCR push → private pre/post gate；正式写操作 → workflow_dispatch-only publish Job。无产品 UI/API/Schema 边界需要新增机制。
- [x] unresolved_cleared — R1–R9 全部 `satisfied`；无未决 Contract、Schema、Migration、Secret、依赖或发布语义。

# 两阶段 Review

## Review A1：上游要求 → Change

重新从本轮用户决定、Roadmap 与 Release Appendix 建立要求集合后，与 Traceability 对照，无 requirement omission。用户后续确认“public Release 可下载完整离线镜像、服务器 Compose 命令不变”已加入 R8/R9，而不是继续沿用先前私有资产假设。

## Review A2：Change → 实现 / 测试 / 文档

逐项检查 `.github/workflows/release.yml`、两个 Unit 测试、Release dry-run 和既有部署文档：R1–R9 均有实现与新鲜证据；PR 无正式写操作；服务器 Runtime 没有分叉；正式 Release 的唯一未执行动作是用户保留的手工 `workflow_dispatch` 发布本身。

## 代码质量 Review

无阻塞问题：

- 保留两个 Job 的最小权限边界，不因修 Bug 合并成大权限 Job；
- publish Job 不增加无意义 checkout；
- GitHub repository context、Package visibility、main SHA、Tag/Release identity 均显式校验；
- candidate 在两个 Job 之间通过 Artifact + SHA256SUMS 传递，不重新 build；
- GHCR push 后 pull-back 比较 image ID 并记录 digest；
- GitHub Release 后验证 tag target 和 4 个 assets；
- 不修改 Compose/Schema/Contract/依赖/Secret；
- 公开 Release asset 包含镜像是用户明确决策，不作为隐式安全假设。

# 部署、兼容与回滚

- 无 Schema/Migration/业务数据变化。
- 不改变 GHCR package 名称、Compose Runtime、AIMA_HOST_ROOT、env 格式或服务器命令。
- Workflow 不修改 GHCR visibility；只要求 Backend/Frontend package 为 private。
- GitHub Release 继续上传包含 `images.tar` 的公开离线部署 tar.gz。
- #39 已写入的 `v2.0.0` GHCR tags 属于未完成正式 GitHub Release 的部分发布状态；下次从最新 main 手工发布 `v2.0.0` 时，正式候选会重新覆盖 VERSION/SHA tag，并在创建 GitHub Release 前后做 digest/asset 验证。
- 回滚本 Change 只需 revert workflow/test/Change 变更；不触碰业务数据或宿主持久目录。

# Git 状态

- Branch: `fix/release-workflow-publication`
- PR: `#226` Draft，候选已达到 `ready_for_review`
- Candidate HEAD: `8bbbfb888019e1be2704aed5ec5ea7a9006582da`
- Release #39 root-cause evidence: run `32803805624`
- Red evidence: run `32805012136`
- Current Green evidence: CI `32808909422`, Runtime `32808909407`, Full-stack `32808909417`, Release dry-run `32808909424`

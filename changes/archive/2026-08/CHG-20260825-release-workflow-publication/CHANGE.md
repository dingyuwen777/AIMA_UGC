---
schema: rvc-change/v1
id: CHG-20260825-release-workflow-publication
title: 系统修复并重构 Release Workflow 发布阶段
level: L3
status: done
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

正式 Release #39（run `32803805624`）已经完成候选构建、离线 Bundle、真实 Compose 回放、GHCR Backend/Frontend push 与 digest 校验，但最后的 GitHub Release 创建失败：

```text
failed to run git: fatal: not a git repository (or any of the parent directories): .git
```

根因是 Release 已正确拆成“只读构建/回放”和“带写权限发布”两个独立 Job，但 `publish-release` 不 checkout 源码，原 `gh release create` 又没有显式 repository context，GitHub CLI 因而尝试从本地 `.git` 推断仓库。

本 Change 保留两阶段最小权限结构，不用额外 checkout 掩盖问题，而是把 GitHub repository context、GHCR visibility、发布阶段和最终验证全部显式化。

# 已确认发布边界

用户最终确认：

```text
AIMA_UGC 源码仓库保持 public
GitHub Release 继续提供可直接下载的完整离线部署包
离线包包含 images.tar（Backend / Frontend / PostgreSQL）
因此 public GitHub Release Asset 中的离线镜像允许公开下载
Backend / Frontend GHCR Package 本身继续保持 private
服务器 canonical Docker Compose 启动命令不改变
正式 Release 只由用户手工 workflow_dispatch 触发
```

# 最终实现

## Phase 1：Build and replay offline candidate

```text
PR / workflow_dispatch
→ checkout candidate
→ 显式 GH_REPO 无 .git context probe
→ 检查两个 GHCR Package visibility=private
→ 正式发布时验证 main 最新 SHA + CI gates
→ Linux/AMD64 Backend/Frontend build + postgres:18.4
→ images.tar + release/migration manifest + SHA256SUMS + DEPLOY.md
→ 删除本地候选运行镜像 tag
→ docker load -i images.tar
→ canonical Compose --no-build --pull never --wait 回放
→ 正式发布才上传 replay-tested candidate Artifact
```

Phase 1 只有 `contents/checks/packages: read`，PR dry-run 不获得仓库或 Package 写权限。

## Phase 2：Publish replay-tested candidate

```text
仅 workflow_dispatch
→ contents:write + packages:write
→ 不 checkout、不依赖 .git
→ GH_REPO / --repo 显式绑定 dingyuwen777/AIMA_UGC
→ 再校验 main / version / GHCR private
→ 下载并校验 Phase 1 candidate
→ push Backend/Frontend VERSION + SHA tag
→ pull-back 比较 image ID 并读取 GHCR digest
→ 更新最终 manifest
→ 生成 AIMA_UGC-vX.Y.Z-deploy.tar.gz（保留 images.tar）
→ gh release create --repo ... --target RELEASE_SHA
→ 验证 Tag target、4 个 Release assets、GHCR private visibility
```

正式 GitHub Release 包含：

```text
release-manifest.json
migration-manifest.json
SHA256SUMS
AIMA_UGC-vX.Y.Z-deploy.tar.gz
```

离线 tar.gz 内继续包含：

```text
images.tar
compose.yaml
env.production.example
release-manifest.json
migration-manifest.json
SHA256SUMS
DEPLOY.md
```

# 服务器兼容性

本 Change 没有建立第二套 Runtime，也没有修改 `compose.yaml`、`env.production`、`AIMA_HOST_ROOT` 或服务器目录语义。Release 下载解压后继续使用：

```bash
docker load -i images.tar
docker compose --env-file env.production config --quiet
docker compose --env-file env.production up -d --no-build --pull never --wait
```

# 方案比较

## 方案 A：publish Job 增加 checkout

能让 `gh` 继续从 `.git` 推断仓库，但为只消费已验证 Artifact 的发布 Job 引入无意义源码依赖，仍保留隐式 context。未采用。

## 方案 B：只增加 `GH_REPO`

可以修复 #39，但不会系统整理触发、权限、GHCR 私有门禁和最终发布验证。仅作为必要机制，不单独采用。

## 方案 C：保留两阶段 + 显式 context + visibility 门禁 + 最终验证（采用）

满足最小权限、可读性、离线交付、服务器兼容和可验证性，同时不改变业务 Runtime。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正式 Release 不再因 publish Job 缺少 `.git` 而失败 | user:2026-08-25-release-workflow-systematic-fix | satisfied | `publish-release` 无 checkout；`GH_REPO` / `--repo` 显式绑定；Release dry-run `32809280798` 的 no-`.git` context probe success |
| R2 | Workflow 系统、清楚、可顺序理解 | user:2026-08-25-release-workflow-systematic-fix | satisfied | `.github/workflows/release.yml` 顶部解释触发与 Phase 1/2；共享 env 集中；步骤使用语义化名称；A1/A2 Review 无阻塞项 |
| R3 | 正式 Release 只由用户手工触发，普通提交不正式发布 | user:2026-08-25-manual-release-only | satisfied | Workflow 无 `push` Release trigger；正式写 Job 只在 `workflow_dispatch`；Unit/CI `32809280804` success |
| R4 | 保留 Build/Replay → GHCR digest → Tag/Release → Bundle 长期能力 | docs/roadmap/02_生产上线实施路线.md | satisfied | Release dry-run `32809280798` 完整 build/bundle/replay success；正式 Phase 2 只消费已回放 candidate |
| R5 | PR dry-run 不获得正式发布写权限 | docs/appendix/11_生产部署与离线Release方案.md | satisfied | workflow 默认 read-only；write permissions 只在 workflow_dispatch 的 `publish-release`；Release dry-run publish Job skipped |
| R6 | publish Job 不依赖 checkout/.git，GitHub CLI 显式绑定仓库 | user:2026-08-25-release-workflow-systematic-fix | satisfied | `publish-release` 无 `actions/checkout`；`GH_REPO=${{ github.repository }}`；`gh release view/create --repo`；Unit + real context probe success |
| R7 | Backend/Frontend GHCR Package 保持 private | user:2026-08-25-private-ghcr-only | satisfied | Release dry-run `32809280798` 通过 GitHub Package API 验证两个 package `visibility=private`；正式 Phase 2 push 前和发布后再次 fail closed 校验 |
| R8 | Public 仓库 Release 可下载完整离线镜像包，包内保留 images.tar | user:2026-08-25-public-release-offline-bundle | satisfied | `docker save` 生成 `images.tar`；最终 `${DEPLOY_ARCHIVE}` 打包整个 bundle并作为 `gh release create` asset；Unit/Release dry-run success |
| R9 | 不影响服务器现有 Docker Compose 启动命令 | user:2026-08-25-preserve-server-compose-command | satisfied | Bundle 继续复制 canonical `compose.yaml`；DEPLOY.md 保持既有 `docker load` + Compose 命令；Unit、Runtime、Release replay success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品 UI；Repository Quality 仍包含并通过 Browser Mock |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端/数据库业务行为；PostgreSQL Integration 仍通过 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract/generated client；漂移检查仍通过 |
| Real Full-stack Golden Path | not_applicable | 不修改产品 Full-stack 链；永久 Full-stack 仍通过；Release 自身另做真实 Compose replay |
| Real Provider Probe | not_applicable | 不修改外部 Provider，也不需要费用调用 |
| Docs / Governance / Other | required | PR-head CI `32809280804`、Runtime `32809280841`、Full-stack `32809280835`、Completion Gate `32809280803`、Release dry-run `32809280798` 全部 success；实现合并后 main 的 CI `32809478114`、Runtime `32809478183`、Full-stack `32809478071`、Completion Gate `32809478106` 全部 success |

# TDD 与验证证据

## Red

PR #226 初始测试 HEAD `157a3a5de8a2f8d42a0534d837d98ca741b19ad9`，CI run `32805012136` 出现预期失败：

```text
2 failed, 627 passed
- 缺少 GH_REPO 显式 repository context
- 缺少发布后 GitHub Release/asset 验证
```

## Green

最终 PR HEAD：`cf426900d47038c07e4da22c4abd2237a6d842d0`。

最终 PR-head 证据：

```text
CI                                  32809280804  success
Runtime Acceptance                  32809280841  success
Full-stack Acceptance               32809280835  success
Change Completion Gate              32809280803  success
Release dry-run for PR #226         32809280798  success
```

Release dry-run 真实证明：

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

PR #226 正常合并，implementation merge：

```text
8f3aa0c1e754b35283e0bce95d02449793512094
```

实现合并后的 main 证据：

```text
CI                                  32809478114  success
Runtime Acceptance                  32809478183  success
Full-stack Acceptance               32809478071  success
Change Completion Gate              32809478106  success
```

正式 `gh release create` 是用户保留的手工 `workflow_dispatch` 写操作，因此没有在 PR/合并过程中自动创建真实版本。已通过 Unit 不变量、无 `.git` GitHub CLI real probe 和完整只读 Release dry-run覆盖 #39 根因与所有写前链路。

# Completion Audit

- [x] upstream_re_read: 重新读取用户最终决定、`AGENTS.md`、Roadmap、Release Appendix 和适用 Skill；完成定义包含手工触发、可读两阶段、public 可下载离线 asset、GHCR private、服务器 Compose 命令不变。
- [x] change_coverage: 对照上游要求检查 R1–R9，无遗漏的 Release 触发、权限、资产、Runtime 或 visibility 要求。
- [x] reverse_audit: 从 GitHub Release asset 反查到完整 tar.gz/images.tar/canonical compose，从服务器命令反查 bundle 的 compose/env，从 GHCR push 反查 private pre/post gate，从写权限反查 workflow_dispatch-only publish Job；无产品 UI/API/Schema 边界需要新增机制。
- [x] unresolved_cleared: R1–R9 均为 `satisfied`，无未决 Contract、Schema、Migration、Secret、依赖或发布语义。

# 两阶段 Review

## Review A1：上游要求 → Change

重新从本轮用户决定、Roadmap 与 Release Appendix 建立完成定义后，与 R1–R9 对照无 requirement omission。用户最终确认的“public Release 可下载完整离线镜像、服务器 Compose 命令不变”已经显式进入要求，而非沿用先前私有 Release Asset 假设。

## Review A2：Change → 实现 / 测试 / 文档

逐项检查 Release workflow、两个 Unit 测试、Release dry-run 和部署文档：R1–R9 均有实现与新鲜证据；PR 无正式写操作；服务器 Runtime 没有分叉；正式版本发布仍由用户手工执行。

# 部署、兼容与回滚

- 无 Schema/Migration/业务数据变化。
- 不改变 GHCR package 名称、Compose Runtime、AIMA_HOST_ROOT、env 格式或服务器命令。
- Workflow 不修改 GHCR visibility，只要求 Backend/Frontend package 实际为 private。
- GitHub Release 继续上传包含 `images.tar` 的 public 离线部署 tar.gz，这是用户明确接受的交付方式。
- #39 已写入的旧 `v2.0.0` GHCR tags 属于未完成正式 GitHub Release 的部分发布状态；下次从最新 main 手工发布时，候选会重新 push version/SHA tag，并在创建 Release 前后校验 digest/assets。
- 回滚只需 revert workflow/test 变更，不触碰业务数据或宿主持久目录。

# Git 状态

- Implementation branch: `fix/release-workflow-publication`
- Implementation PR: `#226` merged
- Implementation merge: `8f3aa0c1e754b35283e0bce95d02449793512094`
- Archive branch: `archive/release-workflow-publication`
- Archive status: `done`

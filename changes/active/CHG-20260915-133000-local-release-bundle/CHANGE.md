---
schema: coding-change/v1
id: CHG-20260915-133000-local-release-bundle
title: 本地一键构建 Release 离线包
level: L3
status: in_progress
owner: ChatGPT
branch: feature/local-release-bundle
created: 2026-09-15
updated: 2026-09-15
completion_gate: required
depends_on: []
affected_areas:
  - release
  - ci
  - developer-tooling
  - operations-docs
affected_paths:
  - scripts/release/release_bundle.py
  - scripts/release/build_local_release.ps1
  - .github/workflows/release.yml
  - tests/unit/test_release_bundle.py
  - tests/unit/test_release_workflow.py
  - tests/unit/test_docker_build_sources.py
  - docs/guides/06_本地Release离线包构建.md
  - docs/guides/README.md
  - changes/active/CHG-20260915-133000-local-release-bundle/CHANGE.md
contracts:
  - Release Bundle 文件集合、manifest、校验和、离线 replay 与服务器 canonical Compose 部署语义
  - 本地 china / GitHub official 构建下载源 Profile
  - GitHub 正式 Release latest-main、Tag identity、GHCR private 与 required-check 门禁
data_changes:
  - 无 Schema、Migration、业务数据或生产持久数据变化
---

# 变更摘要

为 Windows 开发机增加本地一键 Release Bundle 构建入口，并把现有 GitHub Release 中镜像构建、Bundle/manifest/SHA256/DEPLOY/archive 和离线 replay 抽成同一个跨平台 Python 核心。下载源通过 Profile 参数化：本地默认 `china`，GitHub 正式 Release 显式 `official`。GitHub 的 latest-main、stale Tag fail-closed、GHCR private、required checks 和 publish 权限边界保持在 Workflow 中，不下沉或弱化。

# 目标、范围与非目标

## 成功标准

- [ ] PowerShell 一条命令可从仓库根生成 Linux/AMD64 完整离线 Bundle 与部署压缩包。
- [ ] 本地默认 china；GitHub 显式 official；manifest 记录实际 Profile/upstream。
- [ ] 本地与 GitHub 共用 `release_bundle.py` 的 Build/Bundle/replay 核心，不再在 Workflow 内维护第二套等价逻辑。
- [ ] `-Verify` 使用隔离 smoke 资源执行 `docker load` + `--no-build --pull never`；Windows overlay 只用于本地 smoke，不进入 Bundle。
- [ ] `-Formal` 只允许标准 SemVer、clean `main`、HEAD 精确等于最新 `origin/main`。
- [ ] GitHub 正式 Release latest-main / Tag identity / GHCR / CI evidence / PR dry-run 不退化。
- [ ] 用户指南、专项回归、Release PR dry-run、required checks、main-fresh、Change archive 与 #497 Closure 全部闭环。

## 范围

- 新增 `scripts/release/release_bundle.py` 与 PowerShell 薄入口。
- Release Workflow 把构建/Bundle/replay/finalize 委托给共享核心；GitHub 平台身份、安全和发布动作继续由 Workflow 持有。
- 新增核心脚本测试并同步两份现有 Release/构建源回归。
- 新增本地 Release 使用指南和 guides 导航。
- Requirement Source #497、PR、CI、Review 与合并后收尾。

## 非目标

- 本地脚本不 tag/push、创建 GitHub Release、推 GHCR 或部署生产服务器。
- 不修改 Dockerfile、canonical Compose Runtime、业务代码、API/Contract、Schema/Migration、依赖版本或真实 Secret。
- 不让本地 china Profile 进入 GitHub 正式 Release 默认供应链。
- 不承诺 china/official 两个网络源构建产物 bit-for-bit 相同；保持同一依赖锁定和发布 Contract。

## 必须保持不变

- Docker 基础镜像继续使用仓库 canonical image reference；正式 GitHub Release 使用 `official` package-source Profile。
- Bundle 只含 `images.tar`、`compose.yaml`、`env.production.example`、两个 manifest、`SHA256SUMS`、`DEPLOY.md`。
- Linux 服务器继续 `docker load` 后使用 canonical `compose.yaml --no-build --pull never`。
- Windows `compose.windows.yaml` 只能用于本地 smoke storage/permission 适配，不进入服务器 Bundle。
- 正式 Publish Job 继续不 checkout 源码，只消费已 replay 的候选 Artifact；外部发布写权限不下沉到共享 Builder。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Windows PowerShell 一键生成完整 Bundle/archive | #497 / AC1 | in_progress | PowerShell 薄入口已实现草案；待 current-head CI/Release dry-run。 |
| R2 | 本地 china、GitHub official，manifest 记录 Profile/upstream | #497 / AC2 | in_progress | 共享核心 Profile 映射与 manifest 字段已实现；纯逻辑专项测试通过。 |
| R3 | 本地/GitHub 共用一个 Bundle 核心 | #497 / AC3 | in_progress | Workflow 已改为调用共享核心草案；旧内嵌 build/bundle/replay 逻辑已删除；待 CI 审计。 |
| R4 | `-Verify` 隔离离线 replay 并安全清理 | #497 / AC4 | in_progress | 核心实现 Windows overlay/独立 project/temp root；GitHub strict replay 待 PR dry-run 实证。 |
| R5 | `-Formal` clean/main/origin-main/SemVer fail closed | #497 / AC5 | in_progress | guard 纯逻辑测试已覆盖 success + remote drift；待 CI。 |
| R6 | GitHub 正式 Release 安全/身份/入口不退化 | #497 / AC6 | in_progress | Workflow 保留 latest-main、Tag/Release、GHCR private、CI evidence、publish revalidation；静态回归 11/11。 |
| R7 | 测试、文档、CI、main-fresh 与交付收尾 | #497 / AC7 | in_progress | 本地草案专项回归完成；仓库 PR/CI/Release dry-run/post-merge 尚未执行。 |

# 关键设计决定

## 1. 共享核心，而不是第二套 PowerShell 打包逻辑

PowerShell 只处理 Windows 参数和 Python 入口选择；镜像构建、Bundle、manifest、checksum、archive、replay 和 publication finalize 全部由 `release_bundle.py` 持有。GitHub Workflow 同样调用该文件，从结构上避免两套离线包实现漂移。

## 2. Source Profile 只改变下载路径

`china` 使用阿里 Debian / 清华 PyPI / npmmirror；`official` 使用 Debian/PyPI/npm 官方源。Dockerfile、lockfile、镜像 Tag、Schema、Bundle Contract 与部署语义不因 Profile 改变。GitHub Workflow 必须显式传 `official`，不依赖核心默认值。

## 3. 平台安全门禁继续由 GitHub Workflow 持有

共享 Builder 不获得 GitHub Token，不负责 Tag、Release、GHCR push、latest-main 或 required-check 查询。Build Job 先通过这些正式门禁，再调用共享核心；Publish Job 仍无 checkout，并在推送前重新验证候选 identity。

## 4. 本地 Verify 与 GitHub strict replay 区分

本地 `-Verify` 不主动删除用户开发机上的已有镜像，只在独立临时 Compose project/root 中 `docker load` 并用 `--no-build --pull never` 启动。GitHub PR/formal Build 使用 `--strict-replay`：先删除候选镜像，再从 `images.tar` 恢复，以证明 Bundle 离线独立性。

# Validation Matrix

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| Unit / Behavior | required | source profiles、version/formal guard、manifest、checksum/archive/finalize、PowerShell contract、Workflow contract。 |
| Build / Package | required | current-head Release PR dry-run 实际 Linux/AMD64 Backend/Frontend/PostgreSQL build + archive。 |
| Offline Replay / Runtime | required | Release PR dry-run strict replay：删除候选 → docker load → canonical Compose `--no-build --pull never --wait` → Migration/Readiness。 |
| Windows entry | required | PowerShell 静态参数/委托回归；真实 Docker Runtime 由共享核心 + existing Windows overlay contract 与 CI 静态保护；开发环境无 Windows Runner 时不冒充实跑。 |
| Formal GitHub publication side effects | not_applicable | 开发验证明确禁止真实 Tag/GitHub Release/GHCR 正式版本；平台写路径由静态回归、共享 dry-run 核心和已有安全门禁保护。 |
| PostgreSQL / Full-stack | required_by_repository_ci | current-head CI 根据永久 selector 决定并执行真实集成层。 |
| Docs / Governance | required | Issue #497、Change Completion、guide links/docs/Secret/gov gates。 |
| Post-merge | required | Implementation main-fresh CI + Runtime Acceptance、repository-native Change archive、Issue Closure、branch cleanup。 |

# CI / Workflow Responsibility Audit

- `release.yml` 仍只有 Build/Verify 与 Publish 两个责任 Job；没有新增永久 Workflow/Runner。
- 原 Build Job 内重复的 Docker build / Bundle / replay shell 被共享核心替换，不新增重复 setup/install/build。
- PR path filter 增加共享核心、PowerShell 和专项测试，使 Release Contract 自身变化 fail-closed 进入真实 dry-run。
- Publish Job 不 checkout、不构建源码；仍只消费 Build Job replay-tested Artifact，保持最小写权限和不可变候选传递。
- required check 名称与 Branch Ruleset 不在本次修改范围，不删除/改名永久 required checks。

# 文档影响

Docs Impact = targeted。新增 [`docs/guides/06_本地Release离线包构建.md`](../../../docs/guides/06_本地Release离线包构建.md) 作为开发机操作入口，并更新 guides README 导航。正式 GitHub Release 与 Linux 服务器部署语义继续由既有运行/Operations 文档持有，本次不复制第二套生产运维规范。

# 风险、兼容、部署与回滚

- 风险：共享核心成为本地和 GitHub Build 的共同路径，脚本缺陷可能同时影响两者；通过 Unit + 真实 Release PR dry-run + main-fresh CI 控制。
- 风险：Windows 本地 Docker Desktop 路径/权限与 Linux Runner 不同；本地 smoke 只叠加现有 storage-only Windows overlay，最终 Bundle 仍 canonical Linux Compose。
- 兼容：GitHub Release 触发、版本身份、Bundle 文件集合、服务器命令、GHCR/Release asset 不变；manifest 新增 build profile/verification 字段属于向后兼容扩展。
- Migration/Data：无。
- 部署：本任务不直接部署生产、不创建正式 Release。
- 回滚：revert 本 PR 即恢复 Workflow 内嵌构建逻辑，并删除本地辅助入口；已生成的历史 Bundle/Release 不改写。

# Completion Audit

- [ ] upstream_re_read：合并前重读 #497、current main、Release/Compose/构建源/文档事实。
- [ ] change_coverage：R1—R7 全部获得 direct Evidence 或明确 N/A/失败边界。
- [ ] reverse_audit：从 PowerShell、GitHub Build、GitHub Publish、Linux server 四个入口反查共享核心与安全门禁。
- [ ] unresolved_cleared：进入 ready_for_review 前不得残留 in_progress/not_satisfied。

# 两阶段 Review

## Review A1：上游要求 → Change

待实现/验证完成后执行。重点核对 #497 AC1—AC7、用户“本地中国源 / GitHub 官方源”的明确决定，以及不产生正式发布副作用的非目标。

## Review A2：Change → 实现 / 测试 / 文档

待 current-head 实现、专项测试、Release dry-run 与 Docs targeted review 完成后执行。重点反查是否真的删除 Workflow 第二套 Bundle 核心、是否保持 publish no-checkout、安全门禁和服务器 canonical Compose。

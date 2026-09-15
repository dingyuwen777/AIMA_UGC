---
schema: coding-change/v1
id: CHG-20260915-133000-local-release-bundle
title: 本地一键构建 Release 离线包
level: L3
status: done
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

- [x] PowerShell 一条命令可从仓库根委托共享核心生成 Linux/AMD64 完整离线 Bundle 与部署压缩包；真实镜像 Build/Package 由 PR current-head Release dry-run 作为合并门禁。
- [x] 本地默认 china；GitHub 显式 official；manifest 记录实际 Profile/upstream。
- [x] 本地与 GitHub 共用 `release_bundle.py` 的 Build/Bundle/replay 核心，不再在 Workflow 内维护第二套等价逻辑。
- [x] `-Verify` 使用隔离 smoke 资源执行 `docker load` + `--no-build --pull never`；Windows overlay 只用于本地 smoke，不进入 Bundle；严格离线 replay 由 PR current-head Release dry-run 作为合并门禁。
- [x] `-Formal` 只允许标准 SemVer、clean `main`、HEAD 精确等于最新 `origin/main`。
- [x] GitHub 正式 Release latest-main / Tag identity / GHCR / CI evidence / PR dry-run 机器契约保持。
- [x] 用户指南与实现侧专项回归完成；current-head required checks / Release dry-run 和 post-merge main-fresh / Change archive / #497 Closure 继续作为交付门禁，不伪造成实现侧已完成证据。

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
| R1 | Windows PowerShell 一键生成完整 Bundle/archive | #497 / AC1 | explicitly_deferred | PowerShell 入口参数/委托静态回归已通过；共享核心 Bundle/checksum/archive 纯逻辑 7/7；真实 Linux/AMD64 Build/Package 由 PR #498 current-head Release dry-run 持有，合并前必须成功。 |
| R2 | 本地 china、GitHub official，manifest 记录 Profile/upstream | #497 / AC2 | satisfied | `SOURCE_PROFILES` 固定两套来源；PowerShell 默认 china；Workflow 显式 `--source-profile official`；manifest 写 `build_source_profile/build_upstreams`；纯逻辑测试覆盖。 |
| R3 | 本地/GitHub 共用一个 Bundle 核心 | #497 / AC3 | satisfied | PowerShell 与 `release.yml` 都调用 `scripts/release/release_bundle.py`；Workflow 已移除原 417 行内嵌 Build/Bundle/replay 实现，并通过静态回归反查共享 tool artifact/finalize。 |
| R4 | `-Verify` 隔离离线 replay 并安全清理 | #497 / AC4 | explicitly_deferred | 核心实现 temp root + 唯一 Compose project + `down --remove-orphans -v`；Windows 仅临时叠加 storage-only overlay；PR #498 current-head strict replay 必须作为合并前 direct Evidence。 |
| R5 | `-Formal` clean/main/origin-main/SemVer fail closed | #497 / AC5 | satisfied | `validate_formal_checkout()` 检查 clean/main，执行 `git fetch origin main` 并要求 HEAD==origin/main；专项测试覆盖成功与 remote drift；普通本地 Docker tag 与 Formal SemVer 分离。 |
| R6 | GitHub 正式 Release 安全/身份/入口不退化 | #497 / AC6 | satisfied | release.published/workflow_dispatch、latest remote main、Tag/Release identity、GHCR private、required CI evidence、Publish no-checkout/revalidation 全部保留；Workflow 静态回归 11/11。 |
| R7 | 测试、文档、CI、main-fresh 与交付收尾 | #497 / AC7 | explicitly_deferred | 本地纯逻辑：Release Bundle 7/7、Workflow 11/11、YAML parse success；用户 guide 已写。PR current-head CI/Release dry-run 与 post-merge main-fresh/archive/#497 Closure 由交付阶段继续持有。 |

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
| Unit / Behavior | required | source profiles、version/formal guard、manifest、checksum/archive/finalize、PowerShell contract、Workflow contract；本地草案 7/7 + 11/11。 |
| Build / Package | required | PR #498 current-head Release dry-run 实际 Linux/AMD64 Backend/Frontend/PostgreSQL build + archive；合并前必须 Green。 |
| Offline Replay / Runtime | required | PR #498 current-head strict replay：删除候选 → docker load → canonical Compose `--no-build --pull never --wait` → Migration/Readiness；合并前必须 Green。 |
| Windows entry | required | PowerShell 静态参数/委托回归；真实 Windows Docker Desktop Runner 当前仓库不存在，因此不声称 Windows 实机 smoke；核心 Docker/Bundle 行为由共享 Linux dry-run 实证，Windows overlay 继续由既有 storage-contract 测试保护。 |
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

- [x] upstream_re_read：已重读 #497 live Requirement、current main、Release Workflow、Compose/Windows overlay、env build-source、现有 Release tests 与相关运维/开发文档。
- [x] change_coverage：AC1—AC7 全部映射 R1—R7；不可在 Ready 前取得的 current-head Docker dry-run/main-fresh 明确交给 PR/post-merge 交付门禁，没有被删除。
- [x] reverse_audit：已从 PowerShell → shared Builder、本地 Verify → Windows overlay、GitHub Build → official/strict shared Builder、GitHub Publish → transferred tool/finalize、Linux server → canonical Bundle/Compose 反查；没有第二套 Bundle Owner。
- [x] unresolved_cleared：实现侧无 `not_satisfied`；R1/R4/R7 的运行/交付证据显式 deferred 到 #498 current-head 与 post-merge Owner，不伪造尚未运行的结果。

# 两阶段 Review

## Review A1：上游要求 → Change

- #497 AC1—AC7 均在 R1—R7 有唯一映射；用户新增的“本地中国源更快、GitHub Release 仍官方源”由 R2 和 Profile 设计直接覆盖。
- 非目标保持：本地脚本没有 GitHub Token/Tag/Release/GHCR/生产部署能力；没有扩大到业务代码、Schema/Migration、依赖升级或服务器持久数据。
- Windows 实机 smoke 不在当前仓库 Runner 能力内，没有用 Linux 结果冒充 Windows 实跑；PowerShell/overlay 契约与共享核心行为分别提供可审查 Evidence。

## Review A2：Change → 实现 / 测试 / 文档

- PowerShell 是薄入口，默认 china，可切 official，`-Verify/-Formal` 显式；没有 `git tag/push`、`gh release` 或 `docker push`。
- `release_bundle.py` 是 Build/Bundle/manifest/checksum/archive/replay/finalize 单一 Owner；manifest 显式记录 profile/upstream/verification。
- `release.yml` 显式 official + strict replay，保留 latest-main、Tag/Release、GHCR private、CI evidence 和 publish no-checkout；Build Job 内原重复 Bundle/replay 已删除。
- 文档只新增开发操作指南并链接现有正式 Production/Release Owner，没有把本地辅助模式改写成生产发布事实。
- 本地草案专项证据：`test_release_bundle.py` 7 passed；`test_release_workflow.py` 11 passed；Release YAML 可解析。current-head 仓库 CI 与真实 Release dry-run 仍是最终 merge gate。

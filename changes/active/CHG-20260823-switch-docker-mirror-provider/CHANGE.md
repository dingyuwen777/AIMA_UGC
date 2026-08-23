---
schema: rvc-change/v1
id: CHG-20260823-switch-docker-mirror-provider
title: Docker 国内镜像源从 DaoCloud 切换到 1ms
level: L3
status: in_progress
owner: chatgpt
branch: feature/switch-docker-mirror-provider
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - docker-build
  - local-development
  - windows-docker-desktop
  - production-release
affected_paths:
  - Dockerfile
  - compose.yaml
  - env.production.example
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

解决当前 `m.daocloud.io` 在用户真实 Windows Docker Desktop 环境中拉取 PostgreSQL 18.4 长时间停滞的问题，把仓库可审计的 Docker Hub/GHCR 默认镜像前缀切换到 1ms，同时保持版本、业务 Runtime、持久化、Secret、Migration 和未来 Production Release 边界不变。

# 可观察成功标准

- [ ] Python / Node / Nginx / PostgreSQL 的 Docker Hub 默认镜像由 DaoCloud 前缀切换到 `docker.1ms.run`，版本号不变。
- [ ] uv 的 GHCR 默认镜像切换到 `ghcr.1ms.run`，版本号不变。
- [ ] Debian / PyPI / npm 现有 TUNA / npmmirror 下载链保持不变。
- [ ] 不依赖用户本机 `registry-mirrors`、Docker Desktop daemon 配置或 1Panel 本地配置。
- [ ] 不新增 `docker push` / Registry 发布，不改变 AIMA 自有镜像只在当前 Docker Engine 本地 build/tag 的语义。
- [ ] Linux canonical Compose 与 Windows storage-only Compose 的完整 Runtime CI 重新通过。
- [ ] L3 Completion Audit、两阶段 Review、Ready Gate 与最终永久 CI 全部通过后正常合并、独立归档。

# 范围

- Dockerfile / Compose / env template 中的 Docker Hub 与 GHCR 默认镜像地址。
- 构建源 Guide 中的默认源与回退说明。

# 非目标

- 不修改用户 Docker Desktop 或服务器 Docker daemon 的 `registry-mirrors`。
- 不把 `docker.1panel.live` 当成 Dockerfile/Compose 直接镜像前缀；1Panel 当前官方文档只明确其作为 daemon `registry-mirrors` 使用。
- 不使用阿里云 ACR 官方镜像加速器作为通用仓库默认；其地址按账号生成，且官方说明 Docker Hub 加速已停止同步最新镜像并定位个人开发场景。
- 不升级任何镜像、Python、Node、PostgreSQL、uv 或依赖版本。
- 不改变 Stage 11 不可变镜像 Release、digest/Manifest/SBOM/签名、Backup/Restore 设计。

# 必须保持不变

1. 精确版本继续由 Dockerfile/锁文件控制，不使用 `latest`。
2. `uv.lock` / `package-lock.json` 不因镜像源切换发生变化。
3. `compose.yaml` 的业务 service、command、environment、depends_on、Health、port、volume target、Secret 语义不变。
4. Windows `compose.windows.yaml` 继续只是 storage-only override。
5. PostgreSQL/Artifact/log/internal Secret 的持久化与恢复语义不变。
6. Production Server 最终仍使用已验证不可变镜像 + `--no-build --pull never`。

# 已确认关键决策

1. 用户要求不要依赖本机 daemon 环境，直接在仓库中替换镜像源。
2. 用户提出 1ms / 1Panel，也提出阿里云作为备选；基于当前官方事实，采用 1ms 直接镜像前缀：`docker.io → docker.1ms.run`、`ghcr.io → ghcr.1ms.run`。
3. 1Panel 只保留为外部可选 daemon mirror，不成为仓库默认依赖。
4. 阿里云 ACR 官方 Docker Hub 加速器不作为默认：账号专属、官方已提示停止同步最新镜像，且不适合作为产品通用构建默认。

# L3 方案比较

## 方案 A：继续 DaoCloud

优点：已由 CI 验证可用。缺点：用户真实网络中 PostgreSQL 18.4 拉取 393 秒仅完成 44.04MB，当前实际可用性不足。

结论：不继续作为默认。

## 方案 B：依赖 Docker daemon `registry-mirrors`（1ms + 1Panel）

优点：Docker Hub 可配置多 mirror。缺点：依赖每台开发机/服务器的宿主配置，无法由仓库本身保证，也不能直接覆盖 GHCR。

结论：不作为仓库默认机制。

## 方案 C：仓库直接使用 1ms Docker Hub/GHCR 前缀（采用）

优点：不依赖宿主 daemon；1ms 当前官方明确支持 Docker Hub 与 GHCR 前缀替换；Compose/Dockerfile 可直接审计；仍可通过 `env.production` 切回官方源。

代价：仓库构建阶段依赖 1ms 可用性，因此必须保留官方源 override，并由永久 CI 真实 build 验证。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化。
- 部署命令：无变化。
- 回滚：将 `AIMA_BUILD_*_IMAGE` 与 `AIMA_POSTGRES_IMAGE` 默认值恢复到前一镜像提供方或直接官方源；持久数据无需迁移。
- 用户现有 `env.production` 若已复制出 DaoCloud 地址，不会被 Git 更新自动覆盖；需要同步修改这几个镜像变量或重新基于 example 更新。

# 安全、性能与运维风险

- 1ms 是第三方镜像传输服务；完整 Production Release 仍需固定最终 image digest / Manifest / SBOM / 来源校验，不把镜像站域名等同于供应链完整性证明。
- 本轮 CI 证明镜像可拉取和 Runtime 可启动，但不能承诺所有地区固定下载带宽。
- 若 1ms 不可用，可通过 `env.production` 把镜像字段切回 Docker Hub/GHCR 官方值，不需要改业务配置或数据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 不依赖本机 daemon，直接替换仓库镜像源 | user:repo-direct-mirror | not_satisfied | 待 Dockerfile/Compose/env 实现与验证 |
| R2 | 解决 DaoCloud 在真实本地 PostgreSQL 拉取停滞 | user:daocloud-slow | not_satisfied | 待 1ms 默认源真实 CI build/pull 证明可用 |
| R3 | 不破坏正式上线/Production Release 规范 | `docs/roadmap/02_生产上线实施路线.md` | not_satisfied | 待确认只改 build/pull source，Runtime/Release 不变 |
| R4 | Windows CMD/PowerShell 和 Linux/服务器 Compose 继续可用 | `docs/02_环境运行与部署.md` | not_satisfied | 待 Windows/Internal V1-A 永久 CI |
| R5 | L3 Completion Audit、Review、Ready/CI/归档门禁 | `AGENTS.md` | not_satisfied | 完成前补齐 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务行为 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A 完整 Compose 验证 PostgreSQL/Migration/API/Secret/持久化 |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI 作为回归 |
| Real Full-stack Golden Path | required | Stage 8F + 完整 Compose Runtime 保持成功 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为 |
| Docs / Governance / Other | required | Docker/Compose 镜像解析、Windows launcher/runtime、Guide 与 Completion Gate |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户决定、AGENTS、Roadmap 和部署事实。
- [ ] change_coverage: Ready 前核对 R1-R5 与实现/文档/验证。
- [ ] reverse_audit: Ready 前反向检查无 daemon 依赖、无版本升级、无 Runtime/Storage/Secret/push 变化。
- [ ] unresolved_cleared: Ready 前清零 `not_satisfied`。

# 任务

1. [ ] 将 Dockerfile / Compose / env template 的 DaoCloud Docker Hub/GHCR 默认地址切换到 1ms。
2. [ ] 保持 TUNA / npmmirror 和全部版本锁定事实不变。
3. [ ] 更新 Docker 国内构建源 Guide，说明 1ms 默认、1Panel/阿里云为何不作为仓库直接默认。
4. [ ] 创建 Draft PR，跑永久 CI 的真实 Compose build/runtime。
5. [ ] Completion Audit + Requirement Review A1/A2 + Code Quality Review。
6. [ ] Ready Gate/最终永久 CI 全绿后正常合并。
7. [ ] 独立归档 Change 并清理临时分支。

# Git / 交付

- branch: `feature/switch-docker-mirror-provider`
- PR: 待创建
- archive: 实现 PR 正常合并后独立归档

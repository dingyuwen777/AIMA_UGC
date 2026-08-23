---
schema: rvc-change/v1
id: CHG-20260823-switch-docker-mirror-provider
title: Docker 国内镜像源从 DaoCloud 切换到 1ms
level: L3
status: ready_for_review
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
  - .github/workflows/internal-v1a.yml
  - .github/workflows/compose-windows-desktop.yml
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 最终设计结论

AIMA 在中国网络环境下的默认 Docker Hub / GHCR 镜像下载从 DaoCloud 切换到 1ms 的公开直接镜像前缀，不依赖开发机或服务器 Docker daemon 的 `registry-mirrors`：

```text
Docker Hub
→ docker.1ms.run/...

GHCR
→ ghcr.1ms.run/...

Debian / PyPI / npm
→ 继续 TUNA / TUNA / npmmirror
```

所有镜像与依赖版本保持不变，并继续允许 `env.production` 按项覆盖回 Docker Hub / GHCR / Debian / PyPI / npm 官方源。

GitHub Hosted Runner 位于海外。真实验证发现其访问 1ms PostgreSQL blob 时被 1ms/CDN 的 Cloudflare JavaScript challenge 拦截，因此永久 CI 显式使用官方源验证完整 Runtime 和回退机制；这不被描述成对中国网络 1ms 速度的证明。中国网络下 1ms 的实际吞吐仍以目标本地/公司网络实测为准。

# 可观察成功标准

- [x] Python / Node / Nginx / PostgreSQL 的 Docker Hub 默认镜像由 DaoCloud 前缀切换到 `docker.1ms.run`，版本号不变。
- [x] uv 的 GHCR 默认镜像切换到 `ghcr.1ms.run`，版本号不变。
- [x] Debian / PyPI / npm 继续使用既有 TUNA / TUNA / npmmirror，锁文件与版本未改变。
- [x] 仓库默认 1ms 不依赖用户本机 `registry-mirrors`、Docker Desktop daemon 配置或 1Panel 本地配置。
- [x] 不新增 `docker push` / Registry publish；AIMA backend/frontend 仍只由当前 Docker Engine 本地 build/tag。
- [x] 海外永久 CI 通过显式官方源 override 完成 Linux canonical Compose 与 Windows storage-only Compose 全生命周期回归。
- [x] L3 Completion Audit、Requirement Review A1/A2 与 Code Quality Review 已完成；最终 Ready HEAD 的 Completion Gate/永久 CI 作为合并硬门禁。

# 范围

- Dockerfile / Compose / env template 的 Docker Hub 与 GHCR 默认镜像地址。
- GitHub Hosted Runner 的官方源 override，避免海外 Runner 依赖中国镜像 CDN 地域策略。
- Docker 国内构建源 Guide 的默认源、回退和验证边界。

# 非目标

- 不修改用户 Docker Desktop 或服务器 Docker daemon 的 `registry-mirrors`。
- 不把 `docker.1panel.live` 当成 Dockerfile/Compose 直接镜像前缀；当前官方文档主要明确其作为 daemon `registry-mirrors` 使用。
- 不使用阿里云 ACR Docker Hub 镜像加速器作为通用仓库默认；其地址按账号生成，且官方当前已提示 Docker Hub 加速停止同步最新镜像。
- 不升级任何镜像、Python、Node、PostgreSQL、uv 或应用依赖版本。
- 不改变 Stage 11 不可变 Release、digest/Manifest/SBOM/签名、Backup/Restore 设计。
- 不把 GitHub 美国 Runner 的 1ms Cloudflare challenge 推导为“中国网络不可用”；也不把海外 CI 结果冒充中国网络速度测试。

# 必须保持不变

1. 精确版本继续由 Dockerfile/锁文件控制，不使用 `latest`。
2. `uv.lock` / `package-lock.json` 不因镜像源切换发生变化。
3. `compose.yaml` 的业务 service、command、environment、depends_on、Health、port、volume target、Secret 语义不变。
4. Windows `compose.windows.yaml` 继续只是 storage-only override。
5. PostgreSQL/Artifact/log/internal Secret 的持久化与恢复语义不变。
6. Production Server 最终仍使用已验证不可变镜像 + `--no-build --pull never`。

# 已确认关键决策

1. 用户明确要求不要依赖本机 daemon 环境，直接在仓库中替换默认镜像源。
2. 用户提出 1ms / 1Panel，并询问阿里云；基于当前官方能力和仓库约束，采用 1ms 直接前缀：`docker.io → docker.1ms.run`、`ghcr.io → ghcr.1ms.run`。
3. 1ms 基础通道按其当前公开说明可直接使用，不要求 AIMA 配置账号、登录 Secret 或付费能力；VIP/付费能力不作为依赖。
4. 1Panel 只作为管理员可自行配置的 daemon mirror 候选，不成为仓库直接镜像前缀。
5. 阿里云 ACR Docker Hub 镜像加速器不作为默认：账号专属且不适合作为通用、长期仓库事实。
6. 海外 GitHub Hosted Runner 对 1ms blob 的 Cloudflare challenge 是地域/CDN事实，因此 CI 用官方源 override；1ms 中国网络实际速度留给目标环境 smoke。

# L3 方案比较

## 方案 A：继续 DaoCloud

优点：上一 Change 的 CI 可用。缺点：用户真实 Windows 网络中 PostgreSQL 18.4 拉取 393 秒仅约 44 MB，实际体验不可接受。

结论：不继续作为中国环境默认。

## 方案 B：依赖 Docker daemon `registry-mirrors`（1ms + 1Panel）

优点：Docker Hub 可配置多个 mirror。缺点：依赖每台机器宿主配置，仓库无法自包含；同时不能直接解决 GHCR。

结论：不作为仓库默认机制。

## 方案 C：仓库直接使用 1ms Docker Hub/GHCR 前缀（采用）

优点：不依赖宿主 daemon；Docker Hub/GHCR 均可通过显式镜像引用；Compose/Dockerfile 可审计；仍可通过 env 按项回官方源。

代价：构建阶段增加第三方镜像传输依赖；海外 CI 可能受 1ms 地域/CDN策略影响，因此 CI 明确走官方源，并保留目标中国网络 smoke 边界。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化；`uv.lock` / `package-lock.json` 未修改。
- 部署命令：无变化。
- Linux/WSL/服务器 storage：无变化。
- Windows named-volume storage：无变化。
- 回滚：把 `AIMA_BUILD_*_IMAGE` / `AIMA_POSTGRES_IMAGE` 改回官方源或其他已验证镜像前缀；持久 PostgreSQL/Artifact/Secret 不需要迁移。
- 既有本地 `env.production` 是 Git ignored 的机器私有配置，Git pull 不会自动改其中旧 DaoCloud 值；需要把五个镜像变量同步为 1ms，或重新从 `env.production.example` 取值。

# 安全、性能与运维风险

- 1ms 是第三方镜像传输服务；完整 Production Release 仍需最终 image digest / Manifest / SBOM / 来源校验，不能把镜像站域名本身当供应链完整性证明。
- GitHub Hosted Runner 直连 1ms 真实失败证据：Windows Runtime run `32641296439` 的 PostgreSQL blob 下载收到 Cloudflare `Just a moment...` challenge；因此海外 CI 改为官方源不是降低测试，而是隔离地域网络依赖。
- 永久 CI 证明官方回退和 Runtime 完整性，不证明中国到 1ms 的固定下载速度。
- 若 1ms 在目标中国网络不可用，只需在 `env.production` 按项切回官方源或后续经过真实目标网络验证的替代源，无数据迁移。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 不依赖本机 daemon，直接替换仓库镜像源 | user:repo-direct-mirror | satisfied | `Dockerfile`、`compose.yaml`、`env.production.example` 默认直接使用 `docker.1ms.run` / `ghcr.1ms.run`；未要求 daemon 配置 |
| R2 | 不再默认使用真实环境中极慢的 DaoCloud，改为 1ms | user:daocloud-slow | satisfied | PR #177 diff 已移除运行配置中的 DaoCloud 默认并改为 1ms；中国网络实际吞吐明确留给目标环境 smoke，不虚构 CI 速度证据 |
| R3 | 不破坏正式上线/Production Release 规范 | `docs/roadmap/02_生产上线实施路线.md` | satisfied | 仅 build/pull source 与 CI source override 变化；Stage 11 不可变 image/digest/Release 边界未修改，Guide 04 明确保留 |
| R4 | Windows CMD/PowerShell 和 Linux/服务器 Compose 继续可用 | `docs/02_环境运行与部署.md` | satisfied | Windows run `32641522034` success；Internal V1-A run `32641522115` Compose Golden Path success |
| R5 | L3 Completion Audit、Review、Ready/CI/归档门禁 | `AGENTS.md` | satisfied | A1/A2/Code Quality Review 与 Completion Audit 已完成；pre-ready 除预期 in_progress Completion Gate 外永久 CI 全绿，最终 Ready HEAD 继续复跑 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务行为 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A run `32641522115`：PostgreSQL/Migration/API/Secret/persistence/fail-closed 完整 Compose Golden Path success |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI run `32641522047` success 作为回归证据 |
| Real Full-stack Golden Path | required | Stage 8F run `32641522138` success；Internal V1-A 与 Windows merged Runtime 均成功 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 请求或字段 |
| Docs / Governance / Other | required | Windows run `32641522034` success；Guide 04 与 env template 同步；Ready Completion Gate 继续作为最终门禁 |

# Completion Audit

- [x] upstream_re_read: 已重新读取本轮用户决定、当前 `main` 的 `AGENTS.md`、RVC Skill、Blueprint README/07、Roadmap 与部署事实。
- [x] change_coverage: 用户要求的仓库直接 1ms、非 daemon 依赖、正式上线边界、跨平台 Compose 和 L3 交付均已映射到 R1-R5。
- [x] reverse_audit: 已核对无镜像/依赖版本升级、无 Schema/Contract/Migration/Storage/Secret/push 变化，并处理海外 CI 的 1ms 地域失败而未降低 Runtime 测试。
- [x] unresolved_cleared: R1-R5 无 `not_satisfied`；中国网络实际下载速度明确为目标环境 smoke 边界，不被虚构为已验证。

# 两阶段 Review

## Requirement Review A1：上游要求 → Change

通过。用户的直接仓库切源、不依赖本机 daemon、兼顾上线规范、继续合并 main，以及 Roadmap 的 Production Release/Windows/Linux 运行边界均已进入 Change；未发现 requirement omission。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过：

- Docker Hub 四类镜像与 PostgreSQL 默认改为 1ms；GHCR uv 默认改为 `ghcr.1ms.run`；
- TUNA / npmmirror 和所有锁定版本保持；
- 海外 CI 显式官方 override 后，Windows Runtime、Internal V1-A、总 CI、Stage 8F 均通过；
- Guide 记录 1ms 免费基础通道、1Panel/阿里云边界、Cloudflare 海外失败事实和 Production Release 不变项；
- 未把海外 Runner 失败误写成中国用户失败，也未把官方源 CI 冒充 1ms 性能验证。

## Code Quality Review

通过，无 Serious/Important finding：

- 修改局限于构建/拉取 source 与对应验证/文档；
- 无业务逻辑、数据库、Contract、Migration 或依赖升级；
- 通过现有环境变量而非新增平行 Compose 实现回退；
- CI 的官方 override 与目标中国环境默认 source 分工明确；
- 无 Secret、新 Registry credential 或公网 push；
- Production 不可变 Release 方向未降低。

# 验证证据

pre-ready head: `0b796519255f7f709c324e2b68ca6744f1d3f45a`

- `32641522034` Windows Docker Desktop Compose Compatibility: success
- `32641522115` Internal V1-A Deployable Stack: success
- `32641522047` CI: success
- `32641522138` Stage 8F Full-stack Acceptance: success
- `32641522060` Stage 6 Xiaohongshu Vertical Slice: success
- `32641522152` Stage 7 Keyword Packs: success
- `32641522122` Stage 7 Scheduler Runtime: success
- `32641522045` Stage 7 Provider Config Routing: success
- `32641522009` Stage 7 Plan Occurrence Run Snapshot: success
- `32641522083` Local Dev Bootstrap: success
- pre-ready `32641522097` Completion Gate: expected failure because Change was still `in_progress`

# Git / 交付

- branch: `feature/switch-docker-mirror-provider`
- Draft PR: #177
- pre-ready validated head: `0b796519255f7f709c324e2b68ca6744f1d3f45a`
- archive: 实现 PR 正常合并后独立归档

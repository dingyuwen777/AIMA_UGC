---
schema: rvc-change/v1
id: CHG-20260823-official-build-sources-default
title: 统一官方镜像身份与国内下载源
level: L3
status: ready_for_review
owner: chatgpt
branch: feature/official-build-sources-default
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
  - scripts/setup_dev_environment.cmd
  - scripts/setup_dev_environment.sh
  - scripts/dev/configure_docker_desktop_mirrors.ps1
  - tests/unit/test_docker_build_sources.py
  - .github/workflows/internal-v1a.yml
  - .github/workflows/compose-windows-desktop.yml
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

AIMA_UGC 的 Docker 镜像身份固定为官方 Docker Hub reference，下载加速与镜像身份分离。

项目固定使用：

```text
python:3.14.7-slim-trixie
node:24.19.0-bookworm-slim
nginx:1.30.4-alpine3.24
postgres:18.4
```

`uv` 固定为 `0.12.3`，由 Python builder 通过 PyPI 安装，不再使用 GHCR uv 容器镜像。

首次环境初始化在宿主 Docker Engine 配置多个 Docker Hub `registry-mirrors`；后续管理员仍只使用标准 Docker Compose 启停命令。Debian / PyPI / npm 默认使用国内包下载源并允许按机器覆盖。

# 可观察成功标准

- [x] Dockerfile / Compose 的基础容器镜像只使用官方 Docker Hub reference，不包含第三方 registry image reference。
- [x] Compose PostgreSQL 固定为 `postgres:18.4`。
- [x] 不存在 `AIMA_BUILD_PYTHON_IMAGE`、`AIMA_BUILD_UV_IMAGE`、`AIMA_BUILD_NODE_IMAGE`、`AIMA_BUILD_NGINX_IMAGE`、`AIMA_POSTGRES_IMAGE` 当前配置入口。
- [x] Dockerfile 不再依赖 GHCR uv image；`uv==0.12.3` 从可配置 PyPI 下载源安装，并禁止缺少 wheel 时静默源码构建。
- [x] Windows `setup_dev_environment.cmd` 首次初始化可配置 Docker Desktop Docker Engine mirrors；Linux `setup_dev_environment.sh` 配置同一候选列表。
- [x] 默认 Docker Hub mirror 列表包含 `docker.1panel.live`、`hub.1panel.dev`、`docker.m.daocloud.io`，并设置 `max-download-attempts=5`。
- [x] Debian / Debian Security 默认阿里云镜像、PyPI 默认清华 TUNA、npm 默认 npmmirror，并继续允许显式覆盖。
- [x] Windows 日常启动/停止仍只使用现有两条标准 Docker Compose 命令；未增加 Compose wrapper、预拉取或 retag 入口。
- [x] 镜像和依赖版本、lockfile、业务 Runtime、Schema、Migration、Secret、端口与存储语义不变。
- [x] Linux canonical Compose、Windows storage-only Compose、Stage 8F 和相关永久 CI 在审计 HEAD `c3114ee7d756ee9417aaf8c1583bea6b6fab0a77` 通过。

# 范围

- Dockerfile 基础镜像与构建期包下载源。
- Compose PostgreSQL image 与 build args。
- `env.production.example` 构建源配置。
- Windows / CentOS 首次环境初始化的 Docker Hub mirror 配置。
- 永久 Compose CI 中已失效的 image override 配置。
- Windows / Docker 下载源当前运行文档。
- 最小配置回归测试。

# 非目标

- 不在 Dockerfile / Compose / `env.production` 中直接写第三方容器 image reference。
- 不增加日常预拉取、retag 或 Compose wrapper。
- 不兼容、不迁移本机已有第三方 image tag。
- 不升级 Python、uv、Node、Nginx、PostgreSQL 或应用依赖版本。
- 不修改 Schema、Migration、HTTP Contract、Secret、端口、存储或业务语义。
- 不实现完整 Production digest / SBOM / 签名 / Release Bundle。

# 必须保持不变

1. 所有版本继续锁定当前精确值，不使用 `latest`。
2. `uv.lock` / `frontend/package-lock.json` 不变化。
3. `compose.yaml` 的 service、command、environment、depends_on、Health、port、volume target、Secret 语义不变化。
4. `compose.windows.yaml` 继续只做 storage-only override。
5. Windows 日常管理员入口继续是：

```text
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

6. Production 最终仍使用已验证不可变镜像和 `--no-build --pull never`。
7. 包下载源只影响构建传输，不进入业务 Runtime Contract。

# 已确认关键决策

1. 用户要求第三方来源可替换，但项目和本机 Docker image identity 始终使用官方名称。
2. 用户接受第一次通过 `setup_dev_environment.cmd` / `setup_dev_environment.sh` 配置 Docker Hub `registry-mirrors`；日常不再修改镜像源配置。
3. 用户要求后续日常只使用标准 Docker Compose 启动和停止命令，不增加额外启动脚本。
4. Dockerfile / Compose 不使用第三方 Docker image reference，也不保留 image override 变量。
5. Docker build 内 Debian / PyPI / npm 可以继续使用国内源，不影响依赖身份和 lockfile。
6. 为消除 GHCR 特殊下载链路，`uv==0.12.3` 改由 PyPI 安装，基础 OCI 镜像统一到 Docker Hub。
7. 当前 Docker Hub mirror 候选使用 1Panel 两个入口与 DaoCloud Docker Hub mirror；不采用用户当前机器已有不稳定证据的 `docker.1ms.run`。
8. 当前用户文档只描述最终运行事实，不记录方案演变过程。

# L3 方案比较

## 方案 A：第三方 registry 直接写入项目 image reference

优点：不依赖 daemon mirror 配置。缺点：本地 tag 与项目身份绑定第三方 registry，换源会改变镜像名称，违背统一身份要求。

结论：不采用。

## 方案 B：仓库预拉取第三方 image，再 retag 成官方名称

优点：可自行实现多源 fallback。缺点：需要额外启动/预处理入口，无法维持用户只执行两条标准 Compose 命令的要求。

结论：不采用。

## 方案 C：首次初始化配置 Docker Hub mirrors；项目只使用官方 Docker Hub image；包源独立使用国内镜像（采用）

镜像身份固定，下载通道由 Docker Engine 处理；Windows/Linux 首次初始化负责 mirror 配置，日常 Compose 不感知第三方 registry。uv 通过 PyPI 安装后不再需要 GHCR 镜像链路。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化。
- 日常 Compose 启停命令：无变化。
- Windows 首次环境初始化：合并 `%USERPROFILE%\.docker\daemon.json` 的 `registry-mirrors` / `max-download-attempts`，保留原配置并备份，Docker Desktop restart 后用 `docker info` 验证。
- CentOS Stream 9 初始化：原有单 DaoCloud mirror 改为三候选 mirror，并保留 daemon 配置备份/合并/校验/安全重启逻辑。
- 本机已有第三方 image tag：不迁移、不 retag、不作为项目兼容边界。
- 回滚：恢复 Dockerfile/Compose/build-source 默认和首次初始化 mirror 配置；数据库、Artifact 与 Secret 无迁移。

# 安全、性能与运维风险

- 公共 Docker Hub mirror 是外部网络依赖，可能限流、维护或短时不可用；多个候选 mirror 与 Docker 下载重试降低单点风险，但不能保证外部互联网服务永久在线。
- Docker image reference 继续锁定明确版本，不使用 `latest`；完整 Production provenance 仍由后续 digest/Manifest/SBOM/签名闭环。
- `uv==0.12.3` 通过 PyPI 安装时要求 binary wheel，避免下载源缺 wheel 时突然引入 Rust 源码构建路径。
- Python 业务依赖继续受 `uv export --frozen` + hash 校验约束，npm 继续受 lockfile integrity 约束。
- GitHub Hosted Runner 位于海外，永久 CI 显式覆盖构建期包下载源为官方上游；该覆盖不改变 Docker image identity。
- Windows Hosted Runner 能验证 helper PowerShell 语法和标准 Compose CLI；真实个人 Docker Desktop 的 daemon 配置写入/重启需要在目标开发机首次执行 `scripts\setup_dev_environment.cmd` 后由 `docker info` 验证，不能用 Hosted Runner 冒充该目标机证据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Dockerfile / Compose 只使用官方 Docker Hub image identity | user:source-change-identity-fixed | satisfied | PR #182 反向审计；`tests/unit/test_docker_build_sources.py`；CI `32651527854` unit suite 589 passed |
| R2 | 首次 Windows/Linux 初始化配置多个国内 Docker Hub mirrors，日常无需改源 | user:first-setup-configures-mirrors | satisfied | `scripts/setup_dev_environment.cmd`、`scripts/dev/configure_docker_desktop_mirrors.ps1`、`scripts/setup_dev_environment.sh`；Windows workflow `32651527873` 通过 helper 语法与 Compose CLI；目标 Docker Desktop 写入由 helper 自身 `docker info` fail-closed 验证 |
| R3 | 日常仅保留标准 Docker Compose 启动/停止命令 | user:compose-only-daily-entry | satisfied | `docs/guides/03_Windows Docker Desktop Compose运行.md`；Windows Compose workflow `32651527873`；Internal V1-A `32651527847` |
| R4 | 消除 GHCR uv image，uv 固定版本改由 PyPI 下载 | user:resolve-ghcr-with-pypi | satisfied | Dockerfile + unit config test；Internal V1-A `32651527847` 完整 Docker build/Runtime 通过；CI `32651527854` 实际从 PyPI wheel 安装 `uv==0.12.3` |
| R5 | Debian/PyPI/npm 默认国内源且不改变锁定依赖身份 | user:domestic-build-package-sources | satisfied | Dockerfile/Compose/env template + unit config test；PR changed-files 审计确认 `uv.lock` 与 `frontend/package-lock.json` 未变；CI `32651527854` 通过 |
| R6 | 不改变版本、业务 Runtime、持久化、Secret、Schema/Migration | AGENTS.md | satisfied | PR #182 仅 12 个预期 deployment/config/docs/test 文件；无 Migration/Contract/业务代码/lockfile 变更；CI `32651527854`、Internal V1-A `32651527847` 通过 |
| R7 | 保持 Internal V1 / Windows storage-only Compose / Production Release 边界 | docs/roadmap/02_生产上线实施路线.md | satisfied | Roadmap 重新读取；`compose.windows.yaml` 未改；Windows Runtime `32651527873`、Stage 8F `32651527827`、Internal V1-A `32651527847` 均通过 |
| R8 | 完成 L3 Completion Audit、两阶段 Review，并进入 Ready Check / CI 门禁 | AGENTS.md | satisfied | 2026-08-23 完成 upstream re-read、A1/A2、Code Quality Review 与 Completion Audit；本次 `ready_for_review` 提交将由 Change Completion Gate 和全部永久 CI 重新验证，未全绿前 PR 不转 Ready |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A `32651527847`：真实 Compose build、PostgreSQL、Migration、API/Worker/Scheduler、Secret 与持久化生命周期通过；CI Stage 2/3A 同时通过 |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；CI 仍执行 drift/compatibility 检查并通过 |
| Real Full-stack Golden Path | required | Stage 8F `32651527827` 成功；Internal V1-A `32651527847` 成功 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为或真实字段 |
| Docs / Governance / Other | required | CI `32651527854`：Ruff、mypy、589 unit + 74 contract + 30 API、docs/secret/architecture checks、frontend tests/build/E2E 全通过；Windows `32651527873` 成功；Ready transition 后再跑 Change Completion Gate |

# Completion Audit

- [x] upstream_re_read: 2026-08-23 重新读取用户最终决定、AGENTS、Reliable Vibe Coding、completion-gate/verification-review、Blueprint 07、Roadmap Internal V1-A/Stage 11 边界和当前部署文件。
- [x] change_coverage: 重新从上游构建 R1-R8；Docker Hub image identity、首次 host mirrors、uv、Debian/PyPI/npm、两条日常 Compose 命令、Internal V1/Production 不变量均已进入 Change，没有发现遗漏 requirement。
- [x] reverse_audit: 反向检查 Dockerfile → Compose → env template → Windows/Linux setup → CI → Guide；无 GHCR uv `FROM`、无第三方 Docker image reference、无失效 image override；`compose.windows.yaml`、locks、Migration/Contract/业务代码均未被修改。
- [x] unresolved_cleared: R1-R8 全部有实现和当前证据；Browser/Contract/Provider 层按当前边界不适用，required 层均已有新鲜运行证据；真实 Windows Docker Desktop 首次 mirror 写入保留为明确目标机 smoke，不冒充 Hosted Runner 已执行。

# Review

## Requirement Review A1：上游要求 → Change

通过。用户最终明确的“首次 setup 配置 mirrors、日常只用标准 Compose、镜像身份固定官方、uv 去 GHCR、Docker build 包源继续国内、文档只写当前事实”全部映射到 R1-R8。Roadmap 的 canonical Compose、Windows storage-only 和完整 Production Release 后续边界均被保留。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。12 个 PR 变更文件与 affected_paths 一致；镜像 identity、host mirror、package source、Windows/Linux 首次初始化、CI 和 Guide 的事实一致。完整 Compose build/Runtime 与 Windows storage model 均有当前运行证据。

## Code Quality Review

通过，无阻断问题。实现没有增加日常 wrapper、retag 或第二套 Compose Runtime；Windows helper 合并并备份现有 daemon JSON，重启后 fail-closed 验证 mirrors；Linux 复用既有 daemon 合并/备份/validate/安全重启机制。依赖版本、locks、Schema/Migration、业务 API 和 Secret 语义未变化。

现有 CI 仍报告与本 Change 无关的已知 warning：XLSX 重复成员安全测试 warning、Starlette TestClient deprecation warning、npm 依赖 deprecation/install-script 提示；本 Change 不升级依赖以避免扩大范围。

# 验证证据

审计 HEAD：`c3114ee7d756ee9417aaf8c1583bea6b6fab0a77`

- CI `32651527854`: success。
  - Ruff format: 458 files already formatted；Ruff check passed；mypy 235 source files 无错误。
  - Unit: 589 passed，1 warning。
  - Contract: 74 passed。
  - API: 30 passed，1 warning。
  - Frontend unit: 34 passed；Playwright E2E: 13 passed；frontend build success；npm audit 0 vulnerabilities。
- Internal V1-A `32651527847`: success；Compose topology、`up -d --build --wait` lifecycle、repo-relative host root 均通过。
- Windows Docker Desktop Compose Compatibility `32651527873`: success；Windows CMD/PowerShell Compose CLI、helper PowerShell syntax、named-volume Runtime、restart persistence 均通过。
- Stage 8F `32651527827`: success。
- Local Dev Bootstrap `32651527802`: success。
- Stage 6 / Stage 7 相关永久 workflows：当前审计 HEAD 全部 success。
- 当前设计 Red 提交 `d7778ff82d3afe8d42879661fbfaee4fb24f9d8c` 在执行目标断言前被 Ruff format gate 阻断，因此不计有效行为 Red；不伪造 TDD 证据。最终配置/部署行为以当前 Green unit/config checks + 真实 Compose Runtime 证据验收。

`docs/02_环境运行与部署.md` 当前没有与本 Change 直接冲突的 GHCR/image override/包源默认事实，因此未为本 Change强制改写；准确运行事实由 `env.production.example` 与两份直接 Guide 维护。

# Git / 交付

- Branch: `feature/official-build-sources-default`
- Draft PR: #182
- Merge: 未授权；全部新 HEAD 门禁通过后只转 Ready，不合并 main

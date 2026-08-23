---
schema: rvc-change/v1
id: CHG-20260823-official-build-sources-default
title: 统一官方镜像身份与国内下载源
level: L3
status: in_progress
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

- [ ] Dockerfile / Compose 的基础容器镜像只使用官方 Docker Hub reference，不包含第三方 registry image reference。
- [ ] Compose PostgreSQL 固定为 `postgres:18.4`。
- [ ] 不存在 `AIMA_BUILD_PYTHON_IMAGE`、`AIMA_BUILD_UV_IMAGE`、`AIMA_BUILD_NODE_IMAGE`、`AIMA_BUILD_NGINX_IMAGE`、`AIMA_POSTGRES_IMAGE` 当前配置入口。
- [ ] Dockerfile 不再依赖 GHCR uv image；`uv==0.12.3` 从可配置 PyPI 下载源安装，并禁止缺少 wheel 时静默源码构建。
- [ ] Windows `setup_dev_environment.cmd` 首次初始化可配置 Docker Desktop Docker Engine mirrors；Linux `setup_dev_environment.sh` 配置同一候选列表。
- [ ] 默认 Docker Hub mirror 列表包含 `docker.1panel.live`、`hub.1panel.dev`、`docker.m.daocloud.io`，并设置 `max-download-attempts=5`。
- [ ] Debian / Debian Security 默认阿里云镜像、PyPI 默认清华 TUNA、npm 默认 npmmirror，并继续允许显式覆盖。
- [ ] Windows 日常启动/停止仍只使用现有两条标准 Docker Compose 命令；不增加 Compose wrapper、预拉取或 retag 入口。
- [ ] 镜像和依赖版本、lockfile、业务 Runtime、Schema、Migration、Secret、端口与存储语义不变。
- [ ] Linux canonical Compose、Windows storage-only Compose、Stage 8F 和相关永久 CI 继续通过。

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
7. 当前 Docker Hub mirror 候选使用 1Panel 两个入口与 DaoCloud Docker Hub mirror；不采用本机已有实际不稳定证据的 `docker.1ms.run`。
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
- Windows 首次环境初始化：新增 Docker Desktop Docker Engine mirror 配置与实际 `docker info` 验证。
- CentOS Stream 9 初始化：原有单 DaoCloud mirror 改为三候选 mirror，并保留 daemon 配置备份/合并/校验/安全重启逻辑。
- 本机已有第三方 image tag：不迁移、不 retag、不作为项目兼容边界。
- 回滚：恢复 Dockerfile/Compose/build-source 默认和首次初始化 mirror 配置；数据库、Artifact 与 Secret 无迁移。

# 安全、性能与运维风险

- 公共 Docker Hub mirror 是外部网络依赖，可能限流、维护或短时不可用；多个候选 mirror 与 Docker 下载重试降低单点风险，但不能保证外部互联网服务永久在线。
- Docker image reference 继续锁定明确版本，不使用 `latest`；完整 Production provenance 仍由后续 digest/Manifest/SBOM/签名闭环。
- `uv==0.12.3` 通过 PyPI 安装时要求 binary wheel，避免下载源缺 wheel 时突然引入 Rust 源码构建路径。
- Python 业务依赖继续受 `uv export --frozen` + hash 校验约束，npm 继续受 lockfile integrity 约束。
- GitHub Hosted Runner 位于海外，永久 CI 可显式覆盖构建期包下载源为官方上游；该覆盖不改变 Docker image identity。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Dockerfile / Compose 只使用官方 Docker Hub image identity | user:source-change-identity-fixed | not_satisfied | 待最终 diff 与 CI 验证 |
| R2 | 首次 Windows/Linux 初始化配置多个国内 Docker Hub mirrors，日常无需改源 | user:first-setup-configures-mirrors | not_satisfied | 待脚本与目标机/CI 验证 |
| R3 | 日常仅保留标准 Docker Compose 启动/停止命令 | user:compose-only-daily-entry | not_satisfied | 待文档与 Compose CI 验证 |
| R4 | 消除 GHCR uv image，uv 固定版本改由 PyPI 下载 | user:resolve-ghcr-with-pypi | not_satisfied | 待 Docker build 验证 |
| R5 | Debian/PyPI/npm 默认国内源且不改变锁定依赖身份 | user:domestic-build-package-sources | not_satisfied | 待配置测试与 Docker build 验证 |
| R6 | 不改变版本、业务 Runtime、持久化、Secret、Schema/Migration | AGENTS.md | not_satisfied | 待 diff 与 CI 验证 |
| R7 | 保持 Internal V1 / Windows storage-only Compose / Production Release 边界 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 待文档与永久 CI 验证 |
| R8 | 完成 L3 Completion Audit、两阶段 Review、Ready Check 与 CI | AGENTS.md | not_satisfied | 待最终交付门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A Compose Golden Path 验证 PostgreSQL/Migration/Runtime |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client |
| Real Full-stack Golden Path | required | Stage 8F 与完整 Compose Runtime 回归 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为或真实字段 |
| Docs / Governance / Other | required | 配置测试、PowerShell 语法、Windows Compose、Docker build、Completion Gate、文档一致性 |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户决定、AGENTS、Skill、Blueprint、Roadmap 和当前部署事实。
- [ ] change_coverage: Ready 前比较上游要求与 R1-R8，确认 Docker Hub image、host mirrors、uv、Debian/PyPI/npm 和日常命令均已覆盖。
- [ ] reverse_audit: Ready 前反向检查 Dockerfile → Compose → env template → setup scripts → CI → Guide 的一致性，确认没有残留 GHCR uv image、第三方 Docker image reference 或失效 image override。
- [ ] unresolved_cleared: Ready 前清零 `not_satisfied`，所有 required Validation Matrix 有新鲜证据。

# 分步计划

1. Red：更新配置测试，覆盖官方 Docker Hub identity、uv PyPI 安装、国内包源默认和 Windows/Linux 多 mirror 初始化目标。
2. Green：修改 Dockerfile / Compose / env template / setup scripts / CI，使目标测试通过。
3. 文档：同步 Windows 与 Docker 下载源 Guide，仅保留当前运行事实。
4. 验证：目标测试、格式/静态检查、PowerShell 语法、Shell/Compose 配置、Internal V1-A、Windows、Stage 8F、总 CI。
5. Review：重新读取上游完成定义，执行 Completion Audit、Requirement Review A1/A2、Code Quality Review 与 Ready Check。
6. Git：永久 CI 全绿后转 Ready；未经用户明确授权不合并 main。

# 当前验证证据

- 旧设计第三次 Red：单元测试曾在生产配置仍为第三方 image / 官方包源默认时执行并暴露目标差异；其后方案被用户进一步收敛为本 Change 当前设计。
- 当前设计 Red：提交 `d7778ff82d3afe8d42879661fbfaee4fb24f9d8c` 先更新测试；待读取对应 CI 执行结果后记录有效 Red 证据。
- 当前 Green 实现已写入分支，最终验证尚未完成。

# Git / 交付

- Branch: `feature/official-build-sources-default`
- Draft PR: #182
- Merge: 未授权；Ready 后等待用户明确指令

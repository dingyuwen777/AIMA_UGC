---
schema: rvc-change/v1
id: CHG-20260823-official-build-sources-default
title: 官方镜像与官方构建源作为通用默认
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
  - tests/unit/test_docker_build_sources.py
  - .github/workflows/internal-v1a.yml
  - .github/workflows/compose-windows-desktop.yml
  - docs/02_环境运行与部署.md
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

把 AIMA_UGC 的容器镜像身份统一为官方 canonical reference，并把 Debian/PyPI/npm 的 canonical 默认切回官方上游。

容器镜像不再通过 `env.production` 或 Compose build args 选择第三方 registry。项目固定使用：

```text
python:3.14.7-slim-trixie
ghcr.io/astral-sh/uv:0.12.3
node:24.19.0-bookworm-slim
nginx:1.30.4-alpine3.24
postgres:18.4
```

机器需要 registry mirror、企业代理缓存或其他下载加速时，由 Docker Desktop / Docker daemon / 企业基础设施处理，不改变项目里的镜像名称。

Debian / PyPI / npm 不是容器镜像身份，仍保留 `AIMA_BUILD_*` 下载源覆盖能力，但 canonical 默认使用官方上游。

# 可观察成功标准

- [ ] Dockerfile 中 Python、uv、Node、Nginx 直接使用官方镜像 reference，不存在第三方 registry 前缀或镜像地址变量。
- [ ] Compose PostgreSQL 固定为 `postgres:18.4`，不再存在 `AIMA_POSTGRES_IMAGE`。
- [ ] `AIMA_BUILD_PYTHON_IMAGE`、`AIMA_BUILD_UV_IMAGE`、`AIMA_BUILD_NODE_IMAGE`、`AIMA_BUILD_NGINX_IMAGE`、`AIMA_POSTGRES_IMAGE` 从当前配置/Compose/Dockerfile 中移除。
- [ ] Debian / Debian Security / PyPI / npm canonical 默认使用官方源，并继续允许按机器显式覆盖。
- [ ] 当前文档不再把 1ms/DaoCloud 等第三方容器 registry 写成项目镜像引用或默认方案。
- [ ] 镜像和依赖版本、lockfile、业务 Runtime、Schema、Migration、Secret、端口与存储语义不变。
- [ ] 自动测试覆盖官方镜像固定引用与官方包源默认。
- [ ] Linux canonical Compose、Windows storage-only Compose、Stage 8F 和相关永久 CI 继续通过。

# 范围

- Dockerfile 的基础镜像 reference 与包源默认。
- Compose 的 PostgreSQL image、build args 与包源默认。
- `env.production.example` 中构建源配置。
- 永久 Compose CI 中已失效的镜像 override 配置。
- 直接相关部署/Windows/构建源文档。
- 最小回归测试。

# 非目标

- 不兼容、不迁移、不自动 retag 本机已有第三方镜像标签。
- 不提供项目级第三方容器 registry fallback。
- 不修改用户 Docker Desktop / daemon 的 registry mirror 配置。
- 不升级 Python、uv、Node、Nginx、PostgreSQL 或应用依赖版本。
- 不修改 Schema、Migration、HTTP Contract、Secret、端口、存储或业务语义。
- 不实现完整 Production digest / SBOM / 签名 / Release Bundle。

# 必须保持不变

1. 所有镜像继续锁定当前精确版本，不使用 `latest`。
2. `uv.lock` / `frontend/package-lock.json` 不变化。
3. `compose.yaml` 的 service、command、environment、depends_on、Health、port、volume target、Secret 语义不变化。
4. `compose.windows.yaml` 继续只做 storage-only override。
5. Production 最终仍使用已验证不可变镜像和 `--no-build --pull never`。
6. 包源 override 仅影响构建下载，不进入业务 Runtime Contract。

# 已确认关键决策

1. 用户明确要求 `docker.1ms.run/library/postgres:18.4` 等第三方前缀全部改成官方镜像名称。
2. 用户进一步明确：不需要兼容已有第三方镜像；无论之前从哪里拉取，项目统一只使用官方 image reference。
3. 项目不再保留容器镜像地址覆盖变量，避免通过 `env.production` 再把 canonical image 切回第三方 registry。
4. Docker 下载加速如果需要，应由 Docker daemon/Desktop/企业代理基础设施完成，而不是改变项目里的镜像身份。
5. Debian/PyPI/npm 属于包下载源而非容器镜像身份；canonical 默认改官方，保留显式覆盖能力。
6. 历史归档 Change 保留当时的国内镜像决策与验证证据，不改写历史；本 Change 记录后续新决定。

# L3 方案比较

## 方案 A：继续第三方 registry 作为项目默认

优点：中国网络某些环境冷启动可能更快。缺点：镜像 reference 与官方标签不同，项目镜像身份绑定第三方服务；跨网络与本机已有官方标签复用都不自然。

结论：不采用。

## 方案 B：官方默认，但保留 image override 变量

优点：可以从 env 切换 registry。缺点：项目仍允许形成多套镜像身份，与“全部统一官方镜像名称”的要求冲突。

结论：不采用。

## 方案 C：容器镜像固定官方 reference；包源官方默认且可覆盖（采用）

镜像身份完全统一；Docker 层面的下载加速交给 daemon/企业代理；Debian/PyPI/npm 保留独立下载源覆盖，避免网络问题时修改源码。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化。
- 启动命令：无变化。
- 本机已有第三方镜像 tag：不迁移、不 retag、不作为项目兼容边界。
- 旧 `env.production` 中存在已删除 image 变量时：Compose 不再消费这些字段，用户可自行删除；不会影响持久数据。
- 回滚：恢复旧 Dockerfile/Compose/image override 即可；数据库和 Artifact 无迁移。

# 安全、性能与运维风险

- 官方镜像 reference 统一来源语义，但真实下载速度仍取决于网络和 Docker 基础设施。
- 中国网络若访问 Docker Hub/GHCR 较慢，应配置 Docker registry mirror/企业代理缓存；不在项目里改写 image reference。
- 包源仍可显式覆盖，Python 依赖继续受 `uv export --frozen` + hash 校验约束，npm 继续受 lockfile integrity 约束。
- Production 供应链完整性仍依赖后续 digest/Manifest/SBOM/签名，官方名称本身不等于完整 provenance。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 所有容器镜像统一为官方 reference | user:official-image-references-only | not_satisfied | 待实现与验证 |
| R2 | 不兼容、不保留第三方镜像身份或 image override | user:no-third-party-image-compatibility | not_satisfied | 待实现与验证 |
| R3 | 同时审计 Debian/PyPI/npm 等构建源，canonical 默认官方 | user:review-other-sources | not_satisfied | 待实现与验证 |
| R4 | 不改变版本、业务 Runtime、持久化、Secret、Schema/Migration | AGENTS.md | not_satisfied | 待 diff 与 CI 验证 |
| R5 | 保持 Internal V1 / Windows Compose / Production Release 长期边界 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | 待文档与永久 CI 验证 |
| R6 | 完成 L3 Completion Audit、两阶段 Review、Ready Check 与 CI | AGENTS.md | not_satisfied | 待最终交付门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A Compose Golden Path 验证 PostgreSQL/Migration/Runtime |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client |
| Real Full-stack Golden Path | required | Stage 8F 与完整 Compose Runtime 回归 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为或真实字段 |
| Docs / Governance / Other | required | 目标配置测试、Windows Compose、Completion Gate、文档一致性 |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户决定、AGENTS、Skill、Blueprint、Roadmap 和当前部署事实。
- [ ] change_coverage: Ready 前比较上游要求与 R1-R6，确认所有容器镜像和包源类别均已覆盖。
- [ ] reverse_audit: Ready 前反向检查 Dockerfile → Compose → env template → CI → Guide/运行文档的一致性，确认没有残留第三方 image reference 或无效 image override。
- [ ] unresolved_cleared: Ready 前清零 `not_satisfied`，所有 required Validation Matrix 有新鲜证据。

# 分步计划

1. Red：新增配置测试，并确认它因当前第三方镜像/包源实现失败，而非测试自身错误。
2. Green：最小修改 Dockerfile / Compose / env template / CI，固定官方 image reference、官方包源默认。
3. 文档：同步环境、Windows 和构建源 Guide，删除当前有效说明中的第三方 image reference 方案。
4. 验证：目标测试、格式/静态检查、Compose config、Internal V1-A、Windows、Stage 8F、总 CI。
5. Review：重新读取上游完成定义，执行 Completion Audit、Requirement Review A1/A2、Code Quality Review 与 Ready Check。
6. Git：永久 CI 全绿后转 Ready；按仓库规则正常合并并独立归档 Change。

# 当前验证证据

- 第一次 Red 尝试：CI Stage 1 在 `ruff format --check` 因测试文件格式失败，不计有效 Red。
- 第二次 Red 尝试：CI Stage 1 在 `ruff check` 因 import 空行格式失败，不计有效 Red。
- 第三次 Red：正在等待目标断言执行结果。

# Git / 交付

- Branch: `feature/official-build-sources-default`
- Draft PR: #182
- Merge: 待所有门禁通过

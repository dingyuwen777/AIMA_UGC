---
schema: rvc-change/v1
id: CHG-20260823-switch-docker-mirror-provider
title: Docker 国内镜像源与软件包源优化
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
  - .github/workflows/internal-v1a.yml
  - .github/workflows/compose-windows-desktop.yml
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

解决中国网络环境中新电脑首次 Docker Compose 冷启动时基础镜像和软件包下载过慢的问题，同时保持仓库自包含、版本锁定、正式 Production Release 边界以及 Windows/Linux 现有 Runtime 不变。

最终默认组合：

```text
Docker Hub images
→ docker.1ms.run

GHCR uv image
→ ghcr.1ms.run

Debian / Debian Security
→ mirrors.aliyun.com

PyPI
→ mirrors.aliyun.com/pypi/simple

npm
→ registry.npmmirror.com（阿里系）
```

GitHub Hosted Runner 位于海外，真实访问 1ms 时 PostgreSQL blob 被 Cloudflare JavaScript challenge 拦截。因此永久 CI 显式使用官方源验证完整 Runtime 与 source override；中国网络下默认国内源的真实下载速度由目标新电脑/公司服务器实际 smoke 验证。

# 可观察成功标准

- [x] Python / Node / Nginx / PostgreSQL 的 Docker Hub 默认镜像使用 `docker.1ms.run`，版本不变。
- [x] uv GHCR 默认镜像使用 `ghcr.1ms.run`，版本不变。
- [x] Debian / Debian Security 默认使用阿里云公开镜像。
- [x] PyPI 默认使用阿里云公开镜像，`uv.lock` 不改写为镜像专属 lock。
- [x] npm 继续使用 `registry.npmmirror.com`，不重复引入另一套 npm 镜像。
- [x] 默认构建不依赖宿主 Docker daemon `registry-mirrors`。
- [x] 新电脑没有 AIMA/基础镜像时，正式 Compose 入口会自动 pull/build；已有镜像/layer 时 Docker 自动复用。
- [x] 不新增 `docker push` / Registry publish；本地 build 不会公开发布 AIMA 镜像。
- [ ] 海外永久 CI 在官方源 override 下重新完成 Linux canonical Compose、Windows storage-only Compose、总 CI 和 Stage 8F 回归。
- [ ] 完成最新 Requirement Review、Code Quality Review、Ready Gate 后合并并独立归档。

# 范围

- Dockerfile / Compose / env template 的镜像和软件包默认下载源。
- GitHub Hosted Runner 的官方源 override。
- 新电脑冷启动、已有缓存复用和 env.production 旧值说明。
- Docker 国内构建 Guide。

# 非目标

- 不修改用户 Docker Desktop 或服务器 daemon 的 `registry-mirrors`。
- 不把 `docker.1panel.live` 假设成 Dockerfile/Compose 直接镜像前缀。
- 不使用阿里云 ACR Docker Hub 镜像加速器作为仓库 Docker image 默认；该能力与阿里云 Debian/PyPI/npm 镜像是不同服务。
- 不升级 Python、Node、PostgreSQL、uv、nginx 或任何应用依赖版本。
- 不修改 Schema、Migration、HTTP Contract、业务语义、Secret、port 或持久化模型。
- 不实现 Stage 11 完整不可变 Release、digest Manifest、SBOM/签名或 Backup/Restore。

# 必须保持不变

1. 精确版本继续由 Dockerfile/锁文件控制，不使用 `latest`。
2. `uv.lock` / `package-lock.json` 不因换源变化。
3. `compose.yaml` 的 service、command、environment、depends_on、Health、port、volume target、Secret 语义保持。
4. `compose.windows.yaml` 仍只是 storage-only override。
5. PostgreSQL/Artifact/log/internal Secret 持久化与恢复语义不变。
6. Production Server 最终仍加载已验证不可变镜像并以 `--no-build --pull never` 启动。

# 已确认关键决策

1. 用户要求不要依赖本机 daemon，直接在仓库配置默认国内下载源。
2. DaoCloud 在用户真实 Windows Docker Desktop 上拉 PostgreSQL 18.4 时长期停滞，因此不继续作为默认。
3. Docker Hub/GHCR 采用 1ms 公开直接前缀，不要求 AIMA 配置 1ms 登录凭据或付费能力。
4. 用户进一步要求软件包源也优先考虑阿里体系；Debian、Debian Security、PyPI 改为阿里云公开镜像。
5. `registry.npmmirror.com` 已是阿里系当前 NPM 镜像入口，因此 npm 保持现值。
6. 新电脑应从零开始可运行：没有镜像就自动下载，没有 AIMA image 就自动 build；已有镜像/layer 时按 Docker 默认缓存语义复用。
7. Git ignored 的既有 `env.production` 不会被 Git pull 更新；已有机器若仍保存 DaoCloud/TUNA 值，需要手工同步或重新基于 example 生成。
8. 海外 GitHub Runner 对 1ms 的 Cloudflare challenge 不作为中国环境失败证据；永久 CI 使用官方源 override。

# L3 方案比较

## 方案 A：继续 DaoCloud + TUNA

用户真实环境已证明 DaoCloud PostgreSQL 下载体验不可接受；继续使用不能解决问题。

结论：拒绝。

## 方案 B：只依赖宿主 daemon mirror

Docker Hub 可以配置多个 mirror，但每台机器都要单独维护，而且 GHCR、APT、PyPI、npm 仍需独立配置。

结论：不作为仓库默认。

## 方案 C：仓库分协议明确选择国内源（采用）

```text
OCI/Docker Registry → 1ms
APT/PyPI → 阿里云
npm → npmmirror
```

每类协议使用对应服务，同时所有字段可按项回退官方源；最符合新电脑直接运行和长期可维护性。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无变化。
- Windows/Linux 启动命令：无变化。
- 持久化路径/volume：无变化。
- 回滚：在 `env.production` 把对应构建源改回官方地址，或恢复旧 Dockerfile/Compose 默认值；持久数据不需要迁移。
- 新电脑：从最新 `env.production.example` 生成 `env.production` 即得到当前国内默认组合。
- 已有电脑：`env.production` 被 Git ignore，不会自动更新；必须检查其中旧镜像/软件包源。

# 安全、性能与运维风险

- 1ms / 阿里云 / npmmirror 都是构建期网络依赖，不是供应链完整性本身；完整 Production 仍依赖最终 image digest / Manifest / SBOM / 签名等门禁。
- Python 第三方依赖继续通过 `uv export --frozen` + `uv pip sync --require-hashes` 安装。
- npm 继续使用 lockfile integrity。
- Debian 包仍由发行版仓库签名机制校验。
- 海外 GitHub Runner 直连 1ms 的失败是 CDN/地域策略，CI 使用官方源不是绕过业务测试。
- CI 不能证明用户新电脑的固定下载速度；用户本机冷启动是最终中国网络吞吐事实。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 仓库直接配置国内镜像，不依赖本机 daemon | user:repo-direct-mirror | satisfied | `Dockerfile` / `compose.yaml` / `env.production.example` 直接配置 1ms/阿里云/npmmirror |
| R2 | 不再默认使用用户环境中极慢的 DaoCloud | user:daocloud-slow | satisfied | DaoCloud 已从当前默认 Docker image 地址移除 |
| R3 | Debian/PyPI 优先改用阿里云，npm 使用稳定阿里系入口 | user:aliyun-package-mirrors | satisfied | Debian/PyPI 默认已改 `mirrors.aliyun.com`；npm 保持 `registry.npmmirror.com` |
| R4 | 新电脑无任何所需镜像也能自动拉取和构建，有则复用 | user:cold-start | satisfied | Compose 仍使用 `up --build`; 不要求手工 pre-pull；Guide 明确 pull/build/cache 行为；CI 使用唯一 AIMA image tag |
| R5 | 不公开发布本地 AIMA 镜像 | user:no-public-push | satisfied | Dockerfile/Compose/workflow 无 `push`/`buildx --push`；Guide 解释本地 tag |
| R6 | 不破坏 Production Release / Windows / Linux Runtime | `docs/roadmap/02_生产上线实施路线.md` | satisfied | 仅 build/pull source 与 CI override 变化；Storage/Secret/Migration/Release 边界不变 |
| R7 | L3 Review、Ready Gate、CI、合并与归档 | `AGENTS.md` | not_satisfied | 等最新 HEAD 永久 CI 与完成审计后更新 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改用户业务界面/行为 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A Compose Golden Path 重新验证 PostgreSQL/Migration/API/Secret/persistence/fail-closed |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI做回归 |
| Real Full-stack Golden Path | required | Stage 8F + 完整 Compose Runtime 回归 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider |
| Docs / Governance / Other | required | Windows launcher/Runtime、source override、Guide、Completion Gate |

# Completion Audit

- [ ] upstream_re_read: 等最新实现 HEAD 完成后重新读取上游事实。
- [ ] change_coverage: 等最新实现 HEAD 核对 R1-R7。
- [ ] reverse_audit: 等最新 CI 核对无业务/数据/运行语义漂移。
- [ ] unresolved_cleared: R7 尚未满足，不能进入 Ready。

# 任务

1. [x] Docker Hub/GHCR 默认镜像切换到 1ms。
2. [x] Debian/Debian Security/PyPI 默认切换到阿里云。
3. [x] npm 保持阿里系 npmmirror。
4. [x] 海外永久 CI 显式使用官方源 override。
5. [x] Guide 固化新电脑冷启动、缓存、既有 env.production 和 Production 边界。
6. [ ] 跑最新永久 CI，完成 Completion Audit 与两阶段 Review。
7. [ ] Ready、合并 PR #177、独立归档并清理临时分支。

# Git / 交付

- branch: `feature/switch-docker-mirror-provider`
- Draft PR: #177
- archive: 实现 PR 合并后独立归档
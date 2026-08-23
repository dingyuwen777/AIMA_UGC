---
schema: rvc-change/v1
id: CHG-20260823-china-build-mirrors
title: Docker 构建国内源加速与可追溯回退
level: L3
status: in_progress
owner: chatgpt
branch: feature/china-build-mirrors
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
  - ci
affected_paths:
  - Dockerfile
  - compose.yaml
  - env.production.example
  - .github/workflows/internal-v1a.yml
  - .github/workflows/compose-windows-desktop.yml
  - docs/02_环境运行与部署.md
  - docs/blueprint/05_日志安全部署与运维.md
  - docs/roadmap/02_生产上线实施路线.md
  - docs/appendix/11_生产部署与离线Release方案.md
  - docs/guides/03_Windows Docker Desktop Compose运行.md
contracts: []
data_changes: []
---

# 目标

解决中国网络环境下首次 `docker compose ... up --build` 因 Docker Hub/GHCR 基础镜像、Debian apt、PyPI/uv、npm 下载过慢导致的不可接受构建时间，同时不把 AIMA 自有镜像发布到公网、不改变业务 Runtime、不降低未来正式 Production Release 的镜像可追溯与不可变发布边界。

# 可观察成功标准

- [ ] Dockerfile 基础镜像默认通过国内镜像代理拉取，并保留明确版本；管理员可显式切回官方源。
- [ ] PostgreSQL 运行镜像默认使用同一国内镜像代理路径，并保留明确版本。
- [ ] Backend apt 默认使用国内 Debian mirror；Python 依赖默认使用国内 PyPI mirror；Frontend npm 默认使用国内 registry。
- [ ] 国内源配置只影响构建/拉取，不改变应用业务配置、数据库 Schema、Migration、Contract、Secret、端口或持久化语义。
- [ ] 普通 `docker compose ... up --build` 仍只在本机 build/tag image，不包含 `push`，不会发布 AIMA 自有镜像。
- [ ] GitHub 永久 CI 显式使用官方源，证明国内默认值可以被覆盖，避免海外 Runner 反向依赖中国镜像。
- [ ] Windows Docker Desktop 与 Linux/服务器继续复用现有 Compose/Storage 架构。
- [ ] 运行文档明确首次 build 为什么慢、国内源/官方回退、缓存语义以及项目级本地清理方式。
- [ ] L3 Completion Audit、Requirement Review、Code Quality Review、Ready Check 与最终永久 CI 全部通过后再合并/归档。

# 范围

- Docker build/pull 的来源选择与默认值。
- Debian apt、uv/PyPI、npm 的构建期下载源。
- CI 对官方源 override 的验证。
- 本地 Docker 项目级重置说明。

# 非目标

- 不配置或修改用户 Docker Desktop 全局 daemon settings；不覆盖其他项目的 registry mirror。
- 不执行 `docker push`，不新增公网 Registry 发布流程。
- 不升级 Python/Node/nginx/PostgreSQL/uv/npm/Python/Frontend 依赖版本。
- 不实现 Stage 11 完整不可变 Release、digest Manifest、SBOM/签名或私有 Registry。
- 不改变 Windows named-volume 与 Linux/Production bind-mount 持久化模型。

# 必须保持不变

1. 精确版本继续由当前 Dockerfile/锁文件事实控制，普通任务不使用 `latest`。
2. AIMA 自有 backend/frontend image 只在当前 Docker Engine 本地 build/tag，除非未来有独立 Release Change 明确执行 push。
3. Production Server 最终仍使用已验证不可变镜像 + `--no-build --pull never`；当前 Internal V1 的现场 build 只是阶段性能力。
4. PostgreSQL/Artifact/log/internal Secret 的持久化与恢复语义不变。
5. Secret 不进入镜像、Git、构建日志或普通容器环境变量。

# 已确认关键决策

1. 用户明确要求：中国网络环境下下载镜像或在镜像内安装软件时优先使用国内源，并授权修改代码后提交到 main。
2. 不把 Docker Desktop 全局 daemon 配置作为仓库隐式副作用；仓库通过显式镜像 URL/构建参数实现可审计的默认国内加速。
3. Docker 官方镜像与 GHCR uv 使用 DaoCloud public image mirror 的前缀映射；该项目声明镜像内容 SHA256 与源保持一致，并建议优先明确版本/sha256。
4. Debian/PyPI/npm 国内源与仓库现有 Windows 工具链保持一致：TUNA Debian/PyPI + npmmirror npm。
5. 永久 CI 显式覆盖为 Docker Hub/GHCR、Debian/PyPI/npm 官方源，避免 GitHub 海外 Runner 因中国镜像可达性形成假回归。

# L3 方案比较

## 方案 A：用户手工修改 Docker Desktop registry-mirrors

优点：Docker Hub 基础镜像可透明加速。缺点：这是机器全局配置，会影响其他项目；Docker 官方 registry mirror 主要覆盖 docker.io，不能直接解决 GHCR、apt、PyPI、npm；难由仓库 CI 审计。

结论：不作为仓库默认机制，只保留为高级可选项。

## 方案 B：把第三方镜像地址硬编码且不可覆盖

优点：最少配置。缺点：海外 CI/未来其他区域环境会被强制依赖中国镜像；镜像源故障无回退；不符合长期 Release 可追溯边界。

结论：拒绝。

## 方案 C：国内源作为仓库默认值 + 显式 build/source override（采用）

优点：用户复制 `env.production.example` 后无需额外设置即可加速；来源集中、可审计；版本不变；CI/其他区域可以显式回到官方源；未来 Stage 11 可直接将这些输入纳入 Release manifest/digest 校验。

代价：增加少量构建期环境变量，但不进入应用 Runtime Contract。

# 兼容、Migration、部署与回滚

- API/Schema/Migration/Data：无变化。
- 运行兼容：现有 `docker compose` 命令、Windows wrapper、服务名称、端口、volume 均不变。
- 构建兼容：新增 `AIMA_BUILD_*` 与 `AIMA_POSTGRES_IMAGE` 可选配置；不配置时采用国内默认值，显式设置官方值即可回退。
- 回滚：恢复旧 Dockerfile/Compose/env 模板即可；持久 PostgreSQL/Artifact/Secret 不需要迁移或回滚。
- 本地重置：只清理 AIMA Compose project 的容器/网络/volume/image；全局 BuildKit cache 清理仅在 Docker Desktop 专用于 AIMA 时人工选择，不由脚本自动执行。

# 安全、性能与运维风险

- 国内公共镜像代理是第三方网络依赖；当前阶段通过明确版本、可切官方源、CI 官方源回归降低风险。完整 Production Release 后仍必须以 digest/Manifest/SBOM/签名做更强完整性保证。
- `docker compose down -v` 会破坏本地数据库/Artifact/内部 Secret，只允许用户明确要求“一切重新开始”时使用。
- `docker system prune -a --volumes` 会影响其他项目，因此不作为 AIMA 文档默认清理命令。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 下载基础镜像与镜像内安装软件优先使用国内源 | user:china-build-mirrors | not_satisfied | 待 Dockerfile/Compose/env 实现与验证 |
| R2 | 不把 AIMA 镜像发布到公网 | user:no-public-image-publish | satisfied | 当前 Compose/Dockerfile 无 push；本 Change 不新增 push/registry publish |
| R3 | 保持产品上线规范与未来不可变镜像 Release 方向 | `docs/roadmap/02_生产上线实施路线.md` | not_satisfied | 待文档与官方源 override/Release 边界同步 |
| R4 | Windows CMD/PowerShell 与 Linux/服务器现有 Compose 入口继续可用 | `docs/02_环境运行与部署.md` | not_satisfied | 待永久 CI 验证 |
| R5 | 本地 AIMA Docker 状态可以安全重置后重新开始 | user:local-reset | not_satisfied | 待项目级 reset 文档与命令确认 |
| R6 | L3 完成审计、两阶段 Review、Ready Gate 和永久 CI | `AGENTS.md` | not_satisfied | 完成前补齐 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A Compose Golden Path 继续验证 PostgreSQL/Migration/API/Secret/持久化 |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI drift check 作为回归证据 |
| Real Full-stack Golden Path | required | Stage 8F 与完整 Compose Runtime 保持全绿，证明构建来源变化未破坏真实栈 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 请求行为，不需要付费 Probe |
| Docs / Governance / Other | required | Docker source rendering、Windows launcher、Linux/Windows Compose、官方源 override、文档与 Completion Gate |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

1. [ ] Dockerfile 增加可覆盖的国内基础镜像、Debian、PyPI、npm 默认源。
2. [ ] Compose 将 build args 与 PostgreSQL image 接入同一 source 参数。
3. [ ] env.production.example 记录国内默认和官方回退，不要求普通用户日常切换。
4. [ ] CI 显式使用官方源并验证 Compose source 解析。
5. [ ] 同步运行、Blueprint、Roadmap、Production Release、Windows Guide。
6. [ ] 跑目标 CI、Completion Audit、两阶段 Review、Ready Check、最终永久 CI。
7. [ ] 合并后独立归档 Change。

# 验证计划

- `docker compose ... config`：确认默认国内 source 与显式官方 source 都能正确渲染。
- Internal V1-A：官方源 override 下完整 build/start/readiness/persistence/fail-closed 回归。
- Windows Compatibility：官方源 override 下 wrapper + named-volume Runtime 回归。
- 总 CI、Stage 8F、Stage 6/7、Local Dev Bootstrap 全绿。

# 文档影响

- `docs/02_环境运行与部署.md`
- `docs/blueprint/05_日志安全部署与运维.md`
- `docs/roadmap/02_生产上线实施路线.md`
- `docs/appendix/11_生产部署与离线Release方案.md`
- `docs/guides/03_Windows Docker Desktop Compose运行.md`

# Git / 交付

- branch: `feature/china-build-mirrors`
- PR: 待创建
- archive: 合并后独立归档

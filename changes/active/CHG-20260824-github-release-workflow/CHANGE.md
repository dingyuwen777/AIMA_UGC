---
schema: rvc-change/v1
id: CHG-20260824-github-release-workflow
title: GitHub 一键离线 Release Workflow
level: L3
status: in_progress
owner: aima
branch: feature/github-release-workflow
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - ci
  - docs
affected_paths:
  - .github/workflows/release.yml
  - tests/unit/test_docker_build_sources.py
  - docs/02_环境运行与部署.md
  - docs/roadmap/02_生产上线实施路线.md
  - docs/appendix/11_生产部署与离线Release方案.md
contracts: []
data_changes: []
---

# 目标

在不改变本地/Windows/公司服务器现有 Docker 构建默认源和业务 Runtime 的前提下，新增一个可从 GitHub Actions 手工触发的一键 Release Workflow：输入正式 SemVer 版本号后，从当前 `main` 的固定 SHA 构建 Linux/AMD64 Backend/Frontend 镜像，发布到 GHCR，同时把 Backend/Frontend/PostgreSQL 18.4 镜像及部署文件打成可从 GitHub Release 下载的离线包，完成 Tag 与 GitHub Release 创建。

# 成功标准

- [ ] GitHub Actions 中出现 `Release` Workflow，可通过 `workflow_dispatch` 输入 `vMAJOR.MINOR.PATCH` 手工触发，并拒绝非 `main`、非法版本号、重复 Tag/Release 或不满足发布门禁的请求。
- [ ] Release 构建只在 GitHub Hosted Linux Runner 内显式使用 Docker Hub、Debian、PyPI、npm 官方上游；仓库 `Dockerfile`、`compose.yaml`、`env.production.example` 的国内默认下载源不改变，本地 Windows/Linux 使用方式不受影响。
- [ ] Backend/Frontend 只构建一次正式 Linux/AMD64 候选镜像，发布带版本与 SHA 标签的 GHCR 镜像，并记录不可变 digest；PostgreSQL 固定使用当前仓库锁定的官方 `postgres:18.4`。
- [ ] Release 资产至少包含 `AIMA_UGC-vX.Y.Z-deploy.tar.gz`、`release-manifest.json`、`migration-manifest.json`、`SHA256SUMS`；离线包内含 `images.tar`、`compose.yaml`、版本化 `env.production.example`、两个 manifest、`SHA256SUMS` 和 `DEPLOY.md`。
- [ ] CI/Release 构建后实际删除候选运行镜像、从 `images.tar` 重新 `docker load`，再以 `--no-build --pull never` 启动 canonical Compose 并通过 readiness，证明服务器无需现场 build/pull 即可运行本包。
- [ ] Release 包不包含 PostgreSQL 数据、Artifact、日志、真实 `env.production` 或内部/外部 Secret；生产持久根继续与 Release 生命周期分离。
- [ ] 文档明确当前能力是“一键不可变离线 Release 基础”，不把尚未实现的协调 Backup/Restore、HTTPS/认证、SBOM/独立签名或真实 Production Go-Live 伪装成已完成。

# 范围

- 新增 `.github/workflows/release.yml`，同时支持 PR 路径变更时的 Release Bundle dry-run/no-pull 验证与 `main` 上的手工正式发布。
- 复用现有根 `Dockerfile`、canonical `compose.yaml`、`AIMA_HOST_ROOT` 持久化模型和现有 bootstrap/migrate/configure/health 机制。
- GitHub Runner 的构建参数显式覆盖为官方 Debian/PyPI/npm 上游；Docker 基础镜像和 PostgreSQL 使用仓库已锁定的 Docker Hub canonical reference。
- 发布 GHCR Backend/Frontend 镜像，并生成离线 Bundle、manifest、校验和、部署说明。
- 为 Release Workflow 增加仓库级静态/语义回归测试，并同步 Production Release 相关文档。

# 非目标

- 本 Change 不新增 `compose.production.yaml`；当前离线发布继续复用 canonical `compose.yaml`，避免复制第二套 Runtime。未来只有出现独立生产语义时再按 Stage 11A 引入覆盖文件。
- 不实现企业认证/Authorization、HTTPS/HSTS/CSP、正式公网入口或生产资源限额。
- 不实现 PostgreSQL + Artifact 协调 Backup/Restore、自动数据库回滚、RPO/RTO。
- 不在本 Change 引入 SBOM 生成器、第三方签名工具或新项目依赖；`SHA256SUMS` 只作为当前文件完整性校验，不能被描述成独立来源签名。
- 不修改 Windows `compose.windows.yaml`，不把 Windows storage adapter 打入服务器运行路径。
- 不自动触发真实 TikHub/LLM 请求，不包含任何 Provider Secret。

# 必须保持不变

- `Dockerfile` 的基础镜像版本、Python/Node/Nginx/PostgreSQL 锁定版本不升级、不降级。
- `Dockerfile` / `compose.yaml` / `env.production.example` 继续保留面向国内本地环境的默认 Debian/PyPI/npm 下载源；Release 只通过 Workflow 的 build args 覆盖 GitHub Runner 下载源。
- Linux/WSL/公司服务器 canonical Runtime 继续使用 `compose.yaml`；Windows Docker Desktop 继续使用 `compose.yaml + compose.windows.yaml`。
- 生产持久状态继续位于 `${AIMA_HOST_ROOT}/postgres`、`${AIMA_HOST_ROOT}/runtime/data`、`${AIMA_HOST_ROOT}/runtime/logs`、`${AIMA_HOST_ROOT}/shared/secrets`，不进入 Release Bundle。
- Migration 继续由独立 `migrate` service 执行，API/Worker/Scheduler 不自行修改 Schema。
- 不新增 Python/npm 运行依赖，不修改业务 Contract、Schema、Migration 或数据语义。

# 方案比较与关键决策

## 方案 A：canonical Compose + GHCR + GitHub Release 离线 Bundle（采用）

- GitHub Runner 用当前 Dockerfile target 构建 Backend/Frontend；正式手工发布时推送 GHCR，并把相同候选镜像连同 `postgres:18.4` 打入 `images.tar`。
- 离线包直接复用 canonical `compose.yaml`，通过版本化 `AIMA_IMAGE_TAG` 选择本包镜像；服务器 `docker load` 后使用 `--no-build --pull never`。
- 优点：最小增量、与 Original 的“一键 Tag + Release + 可下载镜像”目标一致，同时不复制 Runtime；GHCR digest 与 Release Bundle 可互相审计。
- 代价：当前仍只有 SHA256 文件完整性，没有完整 SBOM/独立来源签名；这些继续作为后续生产强化单元。

## 方案 B：只生成 GitHub Release Bundle，不发布 GHCR（不采用）

- 更简单、权限更少，但失去独立 Registry 镜像 digest/下载路径，与用户要求的 Original 发布效果和长期不可变镜像审计方向不完全一致。

## 方案 C：本次直接完成完整 Stage 11A/11B（不采用）

- 同时引入 Production Compose、HTTPS/认证、SBOM/签名、Backup/Restore 等。
- 会把多个尚未决策/验收的生产领域耦合到一次 Workflow 变更，扩大风险和验证成本，不符合当前“先做一键 Release Workflow”的最小目标。

已确认上游决策：用户 2026-08-24 明确要求开始 GitHub Release Workflow，并确认 GitHub Release 构建环境显式使用 Docker Hub / Debian / PyPI / npm 官方上游；该覆盖必须只作用于 GitHub Release/CI 构建，不能改变本地默认源。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Actions 手工输入版本后可一键打 Tag、构建/发布镜像并创建可下载 GitHub Release | user:2026-08-24-github-release-workflow | not_satisfied | 实现与真实 Runner 验证待完成 |
| R2 | Release Runner 显式使用 Docker Hub / Debian / PyPI / npm 官方上游，且不影响本地国内默认源 | user:2026-08-24-official-release-upstreams | not_satisfied | 静态回归与 Runner 构建证据待完成 |
| R3 | 正式 Release 面向 Linux/AMD64，服务器使用不可变镜像并支持 no-build/no-pull，不现场构建 | docs/roadmap/02_生产上线实施路线.md | not_satisfied | Release Bundle dry-run/no-pull Compose smoke 待完成 |
| R4 | Release Bundle 与持久 PostgreSQL/Artifact/log/Secret 分离，固定 `AIMA_HOST_ROOT` 不随版本切换 | docs/appendix/11_生产部署与离线Release方案.md | not_satisfied | Bundle 内容审计与文档同步待完成 |
| R5 | 当前实现不能把未完成的 Backup/Restore、认证/HTTPS、SBOM/独立签名和完整 Production Go-Live 写成已完成 | docs/appendix/11_生产部署与离线Release方案.md | not_satisfied | 文档完成审计待完成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本次没有前端页面或浏览器交互变化；GitHub Actions UI 由 `workflow_dispatch` 配置提供，不属于产品 Browser E2E。 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端业务规则、API、Repository、Schema 或数据库状态机；PostgreSQL 只作为 Release Compose Golden Path 的真实运行依赖验证。 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client 或其他公共业务 Contract。 |
| Real Full-stack Golden Path | required | Release dry-run 必须真实 build → save → 删除镜像 → load `images.tar` → canonical Compose `--no-build --pull never` → Migration/configure/API/PostgreSQL/frontend readiness。 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 能力，普通 Release 验证明确禁用真实付费调用。 |
| Docs / Governance / Other | required | pytest 静态回归验证 Workflow 触发/源/版本/Bundle/安全边界；Release Workflow PR run、Ruff/CI、Ready Check、文档一致性作为新鲜证据。 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取用户决定、Roadmap Stage 11、Production Release Appendix 和当前机器事实，独立重建完成定义。
- [ ] change_coverage：比较上游要求与当前 Change，确认本单元没有漏掉一键发布、官方上游隔离、不可变镜像、离线 Bundle、no-pull smoke 与持久数据分离。
- [ ] reverse_audit：从 GitHub Release 资产反查服务器实际启动路径，从 canonical Compose 反查 Bundle 必需镜像/配置，并复核 Validation Matrix 的证据等级。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零；延期/不适用项均有正式依据。

# 任务

- [x] 调查当前 AGENTS/Skill、Roadmap、Production Appendix、Dockerfile、Compose、现有 CI 与 Original Release Workflow。
- [ ] 先建立 Release Workflow 失败测试并取得因目标文件/行为缺失而失败的 Red 证据。
- [x] 建立 Validation Matrix 和 L3 方案比较。
- [ ] 实现最小 Release Workflow。
- [ ] 同步环境部署、Roadmap 与 Release Appendix。
- [ ] 取得 Release dry-run/no-pull、目标测试、相关 CI 和机器 Ready Check 的新鲜证据。
- [ ] 完成 Requirement Traceability、Completion Audit 和两阶段 Review。

# 验证

## 计划

- Red：`uv run pytest tests/unit/test_docker_build_sources.py -q`，新增 Release 断言应因 `.github/workflows/release.yml` 尚不存在而失败。
- Green：同一目标测试通过，确认本地默认源仍为国内镜像、Release Workflow 只在 Runner build args 中使用官方上游。
- Release Bundle Golden Path：PR 触发 `Release` Workflow 的 dry-run，真实构建 Linux/AMD64 镜像、拉取 `postgres:18.4`、保存/重新加载 `images.tar`，以 `--no-build --pull never` 启动并验证 readiness。
- 相关：现有 CI / Internal V1-A / Change Completion Gate 等按 GitHub 永久 Workflow 复验。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`（PR 阶段由 changed-since 门禁验证当前 Change；完成前再补等价本地/Runner 证据）。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/02_环境运行与部署.md`：把“未来正式 Release”更新为当前已实现的一键 Release 下载/部署入口，并继续区分 Internal V1-B 与完整 Production。
- `docs/roadmap/02_生产上线实施路线.md`：记录 GitHub Release Workflow 基础已实现时的部分完成状态，不提前宣称 Stage 11A/11B 全部闭环。
- `docs/appendix/11_生产部署与离线Release方案.md`：记录 Workflow、Bundle、官方上游隔离、GHCR/digest/no-pull smoke 的当前机器事实及仍未完成项。

# 兼容、部署与回滚

- 兼容：无业务 API/Schema/数据格式变化；本地/Windows/Linux Internal V1 命令保持不变。
- Migration：本 Change 不新增 Migration。Release Workflow 记录当前 Alembic head；部署时仍由现有 `migrate` service 执行 `alembic upgrade head`。
- 部署：正式 Release 资产只包含应用/数据库镜像与部署元数据，不触碰目标服务器 `${AIMA_HOST_ROOT}` 中既有数据。
- 回滚：Workflow 代码可整体回退；已发布的 Git Tag/Release 属于不可变发布事实，本 Change 不设计自动删除/覆盖已有 Tag/Release。应用层回滚仍受对应版本 Migration 兼容性和后续 Backup/Restore 能力约束。
- 安全：`GITHUB_TOKEN` 仅在正式手工发布时用于 GHCR/GitHub Release；不读取 TikHub/LLM Secret；日志不得输出任何真实外部 Secret。

# 交付

- Branch：`feature/github-release-workflow`
- PR：待创建 Draft PR 并取得 Red/Green/Review/CI 证据。
- 发布：本 Change 只建立发布能力；实现验证阶段不会创建正式业务版本 Tag/Release，首次正式版本由用户在合并到默认分支后从 Actions 手工触发。

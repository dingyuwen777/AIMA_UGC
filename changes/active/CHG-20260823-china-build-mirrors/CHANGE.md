---
schema: rvc-change/v1
id: CHG-20260823-china-build-mirrors
title: Docker 构建国内源加速与可追溯回退
level: L3
status: ready_for_review
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
affected_paths:
  - Dockerfile
  - compose.yaml
  - env.production.example
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 最终设计结论

中国网络环境下的 Internal V1 / 本地完整 Docker build 默认使用可审计、可覆盖的国内下载源，但不修改应用业务 Runtime、持久化、Secret、Schema、Contract 或未来不可变 Production Release 设计。

```text
Docker Hub / GHCR 镜像
→ DaoCloud public image mirror 前缀代理

Debian / Debian Security
→ TUNA

Python 第三方依赖
→ uv.lock 冻结导出 exact version/hash
→ uv pip sync --require-hashes
→ TUNA PyPI
→ 当前 AIMA 源码单独 build/install wheel

npm
→ npmmirror
```

Dockerfile 不再声明外部 `docker/dockerfile:1` syntax frontend，因为当前文件只使用稳定基础语法；这直接消除首次 build 的一项额外公网镜像下载。

所有基础镜像/软件包源都有显式环境变量入口，可切回原官方源；镜像/依赖版本未升级，不使用 `latest`。

# 可观察成功标准

- [x] Python/uv/Node/Nginx 基础镜像默认通过国内镜像代理拉取，并保留原锁定版本。
- [x] PostgreSQL 18.4 默认通过同一国内镜像代理拉取。
- [x] Dockerfile 外部 syntax frontend 下载已移除。
- [x] Backend apt 默认使用 TUNA；Python 依赖从 `uv.lock` 冻结导出后通过 TUNA + hash 校验安装；Frontend npm 默认使用 npmmirror。
- [x] `uv.lock`、`package-lock.json`、Python/Node/nginx/PostgreSQL/uv 版本未因镜像加速修改。
- [x] 国内源参数只影响 build/pull，不进入 AIMA API/Worker/Scheduler 的业务 Runtime Contract。
- [x] 普通 `docker compose ... up --build` 只在当前 Docker Engine build/tag，不包含 `push`，不发布 AIMA 自有镜像。
- [x] Windows Docker Desktop storage override、Linux/服务器 `AIMA_HOST_ROOT`、Secret、Migration、端口和持久化语义保持不变。
- [x] 文档明确首次 build、国内源、官方回退、缓存、本地 image/tag 与项目级破坏性 reset。
- [x] pre-ready 永久 CI 已证明默认国内源完整 build/runtime；Completion Audit 与两阶段 Review 已完成。最终 Ready HEAD 的 Completion Gate/永久 CI 继续作为合并硬门禁。

# 范围

- Docker build/pull 的来源选择与默认值。
- Debian apt、uv/PyPI、npm 的构建期下载源。
- `env.production.example` 的构建源配置与官方回退示例。
- Windows 本地 Docker 项目级重置与构建排障文档。

# 非目标

- 不修改 Docker Desktop 全局 daemon / registry-mirrors，不影响其他项目。
- 不执行或新增 `docker push` / `buildx --push` / 公网 Registry 发布流程。
- 不升级 Python/Node/nginx/PostgreSQL/uv/npm/Python/Frontend 依赖版本。
- 不实现 Stage 11 完整不可变 Release、digest Manifest、SBOM/签名或私有 Registry。
- 不改变 Windows named-volume 与 Linux/Production bind-mount 持久化模型。
- 不修改数据库 Schema、Migration、公共 Contract 或业务语义。

# 必须保持不变

1. 精确版本继续由 Dockerfile/锁文件控制，不使用 `latest`。
2. AIMA backend/frontend image 只在当前 Docker Engine 本地 build/tag，除非未来独立 Release Change 明确发布。
3. Production Server 最终仍使用已验证不可变镜像 + `--no-build --pull never`；当前 Internal V1 现场 build 只是阶段性能力。
4. PostgreSQL/Artifact/log/internal Secret 的持久化与恢复语义不变。
5. Secret 不进入镜像、Git、构建日志或业务容器普通环境变量。

# 已确认关键决策

1. 用户明确要求：中国网络环境下下载镜像或在镜像内安装软件时优先使用国内源，并授权修改代码、正常合并到 `main`。
2. 用户明确允许删除本机 AIMA 镜像、容器和卷，从空状态重新开始。
3. 不把 Docker Desktop 全局 daemon 配置作为仓库副作用；仓库通过显式镜像 URL/build args 实现加速。
4. Docker Hub/GHCR 镜像使用 DaoCloud public image mirror 前缀映射；Debian/PyPI/npm 使用仓库已有 Windows 工具链同类的 TUNA/npmmirror。
5. `uv.lock` 不改成镜像专属 source。直接修改 `UV_DEFAULT_INDEX` 会让 `uv sync --locked` 判断 lock 需要更新；最终采用 `uv export --frozen` + `uv pip sync --require-hashes` 兼顾国内下载和锁文件完整性。
6. BuildKit cache 默认保留；项目级 reset 删除 AIMA 容器/volume/service image，不用 `docker system prune -a --volumes` 误删其他项目。

# L3 方案比较

## 方案 A：手工修改 Docker Desktop 全局 registry mirror

只能部分解决 Docker Hub，且会影响其他项目，也不能统一 GHCR、apt、PyPI、npm。拒绝作为仓库默认。

## 方案 B：硬编码不可覆盖的第三方镜像

无官方回退，海外/未来 Release 环境会被第三方镜像锁死。拒绝。

## 方案 C：国内默认 + 显式构建源参数 + 官方回退（采用）

满足中国网络默认可用性，同时保留版本锁定、配置可审计和跨区域回退。第三方 Python 依赖继续由 `uv.lock` exact version/hash 约束。

# 兼容、Migration、部署与回滚

- API / Schema / Migration / Data：无变化。
- 依赖版本：无升级；`uv.lock`、`package-lock.json` 不变。
- 运行兼容：现有 Linux Compose、Windows CMD/PowerShell wrapper、服务、端口、volume、Secret 均不变。
- 构建兼容：新增 `AIMA_BUILD_*` 与 `AIMA_POSTGRES_IMAGE`；`env.production.example` 默认国内值并列出原官方值。
- 回滚：恢复旧 Dockerfile/Compose/env build-source 配置即可；持久数据不需迁移/回滚。
- 本地破坏性重置（用户已授权丢弃当前本地 AIMA 数据）：Windows 使用 `compose_windows.ps1/cmd down -v --remove-orphans --rmi all`；不默认清全局 BuildKit cache。

# 安全、供应链与运维风险

- 国内公共镜像/包镜像是第三方网络依赖；基础镜像版本保持明确，DaoCloud 代理在实际 CI 中解析到与源相同的镜像 digest；Python package 额外执行 lock hash 校验，npm 继续使用 lock integrity，Debian 仓库继续由 Debian archive key 验证。
- TUNA 明确提醒 Debian Security 镜像可能存在同步延迟。当前 Internal V1 默认使用国内 security mirror 以保证中国网络可构建；完整 Production Release 仍需漏洞/镜像完整性门禁，并可按正式安全策略把 security mirror 切回 Debian 官方源。
- `down -v` 会删除本地 PostgreSQL/Artifact/log/internal Secret，只因本轮用户明确允许本地从空状态重建才作为可执行 reset。
- `docker system prune -a --volumes` 影响其他项目，文档明确禁止作为 AIMA 默认重置。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 下载基础镜像与镜像内安装软件优先使用国内源 | user:china-build-mirrors | satisfied | `Dockerfile`/`compose.yaml`/`env.production.example`；Internal V1-A run `32638629904` 和 Windows Runtime run `32638630015` 均以默认国内源完成真实 build/runtime |
| R2 | 不把 AIMA 镜像发布到公网 | user:no-public-image-publish | satisfied | `compose.yaml`/Dockerfile 无 push；PR diff 未新增 Registry publish；`docs/guides/04_Docker国内构建源与本地重置.md` 明确本地 tag 语义 |
| R3 | 不牺牲产品上线规范和未来不可变 Production Release | `docs/roadmap/02_生产上线实施路线.md` | satisfied | Runtime/持久化/Release 文档未被改写；构建源只作为 build args，Guide 04 明确 Stage 11 仍为 digest/Manifest/SBOM + `--no-build --pull never` |
| R4 | Windows CMD/PowerShell 与 Linux/服务器 Compose 继续可用 | `docs/02_环境运行与部署.md` | satisfied | Windows run `32638630015` 两个 job success；Internal V1-A run `32638629904` absolute + repo-relative Linux Golden Path success |
| R5 | 本地 AIMA Docker 状态可安全清空重新开始，不误删其他项目 | user:local-reset | satisfied | Guide 03/04 固化 project-level `down -v --remove-orphans --rmi all`，并明确不使用全局 `docker system prune -a --volumes` |
| R6 | L3 Completion Audit、两阶段 Review、Ready Check/CI 门禁 | `AGENTS.md` | satisfied | 本 Change 已完成 Completion Audit、Requirement Review 与 Code Quality Review；pre-ready permanent CI 除预期的 in_progress Completion Gate 外全部 success，最终 Ready HEAD Gate/CI 继续作为合并硬门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面或用户业务交互 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A run `32638629904`：真实 PostgreSQL、Migration、API readiness、Secret、持久化/fail-closed lifecycle success |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract/generated client；总 CI run `32638629897` generated drift 等回归 success |
| Real Full-stack Golden Path | required | Stage 8F run `32638629912` success；Internal V1-A 与 Windows merged Runtime 真实启动成功 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 请求行为，不需要付费 Probe |
| Docs / Governance / Other | required | Windows launcher + named-volume run `32638630015` success；Guide 03/04 与 env template 同步；最终 Completion Gate 待 Ready HEAD 复核 |

# Completion Audit

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [x] unresolved_cleared

## Completion Audit 证据

### upstream_re_read

Ready 前重新读取当前 `main` 的 `AGENTS.md`、Reliable Vibe Coding Skill、Blueprint README/07、Roadmap、Blueprint 05 和 Production Release Appendix，并结合本轮用户明确的国内源、不得公网发布、自本机可破坏性重置要求独立重建完成定义。

### change_coverage

上游要求均映射到 Dockerfile/Compose/env template、Windows Guide/新增 Build Guide 和永久 CI。没有 Schema/Contract/Migration/业务行为变化，因此不制造额外数据库或前后端改动。

### reverse_audit

- `compose.yaml` 只有 build args/PostgreSQL image source 变化；业务 environment、depends_on、health、Secret、port、volume target 不变。
- `compose.windows.yaml` 未修改，证明 Windows storage-only 设计没有分叉。
- `uv.lock`/`package-lock.json` 未修改；Python 国内安装使用 frozen export + exact hashes，而不是重锁到镜像站。
- Dockerfile 无 `push`；Compose `up --build` 仍仅本地 build/tag/start。
- Linux Internal V1-A、Windows named-volume Runtime、总 CI、Stage 8F 均重新通过。
- 本地 reset 命令限定 Compose project；全局 prune 明确不作为默认方案。

### unresolved_cleared

R1-R6 无 `not_satisfied`。官方源回退使用改动前同一官方镜像/仓库值，通过可覆盖 Compose build args 暴露；本轮真实完整 Runtime 重点验证国内默认路径。具体用户本机带宽仍需其 Windows Docker Desktop 首次 smoke，CI 不承诺固定下载速度。

# 两阶段 Review

## Requirement Review A1：上游要求 → Change

通过。未发现遗漏：国内镜像/镜像内包源、无公网 push、现有 Windows/Linux/Production 边界、版本锁定、本地可重置和 L3 交付门禁均已进入 Traceability。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。默认国内源已被真实 Compose build 使用；初版直接改 `UV_DEFAULT_INDEX` 导致 `uv sync --locked` 正确失败后已修为 frozen export + hash sync；第二个 uv 0.12.3 CLI 兼容问题也由 CI 暴露并修复。最终 pre-ready Runtime 证据成功。

## Code Quality Review

通过，无 Serious/Important finding：

- 没有依赖版本升级、Schema/Contract/业务行为变化；
- build-source 参数集中在 Compose/env，不进入业务 Runtime；
- 国内 PyPI 不通过改写 `uv.lock` 实现；
- project wheel 与第三方依赖分开安装，第三方继续 hash 验证；
- 不修改 Docker daemon 全局状态；
- reset 不默认删除其他项目资源；
- Production Release 的不可变镜像/完整性/恢复门禁没有被本地加速方案降低。

# Git / 交付

- branch: `feature/china-build-mirrors`
- Draft PR: #175
- pre-ready validated head: `4e099657f2e0b9bd668fe205fc956ebb27602808`
- archive: 实现 PR 正常合并后独立归档

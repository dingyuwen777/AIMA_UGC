---
schema: rvc-change/v1
id: CHG-20260824-github-release-workflow
title: GitHub 一键离线 Release Workflow
level: L3
status: done
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

在不改变本地 Windows/Linux/公司服务器现有 Docker 构建默认源和业务 Runtime 的前提下，新增可从 GitHub Actions 手工触发的一键 Release Workflow：输入正式 SemVer 版本后，从当前 `main` 固定 SHA 构建 Linux/AMD64 Backend/Frontend 候选镜像；候选先生成离线 Bundle 并完成 no-build/no-pull 回放验证，正式 `workflow_dispatch` 再把这组已验证应用镜像发布到 GHCR、记录 digest、创建 Git Tag 与 GitHub Release。

# 成功标准

- [x] `.github/workflows/release.yml` 提供 `workflow_dispatch` + `version` 输入，正式路径拒绝非 `main`、非法 SemVer、重复 Tag/Release、非最新 `main` SHA 或关键 `main` CI 门禁不绿的请求。
- [x] GitHub Hosted Linux Runner 显式使用 Docker Hub canonical image、Debian 官方源、PyPI 官方源和 npm 官方源；仓库现有 `Dockerfile`、`compose.yaml`、`env.production.example` 的本地国内默认下载源保持不变。
- [x] Backend/Frontend 只构建一次 Linux/AMD64 候选；正式发布阶段复用已经离线回放验证的同一候选镜像，推送 GHCR 版本/SHA tag 并记录 repo digest；PostgreSQL 固定 `postgres:18.4` 并记录官方 repo digest。
- [x] Release 资产设计包含 `AIMA_UGC-vX.Y.Z-deploy.tar.gz`、`release-manifest.json`、`migration-manifest.json`、`SHA256SUMS`；Bundle 内含 `images.tar`、canonical `compose.yaml`、版本化 `env.production.example`、两个 manifest、`SHA256SUMS`、`DEPLOY.md`。
- [x] PR Release dry-run 已在 GitHub Hosted Linux Runner 实际执行：删除候选运行镜像 → `docker load -i images.tar` → canonical Compose `--no-build --pull never --wait` → bootstrap/migrate/configure/API/Worker/Scheduler/Frontend readiness 成功。
- [x] Bundle 构建路径不读取真实 TikHub/LLM Secret，不包含 PostgreSQL 数据、Artifact、日志、真实 `env.production` 或内部/外部 Secret；`${AIMA_HOST_ROOT}` 持久状态与 Release 生命周期分离。
- [x] 文档明确当前能力是“一键不可变离线 Release 基础”，并继续把协调 Backup/Restore、认证/HTTPS、SBOM/独立来源签名、服务器侧完整发布/回滚与 Production Go-Live 列为后续能力。

# 范围

- 新增 `.github/workflows/release.yml`：PR 路径变更执行无写权限 dry-run；默认分支 `workflow_dispatch` 执行正式发布。
- 复用根 `Dockerfile`、canonical `compose.yaml`、`AIMA_HOST_ROOT`、bootstrap/migrate/configure/health，不复制第二套 Production Runtime。
- Release Runner 只通过 Docker build args 覆盖 Debian/PyPI/npm 为官方上游；Docker 基础镜像和 PostgreSQL 使用仓库锁定的 Docker Hub canonical reference。
- 正式发布 GHCR Backend/Frontend 版本/SHA tag；生成离线 Bundle、manifest、SHA256 与部署说明。
- 增加静态/语义回归测试，并同步环境运行、Roadmap、Production Release Appendix。

# 非目标

- 不新增 `compose.production.yaml`；没有独立生产语义时继续复用 canonical `compose.yaml`。
- 不实现企业认证/Authorization、HTTPS/HSTS/CSP、正式公网入口或生产资源限额。
- 不实现 PostgreSQL + Artifact 协调 Backup/Restore、数据库自动回滚、RPO/RTO。
- 不在本 Change 引入 SBOM 生成器、第三方签名工具或新项目依赖；当前 `SHA256SUMS` 仅证明文件完整性，不冒充独立来源签名。
- 不修改 Windows `compose.windows.yaml` 的业务语义；Windows storage adapter 不进入服务器 Release Bundle。
- 不自动发起真实 TikHub/LLM 请求，不使用 Provider Secret 做 Release 验证。
- 本 Change 不自动创建一个真实业务版本号的 GitHub Release；首次正式版本由用户在 Implementation PR 合并并确认 `main` 门禁后手工触发。

# 必须保持不变

- Python/Node/Nginx/PostgreSQL 与依赖锁定版本不升级、不降级。
- `Dockerfile` / `compose.yaml` / `env.production.example` 的国内默认 Debian/PyPI/npm 下载源保持；Release 官方上游只存在于 Workflow build args。
- Linux/WSL/公司服务器继续使用 canonical `compose.yaml`；Windows Docker Desktop 继续使用 `compose.yaml + compose.windows.yaml`。
- `${AIMA_HOST_ROOT}/postgres`、`${AIMA_HOST_ROOT}/runtime/data`、`${AIMA_HOST_ROOT}/runtime/logs`、`${AIMA_HOST_ROOT}/shared/secrets` 不进入 Release Bundle，也不被 Workflow 清理。
- Migration 继续由独立 `migrate` service 执行；API/Worker/Scheduler 不隐式修改 Schema。
- 不新增 Python/npm 运行依赖，不修改业务 HTTP Contract、PostgreSQL Schema/Migration 或数据语义。

# 方案比较与关键决策

## 方案 A：canonical Compose + GHCR + GitHub Release 离线 Bundle（采用）

Build/verify job 只拿只读权限，构建 Backend/Frontend + 拉 `postgres:18.4`，生成 Bundle，删除候选 tag 后从 `images.tar` 重放，并以 `--no-build --pull never` 验证。只有正式 `workflow_dispatch` 的 publish job 拿 `contents: write` / `packages: write`，下载同一已验证候选并发布 GHCR/Tag/Release。

优点：服务器可真正离线运行；PR 不具备仓库/Package 写权限；正式发布不重新构建另一份镜像；canonical Runtime 不复制。

代价：当前仍没有协调 Backup/Restore、SBOM、独立签名/provenance 和完整服务器发布/回滚自动化。

## 方案 B：只生成 GitHub Release Bundle，不发布 GHCR（不采用）

权限和流程更少，但缺少独立 Registry digest/镜像获取路径，与用户要求的 Original 一键发布效果和长期不可变镜像审计目标不一致。

## 方案 C：本次直接完成完整 Stage 11A—11E（不采用）

会把 HTTPS/认证、Backup/Restore、服务器发布/回滚、SBOM/签名和生产验收耦合到一次 Workflow Change，扩大范围并引入尚未决策的生产语义。

已确认上游决定：用户 2026-08-24 要求开始 GitHub Release Workflow，并明确 GitHub Release 构建环境显式使用 Docker Hub / Debian / PyPI / npm 官方上游；该覆盖不得改变本地默认构建源。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Actions 手工输入版本后可一键校验 main、发布已验证镜像、打 Tag 并创建可下载 GitHub Release | user:2026-08-24-github-release-workflow | satisfied | `.github/workflows/release.yml` 已实现 `workflow_dispatch`、`publish-release`、GHCR digest、`gh release create --target "$RELEASE_SHA"`；首次真实业务版本按非目标留给合并后人工触发，不用测试版本污染正式 Release 历史。 |
| R2 | Release Runner 显式使用 Docker Hub / Debian / PyPI / npm 官方上游且不影响本地国内默认源 | user:2026-08-24-official-release-upstreams | satisfied | `tests/unit/test_docker_build_sources.py` 静态门禁；最终 Release dry-run `32705187995` 成功执行官方上游构建；本 Change 未修改本地三处默认源。 |
| R3 | Release 面向 Linux/AMD64，服务器使用 `images.tar` + `--no-build --pull never`，不现场构建/拉镜像 | docs/roadmap/02_生产上线实施路线.md | satisfied | 最终 Release dry-run `32705187995` 实际 build linux/amd64、保存并删除候选镜像、重新 load，canonical Compose no-build/no-pull 全栈 readiness 成功。 |
| R4 | Release Bundle 与 PostgreSQL/Artifact/log/Secret 持久状态分离，`AIMA_HOST_ROOT` 不随版本切换 | docs/appendix/11_生产部署与离线Release方案.md | satisfied | Workflow Bundle 白名单仅 7 项；`images.tar` 只有 Backend/Frontend/PostgreSQL 镜像；smoke 使用独立临时 Host Root；正式文档保持 `/data/AIMA_UGC` 为 Release 外持久根。 |
| R5 | 不把未完成 Backup/Restore、认证/HTTPS、SBOM/独立签名或完整 Production Go-Live 写成已完成 | docs/appendix/11_生产部署与离线Release方案.md | satisfied | Roadmap/Appendix/环境文档均把这些能力保留为后续 Production 强化；manifest 也显式标记 SBOM、独立签名与协调 Backup/Restore 当前未实现。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改产品页面或用户业务交互；GitHub Actions `workflow_dispatch` 不是产品 Browser E2E。 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端业务规则、HTTP API、Repository、Schema；PostgreSQL Runtime 作为 Release Full-stack Golden Path 的真实组件验证。 |
| Contract / Generated Client | not_applicable | 不修改 Pydantic/OpenAPI/generated client。 |
| Real Full-stack Golden Path | required | 最终 GitHub Actions run `32705187995`：官方上游 build → `images.tar` → 删除候选镜像 → load → canonical Compose `--no-build --pull never --wait` → bootstrap/migrate/configure/API/Worker/Scheduler/Frontend healthy。 |
| Real Provider Probe | not_applicable | 不改变 TikHub/LLM endpoint/Mapper/Transport；Release 验证明确禁用真实付费 Provider。 |
| Docs / Governance / Other | required | Red/Green 静态测试、最终 Release dry-run、CI、Internal V1-A、Windows Compatibility、Completion Gate 与 Production Release 文档同步共同覆盖。 |

# Completion Audit

- [x] upstream_re_read：完成前重新读取当前分支 `AGENTS.md`、Skill、Blueprint README/07、Roadmap、Production Release Appendix、canonical Compose 和 Release Workflow，未以当前 Change 自身反推需求。
- [x] change_coverage：上游要求已覆盖手工正式发布、官方上游隔离、本地默认源不变、不可变候选、GHCR digest、离线 Bundle/no-pull、持久状态分离和 Production 未完成边界。
- [x] reverse_audit：从 Bundle 反查 canonical Compose 所需 Backend/Frontend/PostgreSQL tag 和 env；从正式 publish 反查其镜像来自已回放候选；PR dry-run 无写权限；Validation Matrix 证明范围与实际边界一致。
- [x] unresolved_cleared：R1—R5 均为 `satisfied`；没有范围内 `not_satisfied`；非目标均有用户目标或 Roadmap/Appendix 边界依据。

# 任务

- [x] 调查当前 AGENTS/Skill、Roadmap、Production Appendix、Dockerfile、Compose、CI 与 Original Release Workflow。
- [x] 建立 Release Workflow 失败测试并取得真实 Red 证据。
- [x] 建立 Validation Matrix 和 L3 方案比较。
- [x] 实现最小 Release Workflow，并把 PR dry-run 与正式 publish 权限拆开。
- [x] 同步环境部署、Roadmap 与 Release Appendix。
- [x] 取得 Release dry-run/no-pull、目标测试、相关 CI 和 Completion Gate 的最终 PR HEAD 新鲜证据。
- [x] 完成 Requirement Traceability、Completion Audit 和两阶段人工 Review。
- [x] Implementation PR #201 正常合并到 `main`。

# 验证

## Red

提交 `ea37b99f1136d3665c31fb6f12d84f721319e4f3`（`添加 Release 最小权限失败测试`）在 CI run `32698875945` / Stage 1 job `97346209910` 得到预期失败：

```text
FAILED tests/unit/test_docker_build_sources.py::test_release_pull_request_dry_run_has_no_repository_write_token
1 failed, 617 passed, 1 warning
```

根因是当时 Release Workflow 顶层仍拥有 `contents: write` / `packages: write`，PR dry-run 权限过大；失败与新增安全要求直接对应。

## Green / 实现修正

提交 `f42c1720a5c8d7ac9917db72fbbfca4b8ba1dd32`（`隔离 Release 发布权限并复用已验证镜像`）把只读 build/replay 与写权限 publish 拆成两个 job；正式 publish 只消费已完成离线回放的候选，不重新 build。

后续 HEAD 又针对 `main` 中 `env.production.example` 已提供 LLM Base URL/Provider/Model 默认值这一事实，修正 Release smoke：在无真实 API Key 的 dry-run 中显式移除三项 LLM Runtime 配置，保证 CI 不把 Provider 默认值误判成启用 LLM；同时把环境文档、Roadmap、Production Release Appendix 的发布顺序统一为“候选离线回放通过后再执行正式 GHCR/Tag/Release 发布”。

## 最终 Implementation PR HEAD 新鲜 Runner 证据

最终 HEAD：`7c589475323393ad1ec1024f10b5940359a710aa`。

全部完成且结论为 `success`：

- Release dry-run：`32705187995`
- CI：`32705188027`
- Internal V1-A Deployable Stack：`32705188073`
- Windows Docker Desktop Compose Compatibility：`32705188018`
- Change Completion Gate：`32705188009`
- Stage 8F Full-stack Acceptance：`32705188048`
- Stage 6 Xiaohongshu Vertical Slice：`32705188117`
- Stage 7 Keyword Packs：`32705188058`
- Stage 7 Plan Occurrence Run Snapshot：`32705188038`
- Stage 7 Scheduler Runtime：`32705188010`
- Stage 7 Provider Config Routing：`32705188023`
- Local Dev Bootstrap：`32705188194`

Release dry-run 的 `Build and replay offline candidate` job 成功完成官方海外上游 build、`postgres:18.4`、Bundle/checksum、删除候选镜像、`docker load`、`--no-build --pull never --wait`、bootstrap/migrate/configure/API/Worker/Scheduler/Frontend readiness 和候选压缩包校验。PR 模式 publish job 按设计 skipped，没有产生 GHCR/Tag/Release 写副作用。

独立 PR #203 已修复 `main` 上 Docker mirror 列表扩展后 Windows CI Fixture 的旧回归，并已合并；本 Change 最终 HEAD 的 Windows Compatibility 已重新通过。

# 两阶段 Review

## Review A1：上游要求 → Change

重新从用户明确决定、Roadmap Stage 11 当前边界和 Production Release Appendix 独立重建要求，确认没有遗漏：一键手工版本发布、main/版本门禁、海外官方源隔离、本地默认源保持、Linux/AMD64、离线 Bundle、no-build/no-pull 回放、GHCR digest、数据/Secret 不入 Bundle、完整 Production 未完成项继续保留。

## Review A2：Change → 实现 / 测试 / 文档

逐项反查 `.github/workflows/release.yml`、静态测试和三个正式文档；PR 模式不获得写权限，正式 publish 复用回放候选；Bundle/manifest 与 canonical Compose tag、Host Root、Alembic head/OpenAPI hash 对齐；没有业务 Contract/Schema/Migration/依赖变化。

## 代码质量 / 风险 Review

- 正确性：正式 publish 开始和 GHCR/Release 创建前均重新校验 `main` 最新 SHA、Tag/Release 不重复；避免构建期间 `main` 前进后发布旧候选。
- 权限：PR/build job 只有 read/check 权限；`contents: write` / `packages: write` 只位于 `workflow_dispatch` publish job。
- 供应链：版本/tag 固定，无 `latest`；PostgreSQL repo digest、应用 GHCR digest 进入 manifest；SBOM/独立签名未伪装完成。
- 数据安全：无 `down -v`；Bundle 白名单排除生产数据/Secret；Release 与 `${AIMA_HOST_ROOT}` 解耦。
- 兼容性：没有修改本地 Compose 命令、国内构建默认源、Windows storage adapter、业务接口、Schema 或依赖。
- 剩余边界：PR 无法也不应执行正式 GHCR/Tag/GitHub Release 写副作用；首次真实业务版本需在合并后的 `main` 由用户手工触发并观察结果。

# 文档影响

- `docs/02_环境运行与部署.md`：增加 Actions 手工 Release、官方海外上游隔离、Bundle 下载/服务器离线启动和 Host Root 数据分离说明，并对齐“先回放候选、后正式发布”的实际顺序。
- `docs/roadmap/02_生产上线实施路线.md`：记录 GitHub Release Workflow 基础部分完成，不提前宣称 Stage 11/Production Go-Live 闭环，并对齐实际发布顺序。
- `docs/appendix/11_生产部署与离线Release方案.md`：记录 Workflow、Bundle、GHCR/digest、no-build/no-pull、当前未包含 SBOM/签名/协调恢复等机器事实，并对齐实际发布顺序。

# 兼容、部署与回滚

- 兼容：无业务 API/Schema/数据格式变化；本地 Windows/Linux/Internal V1 命令不变。
- Migration：不新增 Migration；manifest 记录当前单 Alembic head；部署仍由现有 `migrate` service 执行 `alembic upgrade head`。
- 部署：Release 只携带镜像与部署元数据，不触碰目标服务器 `${AIMA_HOST_ROOT}` 既有 PostgreSQL/Artifact/log/Secret。
- 回滚：Workflow 代码可整体回退；已存在 Tag/Release 不允许覆盖。应用版本回滚仍受对应 Migration 兼容性和后续 Coordinated Backup/Restore 能力约束，本 Change 不制造自动数据库回滚。
- 安全：正式 `env.production`、TikHub/LLM API Key 不进入 Workflow 资产；PR dry-run 没有仓库/Package 写 token。

# Git / 交付状态

- 实现分支：`feature/github-release-workflow`
- Implementation PR：#201 `新增 GitHub 一键离线 Release Workflow`
- Implementation PR 最终 HEAD：`7c589475323393ad1ec1024f10b5940359a710aa`
- Implementation merge：`db749e354b1cf216be9d670a142b825d34e72757`，已正常合并到 `main`。
- 归档分支：`archive/github-release-workflow`，从 Implementation merge 创建，只移动/更新本 Change 记录，不修改业务实现。
- 正式业务版本 Release：未触发；按已确认非目标，合并后由用户在 `Actions → Release → Run workflow` 输入正式 `vMAJOR.MINOR.PATCH`，避免以测试版本污染 Tag/GHCR/Release 历史。

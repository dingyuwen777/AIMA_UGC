---
schema: rvc-change/v1
id: CHG-20260823-china-build-mirrors
title: Docker 构建国内源加速与可追溯回退
level: L3
status: done
owner: chatgpt
branch: archive/china-build-mirrors
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

# 完成结论

AIMA_UGC 的本地完整 Docker / Internal V1 构建已默认接入可覆盖的国内下载源，并保持应用 Runtime、数据、Secret、Schema、Contract 和完整 Production Release 方向不变。

```text
Docker Hub / GHCR 基础镜像
→ DaoCloud public image mirror 前缀代理

Debian / Debian Security
→ TUNA

Python 第三方依赖
→ uv.lock frozen export
→ exact version/hash
→ uv pip sync --require-hashes
→ TUNA PyPI

npm
→ npmmirror
```

Dockerfile 不再声明不必要的 `docker/dockerfile:1` 外部 syntax frontend，因此首次 build 不再额外下载该镜像。

# 关键不变量

- Python 3.14.7、uv 0.12.3、Node 24.19.0、Nginx 1.30.4、PostgreSQL 18.4 等既有版本未升级。
- `uv.lock` 与 `package-lock.json` 未改成国内镜像专属锁文件。
- 国内源只控制 build/pull；API/Worker/Scheduler 业务 Runtime Contract 不读取这些配置。
- Windows named-volume 与 Linux/Production `AIMA_HOST_ROOT` bind-mount 模型不变。
- 当前仓库没有 `docker push`、`buildx --push` 或 AIMA Registry publish；本地 `docker compose ... up --build` 只 build/tag/start 当前 Docker Engine。
- 完整 Production 仍要求可信构建、固定 digest/Manifest/SBOM/来源验证、服务器 `docker load` 后 `--no-build --pull never`。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 下载基础镜像及镜像内软件优先国内源 | user:china-build-mirrors | satisfied | `Dockerfile`、`compose.yaml`、`env.production.example`；最终 Internal V1-A run `32639114288` 与 Windows Runtime run `32639114283` success |
| R2 | AIMA 自有镜像不发布公网 | user:no-public-image-publish | satisfied | Dockerfile/Compose 无 push；PR #175 未新增 Registry publish；Guide 04 说明本地 tag 语义 |
| R3 | 保持后续产品上线和不可变 Production Release 规范 | `docs/roadmap/02_生产上线实施路线.md` | satisfied | 构建源仅作为 build 输入；Runtime/持久化/Release 边界保持 |
| R4 | Windows CMD/PowerShell、Linux/服务器 Compose 均保持可用 | `docs/02_环境运行与部署.md` | satisfied | 最终 Windows run `32639114283`、Internal V1-A run `32639114288` 均 success |
| R5 | 本地 AIMA Docker 状态可安全清空重建，不误删其他项目 | user:local-reset | satisfied | Guide 03/04 固化 `down -v --remove-orphans --rmi all`，明确不默认执行全局 system prune |
| R6 | L3 Completion Audit、两阶段 Review、Ready Gate 和永久 CI | `AGENTS.md` | satisfied | 最终 Ready HEAD `27c8edf9284f0447781a32268426bf22ba49db73` 的 11 个永久工作流全部 success，PR #175 正常合并 |

# Validation Matrix

| Layer | Required | Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改页面/用户业务交互 |
| Backend/API/PostgreSQL Integration | required | Internal V1-A run `32639114288` success |
| Contract / Generated Client | not_applicable | 不修改 Contract；总 CI run `32639114290` success |
| Real Full-stack Golden Path | required | Stage 8F run `32639114249` success；Linux/Windows Compose Runtime success |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM 请求行为 |
| Docs / Governance / Other | required | Completion Gate run `32639114278` success；Windows launchers/runtime run `32639114283` success |

# Completion Audit

- [x] upstream_re_read: Ready 前与实现合并后均重新读取 `AGENTS.md` 及部署/Release 上游事实。
- [x] change_coverage: 用户国内源、不公网发布、本地重置和 Production 不变项均已覆盖。
- [x] reverse_audit: 已反向核对 Dockerfile/Compose、lockfile、Windows/Linux storage、Secret、push 与 reset 边界。
- [x] unresolved_cleared: 无 `not_satisfied`；具体用户本机下载带宽仍需本机 smoke，不由 CI 承诺固定速度。

# 两阶段 Review

- Requirement Review A1：通过，无 requirement omission。
- Requirement Review A2：通过，默认国内源已由真实 Compose build/runtime 证明。
- Code Quality Review：通过，无 Serious/Important finding；没有依赖升级、Schema/Contract 变化或全局 Docker daemon 副作用。

# 验证证据

最终 Ready HEAD：

```text
27c8edf9284f0447781a32268426bf22ba49db73
```

永久工作流全部 success：

```text
Change Completion Gate                    32639114278
CI                                        32639114290
Internal V1-A Deployable Stack            32639114288
Windows Docker Desktop Compatibility      32639114283
Stage 8F Full-stack Acceptance             32639114249
Stage 6 Xiaohongshu Vertical Slice         32639114274
Stage 7 Keyword Packs                      32639114256
Stage 7 Scheduler Runtime                  32639114294
Stage 7 Plan Occurrence Run Snapshot       32639114250
Stage 7 Provider Config Routing            32639114305
Local Dev Bootstrap                        32639114262
```

# Git / 交付

- implementation branch: `feature/china-build-mirrors`
- implementation PR: #175
- implementation merge: `062cda1574cfe1ac93b40b4c543ef246f9f4dd40`
- archive branch: `archive/china-build-mirrors`
- archive PR: 本归档分支对应 PR

# 本地重置边界

用户已明确允许本机 AIMA 数据从空状态重建。Windows 项目级重置：

```powershell
.\scripts\dev\compose_windows.ps1 down -v --remove-orphans --rmi all
```

或：

```cmd
scripts\dev\compose_windows.cmd down -v --remove-orphans --rmi all
```

保留 BuildKit cache 是默认推荐；不使用 `docker system prune -a --volumes` 作为项目级重置，因为它可能删除其他 Docker 项目资源。

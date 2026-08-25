---
schema: rvc-change/v1
id: CHG-20260824-stop-local-backend-postgres
title: 本地 Backend 退出时停止 PostgreSQL 容器
level: L2
status: done
owner: chatgpt
branch: feature/local-backend-stop-postgres
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - local-development
  - developer-experience
  - ci
affected_paths:
  - scripts/dev/backend.py
  - scripts/dev/local_runtime.py
  - .github/workflows/local-dev-bootstrap.yml
  - docs/02_环境运行与部署.md
  - tests/unit/test_local_dev_runtime.py
contracts: []
data_changes: []
---

# 目标

当 `uv run python scripts/dev/backend.py` 的正常本地后端运行结束时，除 API / Worker / Scheduler 子进程外，也停止该 launcher 管理的 `aima-ugc-postgres-dev` Docker 容器，并在控制台明确输出 Docker 容器停止结果。

停止容器不删除 `aima-ugc-postgres-dev-data` named volume，不删除 `.runtime/`、Secret 或业务数据。下一次启动继续复用同一容器与 volume。

隐藏的 `--prepare-only` 保持现有语义：只准备本地后端依赖并保留 PostgreSQL 运行，供 CI/后续调试步骤继续连接。

# 可观察成功标准

- [x] Ctrl+C 结束正常 Backend 时停止 API / Worker / Scheduler，并停止 `aima-ugc-postgres-dev`。
- [x] SIGTERM 或 Backend 主运行阶段异常退出时同样进入 PostgreSQL 容器清理 `finally`。
- [x] 控制台明确输出 PostgreSQL Docker 容器已停止；若容器本来已停止/不存在则输出准确状态，不虚报成功。
- [x] PostgreSQL named volume 不删除，下一次 `backend.py` 可自动重新启动并复用原数据。
- [x] `--prepare-only` 不停止 PostgreSQL，保持现有 CI/调试行为。
- [x] Linux/Windows 共用同一生命周期实现；不新增额外启动/停止命令。
- [x] Local Dev Bootstrap 永久 CI 增加真实 Backend 退出后容器停止 smoke，并继续通过现有数据库准备/重置测试。
- [x] `docs/02_环境运行与部署.md` 描述最新停止语义，不记录实现过程。

# 范围

- 本地源码 Backend launcher 的退出清理。
- PostgreSQL 本地开发容器的安全 stop helper。
- 本地开发 CI 生命周期 smoke。
- 本地运行文档。

# 非目标

- 不删除 PostgreSQL container 或 named volume。
- 不执行 `docker compose down`；源码开发使用的是独立的 `aima-ugc-postgres-dev` 容器，不是完整 Compose Runtime。
- 不停止 Docker Engine / Docker Desktop。
- 不改变完整 Docker Compose Runtime、Production 部署、Schema、Migration、Contract、依赖或业务逻辑。
- 不修改 `frontend.py` 的生命周期。

# 必须保持不变

1. 本地 PostgreSQL 继续固定使用 `postgres:18.4`、`aima-ugc-postgres-dev` 和 `aima-ugc-postgres-dev-data`。
2. 再次启动时，已停止容器由 `ensure_postgres_container()` 自动启动并复用原 volume。
3. `--prepare-only` 保持 PostgreSQL 运行，以支持现有 Local Dev Bootstrap CI 后续步骤。
4. Ctrl+C / SIGTERM 仍优先停止 Worker / Scheduler / API 子进程，再停止 PostgreSQL 容器。
5. 停止失败不得伪装为成功；原始 Backend 错误也不得被 cleanup 错误静默覆盖。

# 已确认关键决策

1. 用户明确要求 `scripts/dev/backend.py` 停止运行时同步停止相关 Docker 容器，并在输出日志中说明容器已停止。
2. 当前源码 Backend launcher 唯一自动管理的 Docker 容器是 `aima-ugc-postgres-dev`；因此只停止该容器，不碰完整 Compose Runtime 或其他 Docker 容器。
3. 停止 container 与删除数据是两件事；本 Change 只执行 stop，named volume 和本地数据继续保留。
4. `--prepare-only` 是仓库现有 CI/调试特殊入口，继续保留“准备后数据库仍可用”的语义。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Backend 正常停止时同步停止其管理的 Docker 容器 | user:backend-stop-docker | satisfied | `backend.py` 统一 `finally` 清理；Ctrl+C 回归测试由总 CI `32654208231` 验证；SIGTERM 真实 lifecycle smoke `32654208213` success |
| R2 | 日志明确说明 Docker 容器停止结果 | user:backend-stop-log | satisfied | unit 覆盖 `stopped/already_stopped/missing` 三种准确日志；Local Dev Bootstrap `32654208213` 实际检查 `[STOP] PostgreSQL Docker container stopped: aima-ugc-postgres-dev` 成功 |
| R3 | 停止不删除 PostgreSQL 数据，后续启动可复用 | docs/02_环境运行与部署.md | satisfied | `stop_postgres_container()` 只有 `docker stop`；真实 smoke `32654208213` 验证 volume 存在、同一 container ID、同一 password hash、停机前 PostgreSQL marker 仍为 `persisted` |
| R4 | 保持 `--prepare-only` 与现有 Local Dev Bootstrap 行为 | .github/workflows/tooling.yml | satisfied | Local Dev Bootstrap `32654208213` 的 prepare/migration/provider/legacy-password/reset 既有步骤与 stop 后再次 `--prepare-only` 全部 success |
| R5 | 完成 L2 Completion Audit、两阶段 Review、Ready Check 与永久 CI | AGENTS.md | satisfied | Final Ready HEAD `9a1de0571868fcf59c25bf77595d9d262b9b6369` 的 Change Completion Gate `32654208234`、总 CI `32654208231`、Local Dev Bootstrap `32654208213`、Internal V1-A `32654208230`、Windows Compose `32654208228` 等 11 个永久 workflow 全部 success；PR #184 已正常合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改前端或浏览器行为 |
| Backend/API/PostgreSQL Integration | required | Local Dev Bootstrap `32654208213` 使用真实 PostgreSQL Docker 容器验证 SIGTERM 退出 stop、volume/data/container ID/password 复用和再次 prepare；同一 run 现有数据库 bootstrap/reset 测试继续通过 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP Contract / generated client；总 CI 仍执行 drift/compatibility 检查并通过 |
| Real Full-stack Golden Path | not_applicable | 本次目标是本地 launcher 生命周期；真实 Backend + PostgreSQL Docker smoke 直接覆盖目标边界，无需用 Browser E2E 冒充该证据 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为 |
| Docs / Governance / Other | required | Red/Green unit、Ctrl+C cleanup unit、Windows/Linux launcher compile、文档检查、Local Dev Bootstrap、总 CI 与 Completion Gate 均已通过 |

# Completion Audit

- [x] upstream_re_read: 2026-08-24 重新读取本轮用户要求、`AGENTS.md`、Reliable Vibe Coding、Blueprint 07、verification-review、当前 `backend.py`、`local_runtime.py`、Local Dev Bootstrap 与环境运行文档。
- [x] change_coverage: 从上游独立重建 R1-R5；覆盖 Backend 退出 stop、明确日志、数据保留/复用、prepare-only 兼容与 L2 交付门禁，没有发现 requirement omission。
- [x] reverse_audit: 反向检查 `backend.py` → `local_runtime.py` → unit → Local Dev Bootstrap → `docs/02`；runtime helper 只 stop 精确容器且没有 `rm`/`volume rm`；workflow 的删除命令仅属于显式 reset/测试 cleanup；Compose Runtime、`frontend.py`、依赖、Contract、Migration 均未修改。
- [x] unresolved_cleared: R1-R5 均有当前实现/运行证据；required Validation Matrix 层有真实证据，其他层有明确不适用依据。

# Review

## Requirement Review A1：上游要求 → Change

通过。用户要求的“backend 脚本停止时停止相关 Docker 容器”与“输出日志说明已停止”分别映射到 R1/R2；仓库既有本地数据库持久化和 `--prepare-only` CI 事实形成 R3/R4；AGENTS 的 L2 交付门禁形成 R5。没有把完整 Compose、其他容器或破坏性数据清理扩大进范围。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。`backend.py` 在交互运行生命周期的统一 `finally` 中先清理 API/Scheduler/Worker，再调用 PostgreSQL stop；`local_runtime.py` 对容器不存在/已停止/运行中给出幂等状态；unit 验证命令与日志，真实 Local Dev smoke 验证 SIGTERM、Docker 状态和持久数据，额外 unit 验证 Ctrl+C；`docs/02` 与实现一致。

## Code Quality Review

通过，无 Serious/Important finding。只操作固定 `aima-ugc-postgres-dev`，不使用 `docker compose down`、`docker rm` 或 volume 删除；Docker Engine 不可用时不虚报成功；`--prepare-only` 明确跳过 stop；如果正常退出时 Docker stop 失败，launcher 返回失败；如果已有主异常正在传播，cleanup 错误只记录而不覆盖原始根因。硬终止进程、操作系统断电等无法执行 Python `finally` 的场景不属于可由进程内 cleanup 保证的正常停止语义。

# 验证证据

## Red

Red commit：`3c65b0e8c1b88798e6dcd752e4dd00ef71b44487`

CI `32653244765` Stage 1：Ruff format / Ruff check / mypy 先通过，随后 unit **2 failed / 589 passed**；两个失败均为 `local_runtime.stop_postgres_container` 尚不存在，构成有效行为 Red。

## Green / Ready

Final Ready HEAD：`9a1de0571868fcf59c25bf77595d9d262b9b6369`

- Local Dev Bootstrap `32654208213`: success；真实 `backend.py` readiness → SIGTERM → PostgreSQL `Running=false` → volume 保留 → 同一 container ID 再启动 → password hash 不变 → PostgreSQL marker `persisted`。
- CI `32654208231`: success；包含 Ruff、mypy、unit、contract、API、frontend unit、Playwright E2E、build/docs/secret/architecture 等全量门禁，并包含 Ctrl+C cleanup 回归。
- Change Completion Gate `32654208234`: success。
- Internal V1-A `32654208230`: success；完整 Compose Golden Path 无回归。
- Windows Docker Desktop Compose Compatibility `32654208228`: success。
- Stage 8F `32654208232`、Stage 6 与 Stage 7 相关永久 workflow：同一 Ready HEAD 全部 success。

现有 CI 仍可能报告与本 Change 无关的 XLSX duplicate-member、Starlette TestClient deprecation、npm dependency/install-script warning；本 Change 不升级依赖，避免扩大范围。

# Git / 交付

- Implementation branch: `feature/local-backend-stop-postgres`
- Implementation PR: #184，已正常 merge 到 `main`
- Implementation merge commit: `350f28e2cdfcdccecfb48448f14300953b92c7c8`
- Archive: 本文件由独立归档 PR 从 `changes/active/` 移入 `changes/archive/2026-08/`；归档 PR/merge 状态由 GitHub PR 与提交历史记录
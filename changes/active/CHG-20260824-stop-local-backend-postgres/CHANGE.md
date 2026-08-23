---
schema: rvc-change/v1
id: CHG-20260824-stop-local-backend-postgres
title: 本地 Backend 退出时停止 PostgreSQL 容器
level: L2
status: in_progress
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

- [ ] Ctrl+C 结束正常 Backend 时停止 API / Worker / Scheduler，并停止 `aima-ugc-postgres-dev`。
- [ ] SIGTERM 或 Backend 主运行阶段异常退出时同样执行 PostgreSQL 容器清理。
- [ ] 控制台明确输出 PostgreSQL Docker 容器已停止；若容器本来已停止/不存在则输出准确状态，不虚报成功。
- [ ] PostgreSQL named volume 不删除，下一次 `backend.py` 可自动重新启动并复用原数据。
- [ ] `--prepare-only` 不停止 PostgreSQL，保持现有 CI/调试行为。
- [ ] Linux/Windows 共用同一生命周期逻辑；不新增额外启动/停止命令。
- [ ] Local Dev Bootstrap 永久 CI 增加真实 Backend 退出后容器停止 smoke，并继续通过现有数据库准备/重置测试。
- [ ] `docs/02_环境运行与部署.md` 描述最新停止语义，不记录实现过程。

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
| R1 | Backend 正常停止时同步停止其管理的 Docker 容器 | user:backend-stop-docker | not_satisfied | 待实现与真实 lifecycle smoke |
| R2 | 日志明确说明 Docker 容器停止结果 | user:backend-stop-log | not_satisfied | 待输出断言与真实 smoke |
| R3 | 停止不删除 PostgreSQL 数据，后续启动可复用 | docs/02_环境运行与部署.md | not_satisfied | 待 helper/CI 验证 |
| R4 | 保持 `--prepare-only` 与现有 Local Dev Bootstrap 行为 | .github/workflows/local-dev-bootstrap.yml | not_satisfied | 待现有 CI 回归 |
| R5 | 完成 L2 Completion Audit、Review、Ready Check 与 CI | AGENTS.md | not_satisfied | 待最终门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不修改前端或浏览器行为 |
| Backend/API/PostgreSQL Integration | required | Local Dev Bootstrap 使用真实 PostgreSQL Docker 容器验证启动、退出 stop、volume 复用 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP Contract / generated client |
| Real Full-stack Golden Path | not_applicable | 本次目标是本地 launcher 生命周期，真实 Backend + PostgreSQL smoke 已直接覆盖目标边界 |
| Real Provider Probe | not_applicable | 不修改 TikHub/LLM Provider 行为 |
| Docs / Governance / Other | required | 单元行为测试、跨平台 py_compile/launcher CI、文档一致性、Completion Gate |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户要求、AGENTS、Skill、Blueprint 07、当前本地运行文档与 launcher 机器事实。
- [ ] change_coverage: Ready 前比较 R1-R5 与实现/测试/文档，确认正常退出、SIGTERM/异常、日志、数据保留和 prepare-only 均覆盖。
- [ ] reverse_audit: Ready 前反向检查 `backend.py` → `local_runtime.py` → Local Dev Bootstrap → 文档，确认没有误停其他容器、没有删除 volume、没有改变 Compose Runtime。
- [ ] unresolved_cleared: Ready 前清零 `not_satisfied`，required 验证层均有新鲜证据。

# 分步计划

1. Red：新增最小单元测试，证明当前 `backend.py`/runtime 没有 PostgreSQL stop 生命周期与准确输出。
2. Green：在 `local_runtime.py` 增加安全、幂等的本地 PostgreSQL stop helper；`backend.py` 在正常运行退出路径统一调用，并输出准确状态。
3. Integration：扩展 Local Dev Bootstrap，真实启动 Backend、发送 SIGTERM、验证 container stopped，同时确认 volume 仍存在并可再次 prepare/start。
4. Docs：更新本地 Backend 停止语义，只描述最新事实。
5. Review/Ready：运行目标测试、总相关 CI、Completion Audit、两阶段 Review、Ready Check；未获明确合并授权不合并 main。

# 当前验证证据

- 当前 `main` 的 `backend.py` finally 只 `_stop_child()` API / Worker / Scheduler，没有 Docker container stop。
- 当前 `local_runtime.py` 只有 `ensure_postgres_container()`，没有对应 stop helper。
- 当前文档明确 named volume 保存数据，但没有“退出 Backend 会停止 container”的行为。

# Git / 交付

- Branch: `feature/local-backend-stop-postgres`
- PR: 待创建
- Merge: 未授权

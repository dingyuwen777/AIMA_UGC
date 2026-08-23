---
schema: rvc-change/v1
id: CHG-20260823-local-dev-bootstrap
title: 收口跨平台本地开发启动与配置
level: L3
status: done
owner: chatgpt
branch: feature/local-dev-bootstrap
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - local-development
  - runtime
  - jobs
  - configuration
  - provider-config
  - documentation
affected_paths:
  - scripts/dev/
  - env.local.example
  - .gitignore
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - .github/workflows/local-dev-bootstrap.yml
  - .github/workflows/stage8f-fullstack.yml
  - tests/unit/jobs/
  - tests/unit/platform/
  - tests/fullstack/run_stage8f_worker.py
  - docs/环境运行与部署.md
  - docs/roadmap/内网V1上线实施计划.md
contracts: []
data_changes: []
---

# 目标

把当前需要开发者手工准备 PostgreSQL、Secret、环境变量、Migration 和 Worker 的源码调试流程收口成跨平台的两个正式开发入口：一个命令启动后端完整本地运行栈，一个命令启动前端开发服务器。Windows 和 Linux 源码调试使用同一套 Python 启动逻辑；本地便利性不得改变正式生产 Secret、Provider Config、PostgreSQL、Job Runtime 和前后端 Contract 边界。

# 成功标准

- [x] Windows/Linux 的后端源码调试统一使用 `uv run python scripts/dev/backend.py`。
- [x] Windows/Linux 的前端源码调试统一使用 `uv run python scripts/dev/frontend.py`。
- [x] `env.local` 不存在时自动从 `env.local.example` 创建，并被 Git 忽略。
- [x] `env.local.example` 只保留开发者真正需要决定的可选 TikHub、LLM 和 Scheduler 配置；数据库、目录、日志细节、Cursor Key 不再要求日常手工填写。
- [x] 后端启动器自动检查 Docker Engine，并自动创建/启动固定 PostgreSQL 18.4 本地容器；数据库密码自动生成并保存到正式 Secret File 边界。
- [x] 后端启动器自动创建 `.runtime/data`、`.runtime/logs`、`.runtime/secrets`，自动生成三个独立 Cursor signing key，并自动执行 `alembic upgrade head`。
- [x] `worker_main.py` 提供正式常驻 Worker + Reaper 进程入口；本地、Stage 8F Full-stack 和未来 Compose 可以复用同一入口。
- [x] 后端启动器默认启动 API + Worker；Scheduler 默认关闭，只有 `AIMA_DEV_ENABLE_SCHEDULER=true` 时启动，避免本地残留 Plan 意外触发付费采集。
- [x] TikHub 未配置时只给清晰 Warning，不阻止 Excel/声音广场/Excel Export；配置后把本地 API Key materialize 到 Secret File，并幂等建立/更新本地 Provider Config。
- [x] LLM 未配置时只给清晰 Warning，不阻止基础功能；配置后把 API Key materialize 到 Secret File，并把现有正式 LLM Runtime 配置传给 API/Worker。
- [x] 前端首次运行在依赖缺失或 `package-lock.json` 变化时自动执行 `npm ci`，之后直接启动 Vite；本地开发不要求手工 `npm run build`。
- [x] 启动输出明确区分基础功能 available、TikHub/AI not configured、Scheduler disabled 和致命启动错误。
- [x] `docs/环境运行与部署.md` 以“两条命令”为本地快速开始，并解释首次启动、数据/Secret 保存位置、TikHub/AI/Scheduler 可选配置、前端 dev 与 production build 的区别。
- [x] Internal V1 Roadmap 在 Internal V1-A 前增加 Local Dev Bootstrap 收口事实，Internal V1-A 继续负责正式 Docker/Compose/Production Config，不把 dev launcher 冒充生产部署。
- [x] 现有 HTTP Contract、OpenAPI/generated client、PostgreSQL Schema/Migration 和业务语义保持不变；Stage 8F Real Full-stack 改为使用正式 Worker 入口并继续通过。

# 范围

- 跨平台 Python dev launcher、共享本地配置解析/准备逻辑。
- 正式 Worker 常驻进程入口。
- 本地 PostgreSQL 容器、Secret、Migration、TikHub Provider Config provisioning。
- 前端首次依赖准备与 Vite 启动。
- 相关 Unit/PostgreSQL/Full-stack 回归与运行文档/Internal V1 Roadmap 同步。

# 非目标

- 不实现 Internal V1-A 的正式 Dockerfile、Compose、Nginx、生产 env、离线 Release 或服务器部署。
- 不把 `env.local` 变成生产运行时 Contract；正式应用仍消费现有 `AIMA_*` 和 Secret File。
- 不把真实 Secret 写入 Git、`env.local.example`、数据库、日志、Job Payload 或前端。
- 不新增 Provider Config 管理页面、LLM Config 数据表、模型管理中心或仅为本地开发存在的公共 Runtime Capability API。
- 不自动创建 Keyword Pack、Global Relevance 或 Collection Plan 等业务配置。
- 不让 Scheduler 默认开启，也不在普通 CI 发起真实 TikHub/LLM 付费请求。
- 不要求本地开发执行 production `npm run build`。

# 必须保持不变

- PostgreSQL 18 是唯一业务事实库；API/Worker/Scheduler/Migration 保持分进程语义。
- `DatabaseRuntime` 继续从 `<AIMA_SECRET_DIR>/postgres_password` 读取数据库 Secret；业务代码不新增密码环境变量。
- TikHub/LLM Secret 继续通过 Secret File 进入正式 Adapter；Provider Config 只保存 `secret_ref`，不保存 API Key。
- Pydantic → OpenAPI → Orval generated client 不变，本 Change 不新增/修改公共 HTTP Contract。
- Migration 仍显式执行，不让 API 启动时自行 `create_all()` 或隐式改 Schema。
- `env.local` 只服务本地 dev launcher，生产部署继续由 Internal V1-A/后续 Release 方案负责。
- Keyword/Relevance/Plan 等业务配置继续以 PostgreSQL + 正式页面为事实源。
- 长期 `docs/roadmap/生产上线实施路线.md` 的 Stage 9—12/Production 规划保持原文；当前顺序增量只进入 Internal V1 执行计划。

# 关键决策

## 方案比较

### 方案 A：继续手工环境变量 + Secret + PostgreSQL + Migration + 多进程

优点：实现改动最小。缺点：把内部运行细节全部暴露给开发者，当前文档已证明难以从零正确启动；Windows/Linux 还会产生大量重复操作。拒绝。

### 方案 B：现在直接用完整 Docker Compose 解决本地开发

优点：依赖集中。缺点：Internal V1-A 的生产 Compose 还没实现；此时用 Compose 会把尚未收口的 Worker/配置复杂度藏进 YAML，也不利于源码热调试。延期到 Internal V1-A。

### 方案 C：跨平台 Python Dev Orchestrator + 正式进程入口（采用）

`backend.py` 只负责开发环境装配和子进程生命周期，仍调用正式 PostgreSQL/Migration/API/Worker/Scheduler/Provider Config 边界；`frontend.py` 负责依赖检查和 Vite。Windows/Linux 使用相同 Python 逻辑，生产部署不使用这些 dev launcher。该方案最少引入新机制，同时保留现有生产架构。

## 配置边界

- 机器可决定：本地 DB 名/用户/密码、目录、Cursor Key、Migration、Worker 参数 → launcher 自动处理。
- 人必须决定：TikHub API Key、LLM Base URL/Model/API Key、是否启用 Scheduler → `env.local`。
- TikHub API Key/LLM API Key 只从 `env.local` 作为开发者输入读取，随后写入 `.runtime/secrets/*`；launcher 在启动正式子进程前移除这些本地明文 Key。
- TikHub Provider Config 使用稳定本地 UUID 幂等 create/update；移除本地 TikHub key 时禁用该本地 Provider Config，避免继续暴露不可执行 Provider。
- Scheduler 默认关闭是费用安全决定；显式启用后仍复用正式 Scheduler 进程。
- 未配置 TikHub/LLM 的首要用户反馈由 Backend launcher 的能力摘要承担；TikHub 前端继续由现有 `collection-capabilities` 驱动，AI Worker 的正式失败码/页面 Job banner 保留。为此不扩大公共 HTTP Contract。

## 兼容、Migration、部署与回滚

- HTTP Contract/OpenAPI/generated：不变；主 CI 的 Contract/generated 检查已经通过。
- Schema/Alembic revision：不新增；launcher 只执行现有 `upgrade head`。
- 现有 `AIMA_*` 运行时配置继续兼容；高级用户仍可直接启动正式进程并自行注入环境。
- Production：不使用 `env.local` 或 dev launcher；Internal V1-A 另行实现 Compose/Secret mount。
- 回滚：删除 dev launcher/测试并还原 Worker/文档/Stage8F workflow 即可；不涉及业务数据 Migration。开发者本地 `.runtime` 与 PostgreSQL dev volume 不自动删除。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地源码开发只需要一个后端命令和一个前端命令，Windows/Linux 使用同一套核心启动逻辑 | user:local-dev-bootstrap-confirmation | satisfied | `scripts/dev/backend.py`、`frontend.py`；Final Ready HEAD 的 Local Dev Bootstrap #19 在 Windows 2025 / Ubuntu 24.04 均 success |
| R2 | `env.local` 缺失时自动从模板创建；TikHub/LLM 未配置不阻塞基础功能，但启动时必须明确 Warning | user:local-dev-bootstrap-confirmation | satisfied | `ensure_env_local()`、能力摘要、Unit tests；模板默认空可选配置；Final CI #2196 success |
| R3 | 数据库、目录、Cursor Secret、Migration 等机器可决定的本地细节不再要求开发者手工配置 | user:local-dev-bootstrap-confirmation | satisfied | `local_runtime.py` + `backend.py`；Local Dev Bootstrap #19 PostgreSQL bootstrap smoke success |
| R4 | TikHub/LLM 真实 Secret 可由本地 `env.local` 输入，但正式运行仍使用 Secret File；TikHub 非敏感 Provider Config 继续保存在数据库 | user:local-dev-bootstrap-confirmation | satisfied | Secret materialize 单测；Local Dev Bootstrap #19 验证 Provider Config 只保存 `secret_ref=tikhub_api_key` |
| R5 | Worker 必须成为正式可执行常驻进程，API + Worker 默认随后端开发入口启动；Scheduler 默认关闭、显式开启 | user:local-dev-bootstrap-confirmation | satisfied | `worker_main.py` + Worker loop unit；`backend.py`；Stage 8F #323 使用正式 Worker entrypoint success |
| R6 | 前端首次运行自动安装锁定依赖并启动 Vite；日常开发不要求 production build | user:local-dev-bootstrap-confirmation | satisfied | `frontend.py`；Local Dev Bootstrap #19 Windows/Ubuntu 都真实执行 `--prepare-only` + `npm ci`；运行文档解释 Vite HMR/build 边界 |
| R7 | 本地便利性不能破坏 PostgreSQL、Secret、Provider Config、Migration、API/Worker/Scheduler 分进程等长期边界 | docs/blueprint/05-日志安全部署与运维.md | satisfied | 子进程继续使用正式 `AIMA_* + Secret File`；ProviderConfig Repository；Final CI #2196、Audit #1059、Stage 4/5D/6/7 全部 success |
| R8 | 该收口应先于 Internal V1-A，V1-A 继续负责正式 Docker/Compose/Production Config | user:local-dev-bootstrap-confirmation + docs/roadmap/内网V1上线实施计划.md | satisfied | Internal V1 Roadmap 以增量 `# 8A Local Dev Bootstrap` 固化；长期 Production Roadmap 保持原文 |
| R9 | 现有真实 Excel Browser Full-stack 必须继续证明 Browser→API→PostgreSQL→正式 Worker→Voice Plaza 接通 | docs/roadmap/内网V1上线实施计划.md | satisfied | `.github/workflows/stage8f-fullstack.yml` 使用 `python -m aima_ugc.entrypoints.worker_main`；Final Stage 8F #323 success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本 Change 不修改页面业务行为或 HTTP Contract；未配置外部能力的首要新增反馈是 launcher 输出，现有页面错误/Capability 行为保持 |
| Backend/API/PostgreSQL Integration | required | Final Local Dev Bootstrap #19：真实 PostgreSQL 18.4 bootstrap、Migration、Secret、Provider Config；Worker entrypoint unit；Final CI #2196 success |
| Contract / Generated Client | required | 本 Change 不改公共 HTTP Contract；Final CI #2196 的 OpenAPI/generated drift/contract 门禁 success |
| Real Full-stack Golden Path | required | Final Stage 8F #323 success：真实 Browser → Vue → FastAPI → PostgreSQL → 正式 `worker_main` → Voice Plaza |
| Real Provider Probe | not_applicable | 不修改 TikHub endpoint/字段/分页/Capability；没有必要产生真实付费请求，只验证本地 Provider Config provisioning |
| Docs / Governance / Other | required | Final Local Dev Bootstrap #19 Windows/Ubuntu launcher + frontend prepare success；`docs/环境运行与部署.md` 与 Internal V1 Roadmap 已同步；长期 Production Roadmap 未被改写；Change Completion Gate #42 success |

# Completion Audit

- [x] upstream_re_read：已重新读取用户确认决定、AGENTS/Skill、运行/Secret/Provider/Worker/Frontend 机器事实和 Internal V1 正式路线，并独立重建完成定义。
- [x] change_coverage：已确认当前 Change 覆盖两个跨平台命令、首次配置、可选能力提示、PostgreSQL/Secret/Migration/Worker、Frontend 首次依赖和文档要求；未把 Change 自身当作需求全集。
- [x] reverse_audit：已从开发者两个命令反向检查 PostgreSQL→Secret→Migration→API/Worker→Scheduler/TikHub/LLM，以及 Frontend→npm ci→Vite；Stage 8F 再从 Browser 反向证明正式 Worker 接线。
- [x] unresolved_cleared：R1—R9 均已 satisfied；Browser Mock/Real Provider Probe 不适用的依据已记录，没有遗留 `not_satisfied`。

# 任务

- [x] 调查当前本地运行文档、Settings、Secret、Provider Config、API/Worker/Scheduler、前端 npm 脚本和 Stage8F Full-stack。
- [x] 建立 dev launcher 与 Worker loop 的失败/回归测试。
- [x] 新增跨平台 `scripts/dev/backend.py` 与共享本地配置/运行辅助。
- [x] 新增跨平台 `scripts/dev/frontend.py`，自动处理 `npm ci` 决策并启动 Vite。
- [x] 简化 `env.local.example` 并忽略真实 `env.local`。
- [x] 正式实现 `worker_main.py` 常驻 Worker/Reaper，并删除被替代的 Full-stack Worker harness。
- [x] 让 Stage8F Full-stack 使用正式 Worker entrypoint。
- [x] 同步 `docs/环境运行与部署.md` 和 Internal V1 Roadmap；长期 Production Roadmap 保持原有 Stage 9—12/Production 定义。
- [x] 取得目标测试、PostgreSQL bootstrap、Contract、Stage8F Full-stack 和主 CI 新鲜证据。
- [x] 完成 Completion Audit、两阶段语义 Review、Ready Check、最终永久 CI 和正常 PR 合并。

# 验证

## Final Ready HEAD `3f738c50d004841e71c80c922f06696a79a6f270`

- Change Completion Gate #42 / run `32615199155`：success。
- Local Dev Bootstrap #19 / run `32615199146`：success。
  - `Launcher (windows-2025)`：success；真实执行 launcher 校验与 `frontend.py --prepare-only`。
  - `Launcher (ubuntu-24.04)`：success；真实执行 launcher 校验与 `frontend.py --prepare-only`。
  - `PostgreSQL bootstrap smoke`：success；真实 PostgreSQL 18.4、Secret、Alembic、Provider Config `secret_ref`。
- CI #2196 / run `32615199157`：success；包含 Ruff、mypy、unit/integration/API/contract/generated、frontend lint/typecheck/unit/build/E2E 等常规门禁。
- Stage 8F Full-stack #323 / run `32615199263`：success；使用正式 `worker_main`。
- Stage 1-7 Audit #1059、Stage 4 #904、Stage 5D #1563、Stage 6 #194、Stage 7 Keyword #1806、Plan #1804、Provider Config #1919、Scheduler #2146：全部 success。

## 合并证据

- PR #157 `收口跨平台本地开发启动与配置`：Ready 后正常 merge。
- Implementation merge commit：`84e89e89f0c40307bc56b15bf68dedbbe1464a47`。
- 没有使用 CI/Branch Protection/质量门禁豁免。

# 文档影响

- `docs/环境运行与部署.md`：以跨平台“两条命令”为本地快速开始，说明首次 PostgreSQL/Secret/Migration、`env.local`、TikHub/AI/Scheduler、Frontend dev/build、数据/日志/重置与生产边界。
- `docs/roadmap/内网V1上线实施计划.md`：保留原 Stage 8F 和 Backlog 内容，增量插入 `Local Dev Bootstrap`，明确它先于 Internal V1-A。
- `docs/roadmap/生产上线实施路线.md`：Review 时发现最初重写过度，已精确恢复原文，本 Change 未改写长期 Stage 9—12/Production 规划。
- Blueprint 04/05 的长期进程与 Secret 边界没有变化，因此不修改；本地 dev launcher 细节由运行文档维护。

# 交付

- Branch：`feature/local-dev-bootstrap`
- PR：#157 `收口跨平台本地开发启动与配置`
- Final Ready HEAD：`3f738c50d004841e71c80c922f06696a79a6f270`
- Implementation merge commit：`84e89e89f0c40307bc56b15bf68dedbbe1464a47`
- 状态：done；当前 Change 已转入 `changes/archive/2026-08/`。
- 发布：不涉及生产发布；合并后形成源码开发正式入口，下一正式开发单元为 Internal V1-A。

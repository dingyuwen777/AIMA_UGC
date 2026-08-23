---
schema: rvc-change/v1
id: CHG-20260823-local-dev-bootstrap
title: 收口跨平台本地开发启动与配置
level: L3
status: in_progress
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
  - .github/workflows/stage8f-fullstack.yml
  - tests/
  - docs/环境运行与部署.md
  - docs/blueprint/04-后端任务API与前端.md
  - docs/blueprint/05-日志安全部署与运维.md
  - docs/roadmap/内网V1上线实施计划.md
contracts: []
data_changes: []
---

# 目标

把当前需要开发者手工准备 PostgreSQL、Secret、环境变量、Migration 和 Worker 的源码调试流程收口成跨平台的两个正式开发入口：一个命令启动后端完整本地运行栈，一个命令启动前端开发服务器。Windows 和 Linux 源码调试使用同一套 Python 启动逻辑；本地便利性不得改变正式生产 Secret、Provider Config、PostgreSQL、Job Runtime 和前后端 Contract 边界。

# 成功标准

- [ ] Windows/Linux 的后端源码调试统一使用 `uv run python scripts/dev/backend.py`。
- [ ] Windows/Linux 的前端源码调试统一使用 `uv run python scripts/dev/frontend.py`。
- [ ] `env.local` 不存在时自动从 `env.local.example` 创建，并被 Git 忽略。
- [ ] `env.local.example` 只保留开发者真正需要决定的可选 TikHub、LLM 和 Scheduler 配置；数据库、目录、日志细节、Cursor Key 不再要求日常手工填写。
- [ ] 后端启动器自动检查 Docker Engine，并自动创建/启动固定 PostgreSQL 18.4 本地容器；数据库密码自动生成并保存到正式 Secret File 边界。
- [ ] 后端启动器自动创建 `.runtime/data`、`.runtime/logs`、`.runtime/secrets`，自动生成三个独立 Cursor signing key，并自动执行 `alembic upgrade head`。
- [ ] `worker_main.py` 提供正式常驻 Worker + Reaper 进程入口；本地、Stage 8F Full-stack 和未来 Compose 可以复用同一入口。
- [ ] 后端启动器默认启动 API + Worker；Scheduler 默认关闭，只有 `AIMA_DEV_ENABLE_SCHEDULER=true` 时启动，避免本地残留 Plan 意外触发付费采集。
- [ ] TikHub 未配置时只给清晰 Warning，不阻止 Excel/声音广场/Excel Export；配置后把本地 API Key materialize 到 Secret File，并幂等建立/更新本地 Provider Config。
- [ ] LLM 未配置时只给清晰 Warning，不阻止基础功能；配置后把 API Key materialize 到 Secret File，并把现有正式 LLM Runtime 配置传给 API/Worker。
- [ ] 前端首次运行在依赖缺失或 `package-lock.json` 变化时自动执行 `npm ci`，之后直接启动 Vite；本地开发不要求手工 `npm run build`。
- [ ] 启动输出明确区分基础功能 available、TikHub/AI not configured、Scheduler disabled 和致命启动错误。
- [ ] `docs/环境运行与部署.md` 以“两条命令”为本地快速开始，并解释首次启动、数据/Secret 保存位置、TikHub/AI/Scheduler 可选配置、前端 dev 与 production build 的区别。
- [ ] Roadmap 在 Internal V1-A 前增加 Local Dev Bootstrap 收口事实，Internal V1-A 继续负责正式 Docker/Compose/Production Config，不把 dev launcher 冒充生产部署。
- [ ] 现有 HTTP Contract、OpenAPI/generated client、PostgreSQL Schema/Migration 和业务语义保持不变；Stage 8F Real Full-stack 改为使用正式 Worker 入口并继续通过。

# 范围

- 跨平台 Python dev launcher、共享本地配置解析/准备逻辑。
- 正式 Worker 常驻进程入口。
- 本地 PostgreSQL 容器、Secret、Migration、TikHub Provider Config provisioning。
- 前端首次依赖准备与 Vite 启动。
- 相关 Unit/Integration/Full-stack 回归与运行文档/Roadmap 同步。

# 非目标

- 不实现 Internal V1-A 的正式 Dockerfile、Compose、Nginx、生产 env、离线 Release 或服务器部署。
- 不把 `env.local` 变成生产运行时 Contract；正式应用仍消费现有 `AIMA_*` 和 Secret File。
- 不把真实 Secret 写入 Git、`env.local.example`、数据库、日志、Job Payload 或前端。
- 不新增 Provider Config 管理页面、LLM Config 数据表或模型管理中心。
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
- TikHub API Key/LLM API Key 只从 `env.local` 作为开发者输入读取，随后写入 `.runtime/secrets/*`，正式子进程不直接消费明文 env key。
- TikHub Provider Config 使用稳定本地 UUID 幂等 create/update；移除本地 TikHub key 时禁用该本地 Provider Config，避免页面继续暴露不可执行能力。
- Scheduler 默认关闭是费用安全决定；显式启用后仍复用正式 Scheduler 进程。

## 兼容、Migration、部署与回滚

- HTTP Contract/OpenAPI/generated：不变。
- Schema/Alembic revision：不新增；launcher 只执行现有 `upgrade head`。
- 现有 `AIMA_*` 运行时配置继续兼容；高级用户仍可直接启动正式进程并自行注入环境。
- Production：不使用 `env.local` 或 dev launcher；Internal V1-A 另行实现 Compose/Secret mount。
- 回滚：删除 dev launcher/测试并还原 Worker/文档/Stage8F workflow 即可；不涉及业务数据 Migration。开发者本地 `.runtime` 与 PostgreSQL dev volume 不自动删除。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地源码开发只需要一个后端命令和一个前端命令，Windows/Linux 使用同一套核心启动逻辑 | user:local-dev-bootstrap-confirmation | not_satisfied | 待实现跨平台 Python launcher |
| R2 | `env.local` 缺失时自动从模板创建；TikHub/LLM 未配置不阻塞基础功能，但启动时必须明确 Warning | user:local-dev-bootstrap-confirmation | not_satisfied | 待实现 env loader 与能力摘要 |
| R3 | 数据库、目录、Cursor Secret、Migration 等机器可决定的本地细节不再要求开发者手工配置 | user:local-dev-bootstrap-confirmation | not_satisfied | 待实现 PostgreSQL/Secret/Migration bootstrap |
| R4 | TikHub/LLM 真实 Secret 可由本地 `env.local` 输入，但正式运行仍使用 Secret File；TikHub 非敏感 Provider Config 继续保存在数据库 | user:local-dev-bootstrap-confirmation | not_satisfied | 待实现 materialize/provisioning；现有 Secret/Provider 边界见 Blueprint 05/System Repository |
| R5 | Worker 必须成为正式可执行常驻进程，API + Worker 默认随后端开发入口启动；Scheduler 默认关闭、显式开启 | user:local-dev-bootstrap-confirmation | not_satisfied | 待实现 `worker_main.py` loop 与 backend orchestrator |
| R6 | 前端首次运行自动安装锁定依赖并启动 Vite；日常开发不要求 production build | user:local-dev-bootstrap-confirmation | not_satisfied | 待实现 frontend launcher；当前 `frontend/package.json` dev/build 语义作为机器事实 |
| R7 | 本地便利性不能破坏 PostgreSQL、Secret、Provider Config、Migration、API/Worker/Scheduler 分进程等长期边界 | docs/blueprint/05-日志安全部署与运维.md | not_satisfied | 待由实现/测试证明继续复用正式边界 |
| R8 | 该收口应先于 Internal V1-A，V1-A 继续负责正式 Docker/Compose/Production Config | docs/roadmap/内网V1上线实施计划.md | not_satisfied | 待同步 Roadmap 与运行文档 |
| R9 | 现有真实 Excel Browser Full-stack 必须继续证明 Browser→API→PostgreSQL→正式 Worker→Voice Plaza 接通 | docs/roadmap/内网V1上线实施计划.md | not_satisfied | 待把 Stage8F workflow 切到正式 Worker entrypoint 并验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本 Change 不修改业务页面或 HTTP Contract；未配置能力的主要反馈由跨平台 launcher 输出承担，不新增前端状态语义 |
| Backend/API/PostgreSQL Integration | required | Worker 常驻循环、Secret/Provider provisioning、现有 PostgreSQL/Migration/Job 行为必须有 Unit/Integration 证据 |
| Contract / Generated Client | required | 本 Change要求公共 HTTP Contract 不变；生成/漂移检查必须证明 Pydantic/OpenAPI/generated client 无意外变化 |
| Real Full-stack Golden Path | required | Stage 8F Excel Browser Full-stack 改用正式 `worker_main` 后继续通过，证明新进程入口真实接线 |
| Real Provider Probe | not_applicable | 不修改 TikHub endpoint/字段/分页/Capability，不需要真实付费请求；只验证本地 Provider Config provisioning |
| Docs / Governance / Other | required | Windows/Linux launcher 静态/单元验证、Frontend 首次依赖决策逻辑、运行文档/Roadmap 与代码一致 |

# Completion Audit

- [ ] upstream_re_read：已重新读取用户确认决定和适用正式事实源，并独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已从开发者两条命令反向检查 PostgreSQL/Secret/Migration/API/Worker/Scheduler/TikHub/LLM/Frontend 链，并复核 Validation Matrix。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；不适用项均有事实依据。

# 任务

- [x] 调查当前本地运行文档、Settings、Secret、Provider Config、API/Worker/Scheduler、前端 npm 脚本和 Stage8F Full-stack。
- [ ] 建立 dev launcher 与 Worker loop 的失败/回归测试。
- [ ] 新增跨平台 `scripts/dev/backend.py` 与共享本地配置/运行辅助。
- [ ] 新增跨平台 `scripts/dev/frontend.py`，自动处理 `npm ci` 决策并启动 Vite。
- [ ] 简化 `env.local.example` 并忽略真实 `env.local`。
- [ ] 正式实现 `worker_main.py` 常驻 Worker/Reaper。
- [ ] 让 Stage8F Full-stack 使用正式 Worker entrypoint。
- [ ] 同步 `docs/环境运行与部署.md`、Blueprint 04/05、Internal V1 Roadmap。
- [ ] 取得目标测试、PostgreSQL Integration、Contract、Stage8F Full-stack 和主 CI 新鲜证据。
- [ ] 完成 Completion Audit、两阶段 Review、Ready Check 与 Git 交付。

# 验证

## 计划

- 目标测试：dev env/parser/bootstrap helper、Worker loop、Frontend dependency decision。
- PostgreSQL Integration：本地 Provider Config provisioning 与现有 DB/Secret 边界。
- Contract：`uv run python scripts/contracts/generate.py --check` + frontend generated drift gate。
- Real Full-stack：`.github/workflows/stage8f-fullstack.yml` 使用正式 Worker entrypoint。
- 静态/构建：Ruff、mypy、Frontend lint/typecheck/build、Windows bootstrap/相关 CI。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/环境运行与部署.md`：本地快速开始、首次启动、`env.local`、可选能力、数据/日志/Secret、Windows/Linux、Frontend dev/build。
- `docs/blueprint/04-后端任务API与前端.md`：正式 Worker 入口与本地调试调用链。
- `docs/blueprint/05-日志安全部署与运维.md`：`env.local` 仅为 dev launcher 输入，正式进程仍使用 Secret File。
- `docs/roadmap/内网V1上线实施计划.md`：Internal V1-A 前增加 Local Dev Bootstrap 收口，不改变 V1-A 的生产部署职责。

# 交付

- Branch：`feature/local-dev-bootstrap`
- Commit：待实现
- PR：待创建
- 发布：不涉及生产发布；合并后仅形成源码开发入口与文档事实。

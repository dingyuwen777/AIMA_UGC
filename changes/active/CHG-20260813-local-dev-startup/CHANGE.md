---
schema: rvc-change/v1
id: CHG-20260813-local-dev-startup
title: 本地开发启动与联调闭环
level: L2
status: ready_for_review
owner: dingyuwen777
branch: build/local-dev-startup
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [toolchain, platform, frontend]
affected_paths: [pyproject.toml, uv.lock, frontend/vite.config.ts, scripts/dev/, .github/workflows/ci.yml, README.md, docs/环境运行与部署.md, docs/blueprint/README.md, docs/blueprint/07-技术决策与实施门禁.md, changes/active/CHG-20260813-local-dev-startup/CHANGE.md]
contracts: []
data_changes: []
---

# 目标

让开发者从最新 `main` 克隆仓库后，按锁文件安装依赖，用两个明确命令分别启动 FastAPI 与 Vite，并通过 Vite 开发代理访问后端现有 `/health/live`，形成可重复验证的本地前后端启动闭环；同时建立长期维护的环境、启动与生产部署入口文档。

# 成功标准

- [x] Python 依赖中包含精确锁定的 ASGI Server，`uv sync --locked` 后无需额外 `pip install` 即可启动后端。
- [x] 后端本地开发命令固定监听 `127.0.0.1:8090`，并支持 `--reload --reload-dir backend/src`。
- [x] 前端 `npm --prefix frontend run dev` 固定监听 `127.0.0.1:5173`，端口占用时失败而不是静默切换。
- [x] Vite 将 `/health` 和 `/api` 代理到本地后端，浏览器通过前端 Origin 可访问 `/health/live`，不需要开发期 CORS 绕行。
- [x] CI 实际同时启动后端和 Vite，验证后端直连健康检查、前端页面和经 Vite 代理的健康检查。
- [x] `docs/环境运行与部署.md` 说明版本、首次安装、本地启动、联调验证以及当前生产部署 Go/No-Go；未实现的生产命令没有伪造。
- [x] 根 README 提供该文档入口；Blueprint README 提供操作入口导航；`07` 只同步新增且已验证的 Uvicorn/本地启动技术事实。
- [x] 现有 Contract、OpenAPI、生成 Client、API 行为和 Stage 1 质量门禁保持不变。

# 范围

- 在根 Python 项目增加 Uvicorn 运行依赖并更新 `uv.lock`。
- 固化本地后端 `127.0.0.1:8090` 与 Vite `127.0.0.1:5173` 开发端口。
- Vite 只代理后端路径前缀 `/health`、`/api`。
- 增加不复制业务逻辑的本地联调 smoke 检查，复用正式 FastAPI `app`、生成 Client 的相对 URL 约定和 Vite 正式开发服务器。
- 更新 CI、README、环境运行部署文档、Blueprint 导航和受影响的 Blueprint 07。

# 非目标

- 不实现 PostgreSQL、`/health/ready`、Config/Secret/Logging/Artifact 或四进程 Stage 2 基础。
- 不实现 Dockerfile、Compose、Release Bundle、Migration、备份或生产部署自动化。
- 不修改现有 `/health/live` HTTP Contract，不新增业务 API。
- 不增加 CORS 作为本地联调方案；开发期保持浏览器同源访问 Vite，再由 Vite 代理后端。
- 不引入额外任务运行器、第二套 Python 项目或一键启动两个长期进程的复杂 Supervisor。

# 必须保持不变

- 仓库根目录仍是唯一 Python/uv 工程；依赖必须进入 `pyproject.toml + uv.lock`。
- FastAPI 应用仍由 `aima_ugc.entrypoints.api_main:app` 提供；本地启动不得复制应用构建逻辑。
- 前端继续使用生成 Client 的相对 URL，不手工改 generated 目录。
- 生产架构仍按 Blueprint 05：同源 Nginx + API/Worker/Scheduler/Migrate/PostgreSQL + 离线 Release；本 Change 只补开发机启动体验。

# 已确认决策

- ASGI Server 使用 `uvicorn==0.52.2`。2026-08-13 PyPI 将其标为 latest，声明 `Python >=3.10` 且包含 Python 3.14 classifier；最终仍以本仓库实际 CI 启动、Wheel 安装和 Lock 验证为采用证据。
- 只安装 Uvicorn 最小依赖，不安装 `uvicorn[standard]`。官方说明 `--reload` 在没有 `watchfiles` 时会回退为 Python 文件修改时间轮询，当前 CI 已使用文档中的 `--reload --reload-dir backend/src` 命令验证成功。
- 本地后端端口固定 `8090`，前端固定 `5173` 且 `strictPort=true`。本地开发只绑定 `127.0.0.1`，默认不暴露到局域网。
- Vite 使用 `server.proxy`，代理 `/health` 与 `/api` 到 `http://127.0.0.1:8090`。这保持生成 Client 的相对路径语义，并避免为了开发环境增加 CORS 公共安全配置。
- 生产部署操作文档在生产制品未落地前明确标记 No-Go；Blueprint 05 的离线 Release 设计仍是目标事实，不把本地 `vite dev` 或 Uvicorn `--reload` 伪装为生产方案。

# 任务

- [x] 读取最新 main 的 AGENTS、Skill、Blueprint、依赖、入口、前端配置和 CI。
- [x] 核验 Uvicorn 与 Vite 官方当前能力。
- [x] Red：增加本地启动 smoke 门禁，在 Uvicorn/Proxy 尚未实现时确认按正确原因失败。
- [x] Green：增加 Uvicorn、更新 Lock、配置 Vite 代理和固定端口，使 smoke 通过。
- [x] 同步 README、环境运行部署文档、Blueprint 导航与 Blueprint 07。
- [x] 完整运行现有后端、Contract、Wheel、前端、audit、生成物无漂移与本地启动 smoke。
- [x] 两阶段 Review：需求符合性 → 代码质量。
- [ ] 合并 PR 后重新验证 `main`，再归档 Change。

# 验证

## Red

- PR #3 Red Run `31681724208` / job `94388453966`：精确 Python/Node/npm、uv 安装、锁定 Python 环境、`npm ci` 与两类 npm audit 均已成功；`Local development startup smoke` 在启动后端时按正确原因失败：`Failed to spawn: uvicorn` / `No such file or directory (os error 2)`。这证明原始缺口是仓库没有正式 ASGI Server 依赖，不是测试环境损坏。

## Lock 生成

- 特性分支临时 bootstrap Run `31681862046` / job `94388891262` 使用 Python 3.14.7 + uv 0.12.3 执行 `uv lock`，生成 commit `8da1b93e8912f80aa865626c63351a8dd9df8cf3`；该 commit 只更新 `uv.lock`，加入 Uvicorn 0.52.2 及其解析依赖。
- 临时 `contents: write` bootstrap workflow 随后已删除；最终分支只保留正式只读 CI。

## Green 与最终验证

- Run `31681920014` / job `94389070648`：首次完整 Green 全绿。实际启动 Uvicorn `127.0.0.1:8090` 与 Vite `127.0.0.1:5173`；smoke 验证后端直连、Vite 首页、Vite `/health/live` 代理全部成功。完整/生产 npm audit 均为 0 vulnerabilities；Contract 重新生成无漂移；Ruff/mypy、Unit 1、Contract 1、API 1、质量脚本、Wheel 构建与隔离安装、ESLint、双 TypeScript typecheck、Vitest 1 file/2 tests、Vite production Build、Playwright CLI 全部通过。
- Run `31682437917` / job `94390723839`：最终 head `f0a416f7f9c678076df770528f94e0f42c702113` 全绿。CI 使用与 README/`docs/环境运行与部署.md` 完全一致的后端开发命令：`uv run uvicorn aima_ugc.entrypoints.api_main:app --host 127.0.0.1 --port 8090 --reload --reload-dir backend/src`；`Local development startup smoke`、生成物无漂移、文档入口/本地链接、后端/仓库检查、Wheel 和全部前端检查均 success。

# 两阶段 Review

## 需求符合性

基于 `main...build/local-dev-startup` 最终 diff 逐项复核：只新增/修改 Uvicorn 运行依赖与 Lock、Vite 开发服务器/代理、smoke、CI、README、环境运行部署文档、Blueprint 07 与导航。未实现 PostgreSQL、`/health/ready`、Config/Secret/Logging/Artifact、Worker/Scheduler/Migration、Docker/Compose/Release、CORS 或业务 API；现有 `/health/live` Contract 与 generated client 均未改动。成功标准与用户补充的运行/部署文档要求均有对应代码、CI 和当前事实文档。

## 代码质量

复核 `pyproject.toml`、`uv.lock`、`frontend/vite.config.ts`、`scripts/dev/check_local_stack.py`、正式只读 CI 和三份受影响文档：本地调试复用正式 FastAPI `app` 与 Vite server；smoke 只观察 HTTP，不复制业务逻辑；端口只绑定回环地址；没有为了联调放宽 CORS；锁文件由真实 uv 生成；CI 在失败时输出两个服务日志并清理后台进程；生产文档没有编造当前不存在的部署命令。未发现严重或重要问题，也未发现无关重构或 Stage 2 范围蔓延。

# 文档影响

- `docs/环境运行与部署.md`：新增为开发机环境、锁定安装、本地启动、Vite 代理、smoke、常见故障和生产部署当前 Go/No-Go 的长期操作入口。
- `README.md`：增加最短安装/启动/smoke 命令和上述文档入口。
- `docs/blueprint/README.md`：增加操作文档导航并同步本地双服务联调已成为机器事实。
- `docs/blueprint/07-技术决策与实施门禁.md`：蓝图 1.2 → 1.3，增加 Uvicorn 0.52.2、本地 8090/5173、Vite `/health`/`/api` 代理和 smoke 的已验证技术基线。
- `docs/blueprint/01-总体架构与技术选型.md`、`04-后端任务API与前端.md`、`05-日志安全部署与运维.md`、`06-开发约束与分阶段实施.md` 复核后无需修改；其长期架构、API 边界、生产离线 Release 目标和阶段顺序仍与本次实现一致。

# Git / 发布

- 分支：`build/local-dev-startup`
- PR：#3 `补齐本地开发启动与联调闭环`，当前待从 Draft 转正式 Review 后合并。
- 生产发布：不适用；本 Change 不产生可部署生产 Release，生产状态明确为 No-Go。
- Migration / 数据变化：无。
- 回滚：移除 Uvicorn 依赖与 Lock 变化、Vite 开发代理、smoke 和对应文档即可；无 Schema/Migration/数据恢复步骤。

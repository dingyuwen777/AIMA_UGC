---
schema: rvc-change/v1
id: CHG-20260813-local-dev-startup
title: 本地开发启动与联调闭环
level: L2
status: in_progress
owner: dingyuwen777
branch: build/local-dev-startup
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [toolchain, platform, frontend]
affected_paths: [pyproject.toml, uv.lock, frontend/vite.config.ts, scripts/dev/, .github/workflows/ci.yml, README.md, docs/环境运行与部署.md, docs/blueprint/07-技术决策与实施门禁.md, changes/active/CHG-20260813-local-dev-startup/CHANGE.md]
contracts: []
data_changes: []
---

# 目标

让开发者从最新 `main` 克隆仓库后，按锁文件安装依赖，用两个明确命令分别启动 FastAPI 与 Vite，并通过 Vite 开发代理访问后端现有 `/health/live`，形成可重复验证的本地前后端启动闭环；同时建立长期维护的环境、启动与生产部署入口文档。

# 成功标准

- [ ] Python 依赖中包含精确锁定的 ASGI Server，`uv sync --locked` 后无需额外 `pip install` 即可启动后端。
- [ ] 后端本地开发命令固定监听 `127.0.0.1:8090`，并支持 `--reload`。
- [ ] 前端 `npm --prefix frontend run dev` 固定监听 `127.0.0.1:5173`，端口占用时失败而不是静默切换。
- [ ] Vite 将 `/health` 和 `/api` 代理到本地后端，浏览器通过前端 Origin 可访问 `/health/live`，不需要开发期 CORS 绕行。
- [ ] CI 实际同时启动后端和 Vite，验证后端直连健康检查、前端页面和经 Vite 代理的健康检查。
- [ ] `docs/环境运行与部署.md` 说明版本、首次安装、本地启动、联调验证以及当前生产部署 Go/No-Go；未实现的生产命令不得伪造。
- [ ] 根 README 提供该文档入口；`07` 只同步新增且已验证的 Uvicorn/本地启动技术事实。
- [ ] 现有 Contract、OpenAPI、生成 Client、API 行为和 Stage 1 质量门禁保持不变。

# 范围

- 在根 Python 项目增加 Uvicorn 运行依赖并更新 `uv.lock`。
- 固化本地后端 `127.0.0.1:8090` 与 Vite `127.0.0.1:5173` 开发端口。
- Vite 只代理后端路径前缀 `/health`、`/api`。
- 增加不复制业务逻辑的本地联调 smoke 检查，复用正式 FastAPI `app`、生成 Client 的相对 URL 约定和 Vite 正式开发服务器。
- 更新 CI、README、环境运行部署文档和受影响的 Blueprint 07。

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

- ASGI Server 使用 `uvicorn==0.52.2`。2026-08-13 PyPI 将其标为 latest，声明 `Python >=3.10` 且包含 Python 3.14 classifier；本 Change 仍以真实 CI 启动验证作为最终采用门禁。
- 只安装 Uvicorn 最小依赖，不安装 `uvicorn[standard]`。官方说明 `--reload` 在没有 `watchfiles` 时会回退为 `*.py` 修改时间轮询，满足当前本地开发需求；额外事件循环/HTTP parser/watchfiles 依赖没有当前必要性。
- 本地后端端口固定 `8090`，前端固定 `5173` 且 `strictPort=true`。本地开发只绑定 `127.0.0.1`，默认不暴露到局域网。
- Vite 使用官方 `server.proxy`，代理 `/health` 与 `/api` 到 `http://127.0.0.1:8090`。这保持生成 Client 的相对路径语义，并避免为了开发环境增加 CORS 公共安全配置。

# 任务

- [x] 读取最新 main 的 AGENTS、Skill、Blueprint、依赖、入口、前端配置和 CI。
- [x] 核验 Uvicorn 与 Vite 官方当前能力。
- [ ] Red：增加本地启动 smoke 门禁，在 Uvicorn/Proxy 尚未实现时确认按正确原因失败。
- [ ] Green：增加 Uvicorn、更新 Lock、配置 Vite 代理和固定端口，使 smoke 通过。
- [ ] 同步 README、环境运行部署文档与 Blueprint 07。
- [ ] 完整运行现有后端、Contract、Wheel、前端、audit、生成物无漂移与本地启动 smoke。
- [ ] 两阶段 Review，PR 合并后再次验证 main，再归档 Change。

# 验证计划

- `uv lock --check`、`uv sync --locked`、直接 import。
- CI 后台启动 `uv run uvicorn aima_ugc.entrypoints.api_main:app --host 127.0.0.1 --port 8090`。
- CI 后台启动 `npm --prefix frontend run dev`。
- `uv run python scripts/dev/check_local_stack.py` 验证：`8090/health/live`、`5173/`、`5173/health/live`。
- 现有 Ruff、mypy、Unit/Contract/API、质量脚本、Wheel 隔离安装、npm audit、生成物零漂移、Lint、双 typecheck、Vitest、Vite Build、Playwright CLI 全部继续执行。

# 文档影响

- 新增 `docs/环境运行与部署.md` 作为环境、本地启动与生产部署的长期操作入口。
- `README.md` 链接该文档并给出最短启动入口。
- `docs/blueprint/07-技术决策与实施门禁.md` 在真实 CI 通过后增加 Uvicorn 版本/本地启动事实；`04/05/06` 的长期边界当前仍有效，除非实施发现冲突不做无关改写。

# Git / 发布

- 分支：`build/local-dev-startup`
- 生产发布：不适用；本 Change 不产生可部署生产 Release。
- 回滚：移除 Uvicorn 依赖、Vite 开发代理、smoke 和对应文档即可；无 Schema/Migration/数据变化。

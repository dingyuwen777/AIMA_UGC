---
schema: rvc-change/v1
id: CHG-20260813-local-dev-startup
title: 本地开发启动、环境引导与联调闭环
level: L3
status: ready_for_review
owner: dingyuwen777
branch: build/local-dev-startup
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [toolchain, platform, frontend, developer-experience]
affected_paths: [.uv-version, pyproject.toml, uv.lock, frontend/vite.config.ts, scripts/setup_dev_environment.cmd, scripts/setup_dev_environment.ps1, scripts/dev/, .github/workflows/ci.yml, README.md, docs/环境运行与部署.md, docs/blueprint/README.md, docs/blueprint/07-技术决策与实施门禁.md, changes/active/CHG-20260813-local-dev-startup/CHANGE.md]
contracts: []
data_changes: []
---

# 目标

让开发者从最新 `main` 克隆仓库后具备两条稳定路径：

1. Windows x64 开发机可双击 `scripts/setup_dev_environment.cmd` 一键检查并准备 Python / Node / npm / uv 与项目依赖；中国大陆环境统一使用仓库批准的国内镜像；版本不符时在有安全卸载依据的情况下先提示用户是否主动卸载旧版本；
2. 环境就绪后用两个明确命令分别启动 FastAPI 与 Vite，并通过 Vite 开发代理访问后端现有 `/health/live`，形成可重复验证的本地前后端启动闭环。

同时建立长期维护的环境、启动与生产部署入口文档。

# L3 方案比较与最终决定

## Windows 环境引导入口

### 方案 1：winget 全自动

优点：代码少，安装/升级/卸载统一。缺点：依赖本机 winget、组织策略和源状态；不利于固定制品来源和清晰展示卸载选择。**不采用。**

### 方案 2：PowerShell + 固定安装包/Registry

PowerShell 自身在受支持 Windows 上可用，不依赖 Python/Node 预装；可以读取仓库版本事实、展示 GUI、读取 Windows Uninstall Registry、执行签名/哈希验证、只在用户确认后卸载。**采用。**

### 方案 3：把运行时二进制提交到 Git

离线性强，但 Git 体积、二进制签名、架构矩阵和版本升级会成为仓库维护负担。当前不是离线开发机需求。**不采用。**

## 国内源

最终固定：

- Python Windows 安装包：清华 TUNA Python 镜像；
- PyPI、uv 自身和 Python 项目依赖：清华 TUNA PyPI；
- Node Windows MSI / `SHASUMS256.txt`：npmmirror Node 二进制镜像；
- npm 自身和前端依赖：`registry.npmmirror.com`。

不自动回退境外运行时源；镜像失败时打印具体 URL 并失败。包源仅在脚本当前进程/命令中生效，完成后恢复原环境变量，不永久污染开发者其他项目的全局 pip/uv/npm 配置。

# 安全与兼容约束

- Python/Node 旧版本默认不卸载；只列出 Windows 已注册旧安装并询问 `[y/N]`。
- Python 支持多版本并存；目标 Python 可通过直接路径或 Windows Python Launcher 发现，项目由 `.python-version + uv` 选目标解释器，不要求旧 Python 从全局 PATH 消失。
- Node 标准 MSI 可能在统一安装位置执行产品升级；脚本的“不主动卸载”不等于承诺 Node 多版本并存。
- npm 标准全局安装不提供并行版本；目标不符时明确询问是否替换当前 npm，用户拒绝则停止并说明仓库工具链未就绪。
- 旧 uv 只有位于 `%USERPROFILE%\.local\bin` 时才允许用户选择自动删除；其他来源视为可能由第三方包管理器所有，不自动删除。
- 不使用 `Win32_Product`，避免触发 MSI repair；卸载只依赖 Windows Uninstall Registry 中已注册的产品码/卸载命令。
- Python 安装包要求 Authenticode `Valid`；Node MSI 要求镜像 `SHASUMS256.txt` SHA-256 一致且 Authenticode `Valid`。
- uv 通过目标 Python + TUNA PyPI 精确安装；最多把目标 Python `Scripts` 加入当前用户 PATH，不改 Machine PATH、不删除其他 PATH 项。
- 不永久修改 `ExecutionPolicy`、系统代理、证书或安全软件。
- Windows CI 只做非破坏性验证，不卸载/安装共享 Runner 软件、不自动操作 GUI。

# 成功标准

- [x] Uvicorn `0.52.2` 进入根 Python 锁，无需额外全局安装即可启动后端。
- [x] 后端正式本地开发命令固定 `127.0.0.1:8090` 并验证 `--reload --reload-dir backend/src`。
- [x] Vite 固定 `127.0.0.1:5173`、`strictPort=true`，代理 `/health`、`/api` 到 8090。
- [x] CI 实际同时启动 Uvicorn 与 Vite，并验证后端直连、前端首页和 Vite 代理。
- [x] `.uv-version` 固定 uv `0.12.3`，正式 CI 和 Windows 环境脚本都读取该机器事实。
- [x] `scripts/setup_dev_environment.cmd` 可双击调用 Windows PowerShell，不依赖 Python/Node 预装。
- [x] PowerShell 引导检测 Python/Node/npm/uv；缺失或不符时进入目标安装/升级流程。
- [x] Python/Node 旧版本先提示是否卸载；默认保留；拒绝不触发静默删除。
- [x] 国内源覆盖 Python 安装包、PyPI/uv/Python 依赖、Node MSI、npm/前端依赖；无自动境外回退。
- [x] Python/Node 制品保持签名/哈希完整性检查。
- [x] 工具满足后自动执行 `uv lock --check`、`uv sync --locked`、`npm ci --prefix frontend` 和 Python package import 验证。
- [x] Windows PowerShell 5.1 CI 验证脚本解析、目标 Python 发现、国内源精确 URL、`.cmd` 入口、无境外运行时源残留及安全静态门禁。
- [x] `README.md`、`docs/环境运行与部署.md`、Blueprint README 和 Blueprint 07 与当前实现一致；生产仍明确 No-Go。
- [x] 现有 HTTP Contract、固定 OpenAPI、生成 Client 和 API 行为未变。

# 非目标

- 不实现 Linux/macOS 自动系统运行时安装器；这两个平台继续按文档手工准备锁定版本。
- 不自动安装 Git、Docker、IDE、PostgreSQL 或当前本地启动不需要的系统软件。
- 不自动启动长期运行的 API/Vite 进程；环境初始化完成后打印正式启动命令。
- 不实现 Stage 2 的 PostgreSQL、`/health/ready`、Config/Secret/Logging/Artifact、Worker/Scheduler/Migration。
- 不实现 Dockerfile、Compose、Release Bundle、备份或生产部署自动化。
- 不修改 `/health/live` Contract，不新增业务 API，不增加 CORS。

# TDD / 实际验证证据

## 本地启动 Red / Green

- Red Run `31681724208` / job `94388453966`：在 Uvicorn 尚未进入依赖时，`Local development startup smoke` 按 `Failed to spawn: uvicorn` / `No such file or directory` 正确失败。
- Lock bootstrap Run `31681862046` / job `94388891262`：Python 3.14.7 + uv 0.12.3 生成 Uvicorn 依赖锁；临时写权限 workflow 随后删除。
- Green Run `31681920014` / job `94389070648`：后端直连、Vite 首页、Vite 代理、Contract、质量脚本、Wheel、前端检查全部通过。
- Run `31682437917` / job `94390723839`：README/运行文档中的 `--reload --reload-dir backend/src` 正式后端命令通过完整 CI。

## Windows 环境引导验证

- Run `31683601743`：Windows PowerShell 5.1 首次静态/纯函数门禁通过；Ubuntu job 暴露 CI 对 `uv --version` 输出格式断言过严，uv 实际已成功安装。修正断言，没有改变 uv 版本。
- Run `31683683182`：Ubuntu Stage 1 与 Windows bootstrap 双 Job 全绿。
- Run `31684963946` / Windows job `94398770263`：新增目标 Python 实际路径验证后，门禁捕获 PowerShell → Python `-c` 引号传递错误；按真实错误修正，不降低门禁。
- TUNA PyPI `simple/uv` 已核验存在 `uv-0.12.3-py3-none-win_amd64.whl`；国内 uv 安装因此改为目标 Python + TUNA PyPI，不再调用境外 Astral installer。
- 最终国内源代码/CI head `3cc365894e68ccb3e1e8a9257aad0e1501c46f04`：PR CI Run `31685192802` 全绿，Windows 门禁验证 TUNA Python、TUNA PyPI、npmmirror Node、npmmirror npm 的精确配置以及无境外运行时源残留。
- Blueprint/README/运行文档同步 head `bbba2f9cf2eece1a2cb76f9b3d9a3a040c1e434e`：PR CI Run `31685616287` 全绿。

# 两阶段 Review

## 需求符合性

复核 `main...build/local-dev-startup`：变更只覆盖本地 ASGI 运行依赖、Vite 开发代理、local smoke、Windows 开发环境引导、CI 与运行/Blueprint 文档。用户要求的“本机没有 Python/Node/npm/uv 时准备目标版本；版本不符时升级；可安全识别的旧 Python/Node 先询问是否卸载；中国大陆相关安装/依赖统一国内源”均有对应实现和门禁。没有进入数据库、业务 API、Docker 生产部署、CORS 或 Stage 2 实现。

## 代码质量与安全

复核 `pyproject.toml`、`uv.lock`、`vite.config.ts`、`check_local_stack.py`、Windows `.cmd/.ps1`、CI 和文档：

- 开发启动复用正式 FastAPI `app` 和 Vite server，smoke 只观察 HTTP，不复制业务逻辑；
- 一键入口不依赖 Python/Node；目标版本均来自机器版本文件；
- 国内源是固定显式来源，临时包源在 `finally` 恢复，不永久覆盖开发者全局配置；
- Python/Node 镜像制品继续做签名/哈希检查；
- 没有 `Win32_Product`、永久 `Set-ExecutionPolicy`、系统代理/证书修改、静默卸载或未知目录 uv 删除；
- Python 多版本并存与 Node/npm 无并行保证的差异被明确处理；
- 生产文档仍为 No-Go，没有把 `vite dev`、Uvicorn reload 或 Windows 环境脚本伪装成生产部署。

未发现严重或重要问题。真实 Windows GUI 安装/卸载没有在共享 CI 执行，这是有意的安全边界，已在正式文档中明确。

# 文档同步

- `README.md`：Windows 一键环境入口、国内源策略、启动和 smoke 最短路径。
- `docs/环境运行与部署.md`：开发机版本、国内源、安装/升级/卸载边界、本地联调、常见问题、生产 No-Go。
- `docs/blueprint/README.md`：操作入口和 Stage 1 当前事实导航。
- `docs/blueprint/07-技术决策与实施门禁.md`：1.2 → 1.5，依次固化 Uvicorn/本地启动、Windows 环境引导、国内源供应链边界。
- `01/04/05/06` 复核后不需要修改；其架构、API、生产 Release 和阶段边界仍成立。

# Git / 发布

- 分支：`build/local-dev-startup`
- PR：#3 `补齐本地开发启动与联调闭环`，待当前 Review 证据 head CI 全绿后转 Ready 并合并。
- 生产发布：不适用；生产仍为 No-Go。
- Migration / 数据变化：无。
- 回滚：移除 Uvicorn/Lock、Vite 代理、smoke、Windows 引导、`.uv-version` 和对应文档/CI；无 Schema/Migration/数据恢复步骤。

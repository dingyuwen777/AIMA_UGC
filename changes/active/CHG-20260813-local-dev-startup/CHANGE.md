---
schema: rvc-change/v1
id: CHG-20260813-local-dev-startup
title: 本地开发启动、环境引导与联调闭环
level: L3
status: in_progress
owner: dingyuwen777
branch: build/local-dev-startup
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [toolchain, platform, frontend, developer-experience]
affected_paths: [.python-version, .node-version, .uv-version, pyproject.toml, uv.lock, frontend/package.json, frontend/vite.config.ts, scripts/setup_dev_environment.cmd, scripts/setup_dev_environment.ps1, scripts/dev/, .github/workflows/ci.yml, README.md, docs/环境运行与部署.md, docs/blueprint/README.md, docs/blueprint/07-技术决策与实施门禁.md, changes/active/CHG-20260813-local-dev-startup/CHANGE.md]
contracts: []
data_changes: []
---

# 目标

让开发者从最新 `main` 克隆仓库后具备两条稳定路径：

1. Windows 开发机可双击 `scripts/setup_dev_environment.cmd` 一键检查并准备 Python / Node / npm / uv 与项目依赖；缺失时使用官方来源安装，版本不符时在执行升级前提示用户是否主动卸载旧版本；
2. 环境就绪后用两个明确命令分别启动 FastAPI 与 Vite，并通过 Vite 开发代理访问后端现有 `/health/live`，形成可重复验证的本地前后端启动闭环。

同时建立长期维护的环境、启动与生产部署入口文档。

# L3 设计结论

## 方案比较

### 方案 1：winget 全自动

优点：代码少，安装/升级/卸载统一。缺点：依赖本机 winget 和源状态；安装行为可能被组织策略或源配置改变；无法稳定满足“调用官方原始安装包并由用户决定是否卸载旧版”的需求。**不采用。**

### 方案 2：官方安装包 / 官方安装器 + PowerShell 引导

Python 使用 python.org 当前冻结版本的传统 Windows 安装器并保留 GUI；Node 使用 nodejs.org 精确版本 MSI；uv 使用 Astral 支持精确版本 URL 的官方 PowerShell installer；npm 优先随目标 Node 安装，只有 Node 已正确而 npm 单独漂移时才精确升级。脚本自身只依赖 Windows PowerShell，因此即使 Python/Node 均不存在也可运行。**采用。**

### 方案 3：把运行时二进制放进仓库

优点：离线可控。缺点：Git 体积和供应链维护成本高，二进制签名/升级/架构矩阵会变成仓库责任，且当前不是离线开发环境需求。**不采用。**

# 安全与兼容约束

- 脚本默认不卸载任何现有软件；只有检测到版本不符时显示已发现旧版本并询问用户是否主动卸载，默认答案为“否”。
- Python 不同版本允许并存；若用户选择保留旧版，脚本只安装目标版本并要求最终 `python --version` 真正解析到仓库版本，否则明确失败，不静默改用错误解释器。
- Node 官方 MSI 对同一标准安装位置可能执行产品升级；用户选择“不卸载”只表示脚本不先主动卸载，不能承诺 MSI 能永久并存多个 Node 主版本。脚本必须明确提示该边界。
- uv/npm 通常是单一命令位置的工具升级，不承诺并存多个全局版本；对来源不明的 uv 安装不直接删除，避免破坏其他包管理器所有权。
- 不使用 `Win32_Product`，避免触发 MSI repair；已安装程序只读 Windows Uninstall Registry。
- 下载只使用固定官方 HTTPS 来源。Node MSI 用官方 `SHASUMS256.txt` 校验 SHA-256；Python installer 校验 Windows Authenticode 有效签名；uv 使用带精确版本号的 Astral 官方 installer URL。
- 不静默提升权限。Python 默认每用户 GUI 安装；Node MSI 如需管理员权限由 Windows/UAC 正常提示。
- 不修改系统代理、证书、ExecutionPolicy 永久值或防病毒设置；PowerShell `ExecutionPolicy Bypass` 只用于当前子进程运行已下载的精确 uv installer。
- 当前一键环境引导只支持 Windows x64；其他平台继续使用文档中的手工锁定安装步骤，不伪装已支持。

# 成功标准

- [x] Uvicorn 已进入根 Python 锁并完成本地双服务 Red/Green。
- [x] 后端本地开发命令固定 `127.0.0.1:8090` 并已验证 `--reload`。
- [x] Vite 固定 `127.0.0.1:5173`，代理 `/health`、`/api` 到 8090。
- [ ] 新增 `.uv-version`，正式 CI 和环境脚本从机器版本文件读取 uv 目标，不再在脚本复制版本号。
- [ ] `scripts/setup_dev_environment.cmd` 可直接双击调用 PowerShell，不依赖 Python/Node 预先存在。
- [ ] PowerShell 引导器检测 Python / Node / npm / uv 当前版本；缺失时安装，版本不符时先展示旧版本并询问是否卸载，再继续目标版本安装/升级。
- [ ] Python 使用官方 GUI 安装器，Node 使用官方 MSI，uv 使用精确版本官方 installer，npm 随 Node 或精确全局升级。
- [ ] 工具链全部达到仓库目标版本后，脚本实际执行 `uv sync --locked` 与 `npm ci --prefix frontend`，再验证 Python package 可导入。
- [ ] Windows CI 至少使用 Windows PowerShell 5.1 解析脚本、加载纯函数、验证目标版本来源、官方精确 URL 构造和版本解析，不在 CI 修改 Runner 已安装软件。
- [ ] `docs/环境运行与部署.md` 把一键脚本作为 Windows 首选路径，并保留手工安装回退；生产部署仍明确 No-Go。
- [ ] `07` 只在 Windows CI 通过后记录 `.uv-version` 和 Windows 环境引导的机器事实。
- [ ] 现有 Contract、OpenAPI、生成 Client、API 行为和 Stage 1 质量门禁保持不变。

# 非目标

- 不实现 Linux/macOS 自动安装器；这两个平台继续按文档手工准备锁定环境。
- 不自动安装 Git、Docker、IDE、数据库或其他当前本地启动不需要的系统软件。
- 不自动启动长期运行的 API/Vite 进程；环境脚本完成依赖准备后打印正式启动命令。
- 不实现 PostgreSQL、`/health/ready`、Config/Secret/Logging/Artifact 或四进程 Stage 2 基础。
- 不实现 Dockerfile、Compose、Release Bundle、Migration、备份或生产部署自动化。
- 不修改现有 `/health/live` HTTP Contract，不新增业务 API。
- 不增加 CORS 作为本地联调方案。

# 验证证据（已完成部分）

- Red Run `31681724208` / job `94388453966`：在 Uvicorn 尚未进入依赖时，smoke 按 `Failed to spawn: uvicorn` 正确失败。
- Lock bootstrap Run `31681862046` / job `94388891262`：用 Python 3.14.7 + uv 0.12.3 生成仅包含 Uvicorn 相关变化的 `uv.lock`；临时写权限 workflow 已删除。
- Green Run `31681920014` / job `94389070648`：后端直连、Vite 首页、Vite 代理、Contract、质量脚本、Wheel 和完整前端门禁全绿。
- 最终本地启动文档命令 Run `31682437917` / job `94390723839`：使用 `--reload --reload-dir backend/src` 的正式开发命令全绿。

# 后续任务

- [ ] 建立 `.uv-version` 并让 CI 使用。
- [ ] 实现 Windows PowerShell 引导器与 `.cmd` 一键入口。
- [ ] 增加 Windows PowerShell 5.1 非破坏性 CI 验证。
- [ ] 更新 README、环境运行部署文档和 Blueprint 07。
- [ ] 重新运行 Linux Stage 1 + Windows bootstrap 两类 CI。
- [ ] 两阶段 Review；PR 合并后重新验证 `main`，再归档 Change。

# Git / 发布

- 分支：`build/local-dev-startup`
- PR：#3
- 生产发布：不适用；本 Change 不产生可部署生产 Release，生产状态保持 No-Go。
- Migration / 数据变化：无。
- 回滚：删除 Windows 环境引导与 `.uv-version`，恢复 CI uv 固定方式，并回退 Uvicorn/Vite/smoke/文档相关变化；无 Schema/Migration/数据恢复步骤。

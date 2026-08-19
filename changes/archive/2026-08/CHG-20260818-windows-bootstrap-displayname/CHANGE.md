---
schema: rvc-change/v1
id: "CHG-20260818-windows-bootstrap-displayname"
title: "修复Windows环境引导严格模式对象属性失败"
level: L2
status: done
owner: "dingyuwen777"
branch: "main"
created: 2026-08-18
updated: 2026-08-19
depends_on: []
affected_areas:
  - "windows-bootstrap"
affected_paths:
  - "scripts/setup_dev_environment.ps1"
  - ".github/workflows/ci.yml"
  - "docs/环境运行与部署.md"
contracts: []
data_changes: []
---

# 目标

让 Windows x64 环境引导在 PowerShell 5.1 StrictMode 下安全处理缺少 `DisplayName` 的卸载注册表项、单条旧版本记录和 Node/npm/uv 安装边界，并继续完成版本判断、用户卸载决策、目标工具验证和项目依赖安装。

# 最终结果

- [x] 缺少 `DisplayName` 的注册表项不再触发 `PropertyNotFoundStrict`，合法 Node.js 项仍被识别；
- [x] 0/1/N 条旧 Node 记录均被固定为数组语义，不再在 `.Count` 处失败；
- [x] 保留 StrictMode、注册表 Provider、旧版本默认保留和用户交互卸载边界；
- [x] npm 安装使用当前解析到的 `npm.cmd` 所在 prefix，避免 PATH 中旧 npm 遮蔽升级结果；
- [x] 国内镜像不再让 PyPI registry URL 差异被误判为 `uv.lock` 漂移；锁定版本/哈希仍受验证；
- [x] Python/Node/npm/uv、项目依赖和实际安装路径有明确可见输出；
- [x] Windows bootstrap CI 纯逻辑/静态安全门禁持续通过。

# 根因与关键决策

1. PowerShell StrictMode 会把不存在的 `$item.DisplayName` 视为终止错误，因此先通过 `PSObject.Properties['DisplayName']` 判断属性存在再读取；
2. PowerShell 会枚举单元素函数返回值，因此调用方使用数组子表达式固定 0/1/N 条结果的集合语义；
3. npm 全局升级使用当前 `npm.cmd` 父目录作为一次性 `--prefix`，不永久修改用户配置；
4. `uv.lock` 的 Registry URL 是锁文件事实，国内镜像只用于实际下载，不改写锁文件身份；采用离线 lock 校验、导出锁定版本/哈希、镜像 `uv pip sync --require-hashes` 和本地 editable 安装；
5. 不使用 `Win32_Product`，不永久修改 ExecutionPolicy，不自动替用户卸载旧版本，也不绕过签名/哈希校验。

# 主要验证证据

原 Change 已记录以下 Red → Green 和真实边界验证：

- 缺少 `DisplayName`：Red `PropertyNotFoundStrict` → Green `Windows registry DisplayName regression passed.`；
- 单条 Node 注册记录：Red `.Count` StrictMode 失败 → Green 到达卸载询问边界；
- npm prefix：行为测试先因 helper 缺失 Red，实现后对 `D:\\nodejs\\npm.cmd` 返回 `D:\\nodejs`；隔离安装 `npm@11.17.0` 成功；
- `uv lock` + 国内镜像：旧 `UV_DEFAULT_INDEX=清华 + uv lock --check` Red，离线锁校验与按哈希同步 Green；
- 正式项目依赖安装：后端锁定依赖、editable 包、`npm ci` 和 `import aima_ugc` 均成功；
- Node MSI 边界验证到签名/哈希校验和 `msiexec /i` 启动前，未替用户实际安装/卸载或弹 UAC；
- PowerShell 5.1 Parser、国内镜像、无境外 fallback、无 `Win32_Product`、无永久 `Set-ExecutionPolicy`、CMD 入口和完整纯逻辑流程均通过。

# 最新集成证据

PR #73 合并后的 main 文件树通过 PR #74 post-merge 验证候选 `ab29f4783972e72d105460971d21bd6ffdc39c28` 重新触发全部正式 Stage workflow，并取得 **12/12 success**。

总 CI Run `32209959634` 中 `Windows bootstrap` Job 完整 success；同一总 CI 的 Stage1、Stage2 Platform、Stage3A Database 也全部 success。该证据是在 P1、TikHub 目录重组与 Stage1–7 共享基线全部集成之后取得，证明本 Change 没有被后续工作破坏。

# 边界与未做事项

- 没有自动化执行完整 `setup_dev_environment.cmd` 去真实升级/卸载系统 Python/Node/npm/uv，因为这会触发用户交互和系统级变更；
- 没有擅自增加 `psycopg-binary` 或其他依赖；
- 不修改目标版本、PATH、代理、证书、安全软件、数据库、Migration 或公共 Contract。

# 两阶段复核

## 需求符合性

所有原成功标准均已满足，Windows bootstrap 入口、StrictMode、安全策略和用户卸载决策边界保持不变。

## 代码质量

修复集中于注册表安全读取、集合边界、npm prefix 与锁定依赖安装路径；无无关架构重构、依赖升级或公共 API 变化。最新整仓 CI 再次覆盖 Windows bootstrap。

# 交付

- 实现早已集成于 `main`；
- 本次只修正 Change 生命周期，不修改业务代码；
- 最新 post-merge 12/12 正式 workflow 已成功；
- `status: done`，归档于 `changes/archive/2026-08/`。

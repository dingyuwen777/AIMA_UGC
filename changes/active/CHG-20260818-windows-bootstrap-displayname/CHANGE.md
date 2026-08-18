---
schema: rvc-change/v1
id: "CHG-20260818-windows-bootstrap-displayname"
title: "修复Windows环境引导严格模式对象属性失败"
level: L2
status: ready_for_review
owner: "dingyuwen777"
branch: "main"
created: 2026-08-18
updated: 2026-08-18
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

Windows x64 环境引导在 PowerShell 5.1 严格模式下安全处理缺少 `DisplayName` 的注册表项和
单条旧版本注册记录，能够继续完成卸载决策、目标工具验证和项目依赖安装，并明确显示安装路径。

# 成功标准

- [x] `Get-AimaRegisteredPrograms` 遇到缺少 `DisplayName` 的对象时不抛异常且不返回该对象。
- [x] 同一批次中具有 `DisplayName=Node.js` 的合法对象仍被返回，版本检测与旧版提示保持有效。
- [x] 脚本继续使用注册表 Provider，不引入 `Win32_Product`，不关闭 StrictMode，不改变默认保留
      旧版本、交互卸载、国内源、签名与哈希校验策略。
- [x] PowerShell 5.1 解析、回归检查和仓库 Windows bootstrap 静态安全门禁通过。
- [x] 单条旧 Node 注册记录不会因 PowerShell 管道自动展开而在 `.Count` 处失败，并能到达卸载询问边界。
- [x] Python/Node 旧版本选择结果、Node 默认安装目录、目标工具实际路径和项目依赖路径均有明确输出。
- [x] 纯逻辑全流程能够从 Node/npm 版本漂移继续到项目依赖安装阶段。
- [x] npm 目标版本安装到当前解析到的 `npm.cmd` 所在 prefix，避免被 PATH 中的旧 npm 遮蔽。
- [x] 国内镜像不会使 PyPI 来源的 `uv.lock` 被误判为漂移；依赖仍按锁定版本和哈希安装。

# 范围

- `Get-AimaRegisteredPrograms` 对可选注册表属性的安全访问；
- Windows bootstrap CI 纯逻辑回归检查；
- 单元素/空集合的 PowerShell 5.1 参数边界；
- 旧版本保留提示及工具、项目依赖安装路径输出；
- 当前 Change 的诊断、范围和验证证据。

# 非目标

- 自动化测试不实际安装、升级或卸载 Python、Node、npm、uv；真实依赖安装仅在工具链满足后执行；
- 不修改目标版本、镜像地址、PATH、ExecutionPolicy、系统代理、证书或安全软件；
- 不改变 Node MSI 的交互安装流程，不处理工作区中其他目录重构和 Provider 变更。

# 必须保持不变

- `.cmd` 双击入口和 PowerShell 5.1 兼容性；
- `.python-version`、`.node-version`、`.uv-version`、`frontend/package.json` 的版本事实源；
- 旧 Python/Node 默认不卸载，只有用户明确确认才调用注册卸载器；
- 国内源无境外自动 fallback，安装制品继续执行 Authenticode/SHA-256 校验；
- 用户当前所有未提交修改保持不变。

# 关键决策

- 根因是卸载注册表中允许存在没有 `DisplayName` 的键，而脚本在检查属性存在前直接读取
  `$item.DisplayName`；StrictMode 把不存在属性变成终止错误。
- 第二个根因是 PowerShell 会枚举函数返回的单元素数组；只有一条旧 Node 记录时，调用方得到
  不带 `Count` 属性的普通注册表对象，StrictMode 再次把 `$oldPrograms.Count` 变成终止错误。
- 保留 StrictMode；通过 `PSObject.Properties['DisplayName']` 先判断属性存在，再读取值并过滤
  空字符串。这样只忽略本来就不是可展示程序的注册表项，不扩大安装或卸载范围。
- 回归测试使用内存构造的注册表对象和函数级命令替身，不访问真实注册表，不触发 MSI/UAC。
- 在调用方使用数组子表达式固定 `0/1/N` 条记录均为数组；保留 StrictMode，并允许卸载确认函数
  接收空集合，不改变用户决定是否卸载的交互边界。
- npm v11 在 Windows 的全局安装把包和可执行入口写入命令级 `prefix`；脚本使用当前解析到的
  `npm.cmd` 父目录作为一次性 `--prefix`，不永久修改用户 npm 配置，同时保证升级后的命令仍由
  当前 PATH 命中。
- `uv.lock` 记录 Registry URL，直接把清华地址设为 `UV_DEFAULT_INDEX` 后执行 `uv lock --check`
  会把只属于镜像地址差异的结果误判为需要更新。改为离线检查并导出锁定版本/哈希，再通过清华
  索引执行 `uv pip sync --require-hashes`，最后从本地仓库安装 editable 包；不改锁文件，也不回退
  境外下载。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立缺少 `DisplayName` 的失败测试并确认修复
- [x] 建立单条旧 Node 注册记录的失败测试并确认 Red
- [x] 完成单元素集合和安装路径输出实现
- [x] 同步受影响文档
- [x] 取得本轮新鲜验证证据

# 验证

## 计划

- 目标测试：模拟一个缺少 `DisplayName` 的卸载项和一个合法 Node.js 项，调用正式枚举函数。
- 相关测试：现有 Windows bootstrap 版本、国内源、静态安全纯逻辑检查。
- 纯逻辑流程：模拟 Node/npm 版本漂移和安装完成状态，确认最终调用项目依赖安装入口。
- 静态检查/构建：Windows PowerShell 5.1 Parser、禁止 `Win32_Product`/永久
  `Set-ExecutionPolicy`、文档与 Secret 门禁。

## 新鲜证据

- Red：PowerShell 5.1 中 dot-source 正式脚本，使用函数级 `Get-ItemProperty` 替身返回一个
  缺少 `DisplayName` 的对象和一个合法 Node.js 对象；退出码 1，正式实现第 234 行产生
  `PropertyNotFoundStrict`，与用户现场一致。
- Green：相同 PowerShell 5.1 回归命令退出码 0，输出
  `Windows registry DisplayName regression passed.`。
- `.Count` Red：PowerShell 5.1 让 `Get-AimaNodeRegistrations` 替身返回单个对象，调用正式
  `Install-AimaNode`；退出码 1，正式实现产生 `PropertyNotFoundStrict,Install-AimaNode`。
- `.Count` Green：同一回归在数组固定后退出码 0，输出默认安装目录和
  `Single Node registration regression passed.`，且成功到达卸载询问替身边界。
- npm prefix Red/Green：新增行为测试先因 `Get-AimaNpmInstallPrefix` 不存在退出码 1；实现后在
  PowerShell 5.1 对 `D:\nodejs\npm.cmd` 返回 `D:\nodejs`，退出码 0。另以隔离临时 prefix 从
  npmmirror 实际安装 `npm@11.17.0`，生成目标 `npm.cmd` 并输出 `11.17.0`，退出码 0，临时目录已清理。
- 本机只读注册表验证：PowerShell 5.1 调用正式 `Get-AimaRegisteredPrograms` 和
  `Get-AimaNodeRegistrations -TargetVersion 24.19.0`，退出码 0；枚举 61 个具名程序，识别
  1 个旧 Node，版本 `24.18.1`。未触发下载、安装、卸载或 UAC。
- Windows bootstrap 完整纯逻辑/静态检查：PowerShell 5.1 Parser、目标版本、版本解析、
  Python 发现、国内镜像精确 URL、无境外源、无 `Win32_Product`、无永久
  `Set-ExecutionPolicy`、CMD 入口、空/单条注册记录、npm prefix、锁定依赖命令及模拟
  Node/npm 版本漂移到依赖安装的完整流程全部通过，退出码 0。
- 真实 Node 安装边界：正式 `Install-AimaNode` 使用 npmmirror 下载 `24.19.0` MSI，完成镜像
  SHA-256 与 Windows Authenticode 校验并到达 `msiexec /i`；测试用函数替身拦截启动，未实际
  安装、卸载或弹 UAC，退出码 0，临时目录已清理。
- uv 镜像 Red：在 `UV_DEFAULT_INDEX=清华` 下执行旧 `uv lock --check`，退出码 1，显示锁文件
  需要更新；移除镜像身份并执行 `uv lock --check --offline`，退出码 0。隔离虚拟环境按
  `export --locked --offline → pip sync --require-hashes → editable install` 从清华镜像安装 38 个
  锁定依赖并成功导入 `aima_ugc 0.1.0`，退出码 0，临时环境已清理。
- 真实项目依赖安装：正式 `Install-AimaProjectDependencies` 退出码 0；后端锁定依赖与 editable
  包同步成功，`npm ci` 安装 391 个包，`import aima_ugc` 输出 `0.1.0`；实际路径为
  `E:\work\03_Aima\code\AIMA_UGC\.venv\Scripts\python.exe` 和
  `E:\work\03_Aima\code\AIMA_UGC\frontend\node_modules`。
- `D:\python314\python.exe` 使用 PyYAML 6.0.3 解析 `.github/workflows/ci.yml`，退出码 0，
  `windows-bootstrap` Job 存在。
- `git diff --check`（本 Change 四个路径）：退出码 0。
- `uv run python scripts/quality/check_docs.py` 与 `scan_secrets.py`：退出码均为 0。
- `uv lock --check --offline`：退出码 0，39 个包的锁文件与声明一致。
- `npm --prefix frontend run build` 首次在受限沙箱内因 Vite 子进程 `spawn EPERM` 退出 1；按原命令
  在允许本地子进程的环境重跑退出码 0，TS7、`vue-tsc` 和 Vite build 全部完成，25 个模块转换，
  生成 `dist/index.html` 与 JS bundle，证明 `npm ci` 的 allow-scripts 警告未造成当前构建缺件。
- 本 Change 元数据通过 `rvc.py` 的 `read_change_metadata` 校验，输出
  `CHG-20260818-windows-bootstrap-displayname ready_for_review 3`。全局 `rvc.py status` 被外部
  并发提交中的 `CHG-20260818-stage1-stage7-comprehensive-corrective` 阻断：该文件把
  `contracts` 等列表写成当前轻量解析器不支持的单行 YAML 列表；本任务未修改该无关 Change。
- 未运行完整 `setup_dev_environment.cmd`：它会真实升级全局 Node/npm，且是否先卸载旧 Node 是
  用户交互决策。本轮已真实验证 Node 安装函数到 MSI 启动前边界、隔离 npm 安装和正式项目依赖
  安装，但没有替用户选择卸载或操作 MSI UI。

# 文档影响

- `docs/环境运行与部署.md` 已同步单/旧版本提示、工具与依赖实际路径，以及兼顾 portable
  `uv.lock` 和国内镜像的精确哈希安装流程；版本、公共 Contract、数据库和 Migration 不变。
- 当前锁定依赖只声明 `psycopg==3.3.4`；Windows 没有本机 libpq/binary wrapper 时，正式
  `import psycopg` 仍会失败。仓库现有测试文档和历史 Change 已把本地 PostgreSQL 验证限定到
  有 wrapper 的环境或 Linux CI；本 Change 未擅自增加 `psycopg-binary` 依赖。

# 交付

- Commit：工作期间出现外部并发提交 `4d493801bbdf2bf5e6e0a8b188464f68cc40c0b2`，其提交消息为
  `调整tikhub_test目录结构`，已把本 Change 大部分文件与大量无关修改一起提交并推送到
  `main/origin/main`；该提交/推送不是本任务 Agent 执行。之后补充的 CI 断言、文档措辞和本
  Change 证据仍未提交。
- PR：本任务未创建或操作。
- 发布：不涉及 Migration 或服务部署；未实际安装/卸载系统 Node/npm/Python/uv。

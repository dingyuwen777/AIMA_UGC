---
schema: rvc-change/v1
id: "CHG-20260818-windows-bootstrap-displayname"
title: "修复Windows环境引导严格模式对象属性失败"
level: L2
status: in_progress
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
- [ ] 单条旧 Node 注册记录不会因 PowerShell 管道自动展开而在 `.Count` 处失败，并能到达卸载询问边界。
- [ ] Python/Node 旧版本选择结果、Node 默认安装目录、目标工具实际路径和项目依赖路径均有明确输出。
- [ ] 纯逻辑全流程能够从 Node/npm 版本漂移继续到项目依赖安装阶段。
- [ ] npm 目标版本安装到当前解析到的 `npm.cmd` 所在 prefix，避免被 PATH 中的旧 npm 遮蔽。
- [ ] 国内镜像不会使 PyPI 来源的 `uv.lock` 被误判为漂移；依赖仍按锁定版本和哈希安装。

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
- [ ] 完成单元素集合和安装路径输出实现
- [ ] 同步受影响文档
- [ ] 取得本轮新鲜验证证据

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
- 本机只读注册表验证：PowerShell 5.1 调用正式 `Get-AimaRegisteredPrograms` 和
  `Get-AimaNodeRegistrations -TargetVersion 24.19.0`，退出码 0；枚举 61 个具名程序，识别
  1 个旧 Node，版本 `24.18.1`。未触发下载、安装、卸载或 UAC。
- Windows bootstrap 完整纯逻辑/静态检查：PowerShell 5.1 Parser、目标版本、版本解析、
  Python 发现、国内镜像精确 URL、无境外源、无 `Win32_Product`、无永久
  `Set-ExecutionPolicy`、CMD 入口及新增注册表回归全部通过，退出码 0。
- `D:\python314\python.exe` 使用 PyYAML 6.0.3 解析 `.github/workflows/ci.yml`，退出码 0，
  `windows-bootstrap` Job 存在。
- `git diff --check -- scripts/setup_dev_environment.ps1 .github/workflows/ci.yml`：退出码 0。
- `uv run python scripts/quality/check_docs.py` 与 `scan_secrets.py`：退出码均为 0。
- 未运行完整 `setup_dev_environment.cmd`：它下一步会打开 Node MSI、更新全局 npm 并安装项目
  依赖，属于真实系统变更和交互式安装；本轮以正式函数真实注册表只读验证和 CI 纯逻辑检查替代。

# 文档影响

- 不改变已批准使用方式、版本、镜像或交互语义，现有 Blueprint/运行文档无需修改；CI 和
  Change 记录缺陷边界与验证事实。

# 交付

- Commit：未授权，未执行。
- PR：未授权，未执行。
- 发布：不涉及依赖、Migration 或服务部署；未执行系统工具安装。

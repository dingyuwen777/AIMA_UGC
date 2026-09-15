# 本地 Release 离线包构建

本指南面向需要在 Windows 开发机上提前生成 AIMA_UGC 离线部署包的开发者。目标不是在本地复制一套 GitHub Release，而是通过同一个 Release Builder 生成与正式 Release 相同的 Bundle Contract，同时保留不同网络环境的下载源选择。

当前机器入口：

- PowerShell 一键入口：[`scripts/release/build_local_release.ps1`](../../scripts/release/build_local_release.ps1)；
- 跨平台核心实现：[`scripts/release/release_bundle.py`](../../scripts/release/release_bundle.py)；
- GitHub 正式发布入口：[`.github/workflows/release.yml`](../../.github/workflows/release.yml)。

## 1. 本地构建解决什么问题

GitHub Release 会在 GitHub Hosted Linux Runner 上生成 Linux/AMD64 Backend、Frontend 和 PostgreSQL 18.4 离线包。本地脚本让你在正式发布前直接在 Windows + Docker Desktop 上完成同一种构建和打包，便于把候选包复制到测试服务器验证。

两条路径共用同一个核心实现：

```text
本地 PowerShell ─┐
                 ├→ release_bundle.py
GitHub Release ──┘
                 → Linux/AMD64 images
                 → images.tar
                 → compose.yaml
                 → env.production.example
                 → release/migration manifest
                 → SHA256SUMS
                 → DEPLOY.md
                 → AIMA_UGC-<version>-deploy.tar.gz
```

本地脚本只负责 **Build + Package + 可选离线 Replay**。它不会创建或移动 Git Tag，不会 push GitHub，不会创建 GitHub Release，不会上传 GHCR，也不会部署生产服务器。

## 2. 为什么本地和 GitHub 使用不同下载源

镜像身份仍使用 [`Dockerfile`](../../Dockerfile) 和 [`compose.yaml`](../../compose.yaml) 中的官方 canonical reference；构建期 Debian / PyPI / npm 下载源通过 Profile 参数化。

### 本地默认：`china`

Windows / 中国网络默认使用项目现有国内源：

```text
Debian          → mirrors.aliyun.com
Debian Security → mirrors.aliyun.com
PyPI            → pypi.tuna.tsinghua.edu.cn
npm             → registry.npmmirror.com
```

Docker Hub 基础镜像仍保持 canonical image name；如果开发机已按 [`docs/guides/04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md) 配置 Docker Desktop registry mirror，会由 Docker Engine 自己加速下载。

### GitHub Release：`official`

[`.github/workflows/release.yml`](../../.github/workflows/release.yml) 显式选择 `official`：

```text
Debian          → deb.debian.org
Debian Security → deb.debian.org
PyPI            → pypi.org
npm             → registry.npmjs.org
```

`release-manifest.json` 会记录实际 `build_source_profile` 和完整 `build_upstreams`。两种 Profile 共用锁文件、Dockerfile、Bundle Contract、镜像 Tag、Schema/manifest 和服务器部署语义，但**不承诺两个网络源构建出的镜像 bit-for-bit 完全一致**。

## 3. Windows 前置条件

从仓库根目录运行，确保：

1. Docker Desktop 已启动，并能执行 `docker version` 和 `docker compose version`；
2. 使用仓库当前 Python 3.14.7 运行环境；精确版本以 [`pyproject.toml`](../../pyproject.toml) 和 CI 当前机器事实为准；
3. 当前目录是 AIMA_UGC 仓库根目录。

PowerShell、Windows Terminal 或 VS Code Terminal 都可以。

如果当前 PowerShell 禁止运行本地脚本，可以只对当前终端临时放开：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

关闭这个终端后该设置失效，不会永久修改系统策略。

## 4. 最常用：构建本地测试包

例如：

```powershell
.\scripts\release\build_local_release.ps1 -Version local-20260915
```

默认行为：

```text
SourceProfile = china
Verify        = false
Formal        = false
```

输出到已被 Git 忽略的：

```text
dist/releases/local-20260915/
├── release-bundle/
│   ├── images.tar
│   ├── compose.yaml
│   ├── env.production.example
│   ├── release-manifest.json
│   ├── migration-manifest.json
│   ├── SHA256SUMS
│   └── DEPLOY.md
└── AIMA_UGC-local-20260915-deploy.tar.gz
```

普通本地版本只要求是合法 Docker tag，可以使用 `local-20260915`、`test-abc123` 等名称。

## 5. 构建后立即验证离线包

如果希望证明最终 `images.tar` 可以独立启动：

```powershell
.\scripts\release\build_local_release.ps1 `
  -Version local-20260915 `
  -Verify
```

`-Verify` 会建立**独立 smoke 环境**：

```text
生成 Bundle
→ docker load images.tar
→ docker compose --no-build --pull never --wait
→ bootstrap / migrate / configure exit=0
→ readiness / 页面 smoke
→ 清理本次 smoke Compose 资源
```

Windows 验证时会临时叠加 [`compose.windows.yaml`](../../compose.windows.yaml) 解决 Docker Desktop 的 Linux 文件权限/存储适配，但它**不会进入最终 Release Bundle**。Bundle 中仍只有 canonical [`compose.yaml`](../../compose.yaml)，因此复制到 Linux 服务器后的部署模型不变。

本地 `-Verify` 不会删除开发机已有的候选镜像来证明严格隔离；GitHub Release PR dry-run 会执行更严格的 replay，在 `docker load` 前删除候选运行镜像并要求完整离线恢复。

## 6. Formal 模式：只允许最新 main

需要在本地生成一个可明确绑定最新远端 `main` 的正式版本候选时：

```powershell
.\scripts\release\build_local_release.ps1 `
  -Version v3.2.0 `
  -Formal `
  -Verify
```

`-Formal` 会 fail closed 检查：

```text
版本必须是 vMAJOR.MINOR.PATCH
+ Git 工作区必须 clean
+ 当前分支必须是 main
+ git fetch origin main 成功
+ HEAD 必须精确等于 origin/main
```

`-Formal` **仍然不会**创建 Tag、push、创建 Release 或上传 GHCR。它只约束本地构建所绑定的源码 revision。

## 7. 本地也可以使用官方源

需要排查国内镜像源差异或尽量接近 GitHub Runner 的构建下载来源时：

```powershell
.\scripts\release\build_local_release.ps1 `
  -Version local-official-test `
  -SourceProfile official `
  -Verify
```

这只改变构建期下载源，不会把本地构建变成 GitHub 正式发布，也不会绕过 GitHub Release 的 latest-main、required checks、Tag identity 或 GHCR private 门禁。

## 8. 自定义输出目录

默认输出是：

```text
dist/releases/<version>/
```

也可以指定：

```powershell
.\scripts\release\build_local_release.ps1 `
  -Version local-20260915 `
  -OutputRoot D:\AIMA-Releases
```

脚本会在该目录下继续创建 `<version>/release-bundle` 和对应部署压缩包。

## 9. 把本地包放到 Linux 服务器

将 `AIMA_UGC-<version>-deploy.tar.gz` 复制到目标服务器后，解压并以包内 `DEPLOY.md` 为准。核心链仍是：

```bash
sha256sum -c SHA256SUMS
docker load -i images.tar
cp env.production.example env.production
chmod 0600 env.production
# 编辑服务器自己的 env.production
docker compose --env-file env.production config --quiet
docker compose --env-file env.production up -d --no-build --pull never --wait
```

服务器持久化、Secret、Backup/Restore 和生产 Release 边界继续以 [`docs/operations/01_生产部署与离线Release方案.md`](../operations/01_生产部署与离线Release方案.md) 为准。不要把开发机的真实 `env.local` / `env.production`、数据库、Artifact 或 Secret 打入离线包。

## 10. 常见失败

### Docker Desktop 未启动

脚本会在 `docker version` / `docker compose version` 阶段失败。启动 Docker Desktop 后重新运行即可。

### 找不到 Python

PowerShell 会先找 `python`，再尝试 Windows `py -3`。两者都不存在时会停止，不会继续生成半成品 Bundle；实际使用时应保持仓库当前 Python 3.14.7 环境。

### Formal 提示工作区不干净

`-Formal` 不会自动 stash、reset 或删除你的修改。先自行处理当前工作区，再重新运行。

### Formal 提示不是最新 main

脚本会执行 `git fetch origin main`，随后要求当前 `HEAD == origin/main`。请正常同步并切换到最新 `main`，不要通过 force/reset 脚本绕过门禁。

### 国内源暂时不可用

可以临时改用：

```powershell
.\scripts\release\build_local_release.ps1 `
  -Version local-official-test `
  -SourceProfile official
```

如果问题来自 Docker Hub 镜像下载而不是 Debian/PyPI/npm，按 [`docs/guides/04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md) 检查 Docker Engine registry mirror。

# Windows Docker Desktop 完整 Compose 运行

本文说明在 Windows 开发机上，不进入 WSL 终端，直接从 CMD 或 PowerShell 使用标准 Docker Compose CLI 启动、停止和维护 AIMA_UGC 的完整 Docker Runtime。

它不是 Production 部署文档。公司 Linux 服务器与完整 Production 仍以 `docs/02_环境运行与部署.md`、`docs/roadmap/02_生产上线实施路线.md`、`docs/appendix/11_生产部署与离线Release方案.md` 为准。

Docker Hub mirrors、构建期包源、缓存和项目级重置见 [`04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)。

---

## 1. 为什么 Windows 仍需要 `compose.windows.yaml`

根 `compose.yaml` 面向 Linux/WSL/公司服务器，bootstrap 会为 PostgreSQL、应用目录和内部 Secret 固定 Linux UID/GID 与 mode。

Windows Docker Desktop 虽然运行 Linux 容器，但 Windows/NTFS 文件共享层不等于 Linux 原生文件系统。数据库和内部 Secret 不为了桌面兼容而放宽 Linux 权限门禁；另一方面，Artifact 和应用 `.log` 属于开发时需要直接查看的普通文件，不需要隐藏在 Docker volume 中。

因此 Windows 原生模式采用混合存储：

```text
compose.yaml
+ compose.windows.yaml
→ 同一业务 Runtime
→ Artifact / 应用日志：AIMA_HOST_ROOT bind mount
→ PostgreSQL / 内部 Secret：Docker-managed named volumes
```

`compose.windows.yaml` 只覆盖 storage source 和 bootstrap 对 Windows bind 目录的权限适配；API、Worker、Scheduler、Migration、PostgreSQL 版本、Health、端口、网络、外部 Secret 和业务配置仍来自根 `compose.yaml`。

---

## 2. 前提与首次环境初始化

- Windows 10/11；
- Docker Desktop 使用 Linux containers；
- 仓库代码已下载到本机；
- Docker Compose Plugin 可用。

首次准备环境运行：

```cmd
scripts\setup_dev_environment.cmd
```

Docker Hub mirror 列表的唯一仓库配置源是：

```text
scripts/config/docker_hub_mirrors.txt
```

该文件每个非空、非 `#` 注释行表示一个 HTTPS mirror，文件顺序就是 AIMA 管理的 mirror 顺序。Windows 和 Linux 环境初始化都读取这一份配置；增删或调整 AIMA mirror 顺序只修改该文件。

Docker Desktop 已安装时，初始化入口会读取该配置，并把 AIMA 管理的 mirrors 写入当前用户的 Docker Engine 配置：

```text
%USERPROFILE%\.docker\daemon.json
```

`daemon.json` 中 `registry-mirrors` 必须与 AIMA 配置文件精确一致，同时保留其他非 mirror Docker Engine 配置；文件已存在且需要修改时先生成时间戳备份。

Docker Desktop 的实际 `docker info` 结果可以同时包含由 Docker Desktop、管理员策略或其他配置来源加入的额外 registry mirrors。有效状态校验不要求 Docker Engine 只能存在 AIMA mirrors，而是要求 AIMA 配置文件中的 mirrors 全部出现，并保持 AIMA 自身的相对顺序。检测到额外 mirrors 时脚本会明确输出 warning，但不会把已生效的 AIMA mirrors 误判为失败。

如果磁盘配置和实际有效状态都已经满足，脚本直接跳过 Docker Desktop restart。确实需要重启时：

```text
docker desktop restart
→ 最长 60 秒命令超时
→ restart 返回后最多 20 秒验证有效 mirrors
→ 每次 docker info probe 最长 3 秒
→ 每 1 秒输出一次等待状态
```

以上时间都是失败保护上限，不是固定等待时间；条件满足后立即继续。真正超过边界仍未看到全部 AIMA mirrors 时脚本 fail closed，并输出最后观测到的有效 mirrors 和 daemon.json 恢复提示。

Docker Desktop 未安装或 Desktop CLI 不可用时脚本会明确提示跳过；安装或修复后重新运行该命令即可。

检查：

```powershell
docker version
docker compose version
docker info
```

---

## 3. 第一次创建 `env.production`

仓库提交：

```text
env.production.example
```

本机真实文件：

```text
env.production
```

它被 `.gitignore` 忽略，可能包含 TikHub / LLM API Key，不能提交 Git。

CMD：

```cmd
copy env.production.example env.production
```

PowerShell：

```powershell
Copy-Item env.production.example env.production
```

Windows 本地推荐把：

```dotenv
AIMA_HOST_ROOT=./.runtime
```

写入 `env.production`。相对路径以执行 Compose 命令时的项目目录为基准；从仓库根运行本文命令时，宿主可见文件位于：

```text
.runtime/
└─ runtime/
   ├─ data/
   └─ logs/
```

PostgreSQL 和内部 Secret 不进入这个目录，仍由 Docker named volume 管理。

---

## 4. Windows 正式启动命令

CMD 和 PowerShell 使用同一条命令：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

当前基础镜像固定为：

```text
python:3.14.7-slim-trixie
node:24.19.0-bookworm-slim
nginx:1.30.4-alpine3.24
postgres:18.4
```

`uv==0.12.3` 在 Python builder 中从配置的 PyPI 源安装，不额外拉取 GHCR uv 镜像。

Compose / Dockerfile 不包含第三方 Docker registry image reference。Docker Engine 根据首次配置的 `registry-mirrors` 处理 Docker Hub 下载，因此实际 mirror 可以变化，而本地和项目镜像名称保持官方 reference。

当前 Docker build 包源默认：

```text
Debian   mirrors.aliyun.com
PyPI     pypi.tuna.tsinghua.edu.cn
npm      registry.npmmirror.com
```

成功后：

```powershell
curl.exe -f http://127.0.0.1:8080/health/ready
```

---

## 5. 日常停止命令

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

`down` 会停止并删除本项目容器和 Compose 网络，但不会删除：

```text
AIMA_HOST_ROOT/runtime/data
AIMA_HOST_ROOT/runtime/logs
windows_postgres named volume
windows_internal_secrets named volume
```

因此下次启动继续使用原 PostgreSQL、Artifact、日志和内部 Secret。

如果只想临时停止容器而保留容器对象：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production stop
```

---

## 6. 查看状态、Artifact 与日志

查看服务：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production ps
```

如果使用推荐配置：

```dotenv
AIMA_HOST_ROOT=./.runtime
```

可以直接从 Windows 文件系统查看：

```text
.runtime\runtime\data\
.runtime\runtime\logs\api.log
.runtime\runtime\logs\worker.log
.runtime\runtime\logs\scheduler.log
```

其中 `runtime/data` 保存 Local ArtifactStore 的文件字节，例如 Excel Input、Raw、Excel Export、Markdown/Word Report 等实际 Artifact；具体业务父事实和 metadata 仍以 PostgreSQL 为准。

应用 `.log` 是人工排障主入口。Docker stdout/stderr 仍可以辅助查看：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production logs -f api
```

查看所有服务 stdout/stderr：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production logs -f
```

---

## 7. `env.production` 的边界

Windows 不新增第二套业务配置文件：

```text
env.local
→ 源码开发 launcher

env.production
→ 完整 Docker Runtime
→ Linux / WSL / Windows Docker Desktop / 公司服务器共用同一业务配置字段
```

Windows 原生模式只改变持久 storage 的宿主实现：

```text
AIMA_HOST_ROOT
→ Windows 下决定 Artifact / 应用日志的实际宿主位置

PostgreSQL / 内部 Secret
→ Windows 下由 compose.windows.yaml 改为 named volume
```

TikHub / LLM API Key 仍由 `env.production` 输入 Compose Secret。

`env.production` 不选择 Python/Node/Nginx/PostgreSQL 的 Docker registry 或镜像名称。Debian/PyPI/npm 构建期包源可以按机器覆盖，具体见 [`04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)。

---

## 8. Windows 数据存储

Windows 原生 Compose 的持久状态固定为：

```text
${AIMA_HOST_ROOT}/runtime/data
→ Artifact

${AIMA_HOST_ROOT}/runtime/logs
→ 应用 .log

windows_postgres
→ PostgreSQL 18 数据

windows_internal_secrets
→ postgres_password + Cursor signing keys
```

实际 volume 名会带 Compose project 前缀，可用：

```powershell
docker volume ls
```

查看 PostgreSQL 与内部 Secret volume。

旧版本 Windows Compose 曾使用：

```text
windows_runtime_data
windows_runtime_logs
```

保存 Artifact 和应用日志。升级到当前混合存储后，这两个旧 volume **不会自动迁移到 `AIMA_HOST_ROOT`，也不会由启动流程自动删除**。如果其中存在仍需保留的历史文件，应在人工确认后导出/迁移；不要为了清理旧 volume 影响当前 PostgreSQL 或内部 Secret。

---

## 9. 破坏性重置

只有确认 Windows 本地 AIMA 数据可以丢弃时才执行重置。

先删除容器、网络、PostgreSQL/internal-secret named volume 与项目镜像：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down -v --remove-orphans --rmi all
```

这里的 `-v` **不会删除 bind-mounted 的 Artifact 和应用日志**。如果也要清空这些宿主文件，需要根据 `env.production` 中实际 `AIMA_HOST_ROOT` 显式删除：

```text
${AIMA_HOST_ROOT}/runtime/data
${AIMA_HOST_ROOT}/runtime/logs
```

例如使用推荐的：

```dotenv
AIMA_HOST_ROOT=./.runtime
```

且当前 PowerShell 位于仓库根时，可以执行：

```powershell
Remove-Item -Recurse -Force .\.runtime\runtime\data -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\.runtime\runtime\logs -ErrorAction SilentlyContinue
```

这是显式破坏性操作；不要把它加入日常停止流程。

不要用：

```text
docker system prune -a --volumes
```

代替项目级重置。

---

## 10. WSL2 模式

如果仓库位于 WSL2 Linux 文件系统并从 WSL shell 运行 Compose，可直接使用根 `compose.yaml`：

```dotenv
AIMA_HOST_ROOT=./.runtime/compose
```

```bash
docker compose --env-file env.production up -d --build --wait
```

这是 Linux bind-mount 模型，包括 PostgreSQL、Artifact、日志和内部 Secret 都位于该 Linux Host Root 下。

如果直接从 Windows CMD / PowerShell 启动，则使用：

```text
compose.yaml + compose.windows.yaml
```

Windows 路线只有 Artifact/日志使用 Host Root；PostgreSQL/内部 Secret 是独立 named volumes。因此即使两个入口设置相似路径，它们也不是同一个 PostgreSQL 实例。

---

## 11. 公司服务器

公司服务器和完整 Production 使用宿主可见、可备份、可恢复且与 Release 解耦的数据根：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

服务器继续使用 Linux bind mount：

```text
/data/AIMA_UGC/postgres
/data/AIMA_UGC/runtime/data
/data/AIMA_UGC/runtime/logs
/data/AIMA_UGC/shared/secrets
```

Windows 混合存储 override 只属于开发机存储适配，不改变 Production Release、Backup/Restore 或 Rollback 设计。

---

## 12. 验证边界

永久 CI 验证：

1. Windows GitHub Runner 可从 CMD / PowerShell 解析 `compose.yaml + compose.windows.yaml + env.production`；
2. Linux Docker Engine 实际运行 Windows merged hybrid Runtime model，验证 bootstrap、PostgreSQL、Migration、Readiness、Artifact/日志 bind mount、宿主文件可见性、Secret mode 和重启持久化；
3. `down -v` 后宿主 Artifact/日志仍保留，而 PostgreSQL/内部 Secret 继续属于 named-volume 生命周期；
4. Dockerfile / Compose 的镜像 identity 与包源配置由仓库单元测试约束；
5. Windows GitHub Runner 直接加载 `configure_docker_desktop_mirrors.ps1`，验证“存在额外有效 mirrors 仍成功、缺少 AIMA mirror 失败、AIMA 相对顺序错误失败、daemon.json 继续精确受 AIMA 管理”；真实 Docker Desktop 应用结果由初始化脚本自身的有界 `docker info` probe 确认。

GitHub Hosted Windows Runner 本身不提供当前仓库可依赖的 Docker Desktop Linux-container Runtime，因此永久 CI 的真实容器 Golden Path 由 Ubuntu Docker Engine 验证 merged Compose 语义；具体开发机首次使用仍需要本机 smoke。

真实 Windows Docker Desktop 首次初始化运行：

```cmd
scripts\setup_dev_environment.cmd
```

随后：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
curl.exe -f http://127.0.0.1:8080/health/ready
```

并检查：

```text
${AIMA_HOST_ROOT}/runtime/data
${AIMA_HOST_ROOT}/runtime/logs/api.log
```

如果开发机出现 Docker Desktop 特有问题，应保留实际错误继续修复，不降低 PostgreSQL/Secret 与 Linux/Production 的安全门禁。

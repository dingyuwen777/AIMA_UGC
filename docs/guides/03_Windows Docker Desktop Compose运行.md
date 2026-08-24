# Windows Docker Desktop 完整 Compose 运行

本文说明在 Windows 开发机上，不进入 WSL 终端，直接从 CMD 或 PowerShell 使用标准 Docker Compose CLI 启动、停止和维护 AIMA_UGC 的完整 Docker Runtime。

它不是 Production 部署文档。公司 Linux 服务器与完整 Production 仍以 `docs/02_环境运行与部署.md`、`docs/roadmap/02_生产上线实施路线.md`、`docs/appendix/11_生产部署与离线Release方案.md` 为准。

Docker Hub mirrors、构建期包源、缓存和项目级重置见 [`04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)。

---

## 1. 为什么 Windows 仍需要 `compose.windows.yaml`

根 `compose.yaml` 面向 Linux/WSL/公司服务器，bootstrap 会为 PostgreSQL、应用目录和内部 Secret 固定 Linux UID/GID 与 mode。

Windows Docker Desktop 虽然运行 Linux 容器，但 Windows/NTFS 文件共享层不等于 Linux 原生文件系统。数据库和内部 Secret 不为了桌面兼容而放宽 Linux 权限门禁。

因此 Windows 原生模式采用：

```text
compose.yaml
+ compose.windows.yaml
→ 同一业务 Runtime
→ 持久 source 改为 Docker-managed named volumes
```

`compose.windows.yaml` 只覆盖 storage source；API、Worker、Scheduler、Migration、PostgreSQL 版本、Health、端口、网络、外部 Secret 和业务配置仍来自根 `compose.yaml`。

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

该文件每个非空、非 `#` 注释行表示一个 HTTPS mirror，文件顺序就是配置到 Docker Engine 的 mirror 顺序。Windows 和 Linux 环境初始化都读取这一份配置；增删或调整 mirror 顺序只修改该文件。

Docker Desktop 已安装时，初始化入口会读取该配置，并把 mirrors 合并到当前用户的 Docker Engine 配置：

```text
%USERPROFILE%\.docker\daemon.json
```

现有 Docker Engine 其他配置会保留；文件已存在时先生成时间戳备份。随后脚本重启 Docker Desktop，并持续通过 `docker info` 检查实际 `RegistryConfig.Mirrors`。只有预期 mirrors 全部按配置顺序生效才继续；在有界等待时间内仍未生效则失败，并保留备份路径供恢复。

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

`down` 会停止并删除本项目容器和 Compose 网络，但不会删除 named volumes。下次启动继续使用原 PostgreSQL、Artifact、日志和内部 Secret。

如果只想临时停止容器而保留容器对象：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production stop
```

---

## 6. 查看状态与日志

查看服务：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production ps
```

查看 API 日志：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production logs -f api
```

查看所有服务日志：

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

Windows 原生模式只改变四类持久 storage 的宿主实现，因此 `AIMA_HOST_ROOT` 不作为 Windows named-volume 的实际数据位置；它继续保留在同一配置 Schema 中供 Linux/WSL/服务器使用。

TikHub / LLM API Key 仍由 `env.production` 输入 Compose Secret。

`env.production` 不选择 Python/Node/Nginx/PostgreSQL 的 Docker registry 或镜像名称。Debian/PyPI/npm 构建期包源可以按机器覆盖，具体见 [`04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)。

---

## 8. Windows 数据存储

Windows 原生 Compose 使用 Docker Desktop 管理的 named volumes：

```text
windows_runtime_data
→ Artifact

windows_runtime_logs
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

查看。

---

## 9. 破坏性重置

只有确认 Windows 本地 AIMA 数据全部可以丢弃时执行：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down -v --remove-orphans --rmi all
```

`-v` 会删除当前 AIMA Compose project 的 PostgreSQL、Artifact、应用日志和内部 Secret。

不要把 `down -v` 当日常停止命令，也不要用：

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

这是 Linux bind-mount 模型。

如果直接从 Windows CMD / PowerShell 启动，则使用：

```text
compose.yaml + compose.windows.yaml
```

两种方式都是本地完整 Docker Runtime，但数据位置不同，不是同一个 PostgreSQL 实例。

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

Windows named-volume override只属于开发机存储适配，不改变 Production Release、Backup/Restore 或 Rollback 设计。

---

## 12. 验证边界

永久 CI 验证：

1. Windows GitHub Runner 可从 CMD / PowerShell 解析 `compose.yaml + compose.windows.yaml + env.production`；
2. Linux Docker Engine 实际运行 Windows named-volume Runtime model，验证 bootstrap、PostgreSQL、Migration、Readiness、Secret mode 和重启持久化；
3. Dockerfile / Compose 的镜像 identity 与包源配置由仓库单元测试约束；
4. Windows GitHub Runner 对 `configure_docker_desktop_mirrors.ps1` 做 PowerShell 语法解析；统一 mirror 配置、Windows/Linux 消费关系和重启后有界验证由仓库测试约束，真实 Docker Desktop 应用结果由初始化脚本自身的 `docker info` 检查确认。

真实 Windows Docker Desktop 首次初始化运行：

```cmd
scripts\setup_dev_environment.cmd
```

随后：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
curl.exe -f http://127.0.0.1:8080/health/ready
```

如果开发机出现 Docker Desktop 特有问题，应保留实际错误继续修复，不降低 Linux/Production 安全门禁。

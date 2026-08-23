# Windows Docker Desktop 完整 Compose 运行

本文只解决一个问题：**在 Windows 开发机上，不进入 WSL 终端，直接从 CMD 或 PowerShell 使用标准 Docker Compose CLI 启动、停止和维护 AIMA_UGC 的完整 Docker Runtime。**

它不是 Production 部署文档。公司 Linux 服务器与完整 Production 仍以 `docs/02_环境运行与部署.md`、`docs/roadmap/02_生产上线实施路线.md`、`docs/appendix/11_生产部署与离线Release方案.md` 为准。

首次 Docker build 的国内镜像/apt/PyPI/npm 加速、为什么本地 build 不等于公网发布，以及怎样只清理 AIMA 后重新开始，见 [`04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)。

---

## 1. 为什么 Windows 仍需要 `compose.windows.yaml`

根 `compose.yaml` 面向 Linux/WSL/公司服务器，bootstrap 会为 PostgreSQL、应用目录和内部 Secret 固定 Linux UID/GID 与 mode。

Windows Docker Desktop 虽然运行 Linux 容器，但 Windows/NTFS 文件共享层不等于 Linux 原生文件系统。数据库和内部 Secret 不应该为了桌面兼容而放宽 Linux 权限门禁。

因此 Windows 原生模式采用：

```text
compose.yaml
+ compose.windows.yaml
→ 同一业务 Runtime
→ 持久 source 改为 Docker-managed named volumes
```

`compose.windows.yaml` 只覆盖 storage source；API、Worker、Scheduler、Migration、PostgreSQL 版本、Health、端口、网络、外部 Secret 和业务配置仍来自根 `compose.yaml`。

`compose.windows.yaml` 是必要的存储适配层；不再需要额外的 CMD / PowerShell wrapper。

---

## 2. 前提

- Windows 10/11；
- Docker Desktop 已启动，并使用 Linux containers；
- 仓库代码已下载到本机；
- Docker Compose Plugin 可用。

从仓库根检查：

```powershell
docker version
docker compose version
```

---

## 3. 第一次只创建一次 `env.production`

仓库提交的是：

```text
env.production.example
```

真实本机文件：

```text
env.production
```

它被 `.gitignore` 忽略，可能包含 TikHub / LLM API Key，不能提交 Git。

### CMD

```cmd
copy env.production.example env.production
```

### PowerShell

```powershell
Copy-Item env.production.example env.production
```

然后编辑 `env.production`。后续启动、停止、查看状态和日志都直接使用标准 Docker Compose CLI，不再运行仓库 wrapper。

---

## 4. Windows 正式启动命令

CMD 和 PowerShell 使用完全相同的命令：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

这条命令会：

```text
缺少基础镜像
→ 自动 pull

AIMA backend/frontend 需要构建
→ 自动 build

已有可复用 image/layer/cache
→ Docker / BuildKit 自动复用

bootstrap
→ PostgreSQL
→ Migration
→ configure
→ API / Worker / Scheduler
→ Frontend
```

不要求提前手工 `docker pull`。

成功后：

```powershell
curl.exe -f http://127.0.0.1:8080/health/ready
```

---

## 5. 日常停止命令

推荐使用：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

`down` 会停止并删除本项目容器和 Compose 网络，但**不会删除 named volumes**。下次执行第 4 节启动命令时，继续使用原 PostgreSQL、Artifact、日志和内部 Secret。

如果只想临时停止容器而保留容器对象，也可以使用：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production stop
```

日常推荐 `down`，因为它能保持运行状态干净，同时数据仍由 named volumes 保留。

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

## 7. `env.production` 是否还是同一个

是。

Windows 不新增第二套业务配置文件：

```text
env.local
→ 源码开发 launcher

env.production
→ 完整 Docker Runtime
→ Linux / WSL / Windows Docker Desktop / 公司服务器共用同一业务配置字段
```

Windows 原生模式只改变四类持久 storage 的宿主实现，因此 `AIMA_HOST_ROOT` 不作为 Windows named-volume 的实际数据位置；它继续保留在同一配置 Schema 中，供 Linux/WSL/服务器使用。

TikHub / LLM API Key 仍由 `env.production` 输入 Compose Secret，不会因为 Windows override 变成普通业务容器环境变量。

当前中国网络默认构建源见 [`04_Docker国内构建源与本地重置.md`](04_Docker国内构建源与本地重置.md)。

---

## 8. Windows 数据存在哪里

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

这些数据由 Docker Desktop 管理，不要求你在仓库目录中手工维护 PostgreSQL 文件权限。

---

## 9. 破坏性重置

只有明确确认 Windows 本地 AIMA 数据全部可以丢弃时执行：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down -v --remove-orphans --rmi all
```

其中 `-v` 会删除当前 AIMA Compose project 的 named volumes，因此删除：

```text
PostgreSQL
Artifact
应用日志
内部 Secret
```

这和日常 `down` 完全不同。不要把 `down -v` 当停止命令。

也不要用：

```text
docker system prune -a --volumes
```

代替项目级重置，因为它可能删除 Docker Desktop 中其他项目的数据。

---

## 10. 和 WSL2 方式有什么区别

如果仓库位于 WSL2 Linux 文件系统，并且在 WSL shell 中运行 Compose，可以直接使用根 `compose.yaml`：

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

以及第 4 节的标准 Compose 命令。

两种方式都是本地完整 Docker Runtime，但数据位置不同，不应把它们理解为同一个 PostgreSQL 实例。

---

## 11. 为什么公司服务器不用 Windows override

公司服务器和完整 Production 需要宿主可见、可备份、可恢复且与 Release 解耦的固定数据根：

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

未来应用版本位于 `/data/AIMA_UGC/releases/<version>`，不能承载上述持久事实。

Windows named-volume override只是**开发机存储适配层**，不会改变 Production Release、Backup/Restore 或 Rollback 设计。

---

## 12. 当前验证边界

永久 CI 分两层证明：

1. Windows GitHub Runner 直接执行 `docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production config --services`，验证 CMD / PowerShell 都能使用标准 Compose CLI 和同一配置组合；
2. Linux Docker Engine 实际运行 `compose.yaml + compose.windows.yaml` 的 named-volume Runtime，验证 bootstrap、PostgreSQL、Migration、Readiness、Secret mode 和重启持久化。

GitHub Hosted Windows Runner 本身不作为真实 Docker Desktop Linux-container Runtime，因此首次在具体开发机使用时，仍应执行一次本机 smoke：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
curl.exe -f http://127.0.0.1:8080/health/ready
```

如果开发机出现 Docker Desktop 特有问题，应保留实际错误继续修复，而不是降低 Linux/Production 安全门禁。
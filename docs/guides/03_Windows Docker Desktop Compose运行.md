# Windows Docker Desktop 完整 Compose 运行

本文只解决一个问题：**在 Windows 开发机上，不进入 WSL 终端，也可以直接从 CMD 或 PowerShell 启动 AIMA_UGC 的完整 Docker Runtime。**

它不是 Production 部署文档。公司 Linux 服务器与完整 Production 仍以 `docs/02_环境运行与部署.md`、`docs/roadmap/02_生产上线实施路线.md`、`docs/appendix/11_生产部署与离线Release方案.md` 为准。

---

## 1. 为什么 Windows 不直接复用 `.runtime/compose` bind mount

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

---

## 2. 前提

- Windows 10/11；
- Docker Desktop 已启动，并使用 Linux containers；
- 仓库代码已下载到本机；
- Docker Compose Plugin 可用。

检查：

```powershell
docker version
docker compose version
```

---

## 3. CMD 启动

从仓库根执行：

```cmd
scripts\dev\compose_windows.cmd
```

第一次如果没有 `env.production`，脚本会从 `env.production.example` 创建一份并退出，要求先编辑配置。

编辑完成后再次执行同一命令：

```cmd
scripts\dev\compose_windows.cmd
```

默认等价于：

```cmd
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

可以直接传 Compose 子命令，例如：

```cmd
scripts\dev\compose_windows.cmd ps
scripts\dev\compose_windows.cmd logs -f api
scripts\dev\compose_windows.cmd down
```

---

## 4. PowerShell 启动

从仓库根执行：

```powershell
.\scripts\dev\compose_windows.ps1
```

如果执行策略阻止本地脚本，可以只对当前调用使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev\compose_windows.ps1
```

也可以传 Compose 子命令：

```powershell
.\scripts\dev\compose_windows.ps1 ps
.\scripts\dev\compose_windows.ps1 logs -f api
.\scripts\dev\compose_windows.ps1 down
```

---

## 5. `env.production` 是否还是同一个

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

---

## 6. Windows 数据存在哪里

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

## 7. 停止、重启和删除

普通停止：

```powershell
.\scripts\dev\compose_windows.ps1 down
```

或：

```cmd
scripts\dev\compose_windows.cmd down
```

**普通 `down` 不删除 named volumes。** 下次启动继续使用原 PostgreSQL、Artifact 和内部 Secret。

破坏性重置：

```powershell
.\scripts\dev\compose_windows.ps1 down -v
```

或者 CMD：

```cmd
scripts\dev\compose_windows.cmd down -v
```

`-v` 会删除本项目 Windows named volumes，从而删除本地数据库、Artifact、日志和内部 Secret。只有确认这些本地开发数据可以丢弃时才使用。

不要把这组 Windows 本地重置操作用于公司服务器或 Production。

---

## 8. 和 WSL2 方式有什么区别

如果仓库位于 WSL2 Linux 文件系统，并且你在 WSL shell 中运行 Compose，可以直接使用根 `compose.yaml`：

```dotenv
AIMA_HOST_ROOT=./.runtime/compose
```

```bash
docker compose --env-file env.production up -d --build --wait
```

这是 Linux bind-mount 模型。

如果你希望直接从 Windows CMD / PowerShell 启动，则使用本文的 Windows launcher + named-volume 模型。

两种方式都是本地完整 Docker Runtime，但**不要把二者的数据目录理解为同一个数据库实例**。

---

## 9. 为什么公司服务器仍然不用 Windows override

公司服务器和完整 Production 需要宿主可见、可备份、可恢复且与 Release 解耦的固定数据根：

```dotenv
AIMA_HOST_ROOT=/data/AIMA_UGC
```

因此服务器继续使用 Linux bind mount：

```text
/data/AIMA_UGC/postgres
/data/AIMA_UGC/runtime/data
/data/AIMA_UGC/runtime/logs
/data/AIMA_UGC/shared/secrets
```

未来应用版本位于 `/data/AIMA_UGC/releases/<version>`，不能承载上述持久事实。

Windows named-volume override只是**开发机存储适配层**，不会改变 Production Release、Backup/Restore 或 Rollback 设计。

---

## 10. 当前验证边界

永久 CI 分两层证明：

1. Windows GitHub Runner 实际执行 CMD / PowerShell launcher，并验证它们自动组合正确的 Compose 文件和参数；
2. Linux Docker Engine 实际运行 `compose.yaml + compose.windows.yaml` 的 named-volume Runtime，验证 bootstrap、PostgreSQL、Migration、Readiness、Secret mode 和重启持久化。

GitHub Hosted Windows Runner 本身不作为真实 Docker Desktop Linux-container Runtime，因此 CI 不应被描述成已经在真实个人 Windows Docker Desktop 上跑完完整业务栈。首次在具体开发机使用时，仍应执行一次本机 smoke：

```powershell
.\scripts\dev\compose_windows.ps1
curl.exe -f http://127.0.0.1:8080/health/ready
```

如果该开发机 smoke 出现 Docker Desktop 特有问题，应保留实际错误继续修复，而不是降低 Linux/Production 安全门禁。

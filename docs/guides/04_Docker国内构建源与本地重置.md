# Docker 国内下载源与本地重置

本文说明 AIMA_UGC 完整 Docker Runtime 的当前镜像身份、国内下载源、缓存和项目级重置方式。

公司 Linux 服务器和完整 Production Release 的长期边界仍以：

- [`docs/02_环境运行与部署.md`](../02_环境运行与部署.md)
- [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)
- [`docs/appendix/11_生产部署与离线Release方案.md`](../appendix/11_生产部署与离线Release方案.md)

为准。

---

## 1. 当前下载模型

AIMA 把“镜像身份”和“下载通道”分开：

```text
Dockerfile / Compose
→ 始终使用官方 Docker Hub image reference

Docker Hub 实际下载
→ 宿主 Docker Engine 的 registry-mirrors

Debian / PyPI / npm
→ Docker build 的独立国内包下载源
```

项目不会把第三方 Docker registry 域名写进 Dockerfile、Compose 或 `env.production` 的 image reference。

---

## 2. 官方 Docker 镜像身份

当前基础镜像固定为：

| 用途 | image reference |
| --- | --- |
| Python | `python:3.14.7-slim-trixie` |
| Node | `node:24.19.0-bookworm-slim` |
| Nginx | `nginx:1.30.4-alpine3.24` |
| PostgreSQL | `postgres:18.4` |

`uv` 固定为 `0.12.3`，在 Python builder 中通过 PyPI 安装，不再额外拉取 GHCR uv 镜像。

因此无论宿主 Docker 实际经过哪个镜像加速站，本地和项目都继续使用上表中的官方名称。

---

## 3. Docker Hub 国内 registry mirrors

Docker Hub mirror 列表的唯一仓库配置源是：

- [`scripts/config/docker_hub_mirrors.txt`](../../scripts/config/docker_hub_mirrors.txt)

配置规则：

```text
每个非空、非 # 注释行 = 一个 HTTPS mirror
文件顺序 = AIMA 管理的 mirror 顺序
Windows 与 Linux 初始化脚本共同读取这一份配置
```

增删 AIMA mirror 或调整顺序时，只修改该文件。脚本、测试和文档不维护第二份 URL 列表。

Docker Engine 同时设置：

```json
"max-download-attempts": 5
```

公共 mirrors 是外部网络服务，可能受到地域、限流、维护或上游状态影响。AIMA 使用多个候选入口与 Docker 下载重试降低单点风险；项目 image reference 始终保持官方名称。

### Windows

第一次准备环境时运行：

- [`scripts/setup_dev_environment.cmd`](../../scripts/setup_dev_environment.cmd)

Docker Desktop 已安装时，脚本读取统一 mirror 配置，并把 AIMA 管理的 mirrors 写入当前用户的 Docker Engine 配置：

```text
%USERPROFILE%\.docker\daemon.json
```

`daemon.json` 的 `registry-mirrors` 必须与 AIMA 配置文件精确一致，`max-download-attempts` 必须为 5；其他 Docker Engine 配置继续保留，文件需要修改时先生成时间戳备份。

Docker Desktop 的最终有效状态以：

```powershell
docker info --format '{{json .RegistryConfig.Mirrors}}'
```

为准。这个有效列表可以包含由 Docker Desktop、管理员策略或其他来源加入的额外 mirrors。AIMA 校验只要求统一配置文件里的 mirrors 全部存在并保持 AIMA 自身相对顺序，不要求有效列表与 AIMA 列表数量相等；额外 mirrors 会明确显示为 warning。

磁盘配置和有效状态都已满足时不会重启 Docker Desktop。需要重启时使用有界流程：

```text
docker desktop restart 最大 60 秒
restart 返回后有效状态验证最大 20 秒
每次 docker info probe 最大 3 秒
等待状态每 1 秒输出
```

这些数字都是失败保护上限，不是固定延迟；状态满足后立即继续。真正超时才 fail closed，并输出最后观测到的有效 mirrors 和恢复提示。

### CentOS Stream 9

首次初始化宿主：

```bash
sudo bash scripts/setup_dev_environment.sh
```

Linux 初始化脚本读取同一份：

- [`scripts/config/docker_hub_mirrors.txt`](../../scripts/config/docker_hub_mirrors.txt)

并将 mirrors 与 `/data/docker`、日志 driver/rotation 等既有 Docker Engine 设置合并到：

```text
/etc/docker/daemon.json
```

配置变更前保留原文件备份，校验 daemon 配置后安全启动或重启 Docker。

### 验证

Windows：

```powershell
docker info --format '{{json .RegistryConfig.Mirrors}}'
```

AIMA 配置文件中的有效行必须全部存在并保持相对顺序；额外有效 mirrors 允许存在。

Linux：

```bash
docker info
```

Linux 初始化脚本直接管理 daemon 的 `registry-mirrors` 列表，当前仍以统一配置文件为输入。

---

## 4. Docker build 国内包源

当前 Compose / Dockerfile 默认使用：

```dotenv
AIMA_BUILD_DEBIAN_MIRROR=https://mirrors.aliyun.com/debian
AIMA_BUILD_DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
AIMA_BUILD_PYPI_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
AIMA_BUILD_NPM_REGISTRY=https://registry.npmmirror.com
```

这些地址只改变包下载位置：

```text
Debian package 名称和版本不变
Python package 名称、版本和 uv.lock 不变
npm package 名称、版本和 package-lock.json 不变
Docker image reference 不变
```

需要替换包源时，只修改本机 `env.production` 中对应字段即可。

---

## 5. uv 与 Python 依赖

Docker backend builder 基于：

```text
python:3.14.7-slim-trixie
```

先从 `AIMA_BUILD_PYPI_INDEX` 安装：

```text
uv==0.12.3
```

安装要求使用二进制 wheel，不允许因为镜像站缺 wheel 静默退回 Rust 源码构建。

项目依赖继续由：

```text
uv.lock
→ uv export --frozen
→ exact version + hash requirements
→ uv pip sync --require-hashes
```

约束。

---

## 6. Windows 日常启动与停止

启动：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

停止：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

用户不需要在日常启动命令里指定任何第三方 Docker registry。

---

## 7. Linux / WSL / 公司服务器启动与停止

启动：

```bash
docker compose --env-file env.production up -d --build --wait
```

停止：

```bash
docker compose --env-file env.production down
```

---

## 8. 缓存行为

Docker / BuildKit 自动复用：

```text
基础镜像 layer
apt layer
Python dependency layer
npm ci layer
AIMA build layer
```

同一官方 image reference 已存在时，后续启动不会重新下载全部镜像 layer。`--build` 会检查构建输入，并按 BuildKit 缓存语义复用未变化的层。

日常不要主动使用：

```text
--no-cache
docker builder prune -a
docker system prune -a
```

除非明确需要无缓存验证。

---

## 9. Windows 数据与项目级重置

Windows 原生 Compose 使用 Docker-managed named volumes 保存 PostgreSQL、Artifact、日志和内部 Secret。

日常 `down` 不删除这些 volumes。

只有确认本地 AIMA 数据全部可以丢弃时执行：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down -v --remove-orphans --rmi all
```

不要用：

```text
docker system prune -a --volumes
```

代替项目级重置，因为它可能删除其他 Docker 项目的数据。

---

## 10. 状态与日志

Windows 查看状态：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production ps
```

查看 API 日志：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production logs -f api
```

Readiness：

```powershell
curl.exe -f http://127.0.0.1:8080/health/ready
```

---

## 11. Production 边界

当前源码 Compose 允许目标机器现场 pull/build，用于本地与 Internal V1。

完整 Production Release 仍按不可变离线交付方向：

```text
可信构建环境
→ 固定版本 / image digest
→ Manifest / SBOM / 来源验证
→ 不可变 Release
→ 服务器 docker load
→ --no-build --pull never
```

正式不可变 Production Release 不依赖生产服务器现场访问 Docker Hub、PyPI、npm 或公共镜像站重新构建。

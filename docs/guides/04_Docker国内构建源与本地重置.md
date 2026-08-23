# Docker 国内构建源与本地重置

本文说明 AIMA_UGC 在中国网络环境下执行完整 Docker build 时使用哪些下载源、为什么第一次 build 可能很慢、为什么本地 build 不等于公网发布，以及怎样只清理 AIMA 本地 Docker 状态后重新开始。

公司 Linux 服务器和完整 Production Release 的长期边界仍以：

- `docs/02_环境运行与部署.md`
- `docs/roadmap/02_生产上线实施路线.md`
- `docs/appendix/11_生产部署与离线Release方案.md`

为准。

---

## 1. 第一次 `docker compose ... up --build` 在做什么

首次完整 build 至少需要：

```text
Python base image
→ uv image
→ Node base image
→ Nginx base image
→ PostgreSQL runtime image
→ Debian apt packages
→ Python packages（从 uv.lock 冻结导出后安装）
→ Frontend packages（npm）
→ build AIMA backend image
→ build AIMA frontend image
→ bootstrap / migrate / configure
→ PostgreSQL / API / Worker / Scheduler / Frontend
```

因此第一次运行不是“只启动几个容器”。如果本机没有基础 layer/cache，Docker 会先下载和构建。

旧 Dockerfile 曾声明外部 `docker/dockerfile:1` syntax frontend；用户实际日志中仅 14.14 MB 的这一层就下载约 307 秒。当前 Dockerfile 只使用稳定基础语法，因此已经移除这个外部 syntax frontend，首次 build 不再为它单独拉镜像。

用户真实环境还出现过 DaoCloud PostgreSQL 18.4 镜像拉取 393 秒仅完成约 44 MB 的情况。这属于镜像传输链路吞吐异常，不是 AIMA Python、PostgreSQL 初始化或 Compose 业务编排本身执行数分钟。

---

## 2. 当前默认国内源

当前 `Dockerfile + compose.yaml + env.production.example` 默认使用：

| 类型 | 默认源 |
| --- | --- |
| Docker Hub official images | `docker.1ms.run/...` |
| GHCR uv image | `ghcr.1ms.run/...` |
| Debian | `https://mirrors.tuna.tsinghua.edu.cn/debian` |
| Debian Security | `https://mirrors.tuna.tsinghua.edu.cn/debian-security` |
| PyPI / uv pip | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| npm | `https://registry.npmmirror.com` |

镜像与依赖的**版本号没有改变**，仍由 Dockerfile、`.python-version`、`.uv-version`、`uv.lock`、`package-lock.json` 等仓库事实锁定，不使用 `latest`。

1ms 当前公开文档明确支持把 Docker Hub/GHCR 域名前缀直接替换为：

```text
docker.io → docker.1ms.run
ghcr.io   → ghcr.1ms.run
```

AIMA 采用这种仓库内显式前缀方式，因此**不依赖**开发机或服务器 Docker daemon 的 `registry-mirrors` 配置。基础通道可以直接使用，不要求在仓库中配置 1ms 账号、登录凭据或 Docker 密钥；付费/VIP 通道属于可选的外部能力，不是 AIMA 构建前置条件。

`docker.1panel.live` 当前官方文档主要作为 Docker daemon 的 `registry-mirrors` 地址使用，因此不把它假设成 Dockerfile/Compose 的直接镜像前缀。若管理员希望给整台 Docker Engine 增加第二镜像加速器，可在宿主自行配置，但这不是仓库运行依赖。

阿里云 ACR 的 Docker Hub 镜像加速器也不作为 AIMA 通用默认：其加速地址按账号生成，并且官方当前已提示 Docker Hub 镜像加速停止同步最新镜像，不适合作为需要长期可复现构建的仓库级公共默认。

Python 依赖没有把 `uv.lock` 改成 TUNA 专属 lock。构建时使用：

```text
uv.lock
→ uv export --frozen --no-dev --no-emit-local
→ 带 exact version / hash 的 requirements
→ uv pip sync --require-hashes --default-index=<TUNA>
→ 单独 build/install 当前 AIMA wheel
```

这样镜像下载走国内 PyPI，但版本和 distribution hash 仍受仓库 lock 约束。

> TUNA 对 Debian Security 明确提示镜像可能存在同步延迟。当前 Internal V1 默认使用国内 security mirror 是为了中国网络下可完成构建；完整 Production Release 仍必须在可信构建环境中完成漏洞/镜像完整性验证，并可按正式发布策略把 `AIMA_BUILD_DEBIAN_SECURITY_MIRROR` 切回 Debian 官方安全源。

---

## 3. 怎样切回官方源

如果 1ms 或某个国内软件包镜像临时不可用，只修改 `env.production` 中对应构建源变量即可，不需要改 Dockerfile、业务配置或持久数据：

```dotenv
AIMA_BUILD_PYTHON_IMAGE=python:3.14.7-slim-trixie
AIMA_BUILD_UV_IMAGE=ghcr.io/astral-sh/uv:0.12.3
AIMA_BUILD_NODE_IMAGE=node:24.19.0-bookworm-slim
AIMA_BUILD_NGINX_IMAGE=nginx:1.30.4-alpine3.24
AIMA_POSTGRES_IMAGE=postgres:18.4
AIMA_BUILD_DEBIAN_MIRROR=http://deb.debian.org/debian
AIMA_BUILD_DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security
AIMA_BUILD_PYPI_INDEX=https://pypi.org/simple
AIMA_BUILD_NPM_REGISTRY=https://registry.npmjs.org
```

这些值只控制 build/pull 下载来源，不会传入 AIMA API/Worker/Scheduler 的业务 Runtime 配置。

---

## 4. 本地 build 会不会把 AIMA 镜像发布到公网

不会。

当前命令：

```text
docker compose ... up -d --build --wait
```

执行的是：

```text
pull 基础镜像
→ 本地 build
→ 本地 tag
→ 本地 create/start container
```

仓库当前没有 `docker push`、`buildx --push` 或 AIMA Registry 发布步骤。

BuildKit 日志中的：

```text
naming to docker.io/library/aima-ugc-backend:internal-v1a
```

表示给**当前 Docker Engine 本地 image store**中的 AIMA image 使用 Docker 风格名称；它不等于上传 Docker Hub。

只有未来正式 Release Change 明确增加 Registry push/publish 时，才会发生对外发布动作。

---

## 5. 为什么 Docker Desktop 里暂时看不到完整镜像/容器

Compose 会先完成需要的 build，再创建依赖链中的容器。

例如 frontend 的 Node base layer 还在下载时：

- `aima-ugc-backend` 可能已经 build/export；
- `aima-ugc-frontend` 尚未完成；
- Compose 还没有进入完整 create/start 阶段，所以 Containers 页面可能没有新的完整 stack。

命令行比 UI 更直接：

```powershell
docker image ls aima-ugc-backend
docker image ls aima-ugc-frontend
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production ps -a
```

Docker Desktop UI 还可能需要刷新。

---

## 6. 第二次 build 为什么通常会快很多

Docker/BuildKit 会缓存：

```text
基础镜像 layer
apt layer
Python dependency layer
npm ci layer
AIMA build layer
```

只要 Dockerfile、lockfile 和相关输入没有变化，后续 build 会复用大量 cache。

不要把以下命令作为日常启动方式：

```text
--no-cache
docker builder prune -a
docker system prune -a
```

它们会主动丢掉缓存，导致重新下载。

---

## 7. Windows：只清理 AIMA 项目后重新开始

如果当前 build 仍在终端运行，先按：

```text
Ctrl+C
```

然后从仓库根执行：

```cmd
scripts\dev\compose_windows.cmd down -v --remove-orphans --rmi all
```

或者 PowerShell：

```powershell
.\scripts\dev\compose_windows.ps1 down -v --remove-orphans --rmi all
```

这会针对当前 AIMA Compose project 清理：

```text
AIMA 容器
AIMA Compose 网络
Windows AIMA named volumes
Compose 使用/构建的 service images
```

其中 `-v` 是破坏性的，会删除 Windows 本地：

```text
PostgreSQL
Artifact
应用日志
内部 Secret
```

只有确认本地这些数据全部可以丢弃时使用。

清理后可以检查：

```powershell
docker ps -a --filter label=com.docker.compose.project=aima-ugc
docker volume ls --filter label=com.docker.compose.project=aima-ugc
docker image ls aima-ugc-backend
docker image ls aima-ugc-frontend
```

---

## 8. 要不要再清 BuildKit cache

通常**不要**。

即使你要把 AIMA 数据、容器和 service image 一切重来，保留基础 image layer 和 BuildKit cache 反而能避免再次下载几十到几百 MB。

如果 Docker Desktop 只用于 AIMA，而且你明确希望连所有 build cache 都重新下载，可以人工执行：

```powershell
docker builder prune -a
```

这不是项目级操作，可能删除其他项目的 Docker build cache。

更强的：

```powershell
docker system prune -a --volumes
```

会影响 Docker Engine 中**其他项目**的容器、image、network、volume，因此 AIMA 文档不把它作为默认重置命令。

---

## 9. 清理后重新启动

Windows CMD：

```cmd
scripts\dev\compose_windows.cmd
```

PowerShell：

```powershell
.\scripts\dev\compose_windows.ps1
```

Linux / WSL / 公司服务器仍按现有 canonical Compose：

```bash
docker compose --env-file env.production up -d --build --wait
```

成功后检查：

```text
http://127.0.0.1:8080/health/ready
```

Windows PowerShell：

```powershell
curl.exe -f http://127.0.0.1:8080/health/ready
```

---

## 10. 验证原则

永久 CI 必须在同一实现头真实执行默认镜像源的完整构建与 Runtime，至少证明：

- 1ms Python / uv / Node / Nginx / PostgreSQL 镜像可拉取；
- `uv.lock` 冻结导出后可从 TUNA PyPI 通过 hash 校验安装；
- TUNA Debian / Debian Security 可完成 `apt-get update/install`；
- npmmirror 可完成 `npm ci`；
- Linux Internal V1-A 完整 bind-mount Golden Path 通过；
- Windows merged named-volume Runtime 和 CMD/PowerShell launcher 通过；
- 总 CI 与 Stage 8F 回归通过。

CI 证明的是配置、构建和运行链有效，不承诺你所在网络到每个国内镜像的固定带宽；具体下载速度仍受本机网络、DNS、Docker Desktop 和镜像节点影响。

---

## 11. Production 为什么仍然安全

国内镜像/软件包源只是**构建输入下载路径**，不改变长期生产设计。

当前 Internal V1 仍允许现场 `--build` 做真实服务器验收；完整 Production Release 仍要求：

```text
可信构建环境
→ 固定版本 / image digest
→ Manifest / SBOM / 来源验证
→ 生成不可变 Release
→ 服务器 docker load
→ --no-build --pull never
```

因此未来 Production Server 不依赖运行时访问 1ms/TUNA/npmmirror 来“现场重新构建”应用。镜像代理优化解决的是当前本地开发/Internal V1 build 速度，不替代 Stage 11 的不可变 Release 完整性门禁。

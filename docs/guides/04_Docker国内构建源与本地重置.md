# Docker 国内构建源与本地重置

本文说明 AIMA_UGC 在中国网络环境下完整 Docker 构建时使用的下载源、冷启动行为、缓存、本地镜像语义和项目级重置方式。

公司 Linux 服务器和完整 Production Release 的长期边界仍以：

- `docs/02_环境运行与部署.md`
- `docs/roadmap/02_生产上线实施路线.md`
- `docs/appendix/11_生产部署与离线Release方案.md`

为准。

---

## 1. 新电脑第一次启动在做什么

Windows Docker Desktop 正式启动命令：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

Linux / WSL / 公司服务器使用 canonical Compose：

```bash
docker compose --env-file env.production up -d --build --wait
```

Docker 必须允许从完全没有 AIMA 镜像、基础镜像和业务容器的状态开始：

```text
本机已有对应 image/layer
→ 直接复用

本机没有对应 image/layer
→ 按 env.production / Dockerfile 配置自动拉取

AIMA backend/frontend 不存在
→ 自动 build

AIMA backend/frontend 构建输入未变化且已有 cache
→ BuildKit 自动复用 cache
```

不要求用户先手工执行 `docker pull`，也不能把“开发机已经缓存过镜像”当成功前提。

首次冷启动通常需要：

```text
Python base image
uv image
Node base image
Nginx base image
PostgreSQL runtime image
Debian packages
Python packages
npm packages
AIMA backend build
AIMA frontend build
bootstrap / migrate / configure
完整 Runtime 启动
```

因此第一次启动明显慢于第二次是正常的；异常的是镜像几十 MB 下载数分钟仍几乎没有进度。

旧 Dockerfile 曾额外声明 `docker/dockerfile:1` syntax frontend；当前 Dockerfile 不需要高级语法，已经移除此额外下载入口。

---

## 2. 当前中国网络默认源

当前 `Dockerfile + compose.yaml + env.production.example` 默认组合：

| 类型 | 默认源 |
| --- | --- |
| Docker Hub official images | `docker.1ms.run/...` |
| GHCR uv image | `ghcr.1ms.run/...` |
| Debian | `https://mirrors.aliyun.com/debian` |
| Debian Security | `https://mirrors.aliyun.com/debian-security` |
| PyPI | `https://mirrors.aliyun.com/pypi/simple` |
| npm | `https://registry.npmmirror.com` |

镜像与依赖版本没有因为换源变化，仍由 Dockerfile、`.python-version`、`.uv-version`、`uv.lock`、`package-lock.json` 等仓库事实锁定，不使用 `latest`。

### 为什么容器镜像用 1ms

AIMA 直接使用 1ms 的 Docker Hub / GHCR 前缀：

```text
docker.io → docker.1ms.run
ghcr.io   → ghcr.1ms.run
```

这样不依赖开发机或服务器的 Docker daemon `registry-mirrors` 配置。

### 为什么 Debian / PyPI 使用阿里云

当前默认：

```text
https://mirrors.aliyun.com/debian
https://mirrors.aliyun.com/debian-security
https://mirrors.aliyun.com/pypi/simple
```

### npm 为什么仍是 npmmirror

`registry.npmmirror.com` 是阿里系当前 NPM 镜像入口，不需要再维护另一套 npm 地址。

---

## 3. Python lock 不因镜像改变

AIMA 不把 `uv.lock` 改写成某个国内镜像专属 lock。

构建流程：

```text
uv.lock
→ uv export --frozen --no-dev --no-emit-local
→ exact version + hash requirements
→ uv pip sync --require-hashes --default-index=<Aliyun PyPI>
→ 单独 build/install 当前 AIMA wheel
```

因此下载地址改变，但版本和 distribution hash 仍受 lock 约束。

---

## 4. 官方源回退

如果某个国内源临时不可用，只改 `env.production` 对应项，不需要修改 Dockerfile、数据库或业务配置：

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

这些字段只控制 build / pull 来源，不进入 AIMA API / Worker / Scheduler 的业务 Runtime Contract。

---

## 5. `env.production` 第一次创建与已有文件

`env.production` 被 Git ignore，是机器私有配置。

### Windows 新电脑

CMD：

```cmd
copy env.production.example env.production
```

PowerShell：

```powershell
Copy-Item env.production.example env.production
```

编辑后直接运行标准 Windows Compose 命令，不需要仓库 wrapper。

### Linux / WSL / 服务器

```bash
cp env.production.example env.production
chmod 0600 env.production
```

已有电脑已经存在 `env.production` 时，`git pull` 不会覆盖它。如果仍保留旧 DaoCloud/TUNA 等值，需要人工同步或在确认本机私有配置可以重建后重新从 example 复制。

当前国内默认字段：

```dotenv
AIMA_BUILD_PYTHON_IMAGE=docker.1ms.run/library/python:3.14.7-slim-trixie
AIMA_BUILD_UV_IMAGE=ghcr.1ms.run/astral-sh/uv:0.12.3
AIMA_BUILD_NODE_IMAGE=docker.1ms.run/library/node:24.19.0-bookworm-slim
AIMA_BUILD_NGINX_IMAGE=docker.1ms.run/library/nginx:1.30.4-alpine3.24
AIMA_POSTGRES_IMAGE=docker.1ms.run/library/postgres:18.4
AIMA_BUILD_DEBIAN_MIRROR=https://mirrors.aliyun.com/debian
AIMA_BUILD_DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
AIMA_BUILD_PYPI_INDEX=https://mirrors.aliyun.com/pypi/simple
AIMA_BUILD_NPM_REGISTRY=https://registry.npmmirror.com
```

---

## 6. 本地 build 不会把 AIMA 发布到公网

当前命令只会：

```text
pull 基础镜像
→ 本地 build
→ 本地 tag
→ 本地 create/start container
```

仓库没有 `docker push`、`buildx --push` 或 Registry publish。

日志中类似：

```text
naming to docker.io/library/aima-ugc-backend:internal-v1a
```

只是当前 Docker Engine 本地 image store 的名称，不表示上传 Docker Hub。

---

## 7. 第二次为什么更快

Docker / BuildKit 会复用：

```text
基础镜像 layer
apt layer
Python dependency layer
npm ci layer
AIMA build layer
```

所以日常不要主动使用：

```text
--no-cache
docker builder prune -a
docker system prune -a
```

除非明确需要验证真正的无缓存冷构建。

---

## 8. Windows 日常停止

推荐：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down
```

普通 `down` 会停止并删除容器/网络，但**保留 Windows named volumes**，所以 PostgreSQL、Artifact、日志和内部 Secret 下次继续使用。

仅临时暂停容器也可以：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production stop
```

---

## 9. Windows 项目级彻底重置

只有确认本地 AIMA 数据全部可丢弃时执行：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production down -v --remove-orphans --rmi all
```

它会清理当前 AIMA Compose project 的：

```text
容器
网络
Windows named volumes
AIMA service images
```

`-v` 会删除本地 PostgreSQL、Artifact、应用日志和内部 Secret。

不要把下面这条作为 AIMA 默认重置：

```text
docker system prune -a --volumes
```

它可能删除 Docker Desktop 中其他项目的数据。

---

## 10. 重新启动与检查

Windows CMD / PowerShell：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
```

Linux / WSL / 公司服务器：

```bash
docker compose --env-file env.production up -d --build --wait
```

成功后：

```powershell
curl.exe -f http://127.0.0.1:8080/health/ready
```

Windows 查看状态：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production ps
```

Windows 查看日志：

```powershell
docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production logs -f api
```

---

## 11. 冷启动验收边界

AIMA 的启动入口必须兼容全新 Docker 环境：

```text
没有 AIMA backend/frontend image
没有 PostgreSQL image
没有 Python/Node/Nginx/uv 基础 image
没有 AIMA volumes
```

在网络源可达时，一条正式 Compose 启动命令必须能够自动完成 pull → build → bootstrap → migrate → configure → runtime。

永久 CI 使用每次唯一的 `AIMA_IMAGE_TAG`，可以证明 AIMA service image 不是依赖某个固定预存 tag 才能启动；GitHub Hosted Runner 本身可能已有公共基础 layer cache，因此它不能被描述成“证明所有公共基础镜像都从零下载”。中国网络下的真正冷拉取速度以新电脑 / 公司服务器实测为准。

---

## 12. 海外 CI 与国内默认源分工

GitHub Hosted Runner 位于海外。本轮历史验证中直接访问 1ms 时，PostgreSQL blob 下载曾触发 Cloudflare JavaScript challenge，Docker 客户端无法处理该网页响应。

因此永久 CI 显式覆盖为官方 Docker Hub / GHCR / Debian / PyPI / npm，验证：

```text
完整 build
PostgreSQL
Migration
API / Worker / Scheduler / Frontend
Readiness
Secret
Persistence
Windows storage model
官方源回退
```

它不承担“中国网络到 1ms/阿里云/npmmirror 的带宽测试”。

目标中国环境验收使用 `env.production` 默认国内源进行真实 pull/build。

---

## 13. Production 边界不变

国内镜像和软件包镜像只是构建期下载路径。

完整 Production Release 仍要求：

```text
可信构建环境
→ 固定版本 / image digest
→ Manifest / SBOM / 来源验证
→ 不可变 Release
→ 服务器 docker load
→ --no-build --pull never
```

因此未来 Production Server 不依赖在线访问 1ms / 阿里云 / npmmirror 来现场重新构建应用。
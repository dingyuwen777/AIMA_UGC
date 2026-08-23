# Docker 官方镜像、国内加速与本地重置

本文说明 AIMA_UGC 完整 Docker Runtime 的镜像身份、构建期包下载源、冷启动、缓存和项目级重置方式，并说明中国网络需要加速时应该改哪里。

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
本机已有相同官方 image reference / 可复用 layer
→ Docker / BuildKit 按自身缓存语义复用

本机没有所需镜像/layer
→ 自动从对应官方 registry 拉取

AIMA backend/frontend 不存在
→ 自动 build

AIMA backend/frontend 构建输入未变化且已有 cache
→ BuildKit 自动复用 cache
```

不要求用户预先执行 `docker pull`，也不能把“开发机已经缓存过镜像”当成功前提。

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

第一次明显慢于第二次通常是正常的；如果镜像或包下载长期没有有效进度，应先判断网络、Docker registry/proxy 和包源可达性，而不是把第三方 registry 地址写进项目的镜像名称。

---

## 2. 容器镜像身份固定使用官方 reference

当前项目固定使用：

| 用途 | 官方 reference |
| --- | --- |
| Python | `python:3.14.7-slim-trixie` |
| uv | `ghcr.io/astral-sh/uv:0.12.3` |
| Node | `node:24.19.0-bookworm-slim` |
| Nginx | `nginx:1.30.4-alpine3.24` |
| PostgreSQL | `postgres:18.4` |

项目不再维护 `AIMA_BUILD_PYTHON_IMAGE`、`AIMA_BUILD_UV_IMAGE`、`AIMA_BUILD_NODE_IMAGE`、`AIMA_BUILD_NGINX_IMAGE` 或 `AIMA_POSTGRES_IMAGE` 这类镜像地址变量，也不把 `docker.1ms.run`、DaoCloud 或其他第三方 registry 写进当前 Runtime 配置。

原因是**镜像身份和下载加速是两件事**。例如：

```text
postgres:18.4
```

与：

```text
docker.1ms.run/library/postgres:18.4
```

是不同的 image reference。即使某次下载内容恰好对应相同 digest，项目也不应该因为网络加速策略形成另一套镜像名称。

本机以前存在的第三方 registry tag 不属于当前项目兼容边界：不自动迁移、不自动 retag，也不为它们增加 fallback。当前 Compose / Dockerfile 始终只引用上表中的官方名称。

---

## 3. 中国网络需要加速容器镜像时怎么做

**保持项目 image reference 不变。**

Docker Hub 镜像需要加速时，可以由目标机器按组织策略配置 Docker Desktop / Docker Engine 的 registry mirror，或使用企业 pull-through cache / registry proxy。GHCR 等非 Docker Hub registry 如果需要加速，应由企业代理缓存或目标环境提供的 registry 基础设施处理。

核心原则：

```text
项目代码看到的名字
→ 始终是官方 reference

下载到底经过官方直连、registry mirror、企业代理或缓存
→ 属于机器 / 基础设施网络层
```

仓库不要求每台机器使用同一个第三方镜像服务，也不把地域 CDN 的域名固化成应用 Runtime Contract。

---

## 4. Debian / PyPI / npm 默认官方源，可按机器覆盖

APT、PyPI 和 npm 是**包下载源**，不是 OCI 镜像 identity，因此继续保留构建参数覆盖能力。

canonical 默认：

```dotenv
AIMA_BUILD_DEBIAN_MIRROR=http://deb.debian.org/debian
AIMA_BUILD_DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security
AIMA_BUILD_PYPI_INDEX=https://pypi.org/simple
AIMA_BUILD_NPM_REGISTRY=https://registry.npmjs.org
```

如果中国网络访问官方包源过慢，只在本机 `env.production` 按需改成可用镜像，例如：

```dotenv
AIMA_BUILD_DEBIAN_MIRROR=https://mirrors.aliyun.com/debian
AIMA_BUILD_DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
AIMA_BUILD_PYPI_INDEX=https://mirrors.aliyun.com/pypi/simple
AIMA_BUILD_NPM_REGISTRY=https://registry.npmmirror.com
```

这些变量只影响 Docker build 的包下载位置：

```text
不会改变 Python / Node / Nginx / PostgreSQL / uv 的镜像名称
不会升级依赖版本
不会改写 uv.lock / package-lock.json
不会改变数据库、Secret、API、Worker 或 Scheduler Runtime Contract
```

---

## 5. Python lock 不因包源改变

AIMA 不把 `uv.lock` 改写成某个镜像站专属 lock。

构建流程保持：

```text
uv.lock
→ uv export --frozen --no-dev --no-emit-local
→ exact version + hash requirements
→ uv pip sync --require-hashes --default-index=<当前配置的 PyPI source>
→ 单独 build/install 当前 AIMA wheel
```

因此即使机器显式切换 PyPI 下载源，版本与 distribution hash 仍由锁文件和 hash 校验约束。

npm 继续通过 `package-lock.json` 的锁定与 integrity 校验约束依赖。

---

## 6. `env.production` 第一次创建与旧配置

`env.production` 被 Git ignore，是机器私有配置。

### Windows

CMD：

```cmd
copy env.production.example env.production
```

PowerShell：

```powershell
Copy-Item env.production.example env.production
```

### Linux / WSL / 服务器

```bash
cp env.production.example env.production
chmod 0600 env.production
```

已有机器的 `env.production` 不会被 `git pull` 覆盖。

如果旧文件仍包含：

```text
AIMA_BUILD_PYTHON_IMAGE
AIMA_BUILD_UV_IMAGE
AIMA_BUILD_NODE_IMAGE
AIMA_BUILD_NGINX_IMAGE
AIMA_POSTGRES_IMAGE
```

这些字段已经不是当前 Compose Contract，项目不会读取它们；可以从本机配置中删除。项目不会尝试兼容旧第三方 image tag，也不会因为删除这些字段改变 PostgreSQL/Artifact/Secret 持久数据。

原有四个包源字段如果存在仍继续生效；不填写时使用官方默认。

---

## 7. 本地 build 不会把 AIMA 发布到公网

当前正式命令只会：

```text
pull 官方基础镜像
→ 本地 build
→ 本地 tag AIMA service image
→ 本地 create/start container
```

仓库没有要求日常启动执行 `docker push`、`buildx --push` 或 Registry publish。

日志中类似：

```text
naming to docker.io/library/aima-ugc-backend:internal-v1a
```

只是 Docker Engine 本地 image store 的名称，不表示已经上传 Docker Hub。

---

## 8. 第二次为什么更快

Docker / BuildKit 可以复用：

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

除非明确要验证真正的无缓存冷构建。

不同第三方 repository tag 不是当前项目需要兼容的镜像 identity；当前判断是否可直接使用的标准仍是项目实际引用的官方镜像名称和 Docker 自身可复用的内容缓存。

---

## 9. Windows 日常停止

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

## 10. Windows 项目级彻底重置

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

## 11. 重新启动与检查

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

## 12. 冷启动验收边界

AIMA 的启动入口必须兼容全新 Docker 环境：

```text
没有 AIMA backend/frontend image
没有 PostgreSQL image
没有 Python/Node/Nginx/uv 基础 image
没有 AIMA volumes
```

在官方 registry 和当前包源可达时，一条正式 Compose 启动命令必须能够自动完成：

```text
pull → build → bootstrap → migrate → configure → runtime
```

永久 CI 使用每次唯一的 `AIMA_IMAGE_TAG`，可以证明 AIMA service image 不依赖某个固定预存 tag 才能启动。GitHub Hosted Runner 可能已有公共基础 layer cache，因此不能把 CI 描述成“证明每个公共基础 layer 都从零下载”。

具体中国网络下载速度属于目标机器网络事实；需要时应分别验证 registry 基础设施和包源，而不是改变项目 image identity。

---

## 13. CI 与当前默认源

GitHub Hosted Runner 直接使用当前 canonical 配置：

```text
官方容器 image reference
官方 Debian / PyPI / npm 默认源
```

CI 主要证明：

```text
Dockerfile / Compose 可构建
PostgreSQL / Migration 可运行
API / Worker / Scheduler / Frontend 可启动
Readiness / Secret / Persistence 正确
Windows storage-only override 正确
```

包源 override 的存在由配置回归测试验证，不需要在每个永久 Workflow 里重复改写一整套镜像身份。

---

## 14. Production 边界不变

本次统一官方 image reference 只改变当前源码构建时如何表达镜像身份，不把 Internal V1-A 的现场 build 提升为最终 Production Release。

完整 Production Release 仍要求：

```text
可信构建环境
→ 固定版本 / image digest
→ Manifest / SBOM / 来源验证
→ 不可变 Release
→ 服务器 docker load
→ --no-build --pull never
```

因此正式 Production Server 最终不依赖现场访问 Docker Hub、GHCR、PyPI、npm 或任何第三方镜像站重新构建应用。
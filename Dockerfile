# 中国网络环境默认使用镜像/软件包代理；所有输入都可由 Compose build args 覆盖回官方源。
# 版本号保持仓库锁定值，不使用 latest。本文件只使用 Dockerfile 稳定基础语法，
# 不声明外部 syntax frontend，避免首次 build 额外下载 docker/dockerfile 镜像。
ARG AIMA_BUILD_PYTHON_IMAGE=m.daocloud.io/docker.io/library/python:3.14.7-slim-trixie
ARG AIMA_BUILD_UV_IMAGE=m.daocloud.io/ghcr.io/astral-sh/uv:0.12.3
ARG AIMA_BUILD_NODE_IMAGE=m.daocloud.io/docker.io/library/node:24.19.0-bookworm-slim
ARG AIMA_BUILD_NGINX_IMAGE=m.daocloud.io/docker.io/library/nginx:1.30.4-alpine3.24

FROM ${AIMA_BUILD_UV_IMAGE} AS uv-bin

FROM ${AIMA_BUILD_PYTHON_IMAGE} AS backend-builder
ARG AIMA_BUILD_PYPI_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
COPY --from=uv-bin /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
# 保留 uv.lock 的官方 PyPI source/hash 事实不变：先冻结导出第三方依赖，
# 再从可配置镜像按 exact version + hash 同步，最后单独构建/安装本项目 wheel。
RUN uv export \
      --frozen \
      --no-dev \
      --no-emit-local \
      --format requirements.txt \
      --generate-hashes \
      --output-file /tmp/requirements.txt \
    && uv venv .venv \
    && uv pip sync \
      --python .venv/bin/python \
      --default-index "${AIMA_BUILD_PYPI_INDEX}" \
      --require-hashes \
      /tmp/requirements.txt \
    && uv build \
      --wheel \
      --out-dir /tmp/dist \
      --default-index "${AIMA_BUILD_PYPI_INDEX}" \
    && uv pip install \
      --python .venv/bin/python \
      --no-deps \
      /tmp/dist/*.whl

FROM ${AIMA_BUILD_PYTHON_IMAGE} AS backend
ARG AIMA_BUILD_DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
ARG AIMA_BUILD_DEBIAN_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive
RUN sed -i \
      -e "s|http://deb.debian.org/debian-security|${AIMA_BUILD_DEBIAN_SECURITY_MIRROR}|g" \
      -e "s|https://deb.debian.org/debian-security|${AIMA_BUILD_DEBIAN_SECURITY_MIRROR}|g" \
      -e "s|http://security.debian.org/debian-security|${AIMA_BUILD_DEBIAN_SECURITY_MIRROR}|g" \
      -e "s|https://security.debian.org/debian-security|${AIMA_BUILD_DEBIAN_SECURITY_MIRROR}|g" \
      -e "s|http://deb.debian.org/debian|${AIMA_BUILD_DEBIAN_MIRROR}|g" \
      -e "s|https://deb.debian.org/debian|${AIMA_BUILD_DEBIAN_MIRROR}|g" \
      /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 aima \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin aima \
    && mkdir -p /app/data /app/logs /app/scripts/deploy \
    && chown -R 10001:10001 /app/data /app/logs
WORKDIR /app
COPY --from=backend-builder /app/.venv /app/.venv
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY scripts/deploy/prepare_host.py ./scripts/deploy/prepare_host.py
USER 10001:10001
EXPOSE 8090
CMD ["uvicorn", "aima_ugc.entrypoints.api_main:app", "--host", "0.0.0.0", "--port", "8090"]

FROM ${AIMA_BUILD_NODE_IMAGE} AS frontend-builder
ARG AIMA_BUILD_NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry="${AIMA_BUILD_NPM_REGISTRY}"
COPY frontend/ ./
RUN npm run build

FROM ${AIMA_BUILD_NGINX_IMAGE} AS frontend
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-builder --chown=nginx:nginx /build/frontend/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
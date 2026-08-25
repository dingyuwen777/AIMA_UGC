# 容器基础镜像固定使用官方 Docker Hub canonical reference；版本号保持仓库锁定值，不使用 latest。
# Docker Hub 下载加速由宿主 Docker registry-mirrors 处理；Debian / PyPI / npm 为独立构建下载源。
# 本文件只使用 Dockerfile 稳定基础语法，不声明外部 syntax frontend。

FROM python:3.14.7-slim-trixie AS backend-builder
ARG AIMA_BUILD_PYPI_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy
WORKDIR /app
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --only-binary=:all: \
      --index-url "${AIMA_BUILD_PYPI_INDEX}" \
      "uv==0.12.3"
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
# uv.lock 继续作为依赖版本与 hash 的机器事实；下载源只改变传输路径。
RUN uv export \
      --frozen \
      --no-dev \
      --no-emit-local \
      --format requirements.txt \
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

FROM python:3.14.7-slim-trixie AS backend
ARG AIMA_BUILD_DEBIAN_MIRROR=https://mirrors.aliyun.com/debian
ARG AIMA_BUILD_DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
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

FROM node:24.19.0-bookworm-slim AS frontend-builder
ARG AIMA_BUILD_NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry="${AIMA_BUILD_NPM_REGISTRY}"
COPY frontend/ ./
RUN npm run build

FROM nginx:1.30.4-alpine3.24 AS frontend
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-builder --chown=nginx:nginx /build/frontend/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
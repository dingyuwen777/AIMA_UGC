# 容器基础镜像固定使用官方 canonical reference；版本号保持仓库锁定值，不使用 latest。
# 机器侧需要 registry mirror 或企业代理缓存时，应由 Docker 基础设施透明处理，
# 不在项目配置中改写镜像身份。本文件只使用 Dockerfile 稳定基础语法，
# 不声明外部 syntax frontend，避免首次 build 额外下载 docker/dockerfile 镜像。

FROM ghcr.io/astral-sh/uv:0.12.3 AS uv-bin

FROM python:3.14.7-slim-trixie AS backend-builder
ARG AIMA_BUILD_PYPI_INDEX=https://pypi.org/simple
COPY --from=uv-bin /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
# 保留 uv.lock 的官方 PyPI source/hash 事实不变：先冻结导出第三方依赖，
# 再从可配置下载源按 exact version + hash 同步，最后单独构建/安装本项目 wheel。
# uv 0.12.3 的 requirements export 默认包含锁文件 hashes，因此无需新版 CLI 的 --generate-hashes。
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
ARG AIMA_BUILD_DEBIAN_MIRROR=http://deb.debian.org/debian
ARG AIMA_BUILD_DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security
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
ARG AIMA_BUILD_NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry="${AIMA_BUILD_NPM_REGISTRY}"
COPY frontend/ ./
RUN npm run build

FROM nginx:1.30.4-alpine3.24 AS frontend
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-builder --chown=nginx:nginx /build/frontend/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
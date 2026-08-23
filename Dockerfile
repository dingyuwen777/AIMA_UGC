# syntax=docker/dockerfile:1

FROM python:3.14.7-slim-trixie AS backend-builder
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14.7-slim-trixie AS backend
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 aima \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin aima \
    && mkdir -p /app/data /app/logs \
    && chown -R 10001:10001 /app/data /app/logs
WORKDIR /app
COPY --from=backend-builder /app/.venv /app/.venv
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
USER 10001:10001
EXPOSE 8090
CMD ["uvicorn", "aima_ugc.entrypoints.api_main:app", "--host", "0.0.0.0", "--port", "8090"]

FROM node:24.19.0-bookworm-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.30.4-alpine3.24 AS frontend
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-builder --chown=nginx:nginx /build/frontend/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]

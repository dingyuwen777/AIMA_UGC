"""验证本地 FastAPI 与 Vite 开发服务器形成联调闭环。"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable

import httpx

BACKEND_LIVE_URL = "http://127.0.0.1:8090/health/live"
BACKEND_READY_URL = "http://127.0.0.1:8090/health/ready"
FRONTEND_URL = "http://127.0.0.1:5173/"
FRONTEND_PROXY_LIVE_URL = "http://127.0.0.1:5173/health/live"
FRONTEND_PROXY_READY_URL = "http://127.0.0.1:5173/health/ready"
TIMEOUT_SECONDS = 45.0


def wait_for(
    name: str,
    url: str,
    validator: Callable[[httpx.Response], bool],
) -> None:
    """等待目标 HTTP 服务就绪，并验证响应语义。"""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_error = "尚未收到响应"

    with httpx.Client(timeout=1.5) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(url)
                if validator(response):
                    print(f"{name} 已就绪：{url}")
                    return
                last_error = f"status={response.status_code} body={response.text[:200]!r}"
            except httpx.HTTPError as exc:
                last_error = repr(exc)
            time.sleep(0.25)

    raise RuntimeError(f"{name} 未在 {TIMEOUT_SECONDS:.0f}s 内就绪：{last_error}")


def is_health_ok(response: httpx.Response) -> bool:
    if response.status_code != 200:
        return False
    try:
        return response.json() == {"status": "ok"}
    except ValueError:
        return False


def is_readiness_ok(response: httpx.Response) -> bool:
    """完整本地后端必须连通 PostgreSQL、ArtifactStore 和日志目录。"""
    if response.status_code != 200:
        return False
    try:
        return response.json() == {
            "status": "ok",
            "checks": {
                "database": "ok",
                "artifact_store": "ok",
                "log_directory": "ok",
            },
        }
    except ValueError:
        return False


def is_frontend_ok(response: httpx.Response) -> bool:
    """Vite 首页必须返回可挂载 Vue 应用的 HTML。"""
    return response.status_code == 200 and '<div id="app"></div>' in response.text


def main() -> int:
    parser = argparse.ArgumentParser(description="检查本地前后端联调")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="同时要求 PostgreSQL、ArtifactStore、日志目录 readiness 通过",
    )
    args = parser.parse_args()

    if args.require_ready:
        wait_for("后端 readiness", BACKEND_READY_URL, is_readiness_ok)
        wait_for("前端开发服务器", FRONTEND_URL, is_frontend_ok)
        wait_for("Vite 后端 readiness 代理", FRONTEND_PROXY_READY_URL, is_readiness_ok)
        print("本地 Backend + Frontend + PostgreSQL 联调检查通过。")
        return 0

    # 保留 Stage 1 无数据库依赖的基础 smoke；日常完整开发环境使用 --require-ready。
    wait_for("后端健康检查", BACKEND_LIVE_URL, is_health_ok)
    wait_for("前端开发服务器", FRONTEND_URL, is_frontend_ok)
    wait_for("Vite 后端代理", FRONTEND_PROXY_LIVE_URL, is_health_ok)
    print("本地前后端基础启动与代理联调检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

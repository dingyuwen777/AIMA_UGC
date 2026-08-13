"""验证本地 FastAPI 与 Vite 开发服务器能够形成联调闭环。"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

BACKEND_HEALTH_URL = "http://127.0.0.1:8090/health/live"
FRONTEND_URL = "http://127.0.0.1:5173/"
FRONTEND_PROXY_HEALTH_URL = "http://127.0.0.1:5173/health/live"
TIMEOUT_SECONDS = 30.0


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
    """健康检查必须返回固定成功结构。"""
    if response.status_code != 200:
        return False
    try:
        return response.json() == {"status": "ok"}
    except ValueError:
        return False


def is_frontend_ok(response: httpx.Response) -> bool:
    """Vite 首页必须返回可挂载 Vue 应用的 HTML。"""
    return response.status_code == 200 and '<div id="app"></div>' in response.text


def main() -> int:
    wait_for("后端健康检查", BACKEND_HEALTH_URL, is_health_ok)
    wait_for("前端开发服务器", FRONTEND_URL, is_frontend_ok)
    wait_for("Vite 后端代理", FRONTEND_PROXY_HEALTH_URL, is_health_ok)
    print("本地前后端启动与代理联调检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

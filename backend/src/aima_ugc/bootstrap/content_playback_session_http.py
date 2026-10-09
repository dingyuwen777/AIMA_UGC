"""仅播放流路径隐藏访问日志中的短期能力令牌。"""

from urllib.parse import parse_qsl, urlencode

from starlette.types import ASGIApp, Receive, Scope, Send

PLAYBACK_SESSION_STATE_KEY = "content_playback_session"


class PlaybackSessionRedactingMiddleware:
    """先保留内存参数再改写原 scope；uvicorn 访问日志只能看到隐藏值。"""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "").rstrip("/")
        if (
            scope["type"] == "http"
            and path.startswith("/api/v1/contents/")
            and path.endswith("/playback/stream")
        ):
            # 尾斜杠直接进入同一路由，避免重定向反射真实令牌或返回 hidden 无效地址。
            scope["path"] = path
            pairs = parse_qsl(
                scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True
            )
            values = [value for key, value in pairs if key == "session"]
            if values:
                scope.setdefault("state", {})[PLAYBACK_SESSION_STATE_KEY] = values[-1]
                scope["query_string"] = urlencode(
                    [(key, "hidden" if key == "session" else value) for key, value in pairs]
                ).encode("ascii")
        await self._app(scope, receive, send)

"""在最终路由的异常处理边界内执行显式权限，未知入口失败关闭。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from aima_ugc.bootstrap.feishu_auth_http import AuthenticationRequired
from aima_ugc.bootstrap.route_policy import ROUTE_POLICIES, RoutePermission
from aima_ugc.contracts.http import HttpErrorItem, HttpErrorResponse
from aima_ugc.modules.identity import AuthorizationDenied, IdentityResolver, Principal
from aima_ugc.modules.identity.feishu import SESSION_COOKIE_NAME


class CsrfRejected(AuthorizationDenied):
    """Cookie 写请求没有可信同源凭据。"""


def _origin(value: str) -> tuple[str, str, int | None] | None:
    """规范协议、主机和默认端口，不接受凭据或畸形地址。"""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, parsed.hostname.lower(), port
    except ValueError:
        return None


def _check_cookie_origin(
    request: Request,
    principal: Principal,
    resolver: IdentityResolver,
) -> None:
    """SameSite 之外再验证业务写请求同源；OAuth GET 回调不进入此检查。"""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if principal.source != "feishu" or SESSION_COOKIE_NAME not in request.cookies:
        return
    origin = request.headers.get("origin") or request.headers.get("referer")
    configured = getattr(resolver, "trusted_browser_urls", ())
    allowed = (
        {_origin(url) for url in configured} if configured else {_origin(str(request.base_url))}
    )
    allowed.discard(None)
    if origin is None or _origin(origin) not in allowed:
        raise CsrfRejected
    if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
        raise CsrfRejected


def _error(request: Request, *, code: str, status: int, detail: str) -> JSONResponse:
    """沿用统一错误 Contract，不将认证故障变为外层中间件 500。"""
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    body = HttpErrorResponse(
        type=f"https://aima.example/problems/{code}",
        title=detail,
        status=status,
        detail=detail,
        request_id=request_id,
        errors=(HttpErrorItem(field=None, code=code, message=detail),),
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={"x-request-id": request_id, "Cache-Control": "private, no-store"},
    )


def _guard(
    original: ASGIApp,
    permission: RoutePermission,
    resolver: IdentityResolver,
) -> ASGIApp:
    """包装 Router 内层 app，认证在解析请求正文或委托业务 Service 之前执行。"""

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        """复用请求级 Principal；成功响应同样禁止跨账号缓存。"""
        if permission != "public":
            request = Request(scope, receive)
            principal = await run_in_threadpool(resolver.resolve, request)
            if permission == "administrator":
                principal.require_administrator()
            _check_cookie_origin(request, principal, resolver)

        async def send_private(message: Any) -> None:
            """身份相关响应不能被共享缓存或另一账号复用。"""
            if message["type"] == "http.response.start" and permission != "public":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"cache-control"
                ]
                message["headers"] = [*headers, (b"cache-control", b"private, no-store")]
            await send(message)

        await original(scope, receive, send_private)

    return guarded


def route_authorization_inventory(application: FastAPI) -> tuple[dict[str, str], ...]:
    """检查每个实际 Method+Path，包括框架 Route 和隐藏路由；不按前缀/方法猜权限。"""
    inventory: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for route in application.routes:
        if not isinstance(route, Route):
            raise RuntimeError(f"未声明权限的路由类型: {type(route).__name__}")
        for method in sorted(route.methods or ()):
            key = (method, route.path)
            if key in seen or key not in ROUTE_POLICIES:
                raise RuntimeError(f"重复或未声明权限的路由: {method} {route.path}")
            seen.add(key)
            inventory.append(
                dict(
                    method=method,
                    path=route.path,
                    permission=ROUTE_POLICIES[key],
                    endpoint=route.name,
                )
            )
    return tuple(inventory)


def install_route_authorization(
    application: FastAPI, *, identity_resolver: IdentityResolver
) -> None:
    """主工厂与最终 assembly 都检查；仅新装路由加守卫，startup 再防晚注册遗漏。"""
    inventory = route_authorization_inventory(application)
    for route in application.routes:
        checked = cast(Route, route)
        permissions = {ROUTE_POLICIES[(method, checked.path)] for method in checked.methods or ()}
        if len(permissions) != 1:
            raise RuntimeError(f"同一 Route 的 Method 权限不一致: {checked.path}")
        permission = next(iter(permissions))
        if not getattr(checked, "aima_authorized", False):
            checked.app = _guard(checked.app, permission, identity_resolver)
            cast(Any, checked).aima_authorized = True
        if isinstance(checked, APIRoute):
            checked.openapi_extra = {
                **(checked.openapi_extra or {}),
                "x-aima-authorization": permission,
            }
    application.state.route_authorization_policy = inventory

    @application.exception_handler(AuthenticationRequired)
    async def authentication_required(request: Request, _: AuthenticationRequired) -> JSONResponse:
        """即使测试/宿主注入 Resolver 未安装 OAuth 路由也保持 401。"""
        return _error(
            request, code="authentication_required", status=401, detail="当前没有有效登录会话。"
        )

    @application.exception_handler(CsrfRejected)
    async def csrf_rejected(request: Request, _: CsrfRejected) -> JSONResponse:
        """CSRF 是已登录请求拒绝，不能误导前端反复登录。"""
        return _error(
            request, code="csrf_rejected", status=403, detail="请从当前系统页面提交操作。"
        )

    if getattr(application.state, "authorization_installed", False):
        return
    application.state.authorization_installed = True

    router = cast(Any, application.router)
    original_lifespan = router.lifespan_context

    @asynccontextmanager
    async def authorization_lifespan(app: FastAPI) -> AsyncIterator[None]:
        """未知或晚注册且未安装 guard 的路由均阻止启动。"""
        route_authorization_inventory(app)
        if any(not getattr(route, "aima_authorized", False) for route in app.routes):
            raise RuntimeError("存在尚未安装权限守卫的路由")
        async with original_lifespan(app):
            yield

    router.lifespan_context = authorization_lifespan

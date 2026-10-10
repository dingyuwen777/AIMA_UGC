"""同一 HTTP 请求只解析一次可信 Principal。"""

from typing import cast

from fastapi import Request

from .models import IdentityResolver, Principal


class RequestCachedIdentityResolver:
    """缓存限定在 Request.state，不跨请求延迟 Session 撤销生效。"""

    def __init__(self, resolver: IdentityResolver) -> None:
        """包装现有 Session/开发身份解析器。"""
        self._resolver = resolver

    @property
    def trusted_browser_urls(self) -> tuple[str, ...]:
        """从认证配置传递公开入口，避免反向代理内部协议影响同源验证。"""
        return cast(tuple[str, ...], getattr(self._resolver, "trusted_browser_urls", ()))

    def resolve(self, request: Request) -> Principal:
        """仅复用本 Resolver 已确认的身份，客户端无法注入缓存。"""
        cached = getattr(request.state, "aima_principal", None)
        if cached is None:
            cached = self._resolver.resolve(request)
            request.state.aima_principal = cached
        return cached

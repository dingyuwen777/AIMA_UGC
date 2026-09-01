"""Principal、开发身份解析器与飞书适配端口。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from aima_ugc.contracts.administration import PrincipalRole, PrincipalSource


class AuthorizationDenied(PermissionError):
    """当前 Principal 不具备后端要求的角色。"""


@dataclass(frozen=True, slots=True)
class Principal:
    """与飞书 open_id 等 Provider 私有身份解耦的统一 Principal。"""

    principal_id: str
    display_name: str
    role: PrincipalRole
    source: PrincipalSource

    def require_administrator(self) -> None:
        """在后端执行管理员权限判断。"""

        if self.role != "administrator":
            raise AuthorizationDenied


class IdentityResolver(Protocol):
    """把当前 HTTP 请求解析为统一 Principal。"""

    def resolve(self, request: Request) -> Principal:
        """从当前请求解析统一 Principal。"""

        ...


class FeishuIdentityClaimsAdapter(Protocol):
    """预留飞书已验证 Claims 到 Principal 的适配边界。"""

    def from_verified_claims(self, claims: Mapping[str, object]) -> Principal:
        """只接收上游已经验证的飞书 Claims，并映射统一 Principal。"""

        ...


class DevelopmentIdentityResolver:
    """第一版显式开发身份；不读取请求头，也不伪装企业认证。"""

    def __init__(
        self,
        *,
        principal_id: str = "local-administrator",
        display_name: str = "本地管理员",
        role: PrincipalRole = "administrator",
    ) -> None:
        """建立不读取请求输入的固定开发身份。"""

        self._principal = Principal(
            principal_id=principal_id,
            display_name=display_name,
            role=role,
            source="development",
        )

    def resolve(self, request: Request) -> Principal:
        """返回进程启动时固定的开发 Principal。"""

        del request
        return self._principal


__all__ = [
    "AuthorizationDenied",
    "DevelopmentIdentityResolver",
    "FeishuIdentityClaimsAdapter",
    "IdentityResolver",
    "Principal",
]

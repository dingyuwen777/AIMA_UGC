"""飞书身份适配器、会话与映射边界的公共入口。"""

from aima_ugc.modules.identity.models import AuthorizationDenied

from .adapter import AUTHORIZE_ENDPOINT, HttpxFeishuClient
from .app_token import FeishuAppTokenCache
from .errors import FeishuError
from .port import (
    FeishuDepartment,
    FeishuIdentityProvider,
    FeishuTokens,
    FeishuUser,
    FeishuUserDetail,
    VerifiedFeishuIdentity,
    resolve_role,
)
from .principal_store import PrincipalStore, ResolvedPrincipal
from .resolver import FeishuSessionIdentityResolver
from .session_store import (
    DEFAULT_SESSION_TTL,
    SESSION_COOKIE_NAME,
    SESSION_TOKEN_BYTES,
    SessionRecord,
    SessionStore,
    generate_session_token,
    hash_session_token,
)

__all__ = [
    "AUTHORIZE_ENDPOINT",
    "DEFAULT_SESSION_TTL",
    "SESSION_COOKIE_NAME",
    "SESSION_TOKEN_BYTES",
    "AuthorizationDenied",
    "FeishuAppTokenCache",
    "FeishuDepartment",
    "FeishuError",
    "FeishuIdentityProvider",
    "FeishuSessionIdentityResolver",
    "FeishuTokens",
    "FeishuUser",
    "FeishuUserDetail",
    "HttpxFeishuClient",
    "PrincipalStore",
    "ResolvedPrincipal",
    "SessionRecord",
    "SessionStore",
    "VerifiedFeishuIdentity",
    "generate_session_token",
    "hash_session_token",
    "resolve_role",
]

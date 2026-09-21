"""飞书登录的三个 HTTP 路由（登录 / 回调 / 登出）与它们的装配。

════════ 这个模块负责什么 ════════

    1. 装配：按配置决定"启用飞书身份"还是"沿用开发身份"（见 `build_feishu_identity`）
    2. 路由：`GET /api/v1/auth/feishu/login`、`GET /api/v1/auth/feishu/callback`、
       `POST /api/v1/auth/logout`
    3. 两处安全翻译：
       · 会话 Cookie 解析失败 → **401**（未登录），与 `require_administrator()` 的
         **403**（已登录但无权限）分开 —— 两者原本都是 `AuthorizationDenied`，
         若混在一起，前端就无法区分"请去登录"和"你别登了"，会写出
         "403 → 自动重登 → 403"的死循环。
       · 授权码 / state 从 query string 里**抹掉**后再交给下游，避免
         uvicorn 访问日志把 `?code=...` 原样打进日志。

════════ 为什么不改 `modules/identity/feishu/` ════════

单 ①② 已验收的零件（适配器 / 映射 / 会话）保持**逐字不动**：本模块只做"接线与编排"，
飞书协议细节仍留在 `modules/identity/feishu/` 内。`AuthenticationRequired` 之所以定义
在这里而不是 `modules/identity/models.py`，是因为 `Principal` 契约与既有异常禁止改动
（任务书 §2.2）；它继承 `AuthorizationDenied`，因此既有 `except AuthorizationDenied`
的调用方**行为不变**。

════════ state 为什么落库、为什么必须一次性 ════════

`identity_login_states` 表只存 state 的 SHA-256，不存原文。回调时用一条
`UPDATE ... WHERE consumed_at IS NULL AND expires_at > now RETURNING return_to`
**原子消费**：并发重放时只有一个请求能拿到行，其余拿不到 → `400`。
不能"先 SELECT 再 UPDATE"：那中间有窗口，两个并发的重放都能通过。
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import SecretStr
from sqlalchemy import insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.administration import (
    AuthConnectorListResponse,
    AuthConnectorResponse,
)
from aima_ugc.contracts.http import HttpErrorItem, HttpErrorResponse
from aima_ugc.modules.identity import (
    AuthorizationDenied,
    DevelopmentIdentityResolver,
    IdentityResolver,
    Principal,
)
from aima_ugc.modules.identity.feishu import (
    DEFAULT_SESSION_TTL,
    SESSION_COOKIE_NAME,
    FeishuError,
    HttpxFeishuClient,
    PrincipalStore,
    SessionStore,
    resolve_role,
)
from aima_ugc.modules.identity.feishu.ratelimit import (
    DEFAULT_GLOBAL_LIMIT,
    DEFAULT_IP_LIMIT,
    LoginRateLimited,
    LoginRateLimiter,
    client_ip_of,
)
from aima_ugc.modules.identity.feishu.redirect import (
    DEFAULT_RETURN_TO,
    is_safe_return_to,
    safe_return_to,
)
from aima_ugc.modules.identity.tables import identity_login_states_table
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.time import beijing_now

_LOGGER = logging.getLogger("aima_ugc")

LOGIN_PATH = "/api/v1/auth/feishu/login"
CALLBACK_PATH = "/api/v1/auth/feishu/callback"
LOGOUT_PATH = "/api/v1/auth/logout"

# 多企业路由：路径里带企业标识。**参数名必须是 `connector_code`**，
# 不能叫 `code` —— 否则会与飞书回调 query 里的授权码参数 `code` 撞名，
# 且 FastAPI 的绑定是**静默**的（不报错，只是拿到错的值）。
MULTI_LOGIN_PATH = "/api/v1/auth/feishu/{connector_code}/login"
MULTI_CALLBACK_PATH = "/api/v1/auth/feishu/{connector_code}/callback"

# 可登录企业列表（**未认证**端点）。登录页用它渲染企业选择。
# ⚠️ 响应**只含 code 与显示名** —— 见 `AuthConnectorResponse` 的说明。
CONNECTORS_PATH = "/api/v1/auth/connectors"


# state 有效期：与飞书授权码的 5 分钟窗口同量级，留出用户点授权页的时间。
DEFAULT_STATE_TTL = timedelta(minutes=10)

# 默认请求的用户身份权限范围：只取当前用户自己的基础资料，不取全量通讯录。
DEFAULT_FEISHU_SCOPE = "contact:user.base:readonly"

# query string 里绝不允许出现在日志中的参数名（授权码 / state / 票据）。
_SENSITIVE_QUERY_KEYS = frozenset({"code", "state", "ticket", "authorization_code"})

# 需要抹掉敏感 query 的路径：只有回调会带授权码。
#
# ⚠️ 多企业回调路径**含变量**（`/feishu/{code}/callback`），
# 不能再靠精确集合匹配 —— 否则新路径不在集合里，中间件不打码，
# **授权码会被 uvicorn 原样写进访问日志**（且不报错，静默泄露）。
# 因此这里用"**前缀 + 后缀**"判定：覆盖飞书回调的所有形态，
# 同时不会误伤登录路径（登录路径不带授权码，即使被处理也无害）。
_REDACTED_QUERY_PATH_PREFIX = "/api/v1/auth/feishu/"
_REDACTED_QUERY_PATH_SUFFIX = "/callback"
_REDACTED_QUERY_PATHS = frozenset({CALLBACK_PATH})


# scope 里暂存真实回调参数的键（不进日志、不序列化）。
_AUTH_PARAMS_STATE_KEY = "feishu_auth_params"


class AuthenticationRequired(AuthorizationDenied):
    """当前请求**没有可用会话**（未登录 / 过期 / 已撤销）。

    继承 `AuthorizationDenied`，因此既有 `except AuthorizationDenied` 仍能捕获；
    但本模块为它注册了**更具体**的 401 处理器，Starlette 按 MRO 优先命中它。
    """


class LoginStateInvalid(RuntimeError):
    """回调携带的 state 不可用（伪造 / 过期 / 已消费）。"""

    def __init__(self, reason: str) -> None:
        """记录拒绝原因，供日志使用（**不含 state 原文**）。"""

        self.reason = reason
        super().__init__(reason)


class FeishuAuthSettings:
    """一次飞书登录装配所需的**最小**配置快照（不读 Secret 内容）。"""

    def __init__(
        self,
        *,
        app_id: str,
        admin_group_id: str,
        user_group_id: str,
        redirect_uri: str,
        scope: str = DEFAULT_FEISHU_SCOPE,
        cookie_secure: bool = False,
        session_ttl: timedelta = DEFAULT_SESSION_TTL,
        state_ttl: timedelta = DEFAULT_STATE_TTL,
        cookie_name: str = SESSION_COOKIE_NAME,
    ) -> None:
        """保存已校验的配置；`connector_id` 由 `app_id` 确定性派生（本期单企业）。"""

        self.app_id = app_id
        self.admin_group_id = admin_group_id
        self.user_group_id = user_group_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.cookie_secure = cookie_secure
        self.session_ttl = session_ttl
        self.state_ttl = state_ttl
        self.cookie_name = cookie_name

    @property
    def connector_id(self) -> str:
        """用 `app_id` 派生本企业的**稳定标识**，避免为"连接器"再引一张表。

        ⚠️ 多企业阶段本类仍是"一家企业一份配置"的载体：真正的多企业由
        `FeishuAuthRoutes` 持有多份本类实例来表达（见其 docstring）。

        ⚠️ 返回**字符串**（`uuid5(...).hex`）而不是 `UUID` 对象：身份相关列在库里
        是 `text`，用 UUID 对象会让 SQLAlchemy 生成 `= $1::UUID` 的比较，
        与 `text` 列不匹配（`operator does not exist: text = uuid`）。

        ⚠️⚠️ **算法与 `platform/identity/connector.py` 的 `FeishuConnector.connector_id`
        必须逐字一致**，且**一个字都不能改** —— 库里已有的身份映射依赖它
        （生产值 `7d88a4816c7a5e07a95ca3c2012fb2f7` 对应 `cli_aa2092574af9dbc2`）。
        算法不一致会让同一家企业在两处得到不同 ID，导致身份映射对不上。
        """

        return uuid5(NAMESPACE_URL, f"https://aima.local/identity/connectors/feishu/{self.app_id}").hex


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    """运行时用到的飞书身份依赖（全部可注入，测试因此不必连真飞书）。"""

    client: HttpxFeishuClient
    session_factory: Callable[[], Session]
    settings: FeishuAuthSettings


def _needs_query_redaction(path: str) -> bool:
    """判断该路径是否要抹掉敏感 query 参数（即"是不是飞书回调"）。

    判定覆盖两种形态：

    · 旧路径（精确）：`/api/v1/auth/feishu/callback`
    · 新路径（带企业标识）：`/api/v1/auth/feishu/<code>/callback`

    ⚠️ 为什么要有这个函数，而不是直接把新路径加进 `_REDACTED_QUERY_PATHS`：
    新路径**含变量**，无法枚举 —— 只能按模式判定。
    而**漏判的后果是授权码明文进访问日志**（安全缺陷），所以这里宁可放宽：
    只要"以飞书身份前缀开头、以 `/callback` 结尾"就处理。
    """

    if path in _REDACTED_QUERY_PATHS:
        return True
    return path.startswith(_REDACTED_QUERY_PATH_PREFIX) and path.endswith(
        _REDACTED_QUERY_PATH_SUFFIX
    )


class _CookieRedactingMiddleware:
    """把回调路径上的敏感 query 参数从 ASGI `scope` 里替换掉，再交给下游。

    ⚠️ 为什么必须做：uvicorn 的访问日志用 `get_path_with_query_string(scope)` 拼行，
    它**照抄** query string。浏览器回调必然带 `?code=...&state=...`，
    若不处理，授权码就被原样写进访问日志（违反"授权码 / state 绝不入日志"）。

    做法是"**先取出、再抹掉**"：真实参数暂存在 `scope["state"]`（内存对象，不参与日志），
    query string 换成打码版本。因此路由仍能拿到参数，日志里只剩 `<已隐藏>`。
    """

    def __init__(self, app: ASGIApp) -> None:
        """保存被包装的 ASGI 应用。"""

        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """进入下游前抹掉敏感 query；非 HTTP 或非目标路径直接透传。"""

        if scope["type"] == "http" and _needs_query_redaction(scope.get("path") or ""):
            self._redact(scope)
        await self._app(scope, receive, send)

    @staticmethod
    def _redact(scope: Scope) -> None:
        """把 `code` / `state` 等参数取到 state 里，并在 query string 中打码。"""

        raw = scope.get("query_string") or b""
        if not raw:
            return
        pairs = parse_qsl(raw.decode("latin-1"), keep_blank_values=True)
        sensitive = {key: value for key, value in pairs if key.lower() in _SENSITIVE_QUERY_KEYS}
        if not sensitive:
            return
        scope.setdefault("state", {})[_AUTH_PARAMS_STATE_KEY] = sensitive
        scope["query_string"] = urlencode(
            [
                (key, "<已隐藏>" if key.lower() in _SENSITIVE_QUERY_KEYS else value)
                for key, value in pairs
            ]
        ).encode("latin-1")


class _LoginStateStore:
    """`identity_login_states` 的唯一读写点（只存 state 的 SHA-256）。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方事务中的 Session（本类不自己提交）。"""

        self._session = session

    @staticmethod
    def _hash(state: str) -> str:
        """state 只以 SHA-256 入库；库里查不到明文，日志里也不写原文。"""

        return sha256(state.encode("utf-8")).hexdigest()

    def issue(
        self,
        *,
        return_to: str,
        ttl: timedelta,
        client_ip: str | None = None,
        connector_id: str | None = None,
    ) -> str:
        """生成新 state 并记录（返回原文，**只在这一次存在于内存**）。

        `client_ip` 写入 `identity_login_states.client_ip`，供登录入口限流按
        "过去 60 秒内同一 IP 发起了多少次登录"计数。取不到时留 `None`。

        `connector_id` **记住这次登录属于哪家企业**。回调时必须核对它与路径里的
        企业标识一致 —— 否则会出现"用 A 企业的 state 走 B 企业的回调"
        （跨企业串号，见 `consume` 的说明）。单企业形态下仍传 `None`（该列可空）。
        """

        state = secrets.token_urlsafe(32)
        now = beijing_now()
        self._session.execute(
            insert(identity_login_states_table).values(
                state_hash=self._hash(state),
                connector_id=connector_id,
                return_to=return_to,
                client_ip=client_ip,
                expires_at=now + ttl,
                consumed_at=None,
                created_at=now,
            )
        )
        return state

    def consume(
        self,
        state: str,
        *,
        expected_connector_id: str | None = None,
    ) -> str:
        """**原子**消费 state 并返回其中的 `return_to`；不可用时抛 `LoginStateInvalid`。

        一条语句同时完成"存在 + 未过期 + 未消费"三个判断，因此并发重放只有一个能成功。

        `expected_connector_id` 是**路径里那家企业**的标识。非空时会额外校验
        "签发这个 state 的企业 == 现在来回调的企业"：

        · 为什么要校验：state 与回调是**两个独立请求**，攻击者（或配置错误）
          可以拿 A 企业签发的 state 去打 B 企业的回调地址。
          若不做校验，系统会用 **B 的 App Secret** 去换 **A 的授权码** ——
          正常情况会失败，但**错误信息可能暴露配置差异**；
          更糟的是两家 Secret 若被配成同一个，会直接**串号**。
        · `None` 表示**单企业形态**（此时 state 里没记企业），跳过该校验 ——
          这就是"改造后旧行为不变"的保证。
        """

        if not state:
            raise LoginStateInvalid("回调参数里没有 state")

        now = beijing_now()
        consumed = cast(
            CursorResult[Any],
            self._session.execute(
                update(identity_login_states_table)
                .where(
                    identity_login_states_table.c.state_hash == self._hash(state),
                    identity_login_states_table.c.consumed_at.is_(None),
                    identity_login_states_table.c.expires_at > now,
                )
                .values(consumed_at=now)
                .returning(
                    identity_login_states_table.c.return_to,
                    identity_login_states_table.c.connector_id,
                )
            ),
        )
        row = consumed.first()
        if row is not None:
            issued_connector_id = row[1]
            # ── 跨企业串号防护（多企业形态才生效）──────────────────────────
            if (
                expected_connector_id is not None
                and issued_connector_id is not None
                and issued_connector_id != expected_connector_id
            ):
                # ⚠️ state **已被消费**（上面那条 UPDATE 已写 consumed_at）——
                # 这是刻意的：一次串号尝试不该让同一个 state 还能被重放。
                raise LoginStateInvalid("connector_mismatch")
            # 登录成功后的跳转目标来自**登录时经白名单过滤**的库内值，不是回调参数。
            return safe_return_to(row[0])

        raise LoginStateInvalid(self._classify(state))

    def _classify(self, state: str) -> str:
        """区分"伪造 / 过期 / 已消费"，**只用于日志**（对外一律 400，不泄露细节）。"""

        row = self._session.execute(
            select(
                identity_login_states_table.c.expires_at,
                identity_login_states_table.c.consumed_at,
            ).where(identity_login_states_table.c.state_hash == self._hash(state))
        ).first()
        if row is None:
            return "unknown"
        if row[1] is not None:
            return "replayed"
        return "expired"


class FeishuLoginRequiredResolver:
    """把"取不到有效会话"翻译成 401，把"已登录但无权限"留给 403。

    包装而非改写 `FeishuSessionIdentityResolver`：单 ①② 的实现保持逐字不变，
    401/403 的区分是**接线层**的职责。被包装的解析器由 `FeishuAuthRoutes` **惰性**建立
    —— 数据库 Runtime 的生命周期归路由装配体，两者必须共用同一个 Session 工厂。
    """

    def __init__(self, routes: FeishuAuthRoutes) -> None:
        """包装路由装配体；解析动作委托给它，避免重复建立数据库连接池。"""

        self._routes = routes

    def resolve(self, request: Request) -> Principal:
        """解析 Principal；无有效会话时抛 `AuthenticationRequired`（→ 401）。"""

        return self._routes.resolve_principal(request)


def build_feishu_auth_settings(settings: PlatformSettings) -> FeishuAuthSettings | None:
    """从平台配置构造飞书登录配置；**未配置返回 `None`**（调用方沿用开发身份）。

    允许 `None` 是刻意的：`AIMA_FEISHU_*` 一个都没设时，进程行为必须与接入前完全一致
    （不破坏既有开发身份与既有测试）。只设了一部分则由 `PlatformSettings` 校验直接报错，
    不会静默降级成"看起来配了、其实没启用"。
    """

    app_id = settings.feishu_app_id
    if app_id is None:
        return None
    admin_group_id = settings.feishu_admin_group_id
    user_group_id = settings.feishu_user_group_id
    redirect_uri = settings.feishu_redirect_uri
    # 走到这里说明配置校验已保证三者非空；显式重复判断只为让类型收窄可读。
    if admin_group_id is None or user_group_id is None or redirect_uri is None:
        return None

    return FeishuAuthSettings(
        app_id=app_id,
        admin_group_id=admin_group_id,
        user_group_id=user_group_id,
        redirect_uri=redirect_uri,
        scope=settings.feishu_scope,
        # Cookie 的 Secure 按环境：默认跟随回调地址的协议（本地 http 关、生产 https 开），
        # 也允许用 AIMA_FEISHU_COOKIE_SECURE 显式覆盖。
        cookie_secure=(
            settings.feishu_cookie_secure
            if settings.feishu_cookie_secure is not None
            else redirect_uri.startswith("https://")
        ),
        session_ttl=timedelta(hours=settings.feishu_session_ttl_hours),
        state_ttl=timedelta(seconds=settings.feishu_state_ttl_seconds),
    )


class FeishuAuthRoutes:
    """登录路由的装配体：持有多企业配置与 DB Runtime，并在关闭时释放连接池。

    ════════ 两种配置形态（并存）════════

    | 形态 | `auth_settings` | `connectors` | 可用路由 |
    |---|---|---|---|
    | **单企业**（改造前的现状）| 有值 | 空 | 旧路径 `/login` · `/callback` |
    | **多企业**（本次新增）| 可为 `None` | 非空 | 新旧路径**都可用** |

    **为什么多企业时旧路径也可用**：它需要"一家默认企业"的语义。
    多企业时把**配置里的第一家**当作默认 —— 这样旧回调地址（已登记进飞书后台）
    不会立刻失效，给迁移留出窗口。
    """

    def __init__(
        self,
        *,
        auth_settings: FeishuAuthSettings | None,
        connectors: Mapping[str, FeishuAuthSettings] | None = None,
        connector_display_names: Mapping[str, str] | None = None,
        session_factory: Callable[[], Session] | None = None,
        client: HttpxFeishuClient | None = None,
        app_secret_reader: Callable[[], SecretStr] | None = None,
        rate_limiter: LoginRateLimiter | None = None,
    ) -> None:
        """保存配置与可注入依赖；`session_factory` / `client` 未注入时惰性自建。

        `connectors` 是 `企业标识 -> 该企业的飞书配置`；为空即单企业形态。
        `connector_display_names` 是 `企业标识 -> 界面上显示的名字`
        （由配置层的 `FeishuConnector.display_name` 提供 ——
        `FeishuAuthSettings` 本身不持有显示名，因为它是运行时快照、只管鉴权要素）。
        """

        self._settings = auth_settings
        self._session_factory = session_factory
        self._client = client
        self._app_secret_reader = app_secret_reader
        # 登录入口限流（方案 §6.0 S8）：默认双轨阈值；测试可注入更小的值。
        self._rate_limiter = rate_limiter or LoginRateLimiter(
            global_limit=DEFAULT_GLOBAL_LIMIT, ip_limit=DEFAULT_IP_LIMIT
        )
        self._runtime: DatabaseRuntime | None = None
        self._owns_runtime = session_factory is None
        # ── 多企业（本次新增）──────────────────────────────────────────────
        # `code -> FeishuAuthSettings`。**为空**表示单企业形态，
        # 此时所有路径都走 `self._settings`（行为与改造前逐字一致）。
        #
        # ⚠️ 为什么保留 `self._settings` 而不改成"注册表 + 默认值"二选一：
        #   `self._settings` 已被 7 处内部代码引用，且旧路由依赖"唯一配置"语义。
        #   加一个并列的映射，改动面最小、旧行为零风险。
        self._connectors: dict[str, FeishuAuthSettings] = dict(connectors or {})
        # 企业标识 → 显示名。只用于前端展示列表；缺失时回退成 code 本身。
        self._connector_display_names: dict[str, str] = dict(connector_display_names or {})

    # ------------------------------------------------------- 多企业：配置查找
    @property
    def supports_multiple_connectors(self) -> bool:
        """**当前是否配置了多家企业**（是数据状态，不是"路由是否存在"）。

        ⚠️ 别和"路由是否注册"混淆：多企业路由**总是注册**（见 `install` 的说明），
        本属性只回答"这次部署实际配了几家"。
        """

        return bool(self._connectors)

    @property
    def connector_codes(self) -> tuple[str, ...]:
        """全部企业标识（按构造顺序）。"""

        return tuple(self._connectors)

    def settings_for(self, connector_code: str | None) -> FeishuAuthSettings | None:
        """按企业标识取配置；`None` 表示"用默认那家"。

        返回 `None` 的两种情形由调用方区分：
        · 单企业形态且传了 `None` → 由 `_require_settings` 给出默认配置；
        · **传了 code 但该企业不存在** → 调用方应回 **404**（而不是静默回退），
          否则用户点了「爱玛登录」却进了 NNIT 的授权页，且没有任何提示。
        """

        if connector_code is None:
            return self._settings
        return self._connectors.get(connector_code)


    # ------------------------------------------------------------------ 装配
    def install(self, application: FastAPI) -> None:
        """把中间件、异常处理器与三个路由装到应用上。"""

        application.add_middleware(_CookieRedactingMiddleware)

        @application.exception_handler(AuthenticationRequired)
        async def _handle_authentication_required(
            request: Request, _: AuthenticationRequired
        ) -> JSONResponse:
            """统一 401 Contract：前端据此跳登录页（**不是** 403，避免误判成"无权限"）。"""

            return _error_response(
                status_code=401,
                request_id=_request_id(request),
                title="需要登录",
                detail="当前会话不存在或已失效，请重新登录。",
                code="authentication_required",
            )

        @application.exception_handler(LoginRateLimited)
        async def _handle_login_rate_limited(
            request: Request, _: LoginRateLimited
        ) -> JSONResponse:
            """登录发起过于频繁 → 429（S8）。

            ⚠️ 对外**不区分** IP 维度与全局维度，也不回显当前计数 ——
            否则等于把"还剩多少额度"告诉探测者，帮助他们卡阈值。
            """

            return _error_response(
                status_code=429,
                request_id=_request_id(request),
                title="请求过于频繁",
                detail="登录发起过于频繁，请稍后再试。",
                code="login_rate_limited",
            )

        @application.exception_handler(_UnknownConnector)
        async def _handle_unknown_connector(
            request: Request, exc: _UnknownConnector
        ) -> JSONResponse:
            """企业标识不在配置里 → 404。

            ⚠️ 为什么不是 503：这是"**你请求的这家企业没配**"，
            不是"服务不可用"。回 404 能让漏配立刻暴露，
            而不是让用户被静默送到另一家企业的授权页。
            """

            return _error_response(
                status_code=404,
                request_id=_request_id(request),
                title="未知的登录企业",
                detail="请求的企业标识不存在，请联系管理员确认配置。",
                code="unknown_connector",
            )

        if self._settings is not None:
            self._install_lifespan(application)
        application.add_api_route(
            LOGIN_PATH,
            self.login,
            methods=["GET"],
            operation_id="startFeishuLogin",
            name="startFeishuLogin",
            tags=["identity"],
            responses=self._error_responses(),
        )
        application.add_api_route(
            CALLBACK_PATH,
            self.callback,
            methods=["GET"],
            operation_id="completeFeishuLogin",
            name="completeFeishuLogin",
            tags=["identity"],
            responses=self._error_responses(),
        )
        # ── 多企业路由（本次新增）──────────────────────────────────────────
        # ⚠️ 路径参数名是 **`connector_code`**，不是 `code` —— 见 `callback` 的 docstring：
        #    `code` 会被飞书回调 query 里的授权码参数抢占，且**静默**出错。
        #
        # ⚠️⚠️ 这 3 条路由**总是注册**，不按配置条件 —— 这是刻意的选择：
        #
        #   路由是**代码提供的能力**，不该随环境变量变化。若改成"配了多企业才注册"，
        #   那么契约生成（CI 不设飞书环境）就拿不到这 3 条 →
        #   **OpenAPI 契约与运行时代码不一致**，前端也无法用生成的 client。
        #
        #   单企业形态下这 3 条的实际行为（由 `_require_settings` 决定）：
        #     · `/feishu/{connector_code}/login|callback` → **404**（企业不存在）
        #     · `/connectors` → **200 + 空列表**（前端据此降级为单按钮）
        application.add_api_route(
            MULTI_LOGIN_PATH,
            self.login,
            methods=["GET"],
            operation_id="startFeishuLoginForConnector",
            name="startFeishuLoginForConnector",
            tags=["identity"],
            responses=self._error_responses(),
        )
        application.add_api_route(
            MULTI_CALLBACK_PATH,
            self.callback,
            methods=["GET"],
            operation_id="completeFeishuLoginForConnector",
            name="completeFeishuLoginForConnector",
            tags=["identity"],
            responses=self._error_responses(),
        )
        # 企业列表（未认证端点，**只返回 code + 显示名**）。
        # ⚠️ 单企业形态返回**空列表**（而非 404）—— 前端把"空列表"当作
        #    "没有多企业可选"的降级信号，比 404 更好处理。
        application.add_api_route(
            CONNECTORS_PATH,
            self.list_connectors,
            methods=["GET"],
            operation_id="listAuthConnectors",
            name="listAuthConnectors",
            tags=["identity"],
            response_model=AuthConnectorListResponse,
        )
        application.add_api_route(
            LOGOUT_PATH,
            self.logout,
            methods=["POST"],
            operation_id="logoutCurrentSession",
            name="logoutCurrentSession",
            tags=["identity"],
            responses=self._error_responses(),
        )

    @staticmethod
    def _error_responses() -> dict[int | str, dict[str, Any]]:
        """三个路由共用的稳定错误 Contract（全部走统一 `HttpErrorResponse`）。"""

        return {
            400: {"model": HttpErrorResponse},
            401: {"model": HttpErrorResponse},
            403: {"model": HttpErrorResponse},
            502: {"model": HttpErrorResponse},
            503: {"model": HttpErrorResponse},
        }

    def _install_lifespan(self, application: FastAPI) -> None:
        """在应用关闭时释放本装配体自建的数据库连接池。"""

        router = cast(Any, application.router)
        original_lifespan = router.lifespan_context

        @asynccontextmanager
        async def lifecycle_lifespan(app: FastAPI) -> Any:
            """包住主 lifespan，退出时释放本模块持有的 Runtime。"""

            async with original_lifespan(app):
                try:
                    yield
                finally:
                    if self._runtime is not None:
                        self._runtime.dispose()

        router.lifespan_context = lifecycle_lifespan

    # ------------------------------------------------------------- 依赖获取
    def _sessions(self) -> Callable[[], Session]:
        """返回 Session 工厂；未注入时惰性建立独立 Runtime 并持有其生命周期。"""

        if self._session_factory is None:
            if self._runtime is None:
                self._runtime = DatabaseRuntime(load_settings())
            self._session_factory = self._runtime.new_session
        return self._session_factory

    def resolve_principal(self, request: Request) -> Principal:
        """解析当前请求的 Principal；无有效会话时抛 `AuthenticationRequired`。

        ⚠️ 这里**必须**用同一个 Session 工厂建立 `FeishuSessionIdentityResolver`，
        而不是在装配阶段就建好一个：数据库 Runtime 归本装配体所有，
        装配阶段还拿不到（`install()` 之前）。惰性建立同时也让"未配置飞书"的进程
        **一次数据库连接都不建**。
        """

        from aima_ugc.modules.identity.feishu import FeishuSessionIdentityResolver

        try:
            return FeishuSessionIdentityResolver(
                # 单 ② 的签名标的是 `sessionmaker`，而本装配体只保证"可调用且返回 Session"
                # （`DatabaseRuntime.new_session` 就是这个形状）。运行期两者等价，这里如实收窄类型。
                session_factory=cast("Any", self._sessions())
            ).resolve(request)

        except AuthorizationDenied as exc:
            # 单 ② 的实现对"没有 Cookie / 会话不存在 / 已撤销 / 已过期"一律抛
            # `AuthorizationDenied`；这些语义都是**未登录**，翻译成 401。
            raise AuthenticationRequired("当前请求没有可用会话") from exc

    def _feishu_client(self) -> HttpxFeishuClient:
        """返回飞书客户端；未注入时按配置惰性建立（Secret 只在此时读取一次）。"""

        if self._client is None:
            if self._settings is None:
                raise RuntimeError("飞书未配置")
            reader = self._app_secret_reader or self._default_app_secret_reader
            self._client = HttpxFeishuClient(
                app_id=self._settings.app_id,
                app_secret=reader(),
            )
        return self._client

    @staticmethod
    def _default_app_secret_reader() -> SecretStr:
        """按配置里的 **Secret 引用**读 App Secret（绝对路径不回显、不写日志）。"""

        from aima_ugc.platform.security import read_secret_ref

        settings = load_settings()
        return read_secret_ref(
            settings.external_secret_root,
            settings.feishu_app_secret_ref,
        )

    # ------------------------------------------------------------------ 路由
    def list_connectors(self) -> AuthConnectorListResponse:
        """返回**可登录企业列表**（供前端登录页渲染企业选择）。

        ⚠️ 这是一个**未认证**端点（登录页在未登录状态下要调它），因此：

        · **只返回 `code` 与显示名** —— 绝不含 Secret / 组 ID / 回调地址；
        · **不透露"某企业是否可用"** —— 那会变成配置探测接口。

        **顺序 = 配置顺序**（前端按钮顺序依赖它，见 `ConnectorRegistry` 的说明）。
        """

        return AuthConnectorListResponse(
            items=[
                AuthConnectorResponse(
                    code=code,
                    display_name=self._connector_display_names.get(code, code),
                )
                for code in self._connectors
            ]
        )

    def login(
        self,
        request: Request,
        return_to: str | None = None,
        connector_code: str | None = None,
        connector: str | None = None,
    ) -> Response:
        """发起登录：限流 → 校验 `return_to` → 生成一次性 state → 302 跳飞书授权页。

        **企业标识的两个来源**：

        | 参数 | 来自 | 用于 |
        |---|---|---|
        | `connector_code` | 新路由的**路径** `/feishu/{connector_code}/login` | 多企业主路径 |
        | `connector` | 旧路由 **query** `/feishu/login?connector=aima` | 兼容主页带 `?c=` |

        ⚠️ 为什么旧路由也要支持指定企业（`?connector=`）：
        飞书后台的「网页应用主页」会配成 `http://x/login?c=aima`，
        前端登录页读到 `?c=` 后**转发给后端**，从而自动路由到正确企业 ——
        用户**不需要在企业列表里手动选**。

        两者都没传时走默认那家（单企业形态即唯一那家）—— **旧行为不变**。
        """

        effective_connector = connector_code or connector
        auth_settings = self._require_settings(effective_connector)
        # 只有站内相对路径能通过；其余（绝对 URL / //evil / javascript:）退回 "/"。
        target = safe_return_to(return_to)
        client_ip = client_ip_of(request)
        session = self._sessions()()
        try:
            with session.begin():
                # ⚠️ 限流判断与"写 state"**必须在同一事务**里：
                # 计数读的是本表过去 60 秒的行数，若分成两个事务，
                # 并发请求会同时读到偏小的计数，阈值被绕过。
                try:
                    self._rate_limiter.check(session, client_ip=client_ip)
                except LoginRateLimited as exc:
                    log_event(
                        _LOGGER,
                        logging.WARNING,
                        "identity.feishu_login_rate_limited",
                        "登录发起过于频繁",
                        request_id=_request_id(request),
                        # 只记维度与计数，**不记 IP**（避免把客户端地址写进日志）。
                        scope=exc.scope,
                        limit=exc.limit,
                        observed=exc.observed,
                    )
                    raise
                state = _LoginStateStore(session).issue(
                    return_to=target,
                    ttl=auth_settings.state_ttl,
                    client_ip=client_ip,
                    # 记住"这次登录属于哪家企业"，回调时核对（防跨企业串号）。
                    connector_id=auth_settings.connector_id,
                )
        finally:
            session.close()

        authorize_url = HttpxFeishuClient.build_authorize_url(
            app_id=auth_settings.app_id,
            redirect_uri=auth_settings.redirect_uri,
            scope=auth_settings.scope,
            state=state,
        )
        # ⚠️ 只记"发起了登录"，**不记 state、不记完整 URL**。
        log_event(
            _LOGGER,
            logging.INFO,
            "identity.feishu_login_started",
            "已发起飞书登录",
            request_id=_request_id(request),
        )
        return RedirectResponse(url=authorize_url, status_code=302)

    def callback(
        self,
        request: Request,
        code: str | None = None,
        state: str | None = None,
        connector_code: str | None = None,
    ) -> Response:
        """飞书回跳：消费 state → 换令牌 → 取用户 → 查组 → 判角色 → 建会话 → 302。

        ⚠️⚠️ **参数名不能叫 `code`**：飞书的 OAuth 授权码在 query string 里叫 `code`，
        若路径参数也叫 `code`，FastAPI 会**静默**把路径值（企业标识）填进这个参数，
        真正的授权码就取不到了 —— 且**不报错**，表现成"飞书说授权码无效"。

        `connector_code` 由新路由
        `/api/v1/auth/feishu/{connector_code}/callback` 注入；
        旧路由不传它，走 `self._settings`（**行为与改造前逐字一致**）。
        """

        auth_settings = self._require_settings(connector_code)
        # 中间件已把真实参数暂存到 state 里并在 query string 上打码；
        # 直接调用（无中间件）时回退读 query 参数，行为保持一致。
        params = getattr(request.state, _AUTH_PARAMS_STATE_KEY, None)
        if isinstance(params, dict):
            code = params.get("code", code)
            state = params.get("state", state)

        request_id = _request_id(request)
        if not code:
            return _error_response(
                status_code=400,
                request_id=request_id,
                title="回调参数不完整",
                detail="飞书回调缺少授权码。",
                code="feishu_callback_incomplete",
            )

        session = self._sessions()()
        try:
            with session.begin():
                try:
                    # 多企业形态下额外核对"签发 state 的企业 == 现在回调的企业"。
                    # 单企业形态（旧路由不带 code）传 `None`，跳过校验 —— 旧行为不变。
                    return_to = _LoginStateStore(session).consume(
                        state or "",
                        expected_connector_id=(
                            auth_settings.connector_id if connector_code is not None else None
                        ),
                    )
                except LoginStateInvalid as exc:
                    log_event(
                        _LOGGER,
                        logging.WARNING,
                        "identity.feishu_state_rejected",
                        "飞书回调 state 校验未通过",
                        request_id=request_id,
                        reason=exc.reason,
                    )
                    return _error_response(
                        status_code=400,
                        request_id=request_id,
                        title="登录请求已失效",
                        detail="请重新发起飞书登录。",
                        code="feishu_state_invalid",
                    )
        finally:
            session.close()

        # ⚠️ 外部 HTTP 一律在数据库事务之外（AGENTS §7）。
        client = self._feishu_client()
        try:
            tokens = client.exchange_authorization_code(code)
            user = client.get_current_user(tokens.access_token)
            group_ids = client.list_user_groups(user.open_id)
        except FeishuError as exc:
            # 失败分类由单 ① 的 `is_retryable` 决定：可重试却仍失败 → 上游暂时不可用(503)，
            # 不可重试（参数/认证类）→ 上游明确拒绝(502)。**绝不回显异常里的任何凭据。**
            status_code = 503 if exc.retryable else 502
            log_event(
                _LOGGER,
                logging.WARNING,
                "identity.feishu_upstream_failed",
                "飞书接口调用失败",
                request_id=request_id,
                step=exc.step,
                upstream_code=exc.code,
                http_status=exc.http_status,
                retryable=exc.retryable,
            )
            return _error_response(
                status_code=status_code,
                request_id=request_id,
                title="飞书服务不可用",
                detail="身份校验暂时无法完成，请稍后重试。",
                code="feishu_upstream_unavailable",
            )

        try:
            # 成员测试判角色（绝不用 groups[0]）；两个组都不属于 → AuthorizationDenied。
            role = resolve_role(
                group_ids,
                admin_group_id=auth_settings.admin_group_id,
                user_group_id=auth_settings.user_group_id,
            )
        except AuthorizationDenied:
            log_event(
                _LOGGER,
                logging.WARNING,
                "identity.feishu_not_authorized",
                "用户不属于任何允许的用户组",
                request_id=request_id,
                group_count=len(group_ids),
            )
            return _error_response(
                status_code=403,
                request_id=request_id,
                title="没有访问权限",
                detail="当前账号不在允许使用本系统的用户组内。",
                code="feishu_group_required",
            )

        provider_subject = user.union_id or user.open_id
        display_name = user.name.strip() or "飞书用户"
        department = self._best_effort_department(client, user.open_id)
        token = self._issue_session(
            auth_settings=auth_settings,
            provider_subject=provider_subject,
            display_name=display_name,
            role=role,
            group_ids=group_ids,
            avatar_url=user.avatar_url,
            department=department,
            request_id=request_id,
            # 多企业形态下把企业标识带进审计；单企业为 None。
            connector_code=connector_code,
        )

        log_event(
            _LOGGER,
            logging.INFO,
            "identity.feishu_login_succeeded",
            "飞书登录成功",
            request_id=request_id,
            # 只记角色与组数量：**不记 open_id / union_id / 令牌 / 授权码**。
            role=role,
            group_count=len(group_ids),
        )
        response = RedirectResponse(url=return_to, status_code=302)
        self._set_session_cookie(response, auth_settings, token)
        return response

    def logout(self, request: Request) -> Response:
        """登出：**服务端撤销会话** + 清 Cookie（幂等，重复登出不报错）。"""

        token = request.cookies.get(SESSION_COOKIE_NAME)
        revoked = False
        if token:
            session = self._sessions()()
            try:
                with session.begin():
                    revoked = SessionStore(session).revoke(token)
            finally:
                session.close()
        log_event(
            _LOGGER,
            logging.INFO,
            "identity.session_logout",
            "已退出登录",
            request_id=_request_id(request),
            revoked=revoked,
        )
        response = Response(status_code=204)
        # Cookie 属性必须与写入时一致，否则浏览器可能留下同名的另一份 Cookie。
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="lax",
            secure=self._cookie_secure(),
        )
        return response

    # ------------------------------------------------------------- 内部实现
    def _issue_session(
        self,
        *,
        auth_settings: FeishuAuthSettings,
        provider_subject: str,
        display_name: str,
        role: str,
        group_ids: tuple[str, ...],
        avatar_url: str | None,
        department: tuple[str, str] | None,
        request_id: str,
        connector_code: str | None = None,
    ) -> str:
        """在**一个事务**里写 Principal 映射、AIMA 会话与登录审计，返回明文令牌。

        `connector_code` 是**哪家企业**（多企业形态下由路由注入；单企业为 `None`）。
        它只进审计，**不参与授权判断**。
        """

        session = self._sessions()()
        try:
            with session.begin():
                principal = PrincipalStore(session).resolve_or_create(
                    connector_id=auth_settings.connector_id,
                    provider="feishu",
                    provider_subject=provider_subject,
                    display_name=display_name,
                )
                PrincipalStore(session).touch_last_seen(
                    connector_id=auth_settings.connector_id,
                    provider_subject=provider_subject,
                )
                token = SessionStore(session).issue(
                    principal_id=principal.principal_id,
                    display_name=principal.display_name,
                    role=role,
                    avatar_url=avatar_url,
                    department_id=department[0] if department else None,
                    department_name=department[1] if department else None,
                    # 判角色依据留痕：排查"为什么他是管理员"时要能回看命中了哪几个组。
                    # 只用于审计，不参与授权判断（授权只看 role）。
                    feishu_group_ids=group_ids,
                    ttl=auth_settings.session_ttl,
                )
                # 登录成功写入 AIMA 既有审计表（S11）。与业务事实**同一事务**，
                # 因此不会出现"会话建了但审计没写"的中间态。
                # ⚠️ `safe_detail` 只放非敏感字段：不记 open_id / union_id / 令牌 / 授权码。
                PostgresAuditRepository(session).append(
                    AuditEvent(
                        id=uuid4(),
                        actor_kind="principal",
                        actor_ref=principal.principal_id,
                        event_type="identity.feishu_login_succeeded",
                        object_type="identity_session",
                        object_id=principal.principal_id,
                        request_id=request_id,
                        safe_detail=cast(
                            Any,
                            {
                                "role": role,
                                "group_count": len(group_ids),
                                "is_new_principal": principal.created,
                                "source": "feishu",
                                # 多企业后"这人是哪家企业的"是关键审计维度。
                                # `safe_detail` 是 jsonb，**加键属兼容变化**（不改结构）。
                                # 单企业形态下为 None（与改造前的记录形态保持一致）。
                                "connector_code": connector_code,
                            },
                        ),
                        created_at=beijing_now(),
                    )
                )
                return token
        finally:
            session.close()

    @staticmethod
    def _best_effort_department(
        client: HttpxFeishuClient,
        open_id: str,
    ) -> tuple[str, str] | None:
        """尽力取部门（展示用）；取不到不影响登录。

        ⚠️ 这两次调用走**应用身份**通讯录接口，需要"通讯录权限范围"覆盖该用户；
        范围不足时飞书**不报错但返回空**。部门只是展示信息，因此这里不因它失败而拒绝登录。
        """

        try:
            detail = client.get_user(open_id)
            if not detail.department_ids:
                return None
            department_id = detail.department_ids[0]
            return department_id, client.get_department(department_id).name or department_id
        except FeishuError:
            return None

    @staticmethod
    def _set_session_cookie(
        response: Response,
        auth_settings: FeishuAuthSettings,
        token: str,
    ) -> None:
        """写入 AIMA 会话 Cookie：HttpOnly + SameSite=Lax + Path=/（Secure 按环境）。"""

        response.set_cookie(
            auth_settings.cookie_name,
            token,
            max_age=int(auth_settings.session_ttl.total_seconds()),
            path="/",
            httponly=True,
            samesite="lax",
            secure=auth_settings.cookie_secure,
        )

    def _cookie_secure(self) -> bool:
        """返回当前环境的 Cookie Secure 开关（未配置时按"非安全"处理）。"""

        return self._settings.cookie_secure if self._settings is not None else False

    def _require_settings(self, connector_code: str | None = None) -> FeishuAuthSettings:
        """取该企业的飞书配置；未配置飞书时返回 503 而不是 500。

        **返回值语义**（`connector_code` 的三种情况）：

        | 传入 | 形态 | 行为 |
        |---|---|---|
        | `None` | 单企业 | 返回唯一配置（**与改造前逐字一致**）|
        | `None` | 多企业 | 返回**第一家**（旧路由的兼容语义）|
        | 具体 code | 多企业 | 返回该企业配置；**不存在则 404** |

        ⚠️ **为什么"企业不存在"要回 404 而不是回退到默认那家**：
        用户点了「爱玛登录」，若静默把他送到 NNIT 的授权页，
        他会看到 NNIT 的企业名 —— 这是**误导**，且没有任何错误提示。
        明确回 404 才能让"配置漏了这家企业"立刻被发现。
        """

        # 单企业形态（含"多企业但未指定 code"的兼容分支）
        if connector_code is None:
            if self._settings is not None:
                return self._settings
            # 多企业形态下 `_settings` 可能为 None：用配置里的第一家兜底。
            if self._connectors:
                return next(iter(self._connectors.values()))
            raise _FeishuNotConfigured

        found = self._connectors.get(connector_code)
        if found is None:
            raise _UnknownConnector(connector_code)
        return found



class _FeishuNotConfigured(Exception):
    """飞书登录未配置（`AIMA_FEISHU_*` 未提供）。"""


class _UnknownConnector(Exception):
    """路径里的企业标识在配置中不存在（多企业形态）。

    与 `_FeishuNotConfigured` 分开，是为了让 HTTP 层给出**不同**的响应：
    前者是 503（能力未启用），后者是 404（这个企业没配）。
    """

    def __init__(self, connector_code: str) -> None:
        """记录那个未知的企业标识（用于日志；**它来自 URL，不是敏感信息**）。"""

        self.connector_code = connector_code
        super().__init__(f"未知的飞书企业标识：{connector_code}")



def _service_unavailable(request: Request, _: Exception) -> JSONResponse:
    """未配置飞书时三个路由统一返回 503（而不是 500 或 404）。"""

    return _error_response(
        status_code=503,
        request_id=_request_id(request),
        title="飞书登录未启用",
        detail="当前部署没有配置飞书身份接入。",
        code="feishu_not_configured",
    )


def _request_id(request: Request) -> str:
    """读取主 API middleware 建立的 request_id；缺失时给安全兜底。"""

    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else secrets.token_hex(8)


def _error_response(
    *,
    status_code: int,
    request_id: str,
    title: str,
    detail: str,
    code: str,
) -> JSONResponse:
    """构造与主 API 一致的 `HttpErrorResponse`（前端 `unwrapResponse` 依赖它）。"""

    payload = HttpErrorResponse(
        type=f"https://aima.example/problems/{code}",
        title=title,
        status=status_code,
        detail=detail,
        request_id=request_id,
        errors=(HttpErrorItem(field=None, code=code, message=detail),),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"x-request-id": request_id},
    )


def build_feishu_identity(
    settings: PlatformSettings | None = None,
    *,
    session_factory: Callable[[], Session] | None = None,
    client: HttpxFeishuClient | None = None,
) -> tuple[IdentityResolver, FeishuAuthRoutes]:
    """装配飞书身份：返回 `(resolver, 路由装配体)`。

    未配置飞书时返回 `DevelopmentIdentityResolver` —— 与接入前的**默认行为完全一致**；
    配置了飞书时才返回 `FeishuLoginRequiredResolver`（无会话 → 401）。

    **支持两种配置形态**：

    · **单企业**（`AIMA_FEISHU_APP_ID` 等）→ 与改造前逐字一致；
    · **多企业**（`AIMA_FEISHU_CONNECTORS`）→ 额外注册带 `{connector_code}` 的路由，
      并为每个企业构造独立的 `FeishuAuthSettings`（各自的 App ID / Secret 引用 / 组 ID / 回调）。
    """

    resolved_settings = load_settings() if settings is None else settings

    # ── 多企业优先：配了 `AIMA_FEISHU_CONNECTORS` 就以它为准 ──────────────
    connector_map = _build_connector_settings_map(resolved_settings)
    if connector_map:
        registry = resolved_settings.feishu_connectors
        display_names = (
            {c.code: c.display_name for c in registry} if registry is not None else {}
        )
        routes = FeishuAuthRoutes(
            # 多企业时 `auth_settings` 传**第一家**：旧路由（无 code）用它兜底，
            # 这样已登记进飞书后台的旧回调地址不会立刻失效。
            auth_settings=next(iter(connector_map.values())),
            connectors=connector_map,
            connector_display_names=display_names,
            session_factory=session_factory,
            client=client,
        )
        resolver: IdentityResolver = FeishuLoginRequiredResolver(routes)
        return resolver, routes

    # ── 单企业（改造前的路径，行为不变）───────────────────────────────────
    auth_settings = build_feishu_auth_settings(resolved_settings)
    routes = FeishuAuthRoutes(
        auth_settings=auth_settings,
        session_factory=session_factory,
        client=client,
    )
    if auth_settings is None:
        # 未配置：既不产生 401 语义，也不改变任何既有路由的行为。
        return DevelopmentIdentityResolver(), routes

    # 配了飞书才启用会话解析（无会话 → 401）；解析器与登录路由共用同一个装配体，
    # 因此也共用同一个数据库 Runtime / Session 工厂。
    resolver2: IdentityResolver = FeishuLoginRequiredResolver(routes)
    return resolver2, routes


def _build_connector_settings_map(
    settings: PlatformSettings,
) -> dict[str, FeishuAuthSettings]:
    """把多企业配置逐家转成 `FeishuAuthSettings`；未启用时返回空字典。

    ⚠️ 每个企业**各自**的 `cookie_secure` 按**自己**的回调协议推断 ——
    不能共用一个值：多企业里可能一家走 https、另一家还在 http 联调。
    """

    registry = settings.feishu_connectors
    if registry is None:
        return {}

    result: dict[str, FeishuAuthSettings] = {}
    for connector in registry:
        result[connector.code] = FeishuAuthSettings(
            app_id=connector.app_id,
            admin_group_id=connector.admin_group_id,
            user_group_id=connector.user_group_id,
            redirect_uri=connector.redirect_uri,
            scope=settings.feishu_scope,
            cookie_secure=(
                settings.feishu_cookie_secure
                if settings.feishu_cookie_secure is not None
                else connector.redirect_uri.startswith("https://")
            ),
            session_ttl=timedelta(hours=settings.feishu_session_ttl_hours),
            state_ttl=timedelta(seconds=settings.feishu_state_ttl_seconds),
        )
    return result



def install_feishu_auth_routes(
    application: FastAPI,
    *,
    auth_routes: FeishuAuthRoutes,
) -> None:
    """把飞书登录路由装到最终应用上，并为"未配置"注册 503 处理器。"""

    application.add_exception_handler(_FeishuNotConfigured, _service_unavailable)
    auth_routes.install(application)


__all__ = [
    "CALLBACK_PATH",
    "DEFAULT_FEISHU_SCOPE",
    "DEFAULT_RETURN_TO",
    "DEFAULT_STATE_TTL",
    "LOGIN_PATH",
    "LOGOUT_PATH",
    "AuthenticationRequired",
    "FeishuAuthRoutes",
    "FeishuAuthSettings",
    "FeishuLoginRequiredResolver",
    "LoginStateInvalid",
    "ResolvedIdentity",
    "build_feishu_auth_settings",
    "build_feishu_identity",
    "install_feishu_auth_routes",
    "is_safe_return_to",
    "safe_return_to",
]

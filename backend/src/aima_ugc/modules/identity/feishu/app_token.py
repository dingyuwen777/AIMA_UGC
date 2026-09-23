"""飞书**应用令牌**（`tenant_access_token`）的获取、缓存与过期刷新。

════════ 为什么必须缓存 ════════

飞书对换令牌接口有频率限制，而一次登录至少要打 3~4 次飞书接口。
如果每次业务调用都重新换一次令牌，早上班高峰期会**自己把自己的配额打满**。
所以令牌在进程内缓存，过期才刷新。

════════ 并发为什么要加锁（双重检查） ════════

多个请求线程可能**同时**发现缓存过期，然后**各自**去打飞书换令牌 ——
这就是"缓存了却依然重复请求"。本模块用锁把并发收敛成一次真实请求：
后到的线程拿到锁后会**重新检查**缓存，发现已经有人换好了就直接复用。
所以锁内必须再检查一次，不能只在锁外检查。

════════ 关于进程边界（诚实说明） ════════

本缓存的作用域是**当前进程**。多 Worker 部署时每个进程各持一份，
进程启动后各自换一次令牌（N 个 Worker ≈ N 次请求，不是请求风暴）。
跨进程共享缓存需要额外的一致性存储，本项目当前没有该基础设施，
因此**不实现**，也不假装实现了。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

import httpx
from pydantic import SecretStr

from .errors import (
    FeishuError,
    as_float,
    decode_feishu_response,
    ensure_feishu_success,
    redact,
)

DEFAULT_FEISHU_BASE_URL = "https://open.feishu.cn"
APP_ACCESS_TOKEN_PATH = "/open-apis/auth/v3/app_access_token/internal"

# 飞书返回的令牌有效期约 7200 秒。提前 300 秒刷新，留出时钟偏差与网络抖动余量，
# 避免"刚取到就过期"导致业务请求白跑一趟。
DEFAULT_REFRESH_MARGIN_SECONDS = 300.0
DEFAULT_TIMEOUT_SECONDS = 10.0

# 响应里缺少 expire 时的保守兜底：按飞书默认 2 小时算，只会让刷新偏早，不会用过期值。
FALLBACK_EXPIRE_SECONDS = 7200.0


class FeishuAppTokenCache:
    """进程内线程安全的 `tenant_access_token` 缓存。

    ⚠️ `app_secret` 以 `SecretStr` 持有：它只在构造请求体的那一刻取值，
    绝不进入日志、异常信息或 `repr`。

    `client` 由调用方提供 —— 连接池的复用与关闭责任都在调用方，
    本类不隐式创建、也不隐式关闭别人的 HTTP Client。
    """

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: SecretStr,
        client: httpx.Client,
        base_url: str = DEFAULT_FEISHU_BASE_URL,
        refresh_margin_seconds: float = DEFAULT_REFRESH_MARGIN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """建立缓存；`clock` 可注入，便于测试时不用真的等 2 小时。"""

        if not app_id or app_id != app_id.strip():
            raise ValueError("飞书 app_id 必须是非空且已清洗的字符串")
        if not app_secret.get_secret_value():
            raise ValueError("飞书 app_secret 不能为空")
        if refresh_margin_seconds < 0:
            raise ValueError("飞书 refresh_margin_seconds 不能为负")

        self._app_id = app_id
        self._app_secret = app_secret
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._refresh_margin_seconds = refresh_margin_seconds
        self._clock = clock
        self._lock = Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    @property
    def refresh_margin_seconds(self) -> float:
        """暴露提前刷新窗口，便于排障时确认"为什么这次又换了一次令牌"。"""

        return self._refresh_margin_seconds

    def get_token(self) -> str:
        """返回可用的应用令牌；缓存有效时**不发起任何 HTTP 请求**。

        并发调用时同一时刻最多只有一次真实换令牌请求，其余线程等锁后复用结果。
        """

        cached = self._usable_token()
        if cached is not None:
            return cached
        with self._lock:
            # 持锁后再检查一遍：等待期间可能已经有线程换好了令牌，
            # 不检查就会重复请求（这就是"缓存了却还是风暴"的成因）。
            cached = self._usable_token()
            if cached is not None:
                return cached
            token, expires_at = self._fetch_token()
            self._token = token
            self._expires_at = expires_at
            return token

    def invalidate(self) -> None:
        """主动作废缓存；用于收到"访问令牌无效"的认证错误后强制下次重新换取。"""

        with self._lock:
            self._token = None
            self._expires_at = 0.0

    def _usable_token(self) -> str | None:
        """返回仍在有效期内的令牌；未取过或已进入提前刷新窗口时返回 `None`。"""

        if self._token is None:
            return None
        if self._clock() >= self._expires_at - self._refresh_margin_seconds:
            return None
        return self._token

    def _fetch_token(self) -> tuple[str, float]:
        """真实调用换令牌接口，返回 `(令牌, 本地到期时刻)`。

        实测响应形态：`app_access_token/internal` 把令牌放在**顶层**（不是 `data` 里），
        且同时返回 `tenant_access_token` 与 `app_access_token` 两个字段 ——
        对内建应用两者是同一个凭证。这里优先取 `tenant_access_token`
        （查用户组等应用身份接口用的就是它），缺失时回退到 `app_access_token`。

        ⚠️ 本方法只在持锁状态下被调用，因此不需要额外的并发保护。
        """

        step = "获取应用令牌"
        secret_value = self._app_secret.get_secret_value()
        try:
            response = self._client.post(
                f"{self._base_url}{APP_ACCESS_TOKEN_PATH}",
                headers={"Content-Type": "application/json; charset=utf-8"},
                json={"app_id": self._app_id, "app_secret": secret_value},
            )
        except httpx.HTTPError as exc:
            raise FeishuError(
                step,
                # 网络异常的文本里可能带上完整 URL / 请求体，必须脱敏。
                msg=redact(f"网络请求失败: {exc}", [secret_value]),
                retryable=True,
            ) from exc

        payload = decode_feishu_response(response, step, [secret_value])
        ensure_feishu_success(response, payload, step, [secret_value])

        token = payload.get("tenant_access_token") or payload.get("app_access_token")
        if not isinstance(token, str) or not token:
            raise FeishuError(
                step,
                code=payload.get("code", 0),
                msg="响应中缺少 tenant_access_token/app_access_token",
                http_status=response.status_code,
                retryable=False,
            )

        expire_seconds = as_float(payload.get("expire"))
        if expire_seconds is None or expire_seconds <= 0:
            expire_seconds = FALLBACK_EXPIRE_SECONDS
        return token, self._clock() + expire_seconds


__all__ = [
    "APP_ACCESS_TOKEN_PATH",
    "DEFAULT_FEISHU_BASE_URL",
    "DEFAULT_REFRESH_MARGIN_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "FALLBACK_EXPIRE_SECONDS",
    "FeishuAppTokenCache",
]

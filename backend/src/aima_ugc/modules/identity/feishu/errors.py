"""飞书**协议细节**的收敛处：错误码分类、响应归一、凭据脱敏。

════════ 为什么"错误码必须精确"是安全要求，不是洁癖 ════════

`99991400` / `99991401` **看起来**像频控（很多博客和示例代码这么写），
它们的实际含义是**认证 / 权限拒绝**（`invalid app_ticket` / `invalid access_token`）。

如果把凭证无效当成频控去重试：重试一万次也不会成功，只会**放大故障**
（每个请求多打 N 次飞书、日志被刷满、真实原因被淹没）。所以本模块把
「可重试」与「不可重试」严格分开，且**判不准时默认不重试**（fail closed）。

**真正的频控码**是 `99991402` / `11020` / `11021`，以及 HTTP `429`。

本模块是 `feishu` 包内**唯一**解释"飞书原始响应长什么样"的地方，
`app_token.py` 与 `adapter.py` 都复用它 —— 同一个坑（404 是 `text/plain`）
只需要在这里防一次。
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from typing import Any

import httpx

# ── 真正的频控错误码：飞书官方「请求过多」背压 ────────────────────────────────
RATE_LIMIT_CODES = frozenset({99991402, 11020, 11021})

# ── 重试绝对不会变好的错误码：认证、权限、参数、授权码类 ──────────────────────
# ⚠️ 99991400/99991401 是最常被误归类成频控的两个。
NON_RETRYABLE_CODES = frozenset(
    {
        99991400,  # invalid app_ticket（认证失败）
        99991401,  # invalid access_token（认证失败）
        99991672,  # 权限不足
        99991679,  # 权限不足
        99991680,  # 权限不足
        99991681,  # 权限不足
        20002,  # client_secret 无效
        20003,  # 授权码无效（只能用一次）
        20004,  # 授权码已过期
        20010,  # 用户无应用使用权限
        20024,  # 授权码与 client_id 不匹配
        20029,  # redirect_uri 不匹配
        20036,  # grant_type 不支持
    }
)

# ── 飞书业务码里的服务端错误：官方标注「请稍后重试」→ 可重试 ──────────────────
SERVER_ERROR_CODES = frozenset({20050})

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_DELAY_SECONDS = 0.5
DEFAULT_MAX_DELAY_SECONDS = 8.0
DEFAULT_JITTER_RATIO = 0.5

REDACTED = "<已隐藏>"

# 太短的字符串做值替换会误伤正常文案，设一个下限。
_MIN_REDACTABLE_LENGTH = 6


class FeishuError(RuntimeError):
    """调飞书接口失败。

    `retryable` 由**错误码**（必要时叠加 HTTP 状态码）决定，见 `is_retryable`。
    ⚠️ 默认 **False**（fail closed）：判不准时不重试 —— 对"永远不会成功"的请求
    重试只会放大故障。

    异常信息里**只允许**出现：失败步骤、飞书错误码、飞书 msg（已脱敏）、log_id、
    HTTP 状态码。**不得**携带 `app_secret`、`user_access_token` 或请求头/请求体。
    """

    def __init__(
        self,
        step: str,
        *,
        code: object = None,
        msg: str = "",
        log_id: str | None = None,
        http_status: int | None = None,
        retryable: bool = False,
    ) -> None:
        """记录失败发生在哪一步、飞书返回什么码，以及这次值不值得重试。"""

        self.step = step
        self.code = code
        self.msg = msg
        self.log_id = log_id
        self.http_status = http_status
        self.retryable = retryable
        super().__init__(
            f"[{step}] code={code} msg={msg} log_id={log_id} http_status={http_status}"
        )


def is_rate_limited(code: object, http_status: int | None = None) -> bool:
    """判断这次失败是不是**真正的频控**（可重试的前提）。

    ⚠️ 严格按错误码判定：`99991400` / `99991401` **不算**频控，它们是认证/权限拒绝。
    """

    if http_status == 429:
        return True
    numeric = _as_int(code)
    return numeric is not None and numeric in RATE_LIMIT_CODES


def is_retryable(code: object, http_status: int | None = None) -> bool:
    """判断这次失败**值不值得重试**。

    可重试：频控、飞书业务码里的服务端错误、HTTP 5xx、业务码 5xxxx 段。
    不可重试：认证 / 权限 / 参数 / 授权码无效（重试无用，只会放大故障）。

    ⚠️ **fail closed**：判不准时返回 `False`。重试的前提是"再试一次可能就好了"，
    这个前提不成立时就不该试。
    """

    numeric = _as_int(code)
    if numeric is not None and numeric in NON_RETRYABLE_CODES:
        return False
    if is_rate_limited(numeric, http_status):
        return True
    if numeric is not None and numeric in SERVER_ERROR_CODES:
        return True
    if http_status is not None and 500 <= http_status < 600:
        return True
    # 飞书业务码里的 5xxxx 段同样是服务端错误
    if numeric is not None and 50000 <= numeric < 60000:
        return True
    return False


def compute_delay(
    attempt: int,
    *,
    base: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    jitter: float = DEFAULT_JITTER_RATIO,
    rand: Callable[[], float] | None = None,
) -> float:
    """算第 `attempt` 次重试该等多久（`attempt` 从 1 开始）。

    指数退避 `base * 2^(attempt-1)`，封顶 `max_delay`，再乘一个随机抖动。

    **为什么要抖动**：如果 100 个请求同时被限流、又同时按"等 1 秒"重试，
    它们会在第 1 秒末尾**再次同时**打过去 → 又一次全被限流（惊群）。
    随机抖动能把它们错开。`rand` 可注入，便于测试时不用等真实时间。
    """

    delay: float = min(base * (2 ** max(0, attempt - 1)), max_delay)
    random_value: float = float((rand or random.random)())
    factor = 1.0 - jitter + 2.0 * jitter * random_value
    return max(0.0, delay * factor)


def redact(text: str, secrets: Iterable[str | None]) -> str:
    """把文本中出现的**已知凭据原值**替换成占位符。

    只做"精确值替换"，不做"看起来像不像 token"的启发式猜测：
    调用方清楚自己发出去的是什么，用原值比对既有保证又不会误伤正常文案。
    """

    result = text
    for secret in secrets:
        if secret is None or len(secret) < _MIN_REDACTABLE_LENGTH:
            continue
        result = result.replace(secret, REDACTED)
    return result


def decode_feishu_response(
    response: httpx.Response,
    step: str,
    secrets: Iterable[str | None] = (),
) -> dict[str, Any]:
    """把飞书 HTTP 响应解成 JSON 对象；不可解析时抛 `FeishuError`。

    ⚠️ **必须先用 Content-Type 判断，再判解析失败**：飞书 404 返回的是
    `text/plain`（内容形如 `404 page not found`），直接 `.json()` 会抛
    `JSONDecodeError`，把"接口路径写错"伪装成"解析器出问题"。

    错误消息一律过 `redact`，避免响应体/URL 里可能夹带的凭据被回显。
    """

    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise FeishuError(
            step,
            msg=redact(
                f"飞书返回非 JSON 响应（HTTP {response.status_code}, "
                f"content-type={content_type or '未提供'}）",
                secrets,
            ),
            http_status=response.status_code,
            retryable=is_retryable(None, response.status_code),
        )
    try:
        payload: Any = response.json()
    except ValueError as exc:
        raise FeishuError(
            step,
            msg=redact(f"飞书返回的 JSON 不可解析: {exc}", secrets),
            http_status=response.status_code,
            retryable=False,
        ) from exc
    if not isinstance(payload, dict):
        raise FeishuError(
            step,
            msg="飞书响应顶层必须是 JSON 对象",
            http_status=response.status_code,
            retryable=False,
        )
    return payload


def ensure_feishu_success(
    response: httpx.Response,
    payload: dict[str, Any],
    step: str,
    secrets: Iterable[str | None] = (),
) -> None:
    """确认这次飞书调用成功；失败时抛出带 `retryable` 分类的 `FeishuError`。

    判据两条，缺一不可：

    1. **HTTP 状态码**要在 2xx（网关/负载层失败时飞书可能连业务码都没给）；
    2. **业务码** `code` 必须是 `0`（响应格式 `{"code": 0, "msg": "success", "data": {...}}`）。

    `code != 0` 即失败 —— 即使 HTTP 200。

    ⚠️ 飞书返回的 `msg` **也要过 `redact`**：上游（网关、代理、被误配的服务端）
    完全可能把请求体或请求头回显在错误信息里。调用方把已知凭据传进来，
    我们就不会把凭据写进日志或异常。
    """

    code = payload.get("code", 0)
    if code not in (0, None):
        raise FeishuError(
            step,
            code=code,
            msg=redact(str(payload.get("msg") or ""), secrets),
            log_id=log_id_of(payload),
            http_status=response.status_code,
            retryable=is_retryable(code, response.status_code),
        )
    if not 200 <= response.status_code < 300:
        raise FeishuError(
            step,
            code=code,
            msg=f"飞书返回 HTTP {response.status_code}",
            log_id=log_id_of(payload),
            http_status=response.status_code,
            retryable=is_retryable(code, response.status_code),
        )


def require_data_object(payload: dict[str, Any], step: str) -> dict[str, Any]:
    """取出飞书响应里的 `data` 对象；缺失或类型不对时报明确的不可重试错误。"""

    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeishuError(step, msg="飞书响应缺少 data 对象", retryable=False)
    return data


def log_id_of(payload: dict[str, Any]) -> str | None:
    """取飞书排障用的 log_id；不同接口放在不同位置，两个都试。"""

    for key in ("log_id", "request_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def as_float(value: object) -> float | None:
    """把 `expire` / `expires_in` 之类的数值字段归一成浮点；数字字符串也接受。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def optional_string(value: object) -> str | None:
    """把飞书可选字段归一成 `str | None`：非字符串或空串一律当"没有"。"""

    if isinstance(value, str) and value:
        return value
    return None


def _as_int(value: object) -> int | None:
    """把飞书错误码归一成整数；数字形态的字符串也接受，其余返回 `None`。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


__all__ = [
    "DEFAULT_BASE_DELAY_SECONDS",
    "DEFAULT_JITTER_RATIO",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_MAX_DELAY_SECONDS",
    "NON_RETRYABLE_CODES",
    "RATE_LIMIT_CODES",
    "REDACTED",
    "SERVER_ERROR_CODES",
    "FeishuError",
    "as_float",
    "compute_delay",
    "decode_feishu_response",
    "ensure_feishu_success",
    "is_rate_limited",
    "is_retryable",
    "log_id_of",
    "optional_string",
    "redact",
    "require_data_object",
]

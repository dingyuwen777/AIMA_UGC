"""飞书身份适配器（**httpx 直调 REST** 版）。

本文件是 `modules/identity/feishu/` 包内发飞书 HTTP 请求的地方，
也是飞书字段（`open_id` / `group_list` / `department_ids` 等）允许出现的边界。
上层只依赖 `port.py` 定义的数据类与协议 —— 换掉飞书、换掉 HTTP 客户端，
业务代码都不用改。

════════ 为什么不引 `lark-oapi`（已定，不再讨论） ════════

`httpx==0.28.1` 已在 `pyproject.toml` 里 → **0 新增依赖**；AIMA 既有的外部调用
（`adapters/llm/` 等）本来就全是 httpx；httpx 自带连接池，不需要 SDK 版的连接池补丁。
因此本适配器**只**用 `httpx` + 标准库。

════════ 三个实测踩过的坑（都在代码里处理了） ════════

1. 组成员列表是 `member/simplelist`，**不是** `member/list`（后者 404）。
2. 飞书 404 返回 `text/plain`（`404 page not found`）→ 直接 `.json()` 会抛异常，
   必须先判 Content-Type，见 `errors.decode_feishu_response`。
3. 频控码是 `99991402` / `11020` / `11021`；`99991400` / `99991401` 是**认证/权限**
   错误，**不是**频控 —— 误判会导致无限重试，见 `errors.is_retryable`。

════════ 身份必须分清（搞混直接调不通） ════════

    用户身份（Bearer user_access_token）：`authen/v1/user_info` → 姓名、头像
    应用身份（Bearer tenant_access_token）：`contact/v3/*`       → 用户组、部门
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr

from .app_token import (
    DEFAULT_FEISHU_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    FeishuAppTokenCache,
)
from .errors import (
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_JITTER_RATIO,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_DELAY_SECONDS,
    FeishuError,
    as_float,
    compute_delay,
    decode_feishu_response,
    ensure_feishu_success,
    optional_string,
    redact,
    require_data_object,
)
from .port import FeishuDepartment, FeishuTokens, FeishuUser, FeishuUserDetail

OIDC_ACCESS_TOKEN_PATH = "/open-apis/authen/v1/oidc/access_token"
USER_INFO_PATH = "/open-apis/authen/v1/user_info"
MEMBER_BELONG_GROUP_PATH = "/open-apis/contact/v3/group/member_belong"
GROUP_MEMBER_SIMPLELIST_PATH = "/open-apis/contact/v3/group/{group_id}/member/simplelist"
USER_PATH = "/open-apis/contact/v3/users/{open_id}"
DEPARTMENT_PATH = "/open-apis/contact/v3/departments/{department_id}"

AUTHORIZE_ENDPOINT = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"

# 飞书用户组分页：page_size 默认 500、上限 1000。
DEFAULT_GROUP_PAGE_SIZE = 500
MAX_GROUP_PAGE_SIZE = 1000


class HttpxFeishuClient:
    """用 `httpx` 直调飞书 REST API 的身份适配器。

    ⚠️ `app_secret` 用 `SecretStr` 持有；`user_access_token` 只作为**局部变量**
    参与一次请求，两者都不落属性、不进日志、不进异常信息。
    """

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: SecretStr,
        base_url: str = DEFAULT_FEISHU_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        group_page_size: int = DEFAULT_GROUP_PAGE_SIZE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
        max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
        jitter_ratio: float = DEFAULT_JITTER_RATIO,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[str, int, float, FeishuError], None] | None = None,
        token_cache: FeishuAppTokenCache | None = None,
    ) -> None:
        """装配适配器。

        `client` / `sleep` / `on_retry` / `token_cache` 都可注入：单元测试因此能用
        `httpx.MockTransport` 走**真实请求路径**，又不必等真实退避时间。
        `client` 为 `None` 时由本适配器创建并负责关闭。

        ⚠️ `base_url` 的取值规则与 `adapters/llm/openai_compatible.py` 一致：
        注入的 Client 自带 `base_url` 时以它为准，避免"请求走 Client 的 base_url、
        换令牌走参数里的 base_url"这种两边不一致的隐患。
        """

        if not app_id or app_id != app_id.strip():
            raise ValueError("飞书 app_id 必须是非空且已清洗的字符串")
        if not app_secret.get_secret_value():
            raise ValueError("飞书 app_secret 不能为空")
        if timeout_seconds <= 0:
            raise ValueError("飞书 timeout_seconds 必须大于 0")
        if max_attempts < 1:
            raise ValueError("飞书 max_attempts 必须大于等于 1")
        if jitter_ratio < 0:
            raise ValueError("飞书 jitter_ratio 不能为负")

        injected_base_url = _absolute_base_url(client)
        resolved_base_url = (injected_base_url or base_url).rstrip("/")
        if not resolved_base_url:
            raise ValueError("飞书 base_url 不能为空（注入的 Client 需自带 base_url）")

        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = resolved_base_url
        # 相对路径能不能用，取决于"**最终请求用的那个 Client** 有没有可用的绝对 base_url"：
        #   - `client is None`（生产路径）→ 适配器自建的 Client 一定带
        #     `base_url=self._base_url`，相对路径可用 → 传给 httpx 的仍是相对路径，
        #     与修复前**逐字相同**；
        #   - 注入了自带绝对 base_url 的 Client → 以它为准，相对路径可用；
        #   - 注入了没有绝对 base_url 的 Client → 相对路径会失败（`httpx` 报
        #     "missing an 'http://' or 'https://' protocol"），必须自己拼绝对地址。
        self._client_resolves_relative_paths = client is None or bool(injected_base_url)
        self._page_size = max(1, min(int(group_page_size), MAX_GROUP_PAGE_SIZE))
        self._max_attempts = int(max_attempts)
        self._base_delay_seconds = base_delay_seconds
        self._max_delay_seconds = max_delay_seconds
        self._jitter_ratio = jitter_ratio
        self._sleep = sleep
        self._on_retry = on_retry
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )
        self._token_cache = token_cache or FeishuAppTokenCache(
            app_id=app_id,
            app_secret=app_secret,
            client=self._client,
            base_url=self._base_url,
        )

    # ------------------------------------------------------------------ 生命周期
    def close(self) -> None:
        """关闭由本适配器自己创建的 HTTP Client；注入的 Client 由调用方关闭。"""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> HttpxFeishuClient:
        """支持 `with` 语句，退出时自动关闭自建连接池。"""

        return self

    def __exit__(self, *_: object) -> None:
        """退出 `with` 块时关闭自建连接池。"""

        self.close()

    # ------------------------------------------------------------- ① 应用令牌
    def get_app_access_token(self) -> str:
        """取应用令牌（`tenant_access_token`）。

        走的接口：`POST /open-apis/auth/v3/app_access_token/internal`
        身份：无需令牌，用 `app_id` + `app_secret` 直接换。

        **重复调用不会重复请求**：真实换取与缓存都在 `FeishuAppTokenCache` 里，
        缓存有效期内直接返回，过期才刷新。
        """

        return self._token_cache.get_token()

    # ------------------------------------------------------- ② 授权码换用户令牌
    def exchange_authorization_code(self, code: str) -> FeishuTokens:
        """用授权码换 `user_access_token`。

        走的接口：`POST /open-apis/authen/v1/oidc/access_token`
        身份：应用身份（`Authorization: Bearer <tenant_access_token>`）。
        ⚠️ 授权码有效期仅 5 分钟且**只能用一次**。
        """

        step = "用授权码换令牌"
        payload = self._request_json(
            step,
            "POST",
            OIDC_ACCESS_TOKEN_PATH,
            headers=self._authorization_headers(self.get_app_access_token()),
            json_body={"grant_type": "authorization_code", "code": code},
            # 授权码只能用一次：上一次请求若其实成功了、只是响应没收到，
            # 重试会拿同一个码再换 → 飞书返回明确的 `20003`。这里保留重试，
            # 但"重试必然失败"的码在 `is_retryable` 里已归为不可重试。
            allow_retry=True,
        )
        data = require_data_object(payload, step)
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise FeishuError(step, msg="响应中缺少 access_token", retryable=False)
        return FeishuTokens(
            access_token=access_token,
            expires_in=int(as_float(data.get("expires_in")) or 0),
            token_type=str(data.get("token_type") or ""),
            scope=str(data.get("scope") or ""),
            refresh_token=optional_string(data.get("refresh_token")),
        )

    # ------------------------------------------------------------- ③ 取当前用户
    def get_current_user(self, user_access_token: str) -> FeishuUser:
        """取当前登录用户。

        走的接口：`GET /open-apis/authen/v1/user_info`
        身份：**用户身份**（`Authorization: Bearer <user_access_token>`）。
        姓名与头像的正确来源就是这里（应用身份接口拿不到姓名）。
        """

        step = "取当前用户"
        payload = self._request_json(
            step,
            "GET",
            USER_INFO_PATH,
            headers=self._authorization_headers(user_access_token),
            # 令牌本身就是凭据 → 必须参与文本脱敏，绝不能被回显。
            secrets=[user_access_token],
        )
        data = require_data_object(payload, step)
        open_id = data.get("open_id")
        if not isinstance(open_id, str) or not open_id:
            raise FeishuError(step, msg="响应中缺少 open_id", retryable=False)
        return FeishuUser(
            open_id=open_id,
            name=str(data.get("name") or ""),
            union_id=optional_string(data.get("union_id")),
            user_id=optional_string(data.get("user_id")),
            tenant_key=optional_string(data.get("tenant_key")),
            avatar_url=optional_string(data.get("avatar_url")),
        )

    # ------------------------------------------------------- ④ 查用户所属用户组
    def list_user_groups(self, open_id: str) -> tuple[str, ...]:
        """查该用户所属的**全部**用户组 ID（自动翻页）。

        走的接口：`GET /open-apis/contact/v3/group/member_belong`
        身份：**应用身份**。

        ⚠️ 需要应用的「通讯录权限范围」设为「全部员工」，否则只会返回该范围内的组，
        且**不会有任何报错** —— 用户明明在组里却被判无权限。

        ⚠️ 返回顺序**原样保留**、不做排序：飞书返回的组顺序**不稳定**，
        调用方必须用 `resolve_role` 做成员测试，不能取第一个元素。
        """

        step = "查用户所属用户组"
        group_ids: list[str] = []
        page_token: str | None = None
        while True:
            query: dict[str, str] = {
                "member_id": open_id,
                "member_id_type": "open_id",
                "page_size": str(self._page_size),
            }
            if page_token:
                query["page_token"] = page_token
            payload = self._request_json(
                step,
                "GET",
                MEMBER_BELONG_GROUP_PATH,
                headers=self._authorization_headers(self.get_app_access_token()),
                params=query,
            )
            data = require_data_object(payload, step)
            group_list = data.get("group_list")
            if isinstance(group_list, list):
                group_ids.extend(item for item in group_list if isinstance(item, str))
            page_token = optional_string(data.get("page_token"))
            if data.get("has_more") is True and page_token:
                continue
            break
        return tuple(group_ids)

    # ------------------------------------------------------------- ⑤ 取组成员
    def list_group_members(self, group_id: str) -> tuple[str, ...]:
        """取某个用户组的成员 `open_id` 列表（自动翻页）。

        走的接口：`GET /open-apis/contact/v3/group/{group_id}/member/simplelist`
        ⚠️ **路径坑（实测）**：是 `member/simplelist`，**不是** `member/list`
        —— 后者返回 **404 `text/plain`**。
        """

        step = "取用户组成员"
        member_ids: list[str] = []
        page_token: str | None = None
        while True:
            query: dict[str, str] = {
                "member_id_type": "open_id",
                "page_size": str(self._page_size),
            }
            if page_token:
                query["page_token"] = page_token
            payload = self._request_json(
                step,
                "GET",
                GROUP_MEMBER_SIMPLELIST_PATH.format(group_id=group_id),
                headers=self._authorization_headers(self.get_app_access_token()),
                params=query,
            )
            data = require_data_object(payload, step)
            members = data.get("memberlist")
            if isinstance(members, list):
                for member in members:
                    if isinstance(member, dict):
                        member_id = member.get("member_id")
                        if isinstance(member_id, str) and member_id:
                            member_ids.append(member_id)
            page_token = optional_string(data.get("page_token"))
            if data.get("has_more") is True and page_token:
                continue
            break
        return tuple(member_ids)

    # ------------------------------------------------------------- ⑥ 查用户详情
    def get_user(self, open_id: str) -> FeishuUserDetail:
        """查通讯录里的用户详情（主要用途：拿**部门 ID**）。

        走的接口：`GET /open-apis/contact/v3/users/{open_id}`
        身份：**应用身份**（`user_id_type=open_id`）。

        ⚠️ 实测坑：用应用令牌调这个接口**拿不到姓名**（`name` 为 `None`），
        因为 `contact:user.base:readonly` 是**用户身份**权限。别指望从这里顺带拿姓名。
        """

        step = "查用户详情"
        payload = self._request_json(
            step,
            "GET",
            USER_PATH.format(open_id=open_id),
            headers=self._authorization_headers(self.get_app_access_token()),
            params={"user_id_type": "open_id"},
        )
        data = require_data_object(payload, step)
        user = data.get("user")
        if not isinstance(user, dict):
            raise FeishuError(step, msg="响应中缺少 user 对象", retryable=False)
        department_ids = user.get("department_ids")
        return FeishuUserDetail(
            open_id=optional_string(user.get("open_id")) or open_id,
            name=optional_string(user.get("name")),
            department_ids=(
                tuple(item for item in department_ids if isinstance(item, str))
                if isinstance(department_ids, list)
                else ()
            ),
            avatar_url=optional_string(user.get("avatar_url")),
        )

    # ------------------------------------------------------------- ⑦ 部门详情
    def get_department(self, department_id: str) -> FeishuDepartment:
        """查部门详情（把部门 ID 换成可读的部门名）。

        走的接口：`GET /open-apis/contact/v3/departments/{department_id}`
        身份：**应用身份**（`department_id_type=open_department_id`）。
        """

        step = "查部门详情"
        payload = self._request_json(
            step,
            "GET",
            DEPARTMENT_PATH.format(department_id=department_id),
            headers=self._authorization_headers(self.get_app_access_token()),
            params={"department_id_type": "open_department_id"},
        )
        data = require_data_object(payload, step)
        department = data.get("department")
        if not isinstance(department, dict):
            raise FeishuError(step, msg="响应中缺少 department 对象", retryable=False)
        return FeishuDepartment(
            department_id=optional_string(department.get("department_id")) or department_id,
            name=optional_string(department.get("name")),
            parent_department_id=optional_string(department.get("parent_department_id")),
        )

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def build_authorize_url(
        *,
        app_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        force_consent: bool = True,
    ) -> str:
        """拼飞书授权页地址（浏览器跳过去，飞书把授权页显示出来）。

        `force_consent=True` 时带 `prompt=consent`，强制用户看到授权页并确认
        （验证与截图时用得上；正式环境可按需关掉）。
        """

        from urllib.parse import urlencode

        params = {
            "client_id": app_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
        if force_consent:
            params["prompt"] = "consent"
        return AUTHORIZE_ENDPOINT + "?" + urlencode(params)

    # ------------------------------------------------------------- 请求与重试
    def _authorization_headers(self, token: str) -> dict[str, str]:
        """构造 `Authorization: Bearer <token>` 请求头。

        令牌只作为参数流入请求头，**不存属性、不留副本**。
        """

        return {"Authorization": f"Bearer {token}"}

    def _request_json(
        self,
        step: str,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        secrets: list[str] | None = None,
        allow_retry: bool = True,
    ) -> dict[str, Any]:
        """发一次飞书请求并返回响应 JSON；失败转成带 `retryable` 分类的 `FeishuError`。

        统一在这里处理三件事：

        1. **HTTP 层失败**（网络错误 / 5xx / 404 `text/plain`）；
        2. **业务码失败**（`code != 0`，即使 HTTP 200 也算失败）；
        3. **凭据脱敏** —— 一切进入异常消息的文本都过 `redact`。

        `allow_retry=False` 时本次请求**一次都不重试**。
        """

        sensitive = [self._app_secret.get_secret_value(), *(secrets or [])]
        attempts = self._max_attempts if allow_retry else 1
        for attempt in range(1, attempts + 1):
            try:
                return self._send_json(
                    step,
                    method,
                    path,
                    headers=headers,
                    params=params,
                    json_body=json_body,
                    secrets=sensitive,
                )
            except FeishuError as exc:
                if not exc.retryable or attempt >= attempts:
                    raise
                delay = compute_delay(
                    attempt,
                    base=self._base_delay_seconds,
                    max_delay=self._max_delay_seconds,
                    jitter=self._jitter_ratio,
                )
                if self._on_retry is not None:
                    self._on_retry(step, attempt, delay, exc)
                self._sleep(delay)
        # 循环只可能以 return 或 raise 结束；这行仅为让类型检查器看到明确终点。
        raise AssertionError("飞书请求重试循环异常退出")  # pragma: no cover

    def _send_json(
        self,
        step: str,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None,
        params: dict[str, str] | None,
        json_body: dict[str, object] | None,
        secrets: list[str],
    ) -> dict[str, Any]:
        """真正调用 `httpx`，并把成功响应归一成飞书 JSON 对象。"""

        try:
            response = self._client.request(
                method,
                # 注入的 Client 自带绝对 base_url 时用相对路径（走它自己的 base_url，
                # 与 `adapters/llm/openai_compatible.py` 的既有规则一致）；
                # 否则参数 `base_url` 才是唯一可用的事实源，必须自己拼成绝对地址 ——
                # 否则 `httpx` 会因为"没有协议头"直接失败。
                # ⚠️ 生产路径（`client=None`）永远走第一个分支，行为与修复前完全一致。
                self._request_target(path),
                headers=headers,
                params=params,
                json=json_body,
            )
        except httpx.HTTPError as exc:
            raise FeishuError(
                step,
                # 网络异常的文本可能带完整 URL / 请求体，必须脱敏。
                msg=redact(f"网络请求失败: {exc}", secrets),
                retryable=True,
            ) from exc

        # ⚠️ 先判 Content-Type：飞书 404 返回 text/plain，直接 .json() 会抛异常。
        payload = decode_feishu_response(response, step, secrets)
        ensure_feishu_success(response, payload, step, secrets)
        return payload

    def _request_target(self, path: str) -> str:
        """返回本次请求应使用的目标：相对路径，或自己拼好的绝对地址。"""

        if self._client_resolves_relative_paths:
            return path
        return f"{self._base_url}{path}"


def _absolute_base_url(client: httpx.Client | None) -> str:
    """取注入 Client 的 base_url，**只接受可用（含协议与主机）的绝对地址**。

    ⚠️ 判据必须是"**是不是绝对 URL**"，而不是"**是不是空串**"。实测（`httpx==0.28.1`）：
    `httpx.Client()` 未传 base_url 时 `str(client.base_url)` **本来就是空串**，
    所以"裸 Client 会走进参数 fallback"这件事本身是对的。

    真正的坑在**只填了路径的 base_url**，例如 `httpx.Client(base_url="/open-apis")`：
    `httpx` 把它解析成一个**不带 scheme / host 的 URL**，`str()` 出来**非空**，
    旧的 `or base_url` 判定会把它当成合法注入值而**跳过参数 fallback** →
    请求时 `httpx` 抛 "Request URL is missing an 'http://' or 'https://' protocol"。
    —— 这正与任务书 §2.3 报告的现象一致，只是触发条件需要**非绝对 URL**。
    """

    if client is None:
        return ""
    base_url = client.base_url
    if not str(base_url).strip():
        return ""
    if not base_url.scheme or not base_url.host:
        return ""
    return str(base_url).strip()


__all__ = [
    "AUTHORIZE_ENDPOINT",
    "DEPARTMENT_PATH",
    "GROUP_MEMBER_SIMPLELIST_PATH",
    "MEMBER_BELONG_GROUP_PATH",
    "OIDC_ACCESS_TOKEN_PATH",
    "USER_INFO_PATH",
    "USER_PATH",
    "HttpxFeishuClient",
]

"""飞书 httpx 身份适配器的单元测试。

覆盖验证清单（DoD）：

    D1  7 个接口都在
    D2  应用令牌有缓存，重复调用不重复请求
    D3  应用令牌过期会刷新
    D4  角色判定用**成员测试**，与组顺序无关
    D5  频控码可重试、认证码不重试
    D6  404（`text/plain`）不崩
    D7  token / secret 不出现在日志与异常里

全部走 `httpx.MockTransport` —— 请求是真的按生产路径发出去的，
只是"网络"被换成了本地假响应。**没有任何测试会真的调用飞书。**
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from aima_ugc.modules.identity.feishu import (
    AuthorizationDenied as feishu_authorization_denied,
)
from aima_ugc.modules.identity.feishu import (
    FeishuAppTokenCache,
    FeishuError,
    FeishuTokens,
    HttpxFeishuClient,
    resolve_role,
)
from aima_ugc.modules.identity.feishu.errors import (
    FeishuError as ErrorsFeishuError,
)
from aima_ugc.modules.identity.feishu.errors import (
    compute_delay,
    is_rate_limited,
    is_retryable,
    redact,
)
from aima_ugc.modules.identity.models import AuthorizationDenied
from pydantic import SecretStr

BASE_URL = "https://open.feishu.cn"
APP_ID = "cli_test_app_id"
APP_SECRET = "unit-test-app-secret-value"
USER_TOKEN = "u-unit-test-user-access-token"
APP_TOKEN_PATH = "/open-apis/auth/v3/app_access_token/internal"
MEMBER_BELONG_PATH = "/open-apis/contact/v3/group/member_belong"
SIMPLELIST_PATH = "/open-apis/contact/v3/group/grp_1/member/simplelist"
USER_INFO_PATH = "/open-apis/authen/v1/user_info"
OIDC_TOKEN_PATH = "/open-apis/authen/v1/oidc/access_token"
USER_DETAIL_PATH = "/open-apis/contact/v3/users/ou_1"
DEPARTMENT_PATH = "/open-apis/contact/v3/departments/od_1"


def _json_response(
    request: httpx.Request, payload: dict[str, Any], status: int = 200
) -> httpx.Response:
    """构造一个飞书风格的 JSON 响应。"""

    return httpx.Response(status, json=payload, request=request)


def _ok(data: dict[str, Any], request: httpx.Request) -> httpx.Response:
    """构造 `{"code": 0, "msg": "success", "data": {...}}` 成功响应。"""

    return _json_response(request, {"code": 0, "msg": "success", "data": data})


def _client(handler: Any) -> httpx.Client:
    """构造带 `MockTransport` 的 Client；**必须带 base_url**，与生产一致用相对路径。"""

    return httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))


def _adapter(client: httpx.Client, **overrides: Any) -> HttpxFeishuClient:
    """构造被测适配器，默认注入零等待的 sleep，避免测试真的等退避时间。"""

    kwargs: dict[str, Any] = {
        "app_id": APP_ID,
        "app_secret": SecretStr(APP_SECRET),
        "client": client,
        "sleep": lambda _seconds: None,
    }
    kwargs.update(overrides)
    return HttpxFeishuClient(**kwargs)


def _token_handler(counter: list[str], expire: int = 7200) -> Any:
    """返回一个只处理换令牌请求、并记录每次调用的 handler。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        counter.append(request.url.path)
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {
                    "code": 0,
                    "msg": "success",
                    "tenant_access_token": f"t-{len(counter)}",
                    "app_access_token": f"t-{len(counter)}",
                    "expire": expire,
                },
            )
        raise AssertionError(f"未预期的请求: {request.url.path}")

    return handler


# ------------------------------------------------------------------ D1 接口齐备
def test_d1_all_seven_feishu_interfaces_exist() -> None:
    """7 个飞书接口每个都有实现，且签名可调用。"""

    for name in (
        "get_app_access_token",
        "exchange_authorization_code",
        "get_current_user",
        "list_user_groups",
        "list_group_members",
        "get_user",
        "get_department",
    ):
        assert callable(getattr(HttpxFeishuClient, name)), f"缺少接口实现: {name}"

    # 授权页地址拼装是纯函数工具，也一并核对。
    url = HttpxFeishuClient.build_authorize_url(
        app_id=APP_ID,
        redirect_uri="http://localhost:8000/callback",
        scope="contact:user.base:readonly",
        state="state-1",
    )
    assert url.startswith("https://accounts.feishu.cn/open-apis/authen/v1/authorize?")
    assert "prompt=consent" in url


# ------------------------------------------------------------ D2 缓存不重复请求
def test_d2_app_token_is_cached_across_calls() -> None:
    """调两次只发 1 次 HTTP —— 缓存真的生效。"""

    paths: list[str] = []
    client = _client(_token_handler(paths))
    try:
        feishu = _adapter(client)
        first = feishu.get_app_access_token()
        second = feishu.get_app_access_token()
    finally:
        client.close()

    assert first == second == "t-1"
    assert paths.count(APP_TOKEN_PATH) == 1


def test_d2_adapter_reuses_injected_token_cache() -> None:
    """两个入口（显式注入的缓存与适配器内部缓存）表现一致，不会各换一次令牌。"""

    paths: list[str] = []
    client = _client(_token_handler(paths))
    try:
        cache = FeishuAppTokenCache(
            app_id=APP_ID,
            app_secret=SecretStr(APP_SECRET),
            client=client,
        )
        feishu = _adapter(client, token_cache=cache)
        assert feishu.get_app_access_token() == "t-1"
        assert cache.get_token() == "t-1"
    finally:
        client.close()

    assert paths.count(APP_TOKEN_PATH) == 1


# ---------------------------------------------------------------- D3 过期会刷新
def test_d3_expired_app_token_is_refreshed() -> None:
    """时钟越过有效期后，下一次调用会重新请求并拿到新令牌。"""

    paths: list[str] = []
    now = [1_000.0]
    client = _client(_token_handler(paths))
    try:
        cache = FeishuAppTokenCache(
            app_id=APP_ID,
            app_secret=SecretStr(APP_SECRET),
            client=client,
            clock=lambda: now[0],
        )
        feishu = _adapter(client, token_cache=cache)

        assert feishu.get_app_access_token() == "t-1"
        now[0] += 7_200.0  # 越过 expire
        assert feishu.get_app_access_token() == "t-2"
    finally:
        client.close()

    assert paths.count(APP_TOKEN_PATH) == 2


def test_d3_refreshes_inside_margin_before_expiry() -> None:
    """到期前 300 秒的窗口内就刷新，避免"刚取到就过期"导致业务请求白跑。"""

    paths: list[str] = []
    now = [1_000.0]
    client = _client(_token_handler(paths))
    try:
        cache = FeishuAppTokenCache(
            app_id=APP_ID,
            app_secret=SecretStr(APP_SECRET),
            client=client,
            clock=lambda: now[0],
        )
        feishu = _adapter(client, token_cache=cache)
        assert feishu.get_app_access_token() == "t-1"

        now[0] += 7_200.0 - 299.0  # 仍在有效期内，但已进入提前刷新窗口
        assert feishu.get_app_access_token() == "t-2"
    finally:
        client.close()

    assert paths.count(APP_TOKEN_PATH) == 2


def test_d3_invalidate_forces_a_refresh() -> None:
    """收到认证错误主动作废缓存后，下一次调用必须重新换取令牌。"""

    paths: list[str] = []
    client = _client(_token_handler(paths))
    try:
        cache = FeishuAppTokenCache(
            app_id=APP_ID,
            app_secret=SecretStr(APP_SECRET),
            client=client,
        )
        assert cache.get_token() == "t-1"
        cache.invalidate()
        assert cache.get_token() == "t-2"
    finally:
        client.close()

    assert paths.count(APP_TOKEN_PATH) == 2


# ------------------------------------------------------- D4 角色判定用成员测试
def test_d4_role_is_membership_test_not_first_group() -> None:
    """「组顺序颠倒」不改变判定结果 —— 证明用的是成员测试而不是 `groups[0]`。"""

    admin_group = "348bg16c7679cbe3"
    user_group = "541fcd285767565g"

    # 同一组集合，两种顺序
    assert resolve_role((admin_group, user_group), admin_group, user_group) == "administrator"
    assert resolve_role((user_group, admin_group), admin_group, user_group) == "administrator"

    # 只在 User 组：即使它排第一、且集合更大，也只能是 user
    assert resolve_role((user_group, "other-1", "other-2"), admin_group, user_group) == "user"

    # 都不在 → 拒绝登录
    with pytest.raises(AuthorizationDenied):
        resolve_role(("other-1", "other-2"), admin_group, user_group)


def test_d4_role_is_identical_for_reversed_adapter_output() -> None:
    """把适配器真实返回的组列表正序/倒序各判一次，结果必须完全一致。"""

    admin_group = "grp_admin"
    user_group = "grp_user"
    groups = ("grp_user", "grp_admin", "grp_unrelated")

    forward = resolve_role(groups, admin_group, user_group)
    backward = resolve_role(tuple(reversed(groups)), admin_group, user_group)

    assert forward == backward == "administrator"


def test_d4_list_user_groups_preserves_order_and_paginates() -> None:
    """分页会翻完，且**原样保留**飞书给的顺序（判定不依赖它，所以更不能偷偷排序）。"""

    seen_tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        assert request.url.path == MEMBER_BELONG_PATH
        page_token = request.url.params.get("page_token")
        seen_tokens.append(page_token)
        if page_token is None:
            return _ok(
                {"group_list": ["grp_b", "grp_a"], "has_more": True, "page_token": "p2"}, request
            )
        return _ok({"group_list": ["grp_c"], "has_more": False}, request)

    client = _client(handler)
    try:
        groups = _adapter(client).list_user_groups("ou_1")
    finally:
        client.close()

    assert groups == ("grp_b", "grp_a", "grp_c")
    assert seen_tokens == [None, "p2"]


def test_d4_repeated_page_token_fails_closed_instead_of_looping() -> None:
    """上游重复分页游标时立即失败，不能让认证请求无限循环。"""

    group_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        """每一页都返回同一个游标，模拟飞书异常分页响应。"""

        nonlocal group_calls
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        group_calls += 1
        return _ok(
            {"group_list": ["grp_a"], "has_more": True, "page_token": "stuck"},
            request,
        )

    client = _client(handler)
    try:
        with pytest.raises(FeishuError, match="page_token 未推进"):
            _adapter(client).list_user_groups("ou_1")
    finally:
        client.close()

    assert group_calls == 2


# --------------------------------------------------------- D5 频控可重试/认证不
def test_d5_rate_limit_codes_are_retryable() -> None:
    """真正的频控码可重试；认证码绝不重试。"""

    for code in (99991402, 11020, 11021):
        assert is_rate_limited(code) is True
        assert is_retryable(code) is True

    # ⚠️ 最容易被误判成频控的两个：它们是认证/权限拒绝
    for code in (99991400, 99991401):
        assert is_rate_limited(code) is False
        assert is_retryable(code) is False

    # 授权码类：重试必然失败
    for code in (20002, 20003, 20004, 20024, 20029):
        assert is_retryable(code) is False

    # HTTP 429 与服务端错误可重试
    assert is_retryable(None, 429) is True
    assert is_retryable(None, 503) is True
    assert is_retryable(20050) is True
    # fail closed：判不准时不重试
    assert is_retryable(None) is False
    assert is_retryable("not-a-code") is False


def test_d5_rate_limited_request_is_retried_then_succeeds() -> None:
    """第一次返回频控码时会退避重试，第二次成功；重试次数与等待都留痕。"""

    attempts: list[str] = []
    retries: list[tuple[str, int, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        attempts.append(request.url.path)
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        if len([p for p in attempts if p == MEMBER_BELONG_PATH]) == 1:
            return _json_response(request, {"code": 99991402, "msg": "rate limit", "log_id": "L1"})
        return _ok({"group_list": ["grp_a"], "has_more": False}, request)

    client = _client(handler)
    try:
        feishu = _adapter(
            client,
            on_retry=lambda step, attempt, delay, exc: retries.append((step, attempt, delay)),
        )
        groups = feishu.list_user_groups("ou_1")
    finally:
        client.close()

    assert groups == ("grp_a",)
    assert attempts.count(MEMBER_BELONG_PATH) == 2
    assert len(retries) == 1
    assert retries[0][0] == "查用户所属用户组"
    assert retries[0][2] >= 0.0


def test_d5_auth_error_is_not_retried() -> None:
    """认证码（99991400）**只发一次**就抛出 —— 不浪费配额、不放大故障。"""

    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        attempts.append(request.url.path)
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        return _json_response(
            request,
            {"code": 99991400, "msg": "invalid app_ticket", "log_id": "L2"},
        )

    client = _client(handler)
    try:
        with pytest.raises(FeishuError) as excinfo:
            _adapter(client, max_attempts=4).list_user_groups("ou_1")
    finally:
        client.close()

    assert excinfo.value.code == 99991400
    assert excinfo.value.retryable is False
    assert attempts.count(MEMBER_BELONG_PATH) == 1


# -------------------------------------------------------------- D6 404 不崩
def test_d6_plain_text_404_raises_domain_error_not_json_error() -> None:
    """飞书 404 返回 `text/plain` —— 必须报领域错误，不能抛 JSON 解析栈。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        return httpx.Response(
            404,
            text="404 page not found",
            headers={"content-type": "text/plain"},
            request=request,
        )

    client = _client(handler)
    try:
        with pytest.raises(FeishuError) as excinfo:
            _adapter(client, max_attempts=1).list_group_members("grp_1")
    finally:
        client.close()

    assert excinfo.value.http_status == 404
    assert "非 JSON" in excinfo.value.msg


def test_d6_plain_text_404_is_retryable_only_as_5xx() -> None:
    """404 属于不可重试的 4xx（路径写错重试一万次也没用）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        return httpx.Response(
            404,
            text="404 page not found",
            headers={"content-type": "text/plain"},
            request=request,
        )

    client = _client(handler)
    try:
        with pytest.raises(FeishuError) as excinfo:
            _adapter(client, max_attempts=4).get_user("ou_1")
    finally:
        client.close()

    assert excinfo.value.retryable is False


def test_d6_group_members_use_member_simplelist_path() -> None:
    """组成员走的是 `member/simplelist`（不是 `member/list`，后者 404），并会翻页。"""

    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        seen_paths.append(request.url.path)
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        if request.url.params.get("page_token") is None:
            return _ok(
                {
                    "memberlist": [{"member_id": "ou_1"}, {"member_id": "ou_2"}],
                    "has_more": True,
                    "page_token": "p2",
                },
                request,
            )
        return _ok({"memberlist": [{"member_id": "ou_3"}], "has_more": False}, request)

    client = _client(handler)
    try:
        members = _adapter(client).list_group_members("grp_1")
    finally:
        client.close()

    assert members == ("ou_1", "ou_2", "ou_3")
    assert SIMPLELIST_PATH in seen_paths
    assert all("member/list" not in path for path in seen_paths)


# ------------------------------------------- D7 token / secret 不外泄
def test_d7_feishu_tokens_repr_hides_the_access_token() -> None:
    """`FeishuTokens` 被 print / 日志带到时不能泄露令牌。"""

    tokens = FeishuTokens(
        access_token=USER_TOKEN,
        expires_in=7200,
        token_type="Bearer",
        scope="contact:user.base:readonly",
        refresh_token="refresh-secret-value",
    )

    assert USER_TOKEN not in repr(tokens)
    assert USER_TOKEN not in str(tokens)
    assert "已隐藏" in repr(tokens)


def test_d7_error_message_does_not_leak_app_secret_even_if_server_echoes_it() -> None:
    """上游把 secret 回显在错误信息里时，异常信息仍然不能带出 secret。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        return _json_response(
            request,
            {
                "code": 20002,
                "msg": f"invalid client_secret: {APP_SECRET} (app_id={APP_ID})",
                "log_id": "L3",
            },
        )

    client = _client(handler)
    try:
        with pytest.raises(FeishuError) as excinfo:
            _adapter(client).get_app_access_token()
    finally:
        client.close()

    assert APP_SECRET not in str(excinfo.value)
    assert APP_SECRET not in repr(excinfo.value)
    assert "已隐藏" in str(excinfo.value)
    assert excinfo.value.code == 20002


def test_d7_error_message_does_not_leak_user_access_token() -> None:
    """`user_access_token` 不得出现在异常信息里（H3：取完用户即弃）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        return _json_response(
            request,
            {
                "code": 99991401,
                "msg": f"invalid access_token: {USER_TOKEN}",
                "log_id": "L4",
            },
        )

    client = _client(handler)
    try:
        with pytest.raises(FeishuError) as excinfo:
            _adapter(client, max_attempts=1).get_current_user(USER_TOKEN)
    finally:
        client.close()

    assert USER_TOKEN not in str(excinfo.value)
    assert excinfo.value.code == 99991401


def test_d7_network_error_message_does_not_leak_secret() -> None:
    """网络层异常（httpx 会把完整 URL / 请求体带进消息）也必须脱敏。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        raise httpx.ConnectError(f"连接失败，请求体含 {APP_SECRET}", request=request)

    client = _client(handler)
    try:
        with pytest.raises(FeishuError) as excinfo:
            _adapter(client).get_app_access_token()
    finally:
        client.close()

    assert APP_SECRET not in str(excinfo.value)
    assert excinfo.value.retryable is True


def test_d7_redact_only_masks_known_values() -> None:
    """脱敏只替换已知凭据原值，不误伤正常文案。"""

    assert redact(f"token={USER_TOKEN}", [USER_TOKEN]) == "token=<已隐藏>"
    # 太短的值不参与替换（否则会把正常文案里的字母也换掉）
    assert redact("abc 正常文案", ["abc"]) == "abc 正常文案"
    assert redact("没有凭据", [None, ""]) == "没有凭据"


def test_d7_adapter_repr_does_not_expose_secret() -> None:
    """适配器对象本身被打印时也不能泄露 Secret。"""

    client = _client(_token_handler([]))
    try:
        feishu = _adapter(client)
        assert APP_SECRET not in repr(feishu)
    finally:
        client.close()


# ------------------------------------------------------------ 其余接口的真实路径
def test_exchange_authorization_code_maps_fields() -> None:
    """授权码换令牌：POST 到 OIDC 路径、带应用令牌，且字段映射正确。"""

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        seen.append(request)
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        assert request.url.path == OIDC_TOKEN_PATH
        return _ok(
            {
                "access_token": USER_TOKEN,
                "expires_in": 7200,
                "token_type": "Bearer",
                "scope": "contact:user.base:readonly",
                "refresh_token": "r-1",
            },
            request,
        )

    client = _client(handler)
    try:
        tokens = _adapter(client).exchange_authorization_code("auth-code-1")
    finally:
        client.close()

    assert tokens.access_token == USER_TOKEN
    assert tokens.expires_in == 7200
    assert tokens.refresh_token == "r-1"
    oidc_request = next(r for r in seen if r.url.path == OIDC_TOKEN_PATH)
    assert oidc_request.headers["authorization"] == "Bearer t-1"
    assert b"authorization_code" in oidc_request.content


def test_exchange_authorization_code_is_never_retried() -> None:
    """授权码只能使用一次；网络结果未知或 5xx 时也不能拿同一码隐藏重试。"""

    oidc_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        """应用令牌成功，授权码交换持续返回可重试的上游失败。"""

        nonlocal oidc_calls
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        assert request.url.path == OIDC_TOKEN_PATH
        oidc_calls += 1
        return _json_response(request, {"code": 99991402, "msg": "rate limited"}, status=503)

    client = _client(handler)
    try:
        with pytest.raises(FeishuError):
            _adapter(client, max_attempts=3).exchange_authorization_code("single-use-code")
    finally:
        client.close()

    assert oidc_calls == 1


def test_get_current_user_uses_user_identity_and_maps_avatar() -> None:
    """取用户必须带**用户令牌**，并映射 `avatar_url`。"""

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        seen.append(request)
        assert request.url.path == USER_INFO_PATH
        return _ok(
            {
                "open_id": "ou_1",
                "name": "张三",
                "union_id": "on_1",
                "user_id": "uid_1",
                "tenant_key": "tk_1",
                "avatar_url": "https://s3-imfile.feishucdn.com/avatar.png",
            },
            request,
        )

    client = _client(handler)
    try:
        user = _adapter(client).get_current_user(USER_TOKEN)
    finally:
        client.close()

    assert user.open_id == "ou_1"
    assert user.name == "张三"
    assert user.union_id == "on_1"
    assert user.avatar_url == "https://s3-imfile.feishucdn.com/avatar.png"
    assert seen[0].headers["authorization"] == f"Bearer {USER_TOKEN}"


def test_get_user_maps_department_ids() -> None:
    """查用户详情：拿部门 ID（应用身份路径）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        assert request.url.path == USER_DETAIL_PATH
        return _ok(
            {
                "user": {
                    "open_id": "ou_1",
                    "name": None,  # 实测：应用身份拿不到姓名
                    "department_ids": ["od_1", "od_2"],
                }
            },
            request,
        )

    client = _client(handler)
    try:
        detail = _adapter(client).get_user("ou_1")
    finally:
        client.close()

    assert detail.open_id == "ou_1"
    assert detail.department_ids == ("od_1", "od_2")
    assert detail.name is None


def test_get_department_maps_name() -> None:
    """部门详情：部门 ID → 可读部门名。"""

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        assert request.url.path == DEPARTMENT_PATH
        return _ok(
            {"department": {"department_id": "od_1", "name": "Project_Aima_CN01P000637"}},
            request,
        )

    client = _client(handler)
    try:
        department = _adapter(client).get_department("od_1")
    finally:
        client.close()

    assert department.department_id == "od_1"
    assert department.name == "Project_Aima_CN01P000637"


def test_group_page_size_is_clamped_to_feishu_limit() -> None:
    """分页大小被夹到飞书上限 1000、下限 1，避免请求被飞书拒绝。"""

    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        if request.url.path == APP_TOKEN_PATH:
            return _json_response(
                request,
                {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
            )
        requested.append(request.url.params["page_size"])
        return _ok({"group_list": [], "has_more": False}, request)

    client = _client(handler)
    try:
        _adapter(client, group_page_size=99999).list_user_groups("ou_1")
        _adapter(client, group_page_size=0).list_user_groups("ou_1")
    finally:
        client.close()

    assert requested == ["1000", "1"]


def test_compute_delay_is_capped_and_jittered() -> None:
    """退避按指数增长、被封顶，抖动因子落在 [1-j, 1+j] 内。"""

    # rand 固定为 0.5 → 抖动因子为 1.0，得到不带抖动的基准值
    assert compute_delay(1, base=0.5, max_delay=8.0, jitter=0.5, rand=lambda: 0.5) == 0.5
    assert compute_delay(2, base=0.5, max_delay=8.0, jitter=0.5, rand=lambda: 0.5) == 1.0
    assert compute_delay(99, base=0.5, max_delay=8.0, jitter=0.5, rand=lambda: 0.5) == 8.0
    # 抖动下界：rand=0 → 因子 0.5
    assert compute_delay(1, base=1.0, max_delay=8.0, jitter=0.5, rand=lambda: 0.0) == 0.5
    # 抖动上界：rand=1 → 因子 1.5
    assert compute_delay(1, base=1.0, max_delay=8.0, jitter=0.5, rand=lambda: 1.0) == 1.5


def test_constructor_rejects_invalid_configuration() -> None:
    """构造参数非法时立刻报错，不留下会在运行期才炸的对象。"""

    client = _client(_token_handler([]))
    try:
        with pytest.raises(ValueError):
            _adapter(client, app_id="   ")
        with pytest.raises(ValueError):
            HttpxFeishuClient(app_id=APP_ID, app_secret=SecretStr(""), client=client)
        with pytest.raises(ValueError):
            _adapter(client, timeout_seconds=0)
        with pytest.raises(ValueError):
            _adapter(client, max_attempts=0)
        with pytest.raises(ValueError):
            _adapter(client, jitter_ratio=-1)
    finally:
        client.close()


def test_errors_module_is_single_source_of_error_type() -> None:
    """包级 `FeishuError` 与 `errors` 模块导出的必须是同一个类，不制造两套异常。"""

    assert FeishuError is ErrorsFeishuError


def test_authorization_denied_reuses_the_identity_module_type() -> None:
    """拒绝登录复用的是 `identity.models` 里已有的异常，不制造第二个同名类。

    这样上层只需要 `except AuthorizationDenied` 一种捕获，不会因为
    "飞书包自己定义了一个同名异常"而漏捕。
    """

    assert feishu_authorization_denied is AuthorizationDenied
    assert issubclass(AuthorizationDenied, PermissionError)


# ------------------------------------- D10 注入的 Client 没有可用 base_url 时
def test_d10_injected_client_without_base_url_still_builds_absolute_urls() -> None:
    """注入 `httpx.Client()`（**不带 base_url**）时，仍必须能拼出完整 URL。

    回归的缺陷：旧实现只判断"注入的 base_url 是不是空串"。
    `httpx.Client()` 的 base_url 恰好是空串，这一步是过的；但**只填路径的
    base_url**（如 `httpx.Client(base_url="/open-apis")`）会被解析成
    **不带 scheme / host 的相对 URL**，`str()` 后**非空** → 旧判定认为"注入值可用"
    而跳过参数 `base_url` → 请求时 `httpx` 报
    "Request URL is missing an 'http://' or 'https://' protocol"。

    本用例覆盖两种注入形态，并断言**请求真的发到了完整地址**。
    """

    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        seen.append(request.url)
        return _json_response(
            request,
            {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
        )

    for bare_client in (
        httpx.Client(transport=httpx.MockTransport(handler)),  # 完全不传 base_url
        httpx.Client(base_url="/open-apis", transport=httpx.MockTransport(handler)),
    ):
        try:
            feishu = _adapter(bare_client, max_attempts=1)
            token = feishu.get_app_access_token()
        finally:
            bare_client.close()

        assert token == "t-1"
        # 换令牌走的是**自己拼的绝对地址**（参数 base_url 的回退生效了）。
        assert str(seen[-1]) == f"{BASE_URL}{APP_TOKEN_PATH}", seen[-1]

    assert len(seen) == 2


def test_d10_injected_client_with_absolute_base_url_keeps_relative_paths() -> None:
    """注入的 Client **自带绝对 base_url** 时，仍走相对路径（保持既有约定）。

    这条是上一条的**反向对照**：证明修复没有把"该用 Client base_url"的情形也改掉。
    """

    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """MockTransport 的假飞书响应；请求仍按生产代码的真实路径发出。"""
        seen.append(request.url)
        return _json_response(
            request,
            {"code": 0, "msg": "success", "tenant_access_token": "t-1", "expire": 7200},
        )

    other_base = "https://open.feishu.cn.example"
    client = httpx.Client(base_url=other_base, transport=httpx.MockTransport(handler))
    try:
        assert _adapter(
            client, base_url="https://should-not-be-used.invalid"
        ).get_app_access_token()
    finally:
        client.close()

    # 以注入 Client 的 base_url 为准，参数里的 base_url 不应参与。
    assert str(seen[0]) == f"{other_base}{APP_TOKEN_PATH}", seen[0]

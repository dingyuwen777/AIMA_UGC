"""`IdentityResolver` 的飞书会话实现：把请求 Cookie 解析成统一 Principal。

════════ 它解决什么问题 ════════

AIMA 的业务代码只知道一个东西：`Principal`（见 `modules/identity/models.py`）。
本类负责把那枚 AIMA 会话 Cookie 换成 `Principal`：

    request.cookies["aima_session"]
        → SHA-256 → 查 identity_sessions
        → 校验未撤销、未过期
        → Principal(principal_id=库里的 Uuid, role=库里的角色, source="feishu")

⚠️ `principal_id` 是**库里的 AIMA Uuid**（不是飞书 `union_id`）。
这正是决策 Y 的要求：业务表只认 Provider-neutral 的 AIMA 身份。

════════ 为什么角色"每次请求读库" ════════

飞书侧把某人从管理员组移除后，AIMA 必须尽快生效。若把角色塞进 Cookie 或内存缓存，
至少要等会话过期（默认 8 小时）才失效。读库是一次主键查询，代价可接受，
换来的是"改权限即时生效"。

════════ 为什么"取不到会话"就拒绝 ════════

`resolve()` 拿不到有效会话时**抛 `AuthorizationDenied`**（AIMA 已有异常，
`bootstrap/api.py` 已有它的 403 处理器），**不返回匿名 Principal**。
理由：默认放行（fail-open）会让"Cookie 处在意外状态"变成静默越权；
安全边界必须 fail-closed。这也与本地开发的 `DevelopmentIdentityResolver`
定位不同 —— 后者是显式固定的开发身份，不是"解析失败"。
"""

from __future__ import annotations

from typing import cast

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from aima_ugc.contracts.administration import PrincipalRole
from aima_ugc.modules.identity.models import AuthorizationDenied, Principal
from aima_ugc.platform.time import beijing_now

from .session_store import SESSION_COOKIE_NAME, SessionStore


class FeishuSessionIdentityResolver:
    """按 AIMA 会话 Cookie 解析 `Principal`；实现 AIMA 的 `IdentityResolver` 协议。

    `session_factory` 由调用方提供（接线单从 `DatabaseRuntime.new_session` 取），
    本类**不自己创建 Engine** —— 数据库生命周期归运行进程，不归身份层。
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        cookie_name: str = SESSION_COOKIE_NAME,
    ) -> None:
        """装配解析器；`cookie_name` 可注入，便于测试与将来改名。"""

        self._session_factory = session_factory
        self._cookie_name = cookie_name

    def resolve(self, request: Request) -> Principal:
        """从当前请求解析统一 Principal；无有效会话时抛 `AuthorizationDenied`。"""

        token = request.cookies.get(self._cookie_name)
        if not token:
            raise AuthorizationDenied

        session = self._session_factory()
        try:
            record = SessionStore(session).find(token)
            # 会话不存在 / 已撤销 / 已过期 —— 三种情况都按"未登录"拒绝，
            # 对外不区分，避免把"这个令牌存在但过期了"这类信息泄露给调用方。
            if record is None or not record.is_usable(now=beijing_now()):
                raise AuthorizationDenied
            # 展示用头像经 `request.state` 传给 HTTP 层。为什么不放进 `Principal`：
            # `Principal` 是 Provider-neutral 公共契约，不能塞飞书私有的展示字段；
            # 而 `/api/v1/principal` 的响应契约又需要头像（方案 §7B）。
            # 用 request.state 做这一跳，同时守住"不改 Principal"这条边界。
            request.state.principal_avatar_url = record.avatar_url
            # 部门名同理：只作展示，不进 `Principal`（方案 §5D.4）。
            request.state.principal_department_name = record.department_name
            return Principal(
                principal_id=str(record.principal_id),
                display_name=record.display_name,
                # `identity_sessions.role` 有 CHECK 约束（administrator / user），
                # 与 `PrincipalRole` 字面量一致；这里如实转换，不做兜底改写。
                role=cast(PrincipalRole, record.role),
                source="feishu",
            )
        finally:
            session.close()


__all__ = ["FeishuSessionIdentityResolver"]

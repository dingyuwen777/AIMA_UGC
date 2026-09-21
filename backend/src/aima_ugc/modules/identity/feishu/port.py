"""飞书身份提供方的接口定义与领域数据类。

**业务代码只认这个文件**：它不依赖 `httpx`、不依赖 `lark-oapi`，也不暴露飞书私有字段。
适配器（`adapter.py`）可以有更多能力，但业务只需要 `FeishuIdentityProvider` 这三个方法。

关于 `AuthorizationDenied`：本项目在 `aima_ugc.modules.identity.models` 已经定义了
同一个语义的异常（`PermissionError` 子类）。这里**直接复用**它而不是再定义一个同名类 ——
同一能力不制造两套平行类型，也让上层 `except` 只需捕获一种异常。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from aima_ugc.modules.identity.models import AuthorizationDenied


@dataclass(frozen=True, slots=True)
class FeishuTokens:
    """授权码换回来的用户令牌。

    ⚠️ `access_token` 即 `user_access_token`：**绝不写日志、绝不发前端、绝不落库**。
    """

    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str | None = None

    def __repr__(self) -> str:
        """只暴露长度与元信息，防止令牌被 print / 日志 / 异常带出去。"""

        return (
            f"FeishuTokens(access_token=<已隐藏 {len(self.access_token)} 字符>, "
            f"expires_in={self.expires_in}, scope={self.scope!r})"
        )

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class FeishuUser:
    """当前登录用户（来自**用户身份**接口 `authen/v1/user_info`）。"""

    open_id: str
    name: str
    union_id: str | None = None
    user_id: str | None = None
    tenant_key: str | None = None
    # 头像原图 URL：它是**公开资源**，不含身份凭证，取它不影响安全性；前端显示头像用。
    avatar_url: str | None = None


@dataclass(frozen=True, slots=True)
class FeishuUserDetail:
    """通讯录里的用户详情（来自**应用身份**接口 `contact/v3/users/{open_id}`）。

    ⚠️ 实测坑：用应用令牌调这个接口**拿不到姓名**（`name` 为 `None`）——
    那需要"用户身份"的 `contact:user.base:readonly`。姓名/头像的正确来源是
    `FeishuUser`（用户身份）；本类只用来补**部门归属**。
    """

    open_id: str
    name: str | None = None
    department_ids: tuple[str, ...] = ()
    avatar_url: str | None = None


@dataclass(frozen=True, slots=True)
class FeishuDepartment:
    """部门详情（来自**应用身份**接口 `contact/v3/departments/{department_id}`）。"""

    department_id: str
    name: str | None = None
    parent_department_id: str | None = None


@dataclass(frozen=True, slots=True)
class VerifiedFeishuIdentity:
    """身份验证的统一收敛结果（供上层映射成 `Principal`）。"""

    provider_subject: str  # 唯一标识，优先 union_id
    display_name: str
    open_id: str
    union_id: str | None
    group_ids: tuple[str, ...] = ()
    role: str = ""  # administrator / user

    def as_safe_dict(self) -> dict[str, object]:
        """给**页面 / 日志**看的脱敏视图。

        `provider_subject` / `open_id` / `union_id` **全部打码**：
        页面永不回显可用的身份标识。需要**完整值**的场景（落库、跨系统比对）
        请直接用对象属性，不要走这个方法 —— 方法名里的 `safe` 就是"可以放心展示"。
        """

        return {
            "provider_subject": _mask_id(self.provider_subject),
            "display_name": self.display_name,
            "open_id": _mask_id(self.open_id),
            "union_id": _mask_id(self.union_id),
            "group_ids": list(self.group_ids),
            "role": self.role,
        }


class FeishuIdentityProvider(Protocol):
    """飞书身份提供方接口 —— 业务只依赖这三个方法。

    适配器额外实现的通讯录查询（取组成员 / 查用户详情 / 查部门）不属于业务端口，
    需要它们的调用方直接依赖具体适配器类型，避免把可选能力塞进业务契约。
    """

    def exchange_authorization_code(self, code: str) -> FeishuTokens:
        """用授权码换 `user_access_token`。"""

        ...

    def get_current_user(self, user_access_token: str) -> FeishuUser:
        """取当前登录用户。"""

        ...

    def list_user_groups(self, open_id: str) -> tuple[str, ...]:
        """查该用户所属的全部用户组 ID（自动翻页）。"""

        ...


def resolve_role(group_ids: Sequence[str], admin_group_id: str, user_group_id: str) -> str:
    """用户组 → 角色。

    规则：

        属于 Admin 组（含 Admin+User 同时属于） → administrator
        仅属于 User 组                          → user
        两个都不属于                            → 拒绝登录

    ⚠️ **必须用成员测试，绝不能用 `groups[0]`**：阶段 1 用 4 个数据点实测过，
    飞书返回的组顺序**不稳定**；按位置取第一个组会随机判错角色。
    本函数只做 `in` 判断，因此结果与 `group_ids` 的顺序、长度无关。

    注意：这里用的是**稳定 Group ID**，不是组名。
    """

    if admin_group_id in group_ids:
        return "administrator"
    if user_group_id in group_ids:
        return "user"
    raise AuthorizationDenied(f"该用户不属于任何允许的用户组（共查到 {len(group_ids)} 个组）")


def _mask_id(value: str | None) -> str | None:
    """用户标识脱敏：保留头尾**便于人工比对**，但**不可直接复制使用**。

    为什么保留头尾：排障时要对比"两次登录是不是同一个人"，全打码就没法比了；
    保留 6+4 位既够比对，又不构成可用的标识。
    """

    if not value:
        return value
    if len(value) <= 12:
        return f"{value[:3]}…"
    return f"{value[:6]}…{value[-4:]}"


__all__ = [
    "FeishuDepartment",
    "FeishuIdentityProvider",
    "FeishuTokens",
    "FeishuUser",
    "FeishuUserDetail",
    "VerifiedFeishuIdentity",
    "resolve_role",
]

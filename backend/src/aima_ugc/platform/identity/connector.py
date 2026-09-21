"""飞书 Connector：**一家企业一份接入配置**，以及它们的注册表。

════════ 这个文件解决什么问题 ════════

接入最初只服务**一家企业**（NNIT）：配置里 `AIMA_FEISHU_APP_ID` 是单个值，
路由是 `/api/v1/auth/feishu/login`，全流程只认一套 App ID / Secret / 用户组。

需求方随后要求**爱玛与 NNIT 各自的员工都能登录同一个 AIMA_UGC**。
数据层其实早就为此设计好了（`identity_external_identities` 的唯一约束带
`connector_id`，而 `connector_id` 由 `app_id` 确定性派生），
但**配置层只有一个字段、路由里没有企业标识** —— 这就是本文件要补的部分。

════════ 为什么是"列表"而不是"字典" ════════

注册表内部用**有序列表**持有 Connector，而不是 `{code: connector}` 字典：

- 前端登录页要按**固定顺序**渲染企业按钮；
- Python 字典虽然 3.7 起保序，但**一旦经过 JSON 往返或某些变换就不再保证**，
  而"按钮顺序每次刷新都变"是很难排查的体验问题；
- 列表 + 显式 `code` 字段让顺序成为**配置里看得见的事实**。

查找时用一次性构建的索引，仍保持 O(1)。

════════ 与 `FeishuAuthSettings` 的关系 ════════

`FeishuAuthSettings`（在 `bootstrap/feishu_auth_http.py`）是**运行时快照**，
由配置构造、供路由使用。本文件的 `FeishuConnector` 是它的**单企业来源**：

    PlatformSettings（环境变量）
        → ConnectorRegistry（本文件，负责校验与查找）
        → FeishuAuthSettings（运行时快照，负责被路由消费）

**为什么不让 `FeishuConnector` 直接取代 `FeishuAuthSettings`**：
后者已被 13 处代码与 6 处测试引用，且承载"已校验配置"的语义。
本文件**只负责"多企业"这一层**，不改既有类型 —— 这是**最小改动**。

════════ 纯数据、无 IO ════════

本模块**不读环境变量、不连数据库、不发网络请求**。
它只做"数据结构 + 校验 + 查找"，因此可以脱离任何运行时被单元测试覆盖。
环境变量的读取仍归 `platform/config/settings.py`。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

# ═══════════════════════════ 常量 ═══════════════════════════

# 企业标识（URL 里那一段）允许的字符。
#
# ⚠️ 为什么必须限制：它会**直接进入 URL 路径**。
# 若允许 `/`、`.`、`%` 等字符，就可能构造出意外的路径（路径穿越、
# 绕过路由匹配、或与静态路由混淆）。只允许小写字母/数字/连字符是最安全的集合。
CONNECTOR_CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# 标识长度上限：既要够用（语义化命名），又要避免超长 URL 段。
MAX_CONNECTOR_CODE_LENGTH = 32

# 显示名长度上限（与 `CurrentPrincipalResponse.display_name` 的可读性口径一致）。
MAX_DISPLAY_NAME_LENGTH = 64


class ConnectorConfigurationError(ValueError):
    """Connector 配置不合法。

    ⚠️ 这个异常**必须在应用启动时抛出**，而不是等到用户点登录才发现 ——
    配置错误属于"部署错误"，越早失败越好（fail fast）。
    """


@dataclass(frozen=True, slots=True)
class FeishuConnector:
    """**一家企业**的飞书接入配置（不可变）。

    这里的每个字段都是"这家企业自己的"，不与其他企业共享。
    时间与范围类参数（`scope` / TTL）**刻意不放进来** —— 它们通常是全局策略，
    由 `PlatformSettings` 统一持有；只有企业特有的身份要素才在这里。
    """

    code: str
    """企业标识，用于 URL 路径（如 `aima` / `nnit`）。**必须 URL 安全。**"""

    display_name: str
    """界面上显示的名字（如 `爱玛科技` / `NNIT`）。"""

    app_id: str
    """飞书 App ID（如 `cli_xxx`）。**不保密** —— 它出现在授权链接里。"""

    app_secret_ref: str
    """App Secret 的**引用**（文件名），不是内容。

    内容由 `platform/security` 读取；配置里永远只存引用。
    """

    admin_group_id: str
    """该企业「管理员」用户组的 ID。命中 → `administrator`。"""

    user_group_id: str
    """该企业「普通用户」用户组的 ID。命中 → `user`。"""

    redirect_uri: str
    """该企业的回调地址。

    ⚠️ 必须与代码里发出的 `redirect_uri` **一字不差**，
    且**路径里要含本企业的 code**（否则回调会走错企业）。
    """

    @property
    def connector_id(self) -> str:
        """由 `app_id` **确定性派生**的稳定标识，用于身份映射表。

        ⚠️⚠️ **这个算法一个字都不能改。**

        库里已有的身份映射记录依赖它：改变算法会让**所有老用户与新身份对不上**
        （表现为"同一个人变成新用户"，会话还在但身份重新建）。
        现有生产数据里 `cli_aa2092574af9dbc2` 对应的值是
        `7d88a4816c7a5e07a95ca3c2012fb2f7`，有专门的回归测试守住它。

        为什么用 `uuid5` 而不是随机 `uuid4`：这里需要的是"同一 app_id 永远得到同一个值"，
        即**确定性**；随机值无法在重启后复现，会让映射表失去意义。
        """

        return uuid5(
            NAMESPACE_URL,
            f"https://aima.local/identity/connectors/feishu/{self.app_id}",
        ).hex


def parse_connector(raw: object, *, index: int) -> FeishuConnector:
    """把一条原始配置（来自 JSON）解析成 `FeishuConnector`，非法就抛错。

    ⚠️ 为什么不用 pydantic 直接建：本函数要在**构造注册表时**给出
    "第几条第几个字段错了"的**可定位错误信息**。pydantic 的嵌套校验错误
    在 JSON 数组里很难看出是哪家企业、哪个字段，而配置错误恰恰最需要一眼看懂。
    """

    if not isinstance(raw, dict):
        raise ConnectorConfigurationError(
            f"第 {index + 1} 个 connector 必须是对象，实际是 {type(raw).__name__}"
        )

    def require_str(field: str, *, max_length: int | None = None) -> str:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ConnectorConfigurationError(
                f"第 {index + 1} 个 connector 缺少非空字符串字段 `{field}`"
            )
        text = value.strip()
        if max_length is not None and len(text) > max_length:
            raise ConnectorConfigurationError(
                f"第 {index + 1} 个 connector 的 `{field}` 超过 {max_length} 字符"
            )
        return text

    code = require_str("code", max_length=MAX_CONNECTOR_CODE_LENGTH)
    if not CONNECTOR_CODE_PATTERN.match(code):
        raise ConnectorConfigurationError(
            f"第 {index + 1} 个 connector 的 `code`={code!r} 不合法："
            "只允许小写字母、数字、连字符，且必须以字母或数字开头"
        )

    return FeishuConnector(
        code=code,
        display_name=require_str("display_name", max_length=MAX_DISPLAY_NAME_LENGTH),
        app_id=require_str("app_id"),
        app_secret_ref=require_str("app_secret_ref"),
        admin_group_id=require_str("admin_group_id"),
        user_group_id=require_str("user_group_id"),
        redirect_uri=require_str("redirect_uri"),
    )


@dataclass(frozen=True, slots=True)
class ConnectorRegistry:
    """一组 Connector，提供**按 code 查找**与**按顺序遍历**。

    构造时即完成全部跨条目校验（见 `build_registry`），
    因此拿到实例就代表"配置已经合法"，后续运行期无需再校验。
    """

    connectors: tuple[FeishuConnector, ...]
    _by_code: dict[str, FeishuConnector]

    def __len__(self) -> int:
        """返回企业数量。"""

        return len(self.connectors)

    def __iter__(self) -> Iterator[FeishuConnector]:
        """按配置顺序遍历（前端按钮顺序依赖它）。"""

        return iter(self.connectors)

    def get(self, code: str) -> FeishuConnector | None:
        """按 code 查找；不存在返回 `None`（调用方决定是 404 还是回退）。"""

        return self._by_code.get(code)

    @property
    def single(self) -> FeishuConnector | None:
        """只有一家企业时返回它，否则 `None`。

        用途：前端登录页判断"要不要显示企业选择列表" —— 只有一家时
        **保持与改造前一致的体验**（直接一个「飞书登录」按钮）。
        """

        return self.connectors[0] if len(self.connectors) == 1 else None

    @property
    def codes(self) -> tuple[str, ...]:
        """全部企业标识（按配置顺序）。"""

        return tuple(c.code for c in self.connectors)


def build_registry(connectors: list[FeishuConnector]) -> ConnectorRegistry:
    """校验并构建注册表；任何跨条目冲突都抛 `ConnectorConfigurationError`。

    ════════ 为什么要做这些跨条目校验 ════════

    单个 Connector 合法，不代表**放在一起**合法。下面每一条都对应一个
    **静默出错**的场景（不校验就不会报错，只会在运行时表现异常）：
    """

    if not connectors:
        raise ConnectorConfigurationError(
            "多企业配置不能是空列表：那会导致所有人（包括管理员）都无法登录"
        )

    # ── ① code 不能重复 ────────────────────────────────────────────────
    # 重复会让查找结果取决于遍历顺序 → **静默丢掉一家企业**。
    seen_codes: set[str] = set()
    for connector in connectors:
        if connector.code in seen_codes:
            raise ConnectorConfigurationError(
                f"connector `code` 重复：{connector.code!r}。"
                "重复会让后一条覆盖前一条，导致某家企业静默失效"
            )
        seen_codes.add(connector.code)

    # ── ② app_id 不能重复（**安全关键**）────────────────────────────────
    # `connector_id` 由 app_id 派生。两个 connector 用同一个 app_id
    # → 派生值相同 → `UNIQUE(connector_id, provider_subject)` **无法区分企业**
    # → 同一人在两家企业会被当成**同一个身份**，这是身份混淆漏洞。
    seen_app_ids: dict[str, str] = {}
    for connector in connectors:
        if connector.app_id in seen_app_ids:
            raise ConnectorConfigurationError(
                f"connector {connector.code!r} 与 {seen_app_ids[connector.app_id]!r} "
                f"使用了同一个 `app_id`（{connector.app_id}）。"
                "两者会派生出相同的 connector_id，导致两个企业的身份互相覆盖"
            )
        seen_app_ids[connector.app_id] = connector.code

    # ── ③ app_secret_ref 不能重复 ──────────────────────────────────────
    # 两家企业共用一个 Secret 文件，几乎必然是配置错误
    # （会拿 A 的密钥去 B 换令牌 → 登录失败，且错误码指向飞书"密钥无效"，难定位）。
    seen_secret_refs: dict[str, str] = {}
    for connector in connectors:
        if connector.app_secret_ref in seen_secret_refs:
            raise ConnectorConfigurationError(
                f"connector {connector.code!r} 与 "
                f"{seen_secret_refs[connector.app_secret_ref]!r} "
                f"使用了同一个 `app_secret_ref`（{connector.app_secret_ref}）。"
                "两家企业应各有一份独立的 Secret 文件"
            )
        seen_secret_refs[connector.app_secret_ref] = connector.code

    # ── ④ redirect_uri 的路径必须含本企业的 code ────────────────────────
    # 这是**回调走错企业**的直接防线：飞书是"按登记的回调地址回跳"，
    # 若配置里指向了别家的路径，回调就会落到别家企业、用错 Secret。
    for connector in connectors:
        expected_fragment = f"/feishu/{connector.code}/callback"
        if expected_fragment not in connector.redirect_uri:
            raise ConnectorConfigurationError(
                f"connector {connector.code!r} 的 `redirect_uri` 必须包含 "
                f"`{expected_fragment}`，实际是 {connector.redirect_uri!r}。"
                "回调地址与企业标识不匹配会导致回调走错企业"
            )

    # ── ⑤ 同一家企业不能同时用两个组 ────────────────────────────────────
    # 管理员组与用户组若相同，角色判定将退化为"只要在组里就是管理员"，
    # 与「两角色」设计冲突，几乎必然是配置抄错。
    for connector in connectors:
        if connector.admin_group_id == connector.user_group_id:
            raise ConnectorConfigurationError(
                f"connector {connector.code!r} 的 `admin_group_id` 与 "
                "`user_group_id` 相同：角色判定会退化为'在组里即管理员'"
            )

    by_code = {c.code: c for c in connectors}
    return ConnectorRegistry(connectors=tuple(connectors), _by_code=by_code)


__all__ = [
    "CONNECTOR_CODE_PATTERN",
    "MAX_CONNECTOR_CODE_LENGTH",
    "MAX_DISPLAY_NAME_LENGTH",
    "ConnectorConfigurationError",
    "ConnectorRegistry",
    "FeishuConnector",
    "build_registry",
    "parse_connector",
]

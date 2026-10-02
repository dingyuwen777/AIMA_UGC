"""五平台账号身份解析的生产事实；人工 Debug 入口调用同一 Owner。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aima_ugc.contracts.collection.accounts import ACCOUNT_ID_TYPES, CollectionAccountIdType
from aima_ugc.contracts.platform import PlatformName

ResolutionReason = Literal["not_found", "ambiguous", "incomplete", "identity_mismatch"]


class AccountIdentityError(ValueError):
    """身份未得到证明时终止该账号，使用可展示的稳定分类。"""

    def __init__(self, reason: ResolutionReason) -> None:
        super().__init__(f"account_{reason}")
        self.reason = reason


class ResolvedAccountIdentity(BaseModel):
    """可持久恢复的已核验身份；作品调用参数和作者校验共用同一事实。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    stable_id: str = Field(min_length=1)
    author_ids: tuple[str, ...] = Field(min_length=1)
    aliases: dict[str, str] = Field(default_factory=dict)
    nickname: str | None = None

    def matches_author(self, external_id: str | None, alternate_ids: Mapping[str, str]) -> bool:
        """稳定作者身份必须匹配；已提供但冲突的 sec_uid 不能被另一个 ID 掩盖。"""
        sec_uid = alternate_ids.get("sec_uid")
        expected_sec_uid = self.aliases.get("sec_uid")
        if sec_uid and expected_sec_uid and sec_uid != expected_sec_uid:
            return False
        return external_id in self.author_ids or bool(sec_uid and sec_uid in self.author_ids)


def direct_account_identity(
    *, platform: PlatformName, id_type: CollectionAccountIdType, id_value: str
) -> ResolvedAccountIdentity:
    """只接受作品接口直接支持的稳定 ID，作者仍须由每条实际作品核验。"""
    if (platform, id_type) not in {("douyin", "sec_uid"), ("weibo", "uid"), ("bilibili", "uid")}:
        raise AccountIdentityError("incomplete")
    return ResolvedAccountIdentity(
        stable_id=id_value, author_ids=(id_value,), aliases={id_type: id_value}
    )


def resolve_profile_identity(
    *,
    platform: PlatformName,
    id_type: CollectionAccountIdType,
    id_value: str,
    profile: dict[str, Any],
) -> ResolvedAccountIdentity:
    """验证实际资料中的定位字段后，才允许构造后续付费作品请求。"""
    if id_type not in ACCOUNT_ID_TYPES[platform]:
        raise AccountIdentityError("incomplete")
    if platform == "xiaohongshu":
        try:
            target = XiaohongshuAccountTarget(**{id_type: id_value})
            result = resolve_account_candidate(target, [profile])
        except XiaohongshuAccountResolutionError as exc:
            raise AccountIdentityError(exc.reason) from exc
        return ResolvedAccountIdentity(
            stable_id=result.user_id,
            author_ids=(result.user_id,),
            aliases={
                "user_id": result.user_id,
                **({"red_id": result.red_id} if result.red_id else {}),
            },
            nickname=result.nickname,
        )
    if platform == "douyin":
        aliases = {
            key: value
            for key, value in {
                "unique_id": _first_string(profile, "unique_id"),
                "sec_uid": _first_string(profile, "sec_uid", "sec_user_id"),
                "uid": _first_string(profile, "uid", "user_id"),
            }.items()
            if value
        }
        stable_id = aliases.get("sec_uid")
        nickname = _first_string(profile, "nickname")
    elif platform == "kuaishou":
        aliases = _kuaishou_identity_from_mapping(profile)
        stable_id = aliases.get("user_id")
        if stable_id and not (stable_id.isascii() and stable_id.isdecimal()):
            raise AccountIdentityError("incomplete")
        nickname = aliases.pop("nickname", None)
    else:
        raise AccountIdentityError("incomplete")
    if not stable_id or id_type not in aliases:
        raise AccountIdentityError("incomplete")
    if aliases[id_type] != id_value:
        raise AccountIdentityError("identity_mismatch")
    author_ids = tuple(dict.fromkeys([stable_id, *([aliases["uid"]] if "uid" in aliases else [])]))
    return ResolvedAccountIdentity(
        stable_id=stable_id, author_ids=author_ids, aliases=aliases, nickname=nickname
    )


def resolve_search_identity(
    *,
    platform: PlatformName,
    id_type: CollectionAccountIdType,
    id_value: str,
    candidates: Sequence[dict[str, Any]],
) -> ResolvedAccountIdentity:
    """搜索须按用户输入的 ID 精确匹配，并跨页消歧；昵称只做辅助展示。"""
    if platform == "xiaohongshu":
        try:
            result = resolve_account_candidate(
                XiaohongshuAccountTarget(red_id=id_value), candidates
            )
        except XiaohongshuAccountResolutionError as exc:
            raise AccountIdentityError(exc.reason) from exc
        return ResolvedAccountIdentity(
            stable_id=result.user_id,
            author_ids=(result.user_id,),
            aliases={"user_id": result.user_id, "red_id": id_value},
            nickname=result.nickname,
        )
    if platform != "kuaishou" or id_type != "kuaishou_id":
        raise AccountIdentityError("incomplete")
    matches: dict[str, ResolvedAccountIdentity] = {}
    for candidate in candidates:
        aliases = _kuaishou_identity_from_mapping(candidate)
        if aliases.get("kuaishou_id") != id_value:
            continue
        identity = resolve_profile_identity(
            platform=platform, id_type=id_type, id_value=id_value, profile=candidate
        )
        matches[identity.stable_id] = identity
    if not matches:
        raise AccountIdentityError("not_found")
    if len(matches) != 1:
        raise AccountIdentityError("ambiguous")
    return next(iter(matches.values()))


def account_search_identity_facts(platform: PlatformName, raw: dict[str, Any]) -> dict[str, str]:
    """分页断点只保存身份消歧字段；完整响应继续由唯一 Raw Artifact 保存。"""
    if platform == "kuaishou":
        aliases = _kuaishou_identity_from_mapping(raw)
        return {
            {"kuaishou_id": "kwaiId", "nickname": "user_name"}.get(key, key): value
            for key, value in aliases.items()
        }
    user = _unwrap_user(raw)
    return {
        key: value
        for key, value in {
            "user_id": _first_string(user, "user_id", "userid", "userId", "id"),
            "red_id": _first_string(user, "red_id", "redId"),
            "nickname": _first_string(user, "nickname", "nick_name", "name"),
        }.items()
        if value is not None
    }


@dataclass(frozen=True, slots=True)
class XiaohongshuAccountTarget:
    """人工配置的小红书账号目标；稳定身份优先级为 user_id > red_id > nickname。"""

    nickname: str | None = None
    red_id: str | None = None
    user_id: str | None = None

    def __post_init__(self) -> None:
        """去除配置空白并拒绝完全没有定位信息的账号。"""
        object.__setattr__(self, "nickname", _normalized_optional(self.nickname))
        object.__setattr__(self, "red_id", _normalized_optional(self.red_id))
        object.__setattr__(self, "user_id", _normalized_optional(self.user_id))
        if self.nickname is None and self.red_id is None and self.user_id is None:
            raise ValueError("小红书账号至少提供 nickname、red_id 或 user_id 之一")


@dataclass(frozen=True, slots=True)
class ResolvedXiaohongshuAccount:
    """完成消歧后可安全用于付费用户笔记请求的稳定账号身份。"""

    user_id: str
    red_id: str | None
    nickname: str | None
    nickname_matches: bool | None


class XiaohongshuAccountResolutionError(ValueError):
    """账号无法安全解析时的失败；reason 用于决定是否允许备用搜索词。"""

    def __init__(self, message: str, *, reason: ResolutionReason) -> None:
        """保存稳定失败分类，供账号解析流程决定是否继续备用搜索。"""
        super().__init__(message)
        self.reason = reason


def resolve_account_candidate(
    target: XiaohongshuAccountTarget,
    candidates: Sequence[dict[str, Any]],
) -> ResolvedXiaohongshuAccount:
    """按稳定身份消歧账号；red_id 精确匹配优先，昵称歧义时拒绝猜测。"""
    identities: dict[str, ResolvedXiaohongshuAccount] = {}
    for raw in candidates:
        candidate = _resolved_candidate(target, raw)
        if candidate is not None:
            identities[candidate.user_id] = candidate
    values = tuple(identities.values())

    if target.user_id is not None:
        matches = tuple(item for item in values if item.user_id == target.user_id)
        if len(matches) == 1:
            candidate = matches[0]
            if target.red_id is not None and candidate.red_id not in {None, target.red_id}:
                raise XiaohongshuAccountResolutionError(
                    f"user_id={target.user_id} 返回的 red_id 与配置不一致",
                    reason="identity_mismatch",
                )
            return candidate
        if len(matches) > 1:
            raise XiaohongshuAccountResolutionError(
                f"user_id={target.user_id} 候选不唯一",
                reason="ambiguous",
            )
        raise XiaohongshuAccountResolutionError(
            f"未找到 user_id={target.user_id} 的账号候选",
            reason="not_found",
        )

    if target.red_id is not None:
        matches = tuple(item for item in values if item.red_id == target.red_id)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise XiaohongshuAccountResolutionError(
                f"小红书号 {target.red_id} 候选不唯一",
                reason="ambiguous",
            )
        raise XiaohongshuAccountResolutionError(
            f"未找到小红书号 {target.red_id} 的精确账号候选",
            reason="not_found",
        )

    assert target.nickname is not None
    matches = tuple(item for item in values if item.nickname == target.nickname)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise XiaohongshuAccountResolutionError(
            f"昵称 {target.nickname} 候选不唯一，必须补充小红书号或 user_id",
            reason="ambiguous",
        )
    raise XiaohongshuAccountResolutionError(
        f"未找到昵称 {target.nickname} 的精确账号候选",
        reason="not_found",
    )


def _resolved_candidate(
    target: XiaohongshuAccountTarget,
    raw: dict[str, Any],
) -> ResolvedXiaohongshuAccount | None:
    """把 Provider 用户候选规范化为稳定身份；缺 user_id 的候选不可用于后续付费请求。"""
    user = _unwrap_user(raw)
    user_id = _first_string(user, "user_id", "userid", "userId", "id")
    if user_id is None:
        return None
    red_id = _first_string(user, "red_id", "redId")
    nickname = _first_string(user, "nickname", "nick_name", "name")
    return ResolvedXiaohongshuAccount(
        user_id=user_id,
        red_id=red_id,
        nickname=nickname,
        nickname_matches=_nickname_matches(target.nickname, nickname),
    )


def _unwrap_user(raw: dict[str, Any]) -> dict[str, Any]:
    """兼容搜索候选和用户详情中的常见用户 wrapper。"""
    for key in ("user", "user_info", "userInfo", "profile"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _nickname_matches(configured: str | None, actual: str | None) -> bool | None:
    """昵称只做辅助核验；缺任一侧时返回未知，不覆盖稳定身份。"""
    if configured is None or actual is None:
        return None
    return configured == actual


def _first_string(raw: dict[str, Any], *keys: str) -> str | None:
    """从 Provider 用户对象中读取第一个非空字符串字段。"""
    for key in keys:
        if key in raw:
            value = _object_string(raw[key])
            if value is not None:
                return value
    return None


def _object_string(value: object) -> str | None:
    """把可序列化标量规范化为去空白字符串。"""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalized_optional(value: str | None) -> str | None:
    """把人工配置中的空字符串归一为 None。"""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _kuaishou_identity_from_mapping(raw: Mapping[str, object]) -> dict[str, str]:
    queue: list[Mapping[str, object]] = [raw]
    seen: set[int] = set()
    result: dict[str, str] = {}
    aliases = {
        "user_id": ("userId", "user_id", "userid"),
        "eid": ("eid", "userEid", "user_eid"),
        "kuaishou_id": ("kwaiId", "kwai_id", "kwaiid", "kuaishouId"),
        "nickname": ("userName", "user_name", "name", "nickname"),
    }
    while queue and len(seen) < 64:
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        for result_key, source_keys in aliases.items():
            if result_key in result:
                continue
            for source_key in source_keys:
                value = current.get(source_key)
                if isinstance(value, bool) or value is None:
                    continue
                text = str(value).strip()
                if text:
                    result[result_key] = text
                    break
        queue.extend(value for value in current.values() if isinstance(value, Mapping))
    return result

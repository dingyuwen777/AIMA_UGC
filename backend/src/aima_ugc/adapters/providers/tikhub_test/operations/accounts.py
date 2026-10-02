"""四平台账号 Discovery 执行器；内容、评论、Raw 和输出继续复用通用调试主链。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlparse
from uuid import UUID
from zoneinfo import ZoneInfo

from aima_ugc.adapters.providers.tikhub import account_runtime
from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.adapters.providers.tikhub.account_identity import _kuaishou_identity_from_mapping
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import default_run_id
from aima_ugc.contracts.canonical import CanonicalContentV1

from .runner import _DEFAULT_OUTPUT_ROOT, TikHubTestRunResult, _RunLimits, _TikHubDebugRunner

_BEIJING = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class DouyinAccountTarget:
    """人工配置的一个抖音账号；可填写 sec_uid、抖音号或主页地址。"""

    nickname: str | None = None
    unique_id: str | None = None
    sec_uid: str | None = None
    uid: str | None = None
    homepage_url: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("nickname", "unique_id", "sec_uid", "uid", "homepage_url"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} 必须为非空字符串或 None")
                object.__setattr__(self, field_name, value.strip())
        if self.homepage_url:
            homepage_id = _platform_homepage_id(self.homepage_url, "douyin")
            if self.sec_uid and self.sec_uid != homepage_id:
                raise ValueError("抖音主页与 sec_uid 身份不一致")
        if all(
            getattr(self, field_name) is None
            for field_name in ("nickname", "unique_id", "sec_uid", "uid", "homepage_url")
        ):
            raise ValueError(
                "抖音账号至少需要 nickname、unique_id、sec_uid、uid、homepage_url 之一"
            )

    @classmethod
    def from_value(
        cls,
        value: DouyinAccountTarget | dict[str, object],
    ) -> DouyinAccountTarget:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("accounts 中每一项必须是 DouyinAccountTarget 或字典")
        allowed = {"nickname", "unique_id", "sec_uid", "uid", "homepage_url"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"抖音账号配置包含未知字段: {', '.join(unknown)}")
        return cls(
            nickname=_optional_config_text(value.get("nickname"), "nickname"),
            unique_id=_optional_config_text(value.get("unique_id"), "unique_id"),
            sec_uid=_optional_config_text(value.get("sec_uid"), "sec_uid"),
            uid=_optional_config_text(value.get("uid"), "uid"),
            homepage_url=_optional_config_text(value.get("homepage_url"), "homepage_url"),
        )

    @property
    def label(self) -> str:
        return (
            self.nickname
            or self.unique_id
            or self.sec_uid
            or self.uid
            or self.homepage_url
            or "未命名账号"
        )

    @property
    def cache_key(self) -> str:
        return "|".join(
            (
                self.nickname or "",
                self.unique_id or "",
                self.sec_uid or "",
                self.uid or "",
                self.homepage_url or "",
            )
        )

    def request_value(self, account_param: str) -> str:
        normalized = account_param.strip().casefold()
        if normalized in {"unique_id", "uniqueid", "douyin_id", "handle"} and self.unique_id:
            return self.unique_id
        if normalized in {"sec_uid", "sec_user_id", "sec_userid"} and self.sec_uid:
            return self.sec_uid
        if normalized in {"uid", "user_id", "userid"} and self.uid:
            return self.uid
        if normalized in {"url", "homepage_url", "user_url"} and self.homepage_url:
            return self.homepage_url
        for value in (self.sec_uid, self.uid, self.homepage_url):
            if value:
                return value
        raise _AccountResolutionError(
            f"抖音账号 {self.label} 缺少可用于 {account_param} 的 "
            "unique_id、sec_uid、uid 或 homepage_url"
        )


@dataclass(frozen=True, slots=True)
class KuaishouAccountTarget:
    """人工配置的一个快手账号；填写快手号、数字 user_id、eid 或主页地址。"""

    nickname: str | None = None
    kuaishou_id: str | None = None
    eid: str | None = None
    user_id: str | None = None
    homepage_url: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "nickname",
            "kuaishou_id",
            "eid",
            "user_id",
            "homepage_url",
        ):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} 必须为非空字符串或 None")
                object.__setattr__(self, field_name, value.strip())
        if self.homepage_url:
            homepage_id = _platform_homepage_id(self.homepage_url, "kuaishou")
            if self.eid and self.eid != homepage_id:
                raise ValueError("快手主页与 eid 身份不一致")
            if self.user_id and homepage_id.isdigit() and self.user_id != homepage_id:
                raise ValueError("快手主页与 user_id 身份不一致")
        if self.user_id is not None and not self.user_id.isdigit():
            raise ValueError("快手 user_id 必须是纯数字；主页 eid 请填写到 eid 字段")
        if all(
            value is None
            for value in (
                self.nickname,
                self.kuaishou_id,
                self.eid,
                self.user_id,
                self.homepage_url,
            )
        ):
            raise ValueError("快手账号至少需要 kuaishou_id、eid、user_id、homepage_url 之一")

    @classmethod
    def from_value(
        cls,
        value: KuaishouAccountTarget | dict[str, object],
    ) -> KuaishouAccountTarget:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("accounts 中每一项必须是 KuaishouAccountTarget 或字典")
        allowed = {"nickname", "kuaishou_id", "eid", "user_id", "homepage_url"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"快手账号配置包含未知字段: {', '.join(unknown)}")
        return cls(
            nickname=_optional_config_text(value.get("nickname"), "nickname"),
            kuaishou_id=_optional_config_text(value.get("kuaishou_id"), "kuaishou_id"),
            eid=_optional_config_text(value.get("eid"), "eid"),
            user_id=_optional_config_text(value.get("user_id"), "user_id"),
            homepage_url=_optional_config_text(value.get("homepage_url"), "homepage_url"),
        )

    @property
    def label(self) -> str:
        return (
            self.nickname
            or self.kuaishou_id
            or self.eid
            or self.user_id
            or self.homepage_url
            or "未命名账号"
        )

    @property
    def cache_key(self) -> str:
        return "|".join(
            (
                self.nickname or "",
                self.kuaishou_id or "",
                self.eid or "",
                self.user_id or "",
                self.homepage_url or "",
            )
        )

    @property
    def profile_reference(self) -> str:
        if self.eid:
            return self.eid
        if self.homepage_url:
            return _kuaishou_reference_from_homepage(self.homepage_url)
        if self.user_id:
            return self.user_id
        raise _AccountResolutionError(f"快手账号 {self.label} 缺少可解析的用户标识")


@dataclass(frozen=True, slots=True)
class WeiboAccountTarget:
    """人工配置的一个微博账号；推荐填写稳定 UID，也可填写昵称或主页地址。"""

    nickname: str | None = None
    uid: str | None = None
    homepage_url: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("nickname", "uid", "homepage_url"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} 必须为非空字符串或 None")
                object.__setattr__(self, field_name, value.strip())
        if self.homepage_url:
            homepage_id = _platform_homepage_id(self.homepage_url, "weibo")
            if self.uid and self.uid != homepage_id:
                raise ValueError("主页与 uid 身份不一致")
        if self.nickname is None and self.uid is None and self.homepage_url is None:
            raise ValueError("微博账号至少需要 nickname、uid、homepage_url 之一")

    @classmethod
    def from_value(
        cls,
        value: WeiboAccountTarget | dict[str, object],
    ) -> WeiboAccountTarget:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("accounts 中每一项必须是 WeiboAccountTarget 或字典")
        allowed = {"nickname", "uid", "homepage_url"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"微博账号配置包含未知字段: {', '.join(unknown)}")
        return cls(
            nickname=_optional_config_text(value.get("nickname"), "nickname"),
            uid=_optional_config_text(value.get("uid"), "uid"),
            homepage_url=_optional_config_text(value.get("homepage_url"), "homepage_url"),
        )

    @property
    def label(self) -> str:
        return self.nickname or self.uid or self.homepage_url or "未命名账号"

    @property
    def cache_key(self) -> str:
        return "|".join((self.nickname or "", self.uid or "", self.homepage_url or ""))


@dataclass(frozen=True, slots=True)
class BilibiliAccountTarget:
    """人工配置的一个 B站 UP 主；推荐填写稳定的数字 UID。"""

    uid: str | None = None
    nickname: str | None = None
    homepage_url: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("uid", "nickname", "homepage_url"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} 必须为非空字符串或 None")
                object.__setattr__(self, field_name, value.strip())
        if self.homepage_url:
            homepage_id = _platform_homepage_id(self.homepage_url, "bilibili")
            if self.uid and self.uid != homepage_id:
                raise ValueError("主页与 uid 身份不一致")
        if self.uid is None and self.homepage_url is None:
            raise ValueError("B站账号至少需要 uid 或 homepage_url")

    @classmethod
    def from_value(
        cls,
        value: BilibiliAccountTarget | dict[str, object],
    ) -> BilibiliAccountTarget:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("accounts 中每一项必须是 BilibiliAccountTarget 或字典")
        allowed = {"uid", "nickname", "homepage_url"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"B站账号配置包含未知字段: {', '.join(unknown)}")
        return cls(
            uid=_optional_config_text(value.get("uid"), "uid"),
            nickname=_optional_config_text(value.get("nickname"), "nickname"),
            homepage_url=_optional_config_text(value.get("homepage_url"), "homepage_url"),
        )

    @property
    def label(self) -> str:
        return self.nickname or self.uid or self.homepage_url or "未命名账号"

    @property
    def cache_key(self) -> str:
        return "|".join((self.uid or "", self.nickname or "", self.homepage_url or ""))


class _AccountResolutionError(RuntimeError):
    """账号身份无法安全解析时使用的非 Secret 错误。"""


class _AccountDebugRunner(_TikHubDebugRunner):
    """账号解析与作品发现独立于关键词链，复用同一内容处理、评论和输出 Owner。"""

    _continue_after_item_http_error = True

    def __init__(
        self,
        *,
        platform: tikhub_runtime.TikHubPlatform,
        keywords: tuple[str, ...],
        search_config: dict[str, object],
        provider_config: TikHubTestConfig,
        output_root: Path,
        run_id: str,
        limits: _RunLimits,
        include_comments: bool,
        include_replies: bool,
        force_refresh: bool,
        write_to_database: bool,
        provider_config_id: UUID | None,
        account_targets: tuple[
            DouyinAccountTarget
            | KuaishouAccountTarget
            | WeiboAccountTarget
            | BilibiliAccountTarget,
            ...,
        ] = (),
        start_date: date | None = None,
        end_date: date | None = None,
        comment_mode: Literal["limited", "all"] = "limited",
        max_account_search_pages: int = 5,
        max_account_post_pages: int | None = 100,
        force_resolve_accounts: bool = False,
        account_feed_config: dict[str, object] | None = None,
    ) -> None:
        limits.validate()
        if comment_mode not in {"limited", "all"}:
            raise ValueError("comment_mode 只能是 limited 或 all")
        if max_account_search_pages < 1:
            raise ValueError("max_account_search_pages 必须大于 0")
        if max_account_post_pages is not None and max_account_post_pages < 1:
            raise ValueError("max_account_post_pages 必须大于 0")
        if bool(account_targets) != (start_date is not None and end_date is not None):
            raise ValueError("账号采集必须同时提供 account_targets、start_date 和 end_date")
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date 不能晚于 end_date")
        if write_to_database:
            raise ValueError("指定账号入口只提供文件模式，不支持 write_to_database=True")
        super().__init__(
            platform=platform,
            keywords=tuple(f"account[{i}]" for i in range(1, len(account_targets) + 1)),
            search_config=search_config,
            provider_config=provider_config,
            output_root=output_root,
            run_id=run_id,
            limits=limits,
            include_comments=include_comments,
            include_replies=include_replies,
            force_refresh=force_refresh,
            write_to_database=False,
            provider_config_id=None,
        )
        self._account_by_key = dict(zip(self.keywords, account_targets, strict=True))
        self.start_date = start_date
        self.end_date = end_date
        self.comment_mode = comment_mode
        self.max_account_search_pages = max_account_search_pages
        self.max_account_post_pages = max_account_post_pages
        self.force_resolve_accounts = force_resolve_accounts
        self.account_feed_config = dict(account_feed_config or {})
        self.account_mode = True

    def _run_search(self, transport: TikHubHttpTransport, keyword: str) -> None:
        """用稳定账号序号替换关键词 Discovery 槽位，避免同名账号覆盖摘要。"""
        target = self._account_by_key[keyword]
        before = len(self._account_results)
        first_block = len(self._blocks)
        if isinstance(target, DouyinAccountTarget):
            self._run_douyin_account(transport, target)
        elif isinstance(target, KuaishouAccountTarget):
            self._run_kuaishou_account(transport, target)
        elif isinstance(target, WeiboAccountTarget):
            self._run_weibo_account(transport, target)
        else:
            self._run_bilibili_account(transport, target)
        if len(self._account_results) > before:
            result = self._account_results[-1]
            result["account_key"] = keyword
            stop = str(result.get("stop_reason") or "account_failed")
            failures = result.get("post_failures")
            result["partial_content_ids"] = [
                block.content.external_content_id
                for block in self._blocks[first_block:]
                if block.content.external_content_id in self._partial_content_ids
                or (
                    block.content.coverage
                    and block.content.coverage.startswith(("partial", "unavailable"))
                )
            ]
            if result.get("status") in {"completed", "completed_with_errors"} and (
                stop not in {"provider_exhausted", "empty_page"}
                or failures
                or result.get("identity_mismatches")
                or result.get("partial_content_ids")
            ):
                result["status"] = "partial"
            self._search_stop_reasons.pop(target.label, None)
            self._search_stop_reasons[keyword] = stop

    def _run_douyin_account(
        self,
        transport: TikHubHttpTransport,
        target: DouyinAccountTarget,
    ) -> None:
        account_param = self.account_feed_config.get("account_id_param", "sec_user_id")
        if not isinstance(account_param, str) or not account_param.strip():
            raise ValueError("account_id_param 必须是非空字符串")
        result: dict[str, object] = {
            "nickname": target.nickname,
            "unique_id": target.unique_id,
            "sec_uid": target.sec_uid,
            "uid": target.uid,
            "homepage_url": target.homepage_url,
            "configured_account_param": account_param,
            "resolved_sec_uid": None,
            "identity_resolution": None,
            "status": "failed",
            "posts_pages": 0,
            "posts_source": "app_v3",
            "posts_discovered": 0,
            "posts_in_range": 0,
            "unique_posts_in_range": 0,
            "identity_mismatches": 0,
            "post_failures": [],
            "stop_reason": None,
            "error_type": None,
            "error_summary": None,
        }
        try:
            account_value, identity_resolution = self._resolve_douyin_account_value(
                transport,
                target=target,
                account_param=account_param,
            )
            result["resolved_sec_uid"] = account_value if _is_sec_uid(account_value) else None
            result["identity_resolution"] = identity_resolution
            state: dict[str, object] | None = None
            use_douplus = (
                self.account_feed_config.get("account_posts_source", "app_v3") == "douplus"
            )
            unique_in_range: set[str] = set()
            seen_post_ids: set[str] = set()
            progressless_pages = 0
            page_no = 0
            while self.max_account_post_pages is None or page_no < self.max_account_post_pages:
                page_no += 1
                if use_douplus:
                    call = account_runtime.build_douyin_douplus_user_posts_call(
                        sec_uid=account_value,
                        state=state,
                        count=cast(int, self.account_feed_config.get("douplus_post_page_size", 10)),
                    )
                else:
                    call = account_runtime.build_douyin_user_posted_videos_call(
                        account_value=account_value,
                        state=state,
                        config=self.account_feed_config,
                    )
                body, raw_record = self._send(transport, call, keyword=target.label)
                self._requests[-1].update(
                    {
                        "account": target.label,
                        "account_value": account_value,
                        "account_page": page_no,
                        "account_stage": "posted_videos",
                    }
                )
                result["posts_pages"] = page_no
                result["posts_source"] = "douplus" if use_douplus else "app_v3"
                items = account_runtime.extract_douyin_user_posted_videos(
                    body,
                    config=(
                        {"account_items_path": "data.data.itemInfoList"}
                        if use_douplus
                        else self.account_feed_config
                    ),
                )
                previous_discovered = len(seen_post_ids)
                for item_index, raw_item in enumerate(items):
                    result["posts_discovered"] = cast(int, result["posts_discovered"]) + 1
                    item_locator = f"account_posts.page[{page_no}].items[{item_index}]"
                    try:
                        content = tikhub_runtime.map_content(
                            platform="douyin",
                            raw=raw_item,
                            context=tikhub_runtime.mapping_context(
                                provider_request_id=raw_record.request_id,
                                provider_attempt_id=raw_record.attempt_id,
                                raw_artifact_id=raw_record.artifact_id,
                                operation=call.operation,
                                source_type="account",
                                source_value=account_value,
                                observed_at=raw_record.observed_at,
                            ),
                            item_locator=item_locator,
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    seen_post_ids.add(content.external_content_id)
                    if not _douyin_content_matches_account(
                        content,
                        target,
                        resolved_sec_uid=(
                            account_value
                            if account_param.strip().casefold()
                            in {"sec_uid", "sec_user_id", "sec_userid"}
                            else None
                        ),
                    ):
                        result["identity_mismatches"] = cast(int, result["identity_mismatches"]) + 1
                        continue
                    if content.published_at is None:
                        cast(list[dict[str, object]], result["post_failures"]).append(
                            {
                                "item_locator": item_locator,
                                "error_type": "MissingPublicationTime",
                                "error_summary": "作品缺少发布时间，无法确认是否在日期范围内",
                            }
                        )
                        continue
                    if not _published_on_inclusive_date_range(
                        content.published_at,
                        start_date=cast(date, self.start_date),
                        end_date=cast(date, self.end_date),
                    ):
                        continue
                    result["posts_in_range"] = cast(int, result["posts_in_range"]) + 1
                    content_id = content.external_content_id
                    unique_in_range.add(content_id)
                    if content_id in self._seen_contents:
                        continue
                    self._seen_contents.add(content_id)
                    self.store.append_canonical("contents", content)
                    try:
                        self._process_content(
                            transport,
                            keyword=target.label,
                            search_content=content,
                            search_raw_locator=(
                                f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                            ),
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "content_id": content_id,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if self._content_limit_reached():
                        result["stop_reason"] = "content_target_reached"
                        result["unique_posts_in_range"] = len(unique_in_range)
                        result["status"] = "completed"
                        self._account_results.append(result)
                        self._search_stop_reasons[target.label] = "content_target_reached"
                        return

                progressless_pages = (
                    progressless_pages + 1
                    if items and len(seen_post_ids) == previous_discovered
                    else 0
                )
                if progressless_pages >= 2:
                    result["stop_reason"] = "repeated_page"
                    break

                if use_douplus:
                    advance = account_runtime.advance_douyin_douplus_user_posts(
                        state=state,
                        body=body,
                    )
                else:
                    advance = account_runtime.advance_douyin_user_posted_videos(
                        state=state,
                        body=body,
                        config=self.account_feed_config,
                    )
                if not advance.should_continue:
                    result["stop_reason"] = advance.stop_reason or "provider_exhausted"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(
                        result.get("stop_reason") or "completed"
                    )
                    return
                state = cast(dict[str, object], advance.next_state)
            result["stop_reason"] = result.get("stop_reason") or "max_account_post_pages_reached"
            result["unique_posts_in_range"] = len(unique_in_range)
            result["status"] = (
                "completed_with_errors"
                if cast(list[dict[str, object]], result["post_failures"])
                else "completed"
            )
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error_summary"] = str(exc)
        self._account_results.append(result)
        account_key = target.label
        if result["status"] in {"completed", "completed_with_errors"}:
            self._search_stop_reasons[account_key] = str(result.get("stop_reason") or "completed")
        else:
            self._search_stop_reasons[account_key] = "account_failed"

    def _resolve_douyin_account_value(
        self,
        transport: TikHubHttpTransport,
        *,
        target: DouyinAccountTarget,
        account_param: str,
    ) -> tuple[str, str | None]:
        """把抖音号解析为作品接口要求的 sec_uid；真实 sec_uid 直接复用。"""

        normalized_param = account_param.strip().casefold()
        if normalized_param not in {"sec_uid", "sec_user_id", "sec_userid"}:
            return target.request_value(account_param), None

        homepage_id = (
            _platform_homepage_id(target.homepage_url, "douyin") if target.homepage_url else None
        )
        if target.unique_id is None and (target.sec_uid or homepage_id):
            sec_uid = target.sec_uid or cast(str, homepage_id)
            if _is_sec_uid(sec_uid):
                return sec_uid, "configured_sec_uid"

        unique_id = target.unique_id
        if unique_id is None and target.sec_uid and not _is_sec_uid(target.sec_uid):
            # 兼容旧配置：此前入口把用户填写的抖音号或短用户标识误放进了
            # sec_uid 字段。非长格式值统一先按 unique_id 解析，避免请求错误 ID。
            unique_id = target.sec_uid
        if unique_id is None:
            raise _AccountResolutionError(
                "抖音账号需要有效 sec_uid、抖音号 unique_id 或完整用户主页"
            )

        profile_call = account_runtime.build_douyin_user_profile_call(
            unique_id=unique_id,
            config=self.account_feed_config,
        )
        body, raw_record = self._send(transport, profile_call, keyword=target.label)
        self._requests[-1].update(
            {
                "account": target.label,
                "account_value": unique_id,
                "account_stage": "profile",
            }
        )
        profile = account_runtime.extract_douyin_user_profile(body)
        resolved_sec_uid = _profile_string(profile, "sec_uid", "sec_user_id")
        if resolved_sec_uid is None:
            raise _AccountResolutionError(
                f"抖音账号 {target.label} 的用户资料未返回 sec_uid；"
                f"原始响应：{self.store.relative_path(raw_record.path)}"
            )
        if (
            target.sec_uid and _is_sec_uid(target.sec_uid) and target.sec_uid != resolved_sec_uid
        ) or (homepage_id and homepage_id != resolved_sec_uid):
            raise _AccountResolutionError("抖音主页、抖音号与 sec_uid 身份不一致")
        if target.uid and _profile_string(profile, "uid", "user_id") != target.uid:
            raise _AccountResolutionError("抖音用户资料与 uid 身份不一致")
        observed_handle = _profile_string(profile, "unique_id")
        if observed_handle and observed_handle != unique_id:
            raise _AccountResolutionError("抖音用户资料与 unique_id 身份不一致")
        return resolved_sec_uid, "unique_id_profile"

    def _run_kuaishou_account(
        self,
        transport: TikHubHttpTransport,
        target: KuaishouAccountTarget,
    ) -> None:
        result: dict[str, object] = {
            "nickname": target.nickname,
            "kuaishou_id": target.kuaishou_id,
            "eid": target.eid,
            "configured_user_id": target.user_id,
            "homepage_url": target.homepage_url,
            "resolved_user_id": None,
            "resolution_method": None,
            "status": "failed",
            "posts_pages": 0,
            "posts_discovered": 0,
            "posts_in_range": 0,
            "unique_posts_in_range": 0,
            "identity_mismatches": 0,
            "post_failures": [],
            "stop_reason": None,
            "error_type": None,
            "error_summary": None,
        }
        try:
            user_id, resolution_method = self._resolve_kuaishou_account(
                transport,
                target=target,
            )
            result["resolved_user_id"] = user_id
            result["resolution_method"] = resolution_method
            state: dict[str, object] | None = None
            unique_in_range: set[str] = set()
            seen_post_ids: set[str] = set()
            progressless_pages = 0
            page_no = 0
            while self.max_account_post_pages is None or page_no < self.max_account_post_pages:
                page_no += 1
                call = account_runtime.build_kuaishou_user_posts_call(
                    user_id=user_id,
                    state=state,
                )
                body, raw_record = self._send(transport, call, keyword=target.label)
                self._requests[-1].update(
                    {
                        "account": target.label,
                        "account_user_id": user_id,
                        "account_page": page_no,
                        "account_stage": "posted_videos",
                    }
                )
                result["posts_pages"] = page_no
                items = account_runtime.extract_kuaishou_user_posts(body)
                previous_discovered = len(seen_post_ids)
                for item_index, raw_item in enumerate(items):
                    result["posts_discovered"] = cast(int, result["posts_discovered"]) + 1
                    item_locator = f"account_posts.page[{page_no}].items[{item_index}]"
                    try:
                        content = tikhub_runtime.map_content(
                            platform="kuaishou",
                            raw=raw_item,
                            context=tikhub_runtime.mapping_context(
                                provider_request_id=raw_record.request_id,
                                provider_attempt_id=raw_record.attempt_id,
                                raw_artifact_id=raw_record.artifact_id,
                                operation=call.operation,
                                source_type="account",
                                source_value=user_id,
                                observed_at=raw_record.observed_at,
                            ),
                            item_locator=item_locator,
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    seen_post_ids.add(content.external_content_id)
                    if not _kuaishou_content_matches_account(
                        content,
                        resolved_user_id=user_id,
                    ):
                        result["identity_mismatches"] = cast(int, result["identity_mismatches"]) + 1
                        continue
                    if content.published_at is None:
                        cast(list[dict[str, object]], result["post_failures"]).append(
                            {
                                "item_locator": item_locator,
                                "error_type": "MissingPublicationTime",
                                "error_summary": "作品缺少发布时间，无法确认是否在日期范围内",
                            }
                        )
                        continue
                    if not _published_on_inclusive_date_range(
                        content.published_at,
                        start_date=cast(date, self.start_date),
                        end_date=cast(date, self.end_date),
                    ):
                        continue
                    result["posts_in_range"] = cast(int, result["posts_in_range"]) + 1
                    content_id = content.external_content_id
                    unique_in_range.add(content_id)
                    if content_id in self._seen_contents:
                        continue
                    self._seen_contents.add(content_id)
                    self.store.append_canonical("contents", content)
                    try:
                        self._process_content(
                            transport,
                            keyword=target.label,
                            search_content=content,
                            search_raw_locator=(
                                f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                            ),
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "content_id": content_id,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if self._content_limit_reached():
                        result["stop_reason"] = "content_target_reached"
                        result["unique_posts_in_range"] = len(unique_in_range)
                        result["status"] = "completed"
                        self._account_results.append(result)
                        self._search_stop_reasons[target.label] = "content_target_reached"
                        return

                progressless_pages = (
                    progressless_pages + 1
                    if items and len(seen_post_ids) == previous_discovered
                    else 0
                )
                if progressless_pages >= 2:
                    result["stop_reason"] = "repeated_page"
                    break

                advance = account_runtime.advance_kuaishou_user_posts(
                    state=state,
                    body=body,
                )
                if not advance.should_continue:
                    result["stop_reason"] = advance.stop_reason or "provider_exhausted"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(result["stop_reason"])
                    return
                state = cast(dict[str, object], advance.next_state)

            result["stop_reason"] = result.get("stop_reason") or "max_account_post_pages_reached"
            result["unique_posts_in_range"] = len(unique_in_range)
            result["status"] = (
                "completed_with_errors"
                if cast(list[dict[str, object]], result["post_failures"])
                else "completed"
            )
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error_summary"] = str(exc)
        self._account_results.append(result)
        if result["status"] in {"completed", "completed_with_errors"}:
            self._search_stop_reasons[target.label] = str(result.get("stop_reason") or "completed")
        else:
            self._search_stop_reasons[target.label] = "account_failed"

    def _resolve_kuaishou_account(
        self,
        transport: TikHubHttpTransport,
        *,
        target: KuaishouAccountTarget,
    ) -> tuple[str, str]:
        if (
            target.user_id
            and not target.eid
            and not target.kuaishou_id
            and (
                not target.homepage_url
                or _platform_homepage_id(target.homepage_url, "kuaishou").isdigit()
            )
        ):
            return target.user_id, "configured_user_id"

        if target.kuaishou_id:
            return self._search_kuaishou_account(
                transport,
                target=target,
                query=target.kuaishou_id,
            )

        if target.nickname and not (target.eid or target.homepage_url or target.user_id):
            return self._search_kuaishou_account(transport, target=target, query=target.nickname)
        reference = target.profile_reference
        profile_call = account_runtime.build_kuaishou_user_profile_call(
            user_reference=reference,
        )
        body, raw_record = self._send(transport, profile_call, keyword=target.label)
        self._requests[-1].update(
            {
                "account": target.label,
                "account_reference": reference,
                "account_stage": "profile",
            }
        )
        profile = account_runtime.extract_kuaishou_user_profile(body)
        identity = _kuaishou_identity_from_mapping(profile)
        user_id = identity.get("user_id")
        if user_id is None or not user_id.isdigit():
            raise _AccountResolutionError(
                f"快手账号 {target.label} 的用户资料未返回纯数字 userId；"
                f"原始响应：{self.store.relative_path(raw_record.path)}"
            )
        if target.user_id and user_id != target.user_id:
            raise _AccountResolutionError("快手主页与 user_id 身份不一致")
        if not _kuaishou_configured_identity_matches(target, identity):
            raise _AccountResolutionError(f"快手账号 {target.label} 配置身份冲突或响应身份字段缺失")
        return user_id, "profile_reference"

    def _search_kuaishou_account(
        self,
        transport: TikHubHttpTransport,
        *,
        target: KuaishouAccountTarget,
        query: str,
    ) -> tuple[str, str]:
        state: dict[str, object] | None = None
        matches: dict[str, dict[str, str]] = {}
        for page_no in range(1, self.max_account_search_pages + 1):
            call = account_runtime.build_kuaishou_user_search_call(
                keyword=query,
                state=state,
            )
            body, _ = self._send(transport, call, keyword=target.label)
            self._requests[-1].update(
                {
                    "account": target.label,
                    "account_query": query,
                    "account_page": page_no,
                    "account_stage": "identity_search",
                }
            )
            for raw_item in account_runtime.extract_kuaishou_user_search_items(body):
                identity = _kuaishou_identity_from_mapping(raw_item)
                user_id = identity.get("user_id")
                if user_id is None or not user_id.isdigit():
                    continue
                if _kuaishou_account_candidate_matches(target, identity, query=query):
                    matches[user_id] = identity

            advance = account_runtime.advance_kuaishou_user_search(
                state=state,
                body=body,
            )
            if not advance.should_continue:
                if advance.stop_reason not in {"provider_exhausted", "empty_page"}:
                    raise _AccountResolutionError("账号搜索分页未完整结束，不能确认唯一身份")
                break
            state = cast(dict[str, object], advance.next_state)
        else:
            raise _AccountResolutionError("账号搜索达到页数上限，不能确认唯一身份")

        if len(matches) != 1:
            if not matches:
                raise _AccountResolutionError(
                    f"快手账号 {target.label} 未找到快手号/昵称精确匹配用户"
                )
            raise _AccountResolutionError(
                f"快手账号 {target.label} 找到多个精确匹配 userId: {', '.join(sorted(matches))}"
            )
        user_id, _ = next(iter(matches.items()))
        return user_id, "search_user_v2"

    def _run_weibo_account(
        self,
        transport: TikHubHttpTransport,
        target: WeiboAccountTarget,
    ) -> None:
        result: dict[str, object] = {
            "nickname": target.nickname,
            "configured_uid": target.uid,
            "homepage_url": target.homepage_url,
            "resolved_uid": None,
            "resolution_method": None,
            "status": "failed",
            "posts_pages": 0,
            "posts_discovered": 0,
            "posts_in_range": 0,
            "unique_posts_in_range": 0,
            "identity_mismatches": 0,
            "post_failures": [],
            "stop_reason": None,
            "error_type": None,
            "error_summary": None,
        }
        try:
            uid, resolution_method = self._resolve_weibo_account(transport, target=target)
            result["resolved_uid"] = uid
            result["resolution_method"] = resolution_method
            state: dict[str, object] | None = None
            unique_in_range: set[str] = set()
            seen_post_ids: set[str] = set()
            progressless_pages = 0
            page_no = 0
            while self.max_account_post_pages is None or page_no < self.max_account_post_pages:
                page_no += 1
                call = account_runtime.build_weibo_user_posts_call(
                    uid=uid,
                    state=state,
                )
                body, raw_record = self._send(transport, call, keyword=target.label)
                self._requests[-1].update(
                    {
                        "account": target.label,
                        "account_uid": uid,
                        "account_page": page_no,
                        "account_stage": "posted_statuses",
                    }
                )
                result["posts_pages"] = page_no
                items = account_runtime.extract_weibo_user_posts(body)
                previous_discovered = len(seen_post_ids)
                for item_index, raw_item in enumerate(items):
                    result["posts_discovered"] = cast(int, result["posts_discovered"]) + 1
                    item_locator = f"account_posts.page[{page_no}].items[{item_index}]"
                    try:
                        content = tikhub_runtime.map_content(
                            platform="weibo",
                            raw=raw_item,
                            context=tikhub_runtime.mapping_context(
                                provider_request_id=raw_record.request_id,
                                provider_attempt_id=raw_record.attempt_id,
                                raw_artifact_id=raw_record.artifact_id,
                                operation=call.operation,
                                source_type="account",
                                source_value=uid,
                                observed_at=raw_record.observed_at,
                            ),
                            item_locator=item_locator,
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    seen_post_ids.add(content.external_content_id)
                    if not _weibo_content_matches_account(content, resolved_uid=uid):
                        result["identity_mismatches"] = cast(int, result["identity_mismatches"]) + 1
                        continue
                    if content.published_at is None:
                        cast(list[dict[str, object]], result["post_failures"]).append(
                            {
                                "item_locator": item_locator,
                                "error_type": "MissingPublicationTime",
                                "error_summary": "作品缺少发布时间，无法确认是否在日期范围内",
                            }
                        )
                        continue
                    if not _published_on_inclusive_date_range(
                        content.published_at,
                        start_date=cast(date, self.start_date),
                        end_date=cast(date, self.end_date),
                    ):
                        continue
                    result["posts_in_range"] = cast(int, result["posts_in_range"]) + 1
                    content_id = content.external_content_id
                    unique_in_range.add(content_id)
                    if content_id in self._seen_contents:
                        continue
                    self._seen_contents.add(content_id)
                    self.store.append_canonical("contents", content)
                    try:
                        self._process_content(
                            transport,
                            keyword=target.label,
                            search_content=content,
                            search_raw_locator=(
                                f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                            ),
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "content_id": content_id,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if self._content_limit_reached():
                        result["stop_reason"] = "content_target_reached"
                        result["unique_posts_in_range"] = len(unique_in_range)
                        result["status"] = "completed"
                        self._account_results.append(result)
                        self._search_stop_reasons[target.label] = "content_target_reached"
                        return

                progressless_pages = (
                    progressless_pages + 1
                    if items and len(seen_post_ids) == previous_discovered
                    else 0
                )
                if progressless_pages >= 2:
                    result["stop_reason"] = "repeated_page"
                    break

                advance = account_runtime.advance_weibo_user_posts(state=state, body=body)
                if not advance.should_continue:
                    result["stop_reason"] = advance.stop_reason or "provider_exhausted"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(result["stop_reason"])
                    return
                state = cast(dict[str, object], advance.next_state)

            result["stop_reason"] = result.get("stop_reason") or "max_account_post_pages_reached"
            result["unique_posts_in_range"] = len(unique_in_range)
            result["status"] = (
                "completed_with_errors"
                if cast(list[dict[str, object]], result["post_failures"])
                else "completed"
            )
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error_summary"] = str(exc)
        self._account_results.append(result)
        if result["status"] in {"completed", "completed_with_errors"}:
            self._search_stop_reasons[target.label] = str(result.get("stop_reason") or "completed")
        else:
            self._search_stop_reasons[target.label] = "account_failed"

    def _resolve_weibo_account(
        self,
        transport: TikHubHttpTransport,
        *,
        target: WeiboAccountTarget,
    ) -> tuple[str, str]:
        if target.uid:
            return target.uid, "configured_uid"
        if target.homepage_url:
            return _weibo_uid_from_homepage(target.homepage_url), "homepage_url"
        if target.nickname:
            return self._search_weibo_account(transport, target=target)
        raise _AccountResolutionError(f"微博账号 {target.label} 缺少可解析的 UID")

    def _run_bilibili_account(
        self,
        transport: TikHubHttpTransport,
        target: BilibiliAccountTarget,
    ) -> None:
        result: dict[str, object] = {
            "nickname": target.nickname,
            "configured_uid": target.uid,
            "homepage_url": target.homepage_url,
            "resolved_uid": None,
            "resolution_method": None,
            "status": "failed",
            "posts_pages": 0,
            "posts_discovered": 0,
            "posts_in_range": 0,
            "unique_posts_in_range": 0,
            "identity_mismatches": 0,
            "post_failures": [],
            "stop_reason": None,
            "error_type": None,
            "error_summary": None,
        }
        try:
            uid, resolution_method = self._resolve_bilibili_account(target=target)
            result["resolved_uid"] = uid
            result["resolution_method"] = resolution_method
            state: dict[str, object] | None = None
            unique_in_range: set[str] = set()
            seen_post_ids: set[str] = set()
            progressless_pages = 0
            page_no = 0
            while self.max_account_post_pages is None or page_no < self.max_account_post_pages:
                page_no += 1
                call = account_runtime.build_bilibili_user_posts_call(uid=uid, state=state)
                body, raw_record = self._send(transport, call, keyword=target.label)
                self._requests[-1].update(
                    {
                        "account": target.label,
                        "account_uid": uid,
                        "account_page": page_no,
                        "account_stage": "posted_videos",
                    }
                )
                result["posts_pages"] = page_no
                items = account_runtime.extract_bilibili_user_posts(body)
                previous_discovered = len(seen_post_ids)
                for item_index, raw_item in enumerate(items):
                    result["posts_discovered"] = cast(int, result["posts_discovered"]) + 1
                    item_locator = f"account_posts.page[{page_no}].items[{item_index}]"
                    try:
                        content = tikhub_runtime.map_content(
                            platform="bilibili",
                            raw=raw_item,
                            context=tikhub_runtime.mapping_context(
                                provider_request_id=raw_record.request_id,
                                provider_attempt_id=raw_record.attempt_id,
                                raw_artifact_id=raw_record.artifact_id,
                                operation=call.operation,
                                source_type="account",
                                source_value=uid,
                                observed_at=raw_record.observed_at,
                            ),
                            item_locator=item_locator,
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    seen_post_ids.add(content.external_content_id)
                    if not _weibo_content_matches_account(content, resolved_uid=uid):
                        result["identity_mismatches"] = cast(int, result["identity_mismatches"]) + 1
                        continue
                    if content.published_at is None:
                        cast(list[dict[str, object]], result["post_failures"]).append(
                            {
                                "item_locator": item_locator,
                                "error_type": "MissingPublicationTime",
                                "error_summary": "作品缺少发布时间，无法确认是否在日期范围内",
                            }
                        )
                        continue
                    if not _published_on_inclusive_date_range(
                        content.published_at,
                        start_date=cast(date, self.start_date),
                        end_date=cast(date, self.end_date),
                    ):
                        continue
                    result["posts_in_range"] = cast(int, result["posts_in_range"]) + 1
                    content_id = content.external_content_id
                    unique_in_range.add(content_id)
                    if content_id in self._seen_contents:
                        continue
                    self._seen_contents.add(content_id)
                    self.store.append_canonical("contents", content)
                    try:
                        self._process_content(
                            transport,
                            keyword=target.label,
                            search_content=content,
                            search_raw_locator=(
                                f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                            ),
                        )
                    except Exception as exc:
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "content_id": content_id,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if self._content_limit_reached():
                        result["stop_reason"] = "content_target_reached"
                        result["unique_posts_in_range"] = len(unique_in_range)
                        result["status"] = "completed"
                        self._account_results.append(result)
                        self._search_stop_reasons[target.label] = "content_target_reached"
                        return

                progressless_pages = (
                    progressless_pages + 1
                    if items and len(seen_post_ids) == previous_discovered
                    else 0
                )
                if progressless_pages >= 2:
                    result["stop_reason"] = "repeated_page"
                    break

                advance = account_runtime.advance_bilibili_user_posts(state=state, body=body)
                if not advance.should_continue:
                    result["stop_reason"] = advance.stop_reason or "provider_exhausted"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(result["stop_reason"])
                    return
                state = cast(dict[str, object], advance.next_state)

            result["stop_reason"] = result.get("stop_reason") or "max_account_post_pages_reached"
            result["unique_posts_in_range"] = len(unique_in_range)
            result["status"] = (
                "completed_with_errors"
                if cast(list[dict[str, object]], result["post_failures"])
                else "completed"
            )
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error_summary"] = str(exc)
        self._account_results.append(result)
        if result["status"] in {"completed", "completed_with_errors"}:
            self._search_stop_reasons[target.label] = str(result.get("stop_reason") or "completed")
        else:
            self._search_stop_reasons[target.label] = "account_failed"

    def _resolve_bilibili_account(
        self,
        *,
        target: BilibiliAccountTarget,
    ) -> tuple[str, str]:
        if target.uid:
            return target.uid, "configured_uid"
        if target.homepage_url:
            return _bilibili_uid_from_homepage(target.homepage_url), "homepage_url"
        raise _AccountResolutionError(f"B站账号 {target.label} 缺少可解析的 UID")

    def _search_weibo_account(
        self,
        transport: TikHubHttpTransport,
        *,
        target: WeiboAccountTarget,
    ) -> tuple[str, str]:
        if target.nickname is None:
            raise _AccountResolutionError("微博昵称搜索需要配置 nickname")
        matches: dict[str, dict[str, str]] = {}
        for page_no in range(1, self.max_account_search_pages + 1):
            call = account_runtime.build_weibo_user_search_call(
                query=target.nickname,
                state={"page": page_no},
                nickname=target.nickname,
            )
            body, _ = self._send(transport, call, keyword=target.label)
            self._requests[-1].update(
                {
                    "account": target.label,
                    "account_query": target.nickname,
                    "account_page": page_no,
                    "account_stage": "identity_search",
                }
            )
            candidates = account_runtime.extract_weibo_user_search_items(body)
            for raw_item in candidates:
                identity = _weibo_identity_from_mapping(raw_item)
                uid = identity.get("uid")
                if uid and _weibo_account_candidate_matches(target, identity):
                    matches[uid] = identity
            if not candidates:
                break
        else:
            raise _AccountResolutionError("微博账号搜索达到页数上限，不能确认唯一身份")

        if len(matches) != 1:
            if not matches:
                raise _AccountResolutionError(
                    f"微博账号 {target.label} 未找到精确 UID；请在配置中填写 uid"
                )
            raise _AccountResolutionError(
                f"微博账号 {target.label} 匹配到多个 UID；请在配置中填写 uid"
            )
        return next(iter(matches)), "nickname_search"


def run_douyin_accounts(
    *,
    accounts: Sequence[DouyinAccountTarget | Mapping[str, object]] | str | bytes,
    start_date: str | date,
    end_date: str | date,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_account_post_pages: int = 100,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    comment_mode: Literal["limited", "all"] = "all",
    force_refresh: bool = False,
    account_posts_path: str = "/api/v1/douyin/app/v3/fetch_user_post_videos",
    account_posts_method: Literal["GET", "POST"] = "GET",
    account_id_param: str = "sec_user_id",
    account_cursor_param: str = "max_cursor",
    account_items_path: str = "data.aweme_list",
    account_cursor_path: str = "data.max_cursor",
    account_has_more_path: str = "data.has_more",
    account_profile_path: str = "/api/v1/douyin/web/handler_user_profile_v2",
    account_profile_id_param: str = "unique_id",
    account_posts_source: Literal["app_v3", "douplus"] = "app_v3",
    douplus_post_page_size: int = 10,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """按指定抖音账号和包含式北京时间日期范围执行全量评论采集。"""

    if account_posts_source not in {"app_v3", "douplus"}:
        raise ValueError("account_posts_source 只能是 app_v3 或 douplus")
    normalized_accounts = _normalize_douyin_account_targets(accounts)
    normalized_start = _normalize_date(start_date, "start_date")
    normalized_end = _normalize_date(end_date, "end_date")
    if normalized_start > normalized_end:
        raise ValueError("start_date 不能晚于 end_date")
    if comment_mode not in {"limited", "all"}:
        raise ValueError("comment_mode 只能是 limited 或 all")
    if comment_mode == "all" and (not include_comments or not include_replies):
        raise ValueError("comment_mode='all' 时 include_comments 和 include_replies 必须为 True")
    if (
        isinstance(douplus_post_page_size, bool)
        or not isinstance(douplus_post_page_size, int)
        or douplus_post_page_size < 1
    ):
        raise ValueError("douplus_post_page_size 必须是正整数")
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    labels = tuple(target.label for target in normalized_accounts)
    account_feed_config: dict[str, object] = {
        "discovery_source": "account",
        "account_posts_path": account_posts_path,
        "account_posts_method": account_posts_method,
        "account_id_param": account_id_param,
        "account_cursor_param": account_cursor_param,
        "account_items_path": account_items_path,
        "account_cursor_path": account_cursor_path,
        "account_has_more_path": account_has_more_path,
        "account_profile_path": account_profile_path,
        "account_profile_id_param": account_profile_id_param,
        "account_posts_source": account_posts_source,
        "douplus_post_page_size": douplus_post_page_size,
    }
    return _AccountDebugRunner(
        platform="douyin",
        keywords=labels,
        search_config=account_feed_config,
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
        limits=_RunLimits(
            max_search_pages=1,
            max_contents=max_contents,
            max_comments_per_content=max_comments_per_content,
            max_comment_pages_per_content=max_comment_pages_per_content,
            max_replies_per_root=max_replies_per_root,
            max_reply_pages_per_root=max_reply_pages_per_root,
        ),
        include_comments=include_comments,
        include_replies=include_replies,
        force_refresh=force_refresh,
        write_to_database=write_to_database,
        provider_config_id=provider_config_id,
        account_targets=normalized_accounts,
        start_date=normalized_start,
        end_date=normalized_end,
        comment_mode=comment_mode,
        max_account_post_pages=max_account_post_pages,
        account_feed_config=account_feed_config,
    ).run()


def run_kuaishou_accounts(
    *,
    accounts: Sequence[KuaishouAccountTarget | Mapping[str, object]] | str | bytes,
    start_date: str | date,
    end_date: str | date,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_account_search_pages: int = 5,
    max_account_post_pages: int | None = None,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    comment_mode: Literal["limited", "all"] = "all",
    force_refresh: bool = True,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """按指定快手账号和包含式北京时间日期范围执行全量评论采集。"""

    normalized_accounts = _normalize_kuaishou_account_targets(accounts)
    normalized_start = _normalize_date(start_date, "start_date")
    normalized_end = _normalize_date(end_date, "end_date")
    if normalized_start > normalized_end:
        raise ValueError("start_date 不能晚于 end_date")
    if comment_mode not in {"limited", "all"}:
        raise ValueError("comment_mode 只能是 limited 或 all")
    if comment_mode == "all" and (not include_comments or not include_replies):
        raise ValueError("comment_mode='all' 时 include_comments 和 include_replies 必须为 True")
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    labels = tuple(target.label for target in normalized_accounts)
    return _AccountDebugRunner(
        platform="kuaishou",
        keywords=labels,
        search_config={"discovery_source": "account"},
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
        limits=_RunLimits(
            max_search_pages=1,
            max_contents=max_contents,
            max_comments_per_content=max_comments_per_content,
            max_comment_pages_per_content=max_comment_pages_per_content,
            max_replies_per_root=max_replies_per_root,
            max_reply_pages_per_root=max_reply_pages_per_root,
        ),
        include_comments=include_comments,
        include_replies=include_replies,
        force_refresh=force_refresh,
        write_to_database=write_to_database,
        provider_config_id=provider_config_id,
        account_targets=normalized_accounts,
        start_date=normalized_start,
        end_date=normalized_end,
        comment_mode=comment_mode,
        max_account_search_pages=max_account_search_pages,
        max_account_post_pages=max_account_post_pages,
    ).run()


def run_bilibili_accounts(
    *,
    accounts: Sequence[BilibiliAccountTarget | Mapping[str, object]] | str | bytes,
    start_date: str | date,
    end_date: str | date,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_account_post_pages: int | None = None,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    comment_mode: Literal["limited", "all"] = "all",
    force_refresh: bool = True,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """按指定 B站 UP 主和包含式北京时间日期范围执行全量评论采集。"""

    normalized_accounts = _normalize_bilibili_account_targets(accounts)
    normalized_start = _normalize_date(start_date, "start_date")
    normalized_end = _normalize_date(end_date, "end_date")
    if normalized_start > normalized_end:
        raise ValueError("start_date 不能晚于 end_date")
    if comment_mode not in {"limited", "all"}:
        raise ValueError("comment_mode 只能是 limited 或 all")
    if comment_mode == "all" and (not include_comments or not include_replies):
        raise ValueError("comment_mode='all' 时 include_comments 和 include_replies 必须为 True")
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    labels = tuple(target.label for target in normalized_accounts)
    return _AccountDebugRunner(
        platform="bilibili",
        keywords=labels,
        search_config={"discovery_source": "account"},
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
        limits=_RunLimits(
            max_search_pages=1,
            max_contents=max_contents,
            max_comments_per_content=max_comments_per_content,
            max_comment_pages_per_content=max_comment_pages_per_content,
            max_replies_per_root=max_replies_per_root,
            max_reply_pages_per_root=max_reply_pages_per_root,
        ),
        include_comments=include_comments,
        include_replies=include_replies,
        force_refresh=force_refresh,
        write_to_database=write_to_database,
        provider_config_id=provider_config_id,
        account_targets=normalized_accounts,
        start_date=normalized_start,
        end_date=normalized_end,
        comment_mode=comment_mode,
        max_account_post_pages=max_account_post_pages,
    ).run()


def run_weibo_accounts(
    *,
    accounts: Sequence[WeiboAccountTarget | Mapping[str, object]] | str | bytes,
    start_date: str | date,
    end_date: str | date,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_account_search_pages: int = 5,
    max_account_post_pages: int | None = None,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    comment_mode: Literal["limited", "all"] = "all",
    force_refresh: bool = True,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """按指定微博账号和包含式北京时间日期范围执行全量评论采集。"""

    normalized_accounts = _normalize_weibo_account_targets(accounts)
    normalized_start = _normalize_date(start_date, "start_date")
    normalized_end = _normalize_date(end_date, "end_date")
    if normalized_start > normalized_end:
        raise ValueError("start_date 不能晚于 end_date")
    if comment_mode not in {"limited", "all"}:
        raise ValueError("comment_mode 只能是 limited 或 all")
    if comment_mode == "all" and (not include_comments or not include_replies):
        raise ValueError("comment_mode='all' 时 include_comments 和 include_replies 必须为 True")
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    labels = tuple(target.label for target in normalized_accounts)
    return _AccountDebugRunner(
        platform="weibo",
        keywords=labels,
        search_config={"discovery_source": "account"},
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
        limits=_RunLimits(
            max_search_pages=1,
            max_contents=max_contents,
            max_comments_per_content=max_comments_per_content,
            max_comment_pages_per_content=max_comment_pages_per_content,
            max_replies_per_root=max_replies_per_root,
            max_reply_pages_per_root=max_reply_pages_per_root,
        ),
        include_comments=include_comments,
        include_replies=include_replies,
        force_refresh=force_refresh,
        write_to_database=write_to_database,
        provider_config_id=provider_config_id,
        account_targets=normalized_accounts,
        start_date=normalized_start,
        end_date=normalized_end,
        comment_mode=comment_mode,
        max_account_search_pages=max_account_search_pages,
        max_account_post_pages=max_account_post_pages,
    ).run()


def _normalize_douyin_account_targets(
    accounts: Sequence[DouyinAccountTarget | Mapping[str, object]] | str | bytes,
) -> tuple[DouyinAccountTarget, ...]:
    if isinstance(accounts, (str, bytes)):
        raise ValueError("accounts 必须是账号配置序列")
    normalized = tuple(
        DouyinAccountTarget.from_value(dict(value) if isinstance(value, Mapping) else value)
        for value in accounts
    )
    if not normalized:
        raise ValueError("accounts 至少包含一个账号")
    keys = [target.cache_key for target in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("accounts 不能包含重复账号配置")
    return normalized


def _normalize_kuaishou_account_targets(
    accounts: Sequence[KuaishouAccountTarget | Mapping[str, object]] | str | bytes,
) -> tuple[KuaishouAccountTarget, ...]:
    if isinstance(accounts, (str, bytes)):
        raise ValueError("accounts 必须是账号配置序列")
    normalized = tuple(
        KuaishouAccountTarget.from_value(dict(value) if isinstance(value, Mapping) else value)
        for value in accounts
    )
    if not normalized:
        raise ValueError("accounts 至少包含一个账号")
    keys = [target.cache_key for target in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("accounts 不能包含重复账号配置")
    return normalized


def _normalize_weibo_account_targets(
    accounts: Sequence[WeiboAccountTarget | Mapping[str, object]] | str | bytes,
) -> tuple[WeiboAccountTarget, ...]:
    if isinstance(accounts, (str, bytes)):
        raise ValueError("accounts 必须是账号配置序列")
    normalized = tuple(
        WeiboAccountTarget.from_value(dict(value) if isinstance(value, Mapping) else value)
        for value in accounts
    )
    if not normalized:
        raise ValueError("accounts 至少包含一个账号")
    keys = [target.cache_key for target in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("accounts 不能包含重复账号配置")
    return normalized


def _normalize_bilibili_account_targets(
    accounts: Sequence[BilibiliAccountTarget | Mapping[str, object]] | str | bytes,
) -> tuple[BilibiliAccountTarget, ...]:
    if isinstance(accounts, (str, bytes)):
        raise ValueError("accounts 必须是账号配置序列")
    normalized = tuple(
        BilibiliAccountTarget.from_value(dict(value) if isinstance(value, Mapping) else value)
        for value in accounts
    )
    if not normalized:
        raise ValueError("accounts 至少包含一个账号")
    keys = [target.cache_key for target in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("accounts 不能包含重复账号配置")
    return normalized


def _douyin_content_matches_account(
    content: CanonicalContentV1,
    target: DouyinAccountTarget,
    *,
    resolved_sec_uid: str | None = None,
) -> bool:
    author = content.author
    if author is None:
        return False
    if target.uid and author.external_account_id and author.external_account_id != target.uid:
        return False
    if target.unique_id and author.handle and author.handle != target.unique_id:
        return False
    observed_sec_uid = author.alternate_ids.get("sec_uid")
    expected_sec_uid = resolved_sec_uid or (
        target.sec_uid if _is_sec_uid(target.sec_uid or "") else None
    )
    if expected_sec_uid and observed_sec_uid and observed_sec_uid != expected_sec_uid:
        return False
    if (
        target.nickname
        and not target.uid
        and not expected_sec_uid
        and author.display_name
        and author.display_name != target.nickname
    ):
        return False
    return bool(
        (target.uid and author.external_account_id == target.uid)
        or (target.unique_id and author.handle == target.unique_id)
        or (expected_sec_uid and observed_sec_uid == expected_sec_uid)
    )


def _platform_homepage_id(homepage_url: str, platform: str) -> str:
    """只解析正式平台完整主页；短链接与内容页不能证明账号身份。"""
    parsed = urlparse(homepage_url)
    allowed_hosts = {
        "douyin": {"www.douyin.com", "douyin.com"},
        "kuaishou": {"www.kuaishou.com", "kuaishou.com"},
        "weibo": {"weibo.com", "www.weibo.com", "m.weibo.cn"},
        "bilibili": {"space.bilibili.com"},
    }
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in allowed_hosts[platform]
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"{platform} homepage_url 必须是官方平台完整主页")
    parts = [part for part in parsed.path.split("/") if part]
    if platform == "bilibili" and parts and parts[0].isdigit():
        return parts[0]
    markers = {"douyin": {"user"}, "kuaishou": {"profile"}, "weibo": {"u", "profile"}}
    if len(parts) == 2 and parts[0] in markers.get(platform, set()):
        value = parts[1]
        if platform != "weibo" or value.isdigit():
            return value
    if platform == "weibo" and len(parts) == 1 and parts[0].isdigit():
        return parts[0]
    raise ValueError(f"{platform} homepage_url 中没有有效的账号身份，请填写稳定 ID")


def _kuaishou_reference_from_homepage(homepage_url: str) -> str:
    return _platform_homepage_id(homepage_url, "kuaishou")


def _kuaishou_account_candidate_matches(
    target: KuaishouAccountTarget,
    candidate: Mapping[str, str],
    *,
    query: str,
) -> bool:
    candidate_nickname = candidate.get("nickname")
    if target.kuaishou_id:
        return candidate.get(
            "kuaishou_id"
        ) == target.kuaishou_id and _kuaishou_configured_identity_matches(target, candidate)
    if target.eid:
        return candidate.get("eid") == target.eid or candidate.get("kuaishou_id") == target.eid
    return (
        candidate.get("kuaishou_id") == query
        or candidate.get("eid") == query
        or candidate_nickname == query
    )


def _kuaishou_configured_identity_matches(
    target: KuaishouAccountTarget,
    candidate: Mapping[str, str],
) -> bool:
    """同时校验稳定标识；缺少约束字段不能当作身份一致。"""
    for configured, key in (
        (target.user_id, "user_id"),
        (target.eid, "eid"),
        (target.kuaishou_id, "kuaishou_id"),
    ):
        if configured is not None and candidate.get(key) != configured:
            return False
    if target.homepage_url:
        homepage_id = _platform_homepage_id(target.homepage_url, "kuaishou")
        if homepage_id not in {
            candidate.get("user_id"),
            candidate.get("eid"),
            candidate.get("kuaishou_id"),
        }:
            return False
    return True


def _kuaishou_content_matches_account(
    content: CanonicalContentV1,
    *,
    resolved_user_id: str,
) -> bool:
    author = content.author
    if author is None:
        return False
    return author.external_account_id == resolved_user_id


def _weibo_uid_from_homepage(homepage_url: str) -> str:
    return _platform_homepage_id(homepage_url, "weibo")


def _bilibili_uid_from_homepage(homepage_url: str) -> str:
    return _platform_homepage_id(homepage_url, "bilibili")


def _weibo_identity_from_mapping(raw: Mapping[str, object]) -> dict[str, str]:
    queue: list[Mapping[str, object]] = [raw]
    seen: set[int] = set()
    result: dict[str, str] = {}
    aliases = {
        "uid": ("uid", "user_id", "userId", "id"),
        "nickname": ("screen_name", "nickname", "nick_name", "name"),
    }
    while queue and len(seen) < 32:
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


def _weibo_account_candidate_matches(
    target: WeiboAccountTarget,
    candidate: Mapping[str, str],
) -> bool:
    if target.uid is not None and candidate.get("uid") != target.uid:
        return False
    if target.nickname is not None and candidate.get("nickname") != target.nickname:
        return False
    return bool(candidate.get("uid"))


def _weibo_content_matches_account(
    content: CanonicalContentV1,
    *,
    resolved_uid: str,
) -> bool:
    author = content.author
    if author is None or not author.external_account_id:
        return False
    return author.external_account_id == resolved_uid


def _is_sec_uid(value: str) -> bool:
    """识别抖音常见的长格式 sec_uid；短值通常是抖音号 unique_id。"""

    return value.startswith("MS4wLjAB") or len(value) >= 30


def _profile_string(profile: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_date(value: str | date, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.astimezone(_BEIJING).date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是 YYYY-MM-DD 日期")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是 YYYY-MM-DD 日期") from exc


def _published_on_inclusive_date_range(
    published_at: datetime | None,
    *,
    start_date: date,
    end_date: date,
) -> bool:
    if published_at is None:
        return False
    return start_date <= published_at.astimezone(_BEIJING).date() <= end_date


def _optional_config_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须为非空字符串或 None")
    return value.strip()

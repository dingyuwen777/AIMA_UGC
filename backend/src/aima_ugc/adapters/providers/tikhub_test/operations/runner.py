"""复用生产 TikHub Runtime 的五平台人工调试执行器。"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import parse_qs, urlparse
from uuid import UUID
from zoneinfo import ZoneInfo

from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.adapters.providers.tikhub.capabilities import TIKHUB_PLATFORM_CAPABILITIES
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import (
    DebugState,
    RawOutputRecord,
    RunOutputStore,
    default_run_id,
)
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import (
    CollectionDecisionContextV1,
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    CollectionDecisionV1,
    ContentObservationV1,
    PreviousContentStateV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.contracts.export import UnifiedDataExcelCommentV1, UnifiedDataExcelV1
from aima_ugc.contracts.provider import assert_secret_free
from aima_ugc.modules.collection.decision import (
    CollectionDecisionService,
    known_comment_boundary_reached,
)
from aima_ugc.platform.export import (
    export_comment_labeling_excel,
    export_unified_data_excel,
    project_canonical_comment,
    project_canonical_content,
)

if TYPE_CHECKING:
    from aima_ugc.bootstrap.tikhub_test_database import TikHubDebugDatabaseSession

_DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"
_CAPABILITIES = {item.platform: item for item in TIKHUB_PLATFORM_CAPABILITIES}
_BEIJING = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class TikHubTestRunResult:
    platform: tikhub_runtime.TikHubPlatform
    run_dir: Path
    workbook_path: Path
    run_summary_path: Path
    content_count: int
    root_comment_count: int
    reply_count: int
    request_count: int


@dataclass(frozen=True, slots=True)
class _RunLimits:
    max_search_pages: int
    max_contents: int | None
    max_comments_per_content: int
    max_comment_pages_per_content: int | None
    max_replies_per_root: int
    max_reply_pages_per_root: int | None

    def validate(self) -> None:
        values = {
            "max_search_pages": self.max_search_pages,
            "max_comments_per_content": self.max_comments_per_content,
            "max_comment_pages_per_content": self.max_comment_pages_per_content,
            "max_replies_per_root": self.max_replies_per_root,
            "max_reply_pages_per_root": self.max_reply_pages_per_root,
        }
        if self.max_contents is not None:
            values["max_contents"] = self.max_contents
        invalid = [
            name
            for name, value in values.items()
            if isinstance(value, int) and value < 1
        ]
        if invalid:
            raise ValueError(f"TikHub 调试上限必须大于 0: {', '.join(invalid)}")


@dataclass(frozen=True, slots=True)
class XiaohongshuAccountTarget:
    """人工配置的一个小红书账号；至少提供一个身份字段。"""

    nickname: str | None = None
    red_id: str | None = None
    user_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("nickname", "red_id", "user_id"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} 必须为非空字符串或 None")
                object.__setattr__(self, field_name, value.strip())
        if self.nickname is None and self.red_id is None and self.user_id is None:
            raise ValueError("小红书账号至少需要 nickname、red_id、user_id 之一")

    @classmethod
    def from_value(
        cls,
        value: XiaohongshuAccountTarget | dict[str, object],
    ) -> XiaohongshuAccountTarget:
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("accounts 中每一项必须是 XiaohongshuAccountTarget 或字典")
        allowed = {"nickname", "red_id", "user_id"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"小红书账号配置包含未知字段: {', '.join(unknown)}")
        return cls(
            nickname=_optional_config_text(value.get("nickname"), "nickname"),
            red_id=_optional_config_text(value.get("red_id"), "red_id"),
            user_id=_optional_config_text(value.get("user_id"), "user_id"),
        )

    @property
    def label(self) -> str:
        return self.nickname or self.red_id or self.user_id or "未命名账号"

    @property
    def cache_key(self) -> str:
        return "|".join((self.nickname or "", self.red_id or "", self.user_id or ""))


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
        if self.user_id is not None and not self.user_id.isdigit():
            raise ValueError("快手 user_id 必须是纯数字；主页 eid 请填写到 eid 字段")
        if all(
            value is None
            for value in (self.kuaishou_id, self.eid, self.user_id, self.homepage_url)
        ):
            raise ValueError(
                "快手账号至少需要 kuaishou_id、eid、user_id、homepage_url 之一"
            )

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


class _TikHubHttpStatusError(RuntimeError):
    """保留已落盘 HTTP 失败的安全关联信息，供内容级决策使用。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        operation: str,
        external_request_id: str | None,
        raw_file: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.operation = operation
        self.external_request_id = external_request_id
        self.raw_file = raw_file
        self.retryable = retryable


class _AccountResolutionError(RuntimeError):
    """账号身份无法安全解析时使用的非 Secret 错误。"""


class _TikHubDebugRunner:
    _continue_after_item_http_error = False

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
            XiaohongshuAccountTarget
            | DouyinAccountTarget
            | KuaishouAccountTarget
            | WeiboAccountTarget
            | BilibiliAccountTarget,
            ...
        ] = (),
        start_date: date | None = None,
        end_date: date | None = None,
        comment_mode: Literal["limited", "all"] = "limited",
        max_account_search_pages: int = 5,
        max_user_note_pages: int = 100,
        max_account_post_pages: int | None = 100,
        force_resolve_accounts: bool = False,
        account_feed_config: dict[str, object] | None = None,
    ) -> None:
        limits.validate()
        if comment_mode not in {"limited", "all"}:
            raise ValueError("comment_mode 只能是 limited 或 all")
        if max_account_search_pages < 1:
            raise ValueError("max_account_search_pages 必须大于 0")
        if max_user_note_pages < 1:
            raise ValueError("max_user_note_pages 必须大于 0")
        if max_account_post_pages is not None and max_account_post_pages < 1:
            raise ValueError("max_account_post_pages 必须大于 0")
        if bool(account_targets) != (start_date is not None and end_date is not None):
            raise ValueError("账号采集必须同时提供 account_targets、start_date 和 end_date")
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date 不能晚于 end_date")
        self.platform = platform
        self.keywords = keywords
        self.search_config = search_config
        self.provider_config = provider_config
        self.run_id = run_id
        self.limits = limits
        self.include_comments = include_comments
        self.include_replies = include_replies
        self.force_refresh = force_refresh
        self.write_to_database = write_to_database
        self.provider_config_id = provider_config_id
        self.account_targets = account_targets
        self.start_date = start_date
        self.end_date = end_date
        self.comment_mode = comment_mode
        self.max_account_search_pages = max_account_search_pages
        self.max_user_note_pages = max_user_note_pages
        self.max_account_post_pages = max_account_post_pages
        self.force_resolve_accounts = force_resolve_accounts
        self.account_feed_config = dict(account_feed_config or {})
        self.account_mode = bool(account_targets)
        self.capability = _CAPABILITIES[platform]
        self.decision_service = CollectionDecisionService()
        self.store = RunOutputStore.create(
            output_root=output_root,
            platform=platform,
            run_id=run_id,
        )
        self.state = DebugState.load(output_root / platform / "state.json")
        self._database: TikHubDebugDatabaseSession | None = None
        self._request_no = 0
        self._requests: list[dict[str, object]] = []
        self._content_failures: list[dict[str, object]] = []
        self._blocks: list[UnifiedDataExcelV1] = []
        self._matched_keywords: dict[str, list[str]] = {}
        self._seen_contents: set[str] = set()
        self._seen_comments: set[tuple[str, str]] = set()
        self._root_comment_count = 0
        self._reply_count = 0
        self._search_stop_reasons: dict[str, str] = {}
        self._account_results: list[dict[str, object]] = []
        self._account_cache: dict[str, dict[str, object]] = {}
        self._partial_content_ids: set[str] = set()
        self._comment_coverage_failures: list[dict[str, object]] = []
        self._comment_count_discrepancies: list[dict[str, object]] = []
        self._account_cache_path = self.store.run_dir.parent.parent / "resolved_accounts.json"
        if self.account_mode and self.platform == "xiaohongshu":
            self._account_cache = _load_resolved_account_cache(self._account_cache_path)

    def run(self) -> TikHubTestRunResult:
        error: Exception | None = None
        try:
            if self.write_to_database:
                if self.provider_config_id is None:
                    raise ValueError("write_to_database=True 时必须显式提供 provider_config_id")
                from aima_ugc.bootstrap.tikhub_test_database import (
                    create_tikhub_debug_database_session,
                )

                self._database = create_tikhub_debug_database_session(
                    platform=self.platform,
                    keywords=self.keywords,
                    run_id=self.run_id,
                    provider_config_id=self.provider_config_id,
                    expected_base_url=self.provider_config.base_url,
                    expected_api_key=self.provider_config.api_key,
                    provider_timeout_seconds=self.provider_config.timeout_seconds,
                    search_config=self.search_config,
                    policy=self._policy(),
                )

            with TikHubHttpTransport(
                base_url=self.provider_config.base_url,
                timeout_seconds=self.provider_config.timeout_seconds,
            ) as transport:
                if self.account_mode:
                    for target in self.account_targets:
                        if self.platform == "douyin":
                            self._run_douyin_account(
                                transport,
                                _as_douyin_account_target(target),
                            )
                        elif self.platform == "kuaishou":
                            self._run_kuaishou_account(
                                transport,
                                _as_kuaishou_account_target(target),
                            )
                        elif self.platform == "weibo":
                            self._run_weibo_account(
                                transport,
                                _as_weibo_account_target(target),
                            )
                        elif self.platform == "bilibili":
                            self._run_bilibili_account(
                                transport,
                                _as_bilibili_account_target(target),
                            )
                        else:
                            self._run_account(
                                transport,
                                _as_xiaohongshu_account_target(target),
                            )
                else:
                    for keyword in self.keywords:
                        if self._content_limit_reached():
                            self._search_stop_reasons[keyword] = (
                                "not_started_content_target_reached"
                            )
                            continue
                        self._run_search(transport, keyword)
        except Exception as exc:
            error = exc
        finally:
            if self._database is not None:
                try:
                    self._database.finish(
                        error=error,
                        stop_reasons=self._search_stop_reasons,
                    )
                except Exception as finish_exc:
                    if error is None:
                        error = finish_exc
                finally:
                    self._database = None
            self.state.save()
            if self.account_mode and self.platform == "xiaohongshu":
                try:
                    _save_resolved_account_cache(self._account_cache_path, self._account_cache)
                except Exception as cache_exc:
                    if error is None:
                        error = cache_exc
            records = self._blocks_with_keywords()
            if self.platform in {"douyin", "kuaishou", "weibo", "bilibili"} and self.account_mode:
                workbook_path = export_comment_labeling_excel(
                    records,
                    self.store.raw_data_dir
                    / f"{self.platform}_comments_for_labeling.xlsx",
                ).output_path
            else:
                workbook_path = export_unified_data_excel(
                    records,
                    self.store.raw_data_dir / f"{self.platform}_raw_data.xlsx",
                    include_analysis=False,
                ).output_path
            run_summary_path = self.store.write_run_summary(self._run_summary(error))

        if error is not None:
            raise error
        return TikHubTestRunResult(
            platform=self.platform,
            run_dir=self.store.run_dir,
            workbook_path=workbook_path,
            run_summary_path=run_summary_path,
            content_count=len(self._blocks),
            root_comment_count=self._root_comment_count,
            reply_count=self._reply_count,
            request_count=self._request_no,
        )

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
            douplus_fallback_active = False
            unique_in_range: set[str] = set()
            page_no = 0
            while (
                self.max_account_post_pages is None
                or page_no < self.max_account_post_pages
            ):
                page_no += 1
                if douplus_fallback_active:
                    call = tikhub_runtime.build_douyin_douplus_user_posts_call(
                        sec_uid=account_value,
                        state=state,
                        count=self._douyin_douplus_post_page_size(),
                    )
                else:
                    call = tikhub_runtime.build_douyin_user_posted_videos_call(
                        account_value=account_value,
                        state=state,
                        config=self.account_feed_config,
                    )
                try:
                    body, raw_record = self._send(transport, call, keyword=target.label)
                except _TikHubHttpStatusError as exc:
                    fallback_enabled = self.account_feed_config.get(
                        "douplus_posts_fallback_enabled",
                        True,
                    )
                    can_fallback = (
                        fallback_enabled is True
                        and not douplus_fallback_active
                        and exc.status_code == 400
                        and exc.operation == "fetch_user_post_videos"
                        and _is_sec_uid(account_value)
                    )
                    if not can_fallback:
                        raise
                    douplus_fallback_active = True
                    state = None
                    result["posts_source"] = "douplus_fallback"
                    call = tikhub_runtime.build_douyin_douplus_user_posts_call(
                        sec_uid=account_value,
                        state=state,
                        count=self._douyin_douplus_post_page_size(),
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
                items = tikhub_runtime.extract_douyin_user_posted_videos(
                    body,
                    config=self.account_feed_config,
                )
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
                        result["identity_mismatches"] = (
                            cast(int, result["identity_mismatches"]) + 1
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

                if douplus_fallback_active:
                    advance = tikhub_runtime.advance_douyin_douplus_user_posts(
                        state=state,
                        body=body,
                    )
                else:
                    advance = tikhub_runtime.advance_douyin_user_posted_videos(
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
            result["stop_reason"] = "max_account_post_pages_reached"
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
            self._search_stop_reasons[account_key] = str(
                result.get("stop_reason") or "completed"
            )
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

        if target.sec_uid and (target.unique_id is not None or _is_sec_uid(target.sec_uid)):
            return target.sec_uid, "configured_sec_uid"

        unique_id = target.unique_id
        if unique_id is None and target.sec_uid and not _is_sec_uid(target.sec_uid):
            # 兼容旧配置：此前入口把用户填写的抖音号或短用户标识误放进了
            # sec_uid 字段。非长格式值统一先按 unique_id 解析，避免请求错误 ID。
            unique_id = target.sec_uid
        if unique_id is None:
            return target.request_value(account_param), None

        profile_call = tikhub_runtime.build_douyin_user_profile_call(
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
        profile = tikhub_runtime.extract_douyin_user_profile(body)
        resolved_sec_uid = _profile_string(profile, "sec_uid", "sec_user_id")
        if resolved_sec_uid is None:
            raise _AccountResolutionError(
                f"抖音账号 {target.label} 的用户资料未返回 sec_uid；"
                f"原始响应：{self.store.relative_path(raw_record.path)}"
            )
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
            page_no = 0
            while (
                self.max_account_post_pages is None
                or page_no < self.max_account_post_pages
            ):
                page_no += 1
                call = tikhub_runtime.build_kuaishou_user_posts_call(
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
                items = tikhub_runtime.extract_kuaishou_user_posts(body)
                page_published_dates: list[date] = []
                page_has_unknown_published_at = False
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
                        page_has_unknown_published_at = True
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if content.published_at is None:
                        page_has_unknown_published_at = True
                    else:
                        page_published_dates.append(
                            content.published_at.astimezone(_BEIJING).date()
                        )
                    if not _kuaishou_content_matches_account(
                        content,
                        resolved_user_id=user_id,
                    ):
                        result["identity_mismatches"] = (
                            cast(int, result["identity_mismatches"]) + 1
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

                if (
                    page_published_dates
                    and not page_has_unknown_published_at
                    and max(page_published_dates) < cast(date, self.start_date)
                ):
                    # 作品接口固定按 latest 倒序。当前整页都早于包含式起始日时，
                    # 后续页只会更早；此处应正常结束，不能继续请求已经越过日期
                    # 边界的旧 pcursor，并让一次 Provider 400 抹掉已采结果。
                    result["stop_reason"] = "account_posts_before_start_date"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(result["stop_reason"])
                    return

                advance = tikhub_runtime.advance_kuaishou_user_posts(
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

            result["stop_reason"] = "max_account_post_pages_reached"
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
            self._search_stop_reasons[target.label] = str(
                result.get("stop_reason") or "completed"
            )
        else:
            self._search_stop_reasons[target.label] = "account_failed"

    def _resolve_kuaishou_account(
        self,
        transport: TikHubHttpTransport,
        *,
        target: KuaishouAccountTarget,
    ) -> tuple[str, str]:
        if target.user_id:
            return target.user_id, "configured_user_id"

        if target.kuaishou_id:
            return self._search_kuaishou_account(
                transport,
                target=target,
                query=target.kuaishou_id,
            )

        reference = target.profile_reference
        profile_call = tikhub_runtime.build_kuaishou_user_profile_call(
            user_reference=reference,
        )
        try:
            body, raw_record = self._send(transport, profile_call, keyword=target.label)
        except _TikHubHttpStatusError as exc:
            if exc.status_code != 400:
                raise
            # 兼容旧配置把“快手号”误填进 eid 的情况；资料接口拒绝后，
            # 改走用户搜索并做精确身份匹配，绝不按模糊首条结果猜账号。
            query = target.eid or target.nickname
            if query is None:
                raise
            return self._search_kuaishou_account(
                transport,
                target=target,
                query=query,
            )
        self._requests[-1].update(
            {
                "account": target.label,
                "account_reference": reference,
                "account_stage": "profile",
            }
        )
        profile = tikhub_runtime.extract_kuaishou_user_profile(body)
        identity = _kuaishou_identity_from_mapping(profile)
        user_id = identity.get("user_id")
        if user_id is None or not user_id.isdigit():
            raise _AccountResolutionError(
                f"快手账号 {target.label} 的用户资料未返回纯数字 userId；"
                f"原始响应：{self.store.relative_path(raw_record.path)}"
            )
        if target.eid and identity.get("eid") not in {None, target.eid}:
            raise _AccountResolutionError(f"快手账号 {target.label} eid 身份不一致")
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
            call = tikhub_runtime.build_kuaishou_user_search_call(
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
            for raw_item in tikhub_runtime.extract_kuaishou_user_search_items(body):
                identity = _kuaishou_identity_from_mapping(raw_item)
                user_id = identity.get("user_id")
                if user_id is None or not user_id.isdigit():
                    continue
                if _kuaishou_account_candidate_matches(target, identity, query=query):
                    matches[user_id] = identity

            advance = tikhub_runtime.advance_kuaishou_user_search(
                state=state,
                body=body,
            )
            if not advance.should_continue:
                break
            state = cast(dict[str, object], advance.next_state)

        if len(matches) != 1:
            if not matches:
                raise _AccountResolutionError(
                    f"快手账号 {target.label} 未找到快手号/昵称精确匹配用户"
                )
            raise _AccountResolutionError(
                f"快手账号 {target.label} 找到多个精确匹配 userId: "
                f"{', '.join(sorted(matches))}"
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
            page_no = 0
            while (
                self.max_account_post_pages is None
                or page_no < self.max_account_post_pages
            ):
                page_no += 1
                call = tikhub_runtime.build_weibo_user_posts_call(
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
                items = tikhub_runtime.extract_weibo_user_posts(body)
                page_published_dates: list[date] = []
                page_has_unknown_published_at = False
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
                        page_has_unknown_published_at = True
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if content.published_at is None:
                        page_has_unknown_published_at = True
                    else:
                        page_published_dates.append(
                            content.published_at.astimezone(_BEIJING).date()
                        )
                    if not _weibo_content_matches_account(content, resolved_uid=uid):
                        result["identity_mismatches"] = (
                            cast(int, result["identity_mismatches"]) + 1
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

                if (
                    page_published_dates
                    and not page_has_unknown_published_at
                    and max(page_published_dates) < cast(date, self.start_date)
                ):
                    # 用户时间线按最新微博向历史方向翻页；整页已早于起始日时，
                    # 后续页不会再包含目标范围内微博，避免无意义请求旧 since_id。
                    result["stop_reason"] = "account_posts_before_start_date"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(result["stop_reason"])
                    return

                advance = tikhub_runtime.advance_weibo_user_posts(state=state, body=body)
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

            result["stop_reason"] = "max_account_post_pages_reached"
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
            self._search_stop_reasons[target.label] = str(
                result.get("stop_reason") or "completed"
            )
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
            page_no = 0
            while self.max_account_post_pages is None or page_no < self.max_account_post_pages:
                page_no += 1
                call = tikhub_runtime.build_bilibili_user_posts_call(uid=uid, state=state)
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
                items = tikhub_runtime.extract_bilibili_user_posts(body)
                page_published_dates: list[date] = []
                page_has_unknown_published_at = False
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
                        page_has_unknown_published_at = True
                        failures = cast(list[dict[str, object]], result["post_failures"])
                        failures.append(
                            {
                                "item_locator": item_locator,
                                "error_type": type(exc).__name__,
                                "error_summary": str(exc),
                            }
                        )
                        continue
                    if content.published_at is None:
                        page_has_unknown_published_at = True
                    else:
                        page_published_dates.append(
                            content.published_at.astimezone(_BEIJING).date()
                        )
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

                if (
                    page_published_dates
                    and not page_has_unknown_published_at
                    and max(page_published_dates) < cast(date, self.start_date)
                ):
                    result["stop_reason"] = "account_posts_before_start_date"
                    result["unique_posts_in_range"] = len(unique_in_range)
                    result["status"] = (
                        "completed_with_errors"
                        if cast(list[dict[str, object]], result["post_failures"])
                        else "completed"
                    )
                    self._account_results.append(result)
                    self._search_stop_reasons[target.label] = str(result["stop_reason"])
                    return

                advance = tikhub_runtime.advance_bilibili_user_posts(state=state, body=body)
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

            result["stop_reason"] = "max_account_post_pages_reached"
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
            self._search_stop_reasons[target.label] = str(
                result.get("stop_reason") or "completed"
            )
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
            call = tikhub_runtime.build_weibo_user_search_call(
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
            candidates = tikhub_runtime.extract_weibo_user_search_items(body)
            for raw_item in candidates:
                identity = _weibo_identity_from_mapping(raw_item)
                uid = identity.get("uid")
                if uid and _weibo_account_candidate_matches(target, identity):
                    matches[uid] = identity
            if not candidates:
                break

        if len(matches) != 1:
            if not matches:
                raise _AccountResolutionError(
                    f"微博账号 {target.label} 未找到精确 UID；请在配置中填写 uid"
                )
            raise _AccountResolutionError(
                f"微博账号 {target.label} 匹配到多个 UID；请在配置中填写 uid"
            )
        return next(iter(matches)), "nickname_search"

    def _run_account(
        self,
        transport: TikHubHttpTransport,
        target: XiaohongshuAccountTarget,
    ) -> None:
        result: dict[str, object] = {
            "nickname": target.nickname,
            "red_id": target.red_id,
            "configured_user_id": target.user_id,
            "status": "failed",
            "resolution_method": None,
            "user_id": None,
            "notes_pages": 0,
            "notes_discovered": 0,
            "notes_in_range": 0,
            "unique_notes_in_range": 0,
            "note_failures": [],
            "stop_reason": None,
            "error_type": None,
            "error_summary": None,
        }
        try:
            resolved, resolution_method = self._resolve_account(transport, target)
            result["user_id"] = resolved["user_id"]
            result["resolution_method"] = resolution_method
            self._run_account_notes(transport, target, resolved, result)
            result["status"] = (
                "completed_with_errors"
                if cast(list[dict[str, object]], result["note_failures"])
                else "completed"
            )
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            result["error_summary"] = str(exc)
        self._account_results.append(result)
        account_key = target.label
        if result["status"] == "completed":
            self._search_stop_reasons[account_key] = str(result.get("stop_reason") or "completed")
        else:
            self._search_stop_reasons[account_key] = "account_failed"

    def _resolve_account(
        self,
        transport: TikHubHttpTransport,
        target: XiaohongshuAccountTarget,
    ) -> tuple[dict[str, str], str]:
        cached = None if self.force_resolve_accounts else self._account_cache.get(target.cache_key)
        candidate: dict[str, str] | None = None
        resolution_method = "configured_user_id"
        if target.user_id:
            candidate = {"user_id": target.user_id}
        elif cached is not None:
            cached_user_id = _optional_config_text(cached.get("user_id"), "cached user_id")
            if cached_user_id:
                candidate = {
                    "user_id": cached_user_id,
                    **_identity_from_mapping(cached),
                }
                resolution_method = "cache"
        if candidate is None:
            candidate, resolution_method = self._search_account_user(transport, target)

        if resolution_method == "cache":
            # The cache is written only after a successful identity search/detail
            # validation. Re-validating it on every run makes collection depend on
            # the provider's user-info endpoint, which can fail independently of
            # the posted-notes endpoint. Set force_resolve_accounts=True when a
            # fresh identity check is explicitly required.
            _validate_account_identity(target, candidate)
            return (
                {
                    key: value
                    for key, value in candidate.items()
                    if key in {"user_id", "red_id", "nickname"} and value
                },
                resolution_method,
            )

        info_call = tikhub_runtime.build_xiaohongshu_user_info_call(
            user_id=candidate["user_id"]
        )
        info_body, info_raw = self._send(transport, info_call, keyword=target.label)
        self._requests[-1].update(
            {
                "account": target.label,
                "account_user_id": candidate["user_id"],
                "account_stage": "identity_validation",
            }
        )
        info = tikhub_runtime.extract_xiaohongshu_user_info(info_body)
        observed = _identity_from_mapping(info)
        candidate_user_id = candidate.get("user_id")
        observed_user_id = observed.get("user_id")
        if (
            candidate_user_id
            and observed_user_id
            and candidate_user_id != observed_user_id
        ):
            raise _AccountResolutionError(
                f"账号 {target.label} 用户搜索与用户详情的 user_id 身份不一致"
            )
        combined = {**candidate, **observed}
        _validate_account_identity(target, combined)
        if not combined.get("user_id"):
            raise _AccountResolutionError("用户信息未返回可用 user_id")
        resolved = {
            key: value
            for key, value in combined.items()
            if key in {"user_id", "red_id", "nickname"} and value
        }
        self._account_cache[target.cache_key] = {
            "nickname": target.nickname,
            "red_id": target.red_id,
            "user_id": resolved["user_id"],
            "resolved_at": info_raw.observed_at.isoformat(),
            "resolution_method": resolution_method,
        }
        return resolved, resolution_method

    def _search_account_user(
        self,
        transport: TikHubHttpTransport,
        target: XiaohongshuAccountTarget,
    ) -> tuple[dict[str, str], str]:
        query = target.red_id or target.nickname
        if query is None:
            raise _AccountResolutionError("账号缺少可用于搜索的 nickname 或 red_id")
        state: dict[str, object] | None = None
        matches: dict[str, dict[str, str]] = {}
        for page_no in range(1, self.max_account_search_pages + 1):
            call = tikhub_runtime.build_xiaohongshu_user_search_call(
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
            for raw_item in tikhub_runtime.extract_xiaohongshu_user_search_items(body):
                identity = _identity_from_mapping(raw_item)
                if not identity.get("user_id"):
                    continue
                if _account_candidate_matches(target, identity):
                    matches[identity["user_id"]] = identity

            advance = tikhub_runtime.advance_xiaohongshu_user_search(
                state=state,
                body=body,
            )
            if not advance.should_continue:
                if matches:
                    break
                raise _AccountResolutionError(
                    f"账号 {target.label} 无法唯一匹配；stop_reason={advance.stop_reason}"
                )
            state = cast(dict[str, object], advance.next_state)
        if len(matches) != 1:
            if not matches:
                raise _AccountResolutionError(f"账号 {target.label} 未找到精确匹配用户")
            raise _AccountResolutionError(
                f"账号 {target.label} 找到多个精确匹配 user_id: {', '.join(sorted(matches))}"
            )
        return next(iter(matches.values())), "search_users"

    def _run_account_notes(
        self,
        transport: TikHubHttpTransport,
        target: XiaohongshuAccountTarget,
        resolved: dict[str, str],
        result: dict[str, object],
    ) -> None:
        user_id = resolved["user_id"]
        state: dict[str, object] | None = None
        unique_in_range: set[str] = set()
        for page_no in range(1, self.max_user_note_pages + 1):
            call = tikhub_runtime.build_xiaohongshu_user_posted_notes_call(
                user_id=user_id,
                state=state,
            )
            body, raw_record = self._send(transport, call, keyword=target.label)
            self._requests[-1].update(
                {
                    "account": target.label,
                    "account_user_id": user_id,
                    "account_page": page_no,
                    "account_stage": "posted_notes",
                }
            )
            result["notes_pages"] = page_no
            items = tikhub_runtime.extract_xiaohongshu_user_posted_notes(body)
            for item_index, raw_item in enumerate(items):
                result["notes_discovered"] = cast(int, result["notes_discovered"]) + 1
                item_locator = f"account_notes.page[{page_no}].items[{item_index}]"
                try:
                    content = tikhub_runtime.map_content(
                        platform="xiaohongshu",
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
                    failures = cast(list[dict[str, object]], result["note_failures"])
                    failures.append(
                        {
                            "item_locator": item_locator,
                            "error_type": type(exc).__name__,
                            "error_summary": str(exc),
                        }
                    )
                    continue
                if not _published_on_inclusive_date_range(
                    content.published_at,
                    start_date=cast(date, self.start_date),
                    end_date=cast(date, self.end_date),
                ):
                    continue
                result["notes_in_range"] = cast(int, result["notes_in_range"]) + 1
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
                    failures = cast(list[dict[str, object]], result["note_failures"])
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
                    result["unique_notes_in_range"] = len(unique_in_range)
                    return

            advance = tikhub_runtime.advance_xiaohongshu_user_posted_notes(
                state=state,
                body=body,
            )
            if not advance.should_continue:
                result["stop_reason"] = advance.stop_reason or "provider_exhausted"
                result["unique_notes_in_range"] = len(unique_in_range)
                return
            state = cast(dict[str, object], advance.next_state)
        result["stop_reason"] = "max_user_note_pages_reached"
        result["unique_notes_in_range"] = len(unique_in_range)

    def _run_search(self, transport: TikHubHttpTransport, keyword: str) -> None:
        pagination: dict[str, object] | None = None
        for page_no in range(1, self.limits.max_search_pages + 1):
            call = tikhub_runtime.build_search_call(
                platform=self.platform,
                keyword=keyword,
                config=self.search_config,
                state=pagination,
            )
            body, raw_record = self._send(transport, call, keyword=keyword)
            self._requests[-1]["keyword"] = keyword
            items = tikhub_runtime.extract_search_items(self.platform, body)
            for item_index, raw_item in enumerate(items):
                item_locator = f"search.page[{page_no}].items[{item_index}]"
                candidate_id = self._discover_candidate(
                    raw_record=raw_record,
                    item_kind="content",
                    item_locator=item_locator,
                )
                try:
                    content = tikhub_runtime.map_content(
                        platform=self.platform,
                        raw=raw_item,
                        context=tikhub_runtime.mapping_context(
                            provider_request_id=raw_record.request_id,
                            provider_attempt_id=raw_record.attempt_id,
                            raw_artifact_id=raw_record.artifact_id,
                            operation=call.operation,
                            source_type="keyword",
                            source_value=keyword,
                            observed_at=raw_record.observed_at,
                        ),
                        item_locator=item_locator,
                    )
                except Exception as exc:
                    self._record_candidate_failure(
                        candidate_id=candidate_id,
                        raw_record=raw_record,
                        error=exc,
                    )
                    raise
                content_id = content.external_content_id
                self._remember_keyword(content_id, keyword)
                is_new = content_id not in self._seen_contents
                if is_new:
                    self._seen_contents.add(content_id)
                    self.store.append_canonical("contents", content)
                self._ingest_content(content, candidate_id=candidate_id)
                if not is_new:
                    continue
                self._process_content(
                    transport,
                    keyword=keyword,
                    search_content=content,
                    search_raw_locator=(
                        f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                    ),
                )
                if self._content_limit_reached():
                    self._search_stop_reasons[keyword] = "content_target_reached"
                    return

            advance = tikhub_runtime.advance_search(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                self._search_stop_reasons[keyword] = advance.stop_reason or "provider_exhausted"
                return
            pagination = cast(dict[str, object], advance.next_state)
        self._search_stop_reasons[keyword] = "max_search_pages_reached"

    def _process_content(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        search_content: CanonicalContentV1,
        search_raw_locator: str,
    ) -> None:
        content_id = search_content.external_content_id
        previous_exists = self.state.has_content(self.platform, content_id)
        previous_count = self.state.previous_comment_count(self.platform, content_id)
        decision = self._decide(
            content=search_content,
            previous_exists=previous_exists,
            previous_count=previous_count,
            after_detail=False,
        )
        decision = self._apply_comment_mode(decision)
        content = search_content
        content_raw_locator = search_raw_locator

        if decision.detail_action == "fetch":
            detail_call = tikhub_runtime.build_detail_call(self.platform, search_content)
            try:
                detail_body, detail_raw = self._send(
                    transport,
                    detail_call,
                    keyword=keyword,
                )
            except _TikHubHttpStatusError as exc:
                can_collect_from_account_item = (
                    self._continue_after_item_http_error
                    or (
                        self.platform == "douyin"
                        and detail_call.operation == "fetch_one_video_v3"
                        and exc.status_code == 400
                    )
                    or self._strict_kuaishou_comment_mode()
                    or self._strict_weibo_comment_mode()
                    or self._strict_bilibili_comment_mode()
                )
                if can_collect_from_account_item:
                    self._content_failures.append(
                        {
                            "external_content_id": content_id,
                            "stage": "detail",
                            "operation": exc.operation,
                            "status_code": exc.status_code,
                            "external_request_id": exc.external_request_id,
                            "raw_file": exc.raw_file,
                        }
                    )
                    fallback_comments: list[UnifiedDataExcelCommentV1] = []
                    fallback_coverage = "unavailable"
                    fallback_decision = self._apply_comment_mode(decision)
                    if fallback_decision.comment_action not in {"skip", "defer_until_detail"}:
                        fallback_comments, fallback_coverage = self._fetch_comments(
                            transport,
                            keyword=keyword,
                            content=search_content,
                            action=fallback_decision.comment_action,
                            target=(
                                None
                                if self.account_mode and self.comment_mode == "all"
                                else fallback_decision.comment_target
                                or self.limits.max_comments_per_content
                            ),
                        )
                    self._blocks.append(
                        UnifiedDataExcelV1(
                            content=project_canonical_content(
                                search_content,
                                coverage=fallback_coverage,
                                raw_locator=search_raw_locator,
                            ),
                            comments=tuple(fallback_comments),
                        )
                    )
                    return
                raise
            detail_items = tikhub_runtime.extract_detail_items(self.platform, detail_body)
            mapped_details: list[tuple[CanonicalContentV1, str]] = []
            for index, detail_item in enumerate(detail_items):
                item_locator = f"detail.items[{index}]"
                candidate_id = self._discover_candidate(
                    raw_record=detail_raw,
                    item_kind="content",
                    item_locator=item_locator,
                )
                try:
                    mapped = tikhub_runtime.map_content(
                        platform=self.platform,
                        raw=detail_item,
                        context=tikhub_runtime.mapping_context(
                            provider_request_id=detail_raw.request_id,
                            provider_attempt_id=detail_raw.attempt_id,
                            raw_artifact_id=detail_raw.artifact_id,
                            operation=detail_call.operation,
                            source_type="content",
                            source_value=content_id,
                            observed_at=detail_raw.observed_at,
                        ),
                        item_locator=item_locator,
                    )
                except Exception as exc:
                    self._record_candidate_failure(
                        candidate_id=candidate_id,
                        raw_record=detail_raw,
                        error=exc,
                    )
                    raise
                self.store.append_canonical("contents", mapped)
                self._ingest_content(mapped, candidate_id=candidate_id)
                mapped_details.append(
                    (
                        mapped,
                        f"{self.store.relative_path(detail_raw.path)}#{item_locator}",
                    )
                )
            matching = next(
                (item for item in mapped_details if item[0].external_content_id == content_id),
                None,
            )
            if matching is None:
                raise RuntimeError(
                    f"TikHub {self.platform} Detail 未返回目标内容 {content_id} 的可映射数据"
                )
            content, content_raw_locator = matching
            decision = self._decide(
                content=content,
                previous_exists=previous_exists,
                previous_count=previous_count,
                after_detail=True,
            )
            decision = self._apply_comment_mode(decision)

        comments: list[UnifiedDataExcelCommentV1] = []
        coverage = self._coverage_for_skipped_comments(
            decision.comment_action, decision.comment_reason
        )
        if decision.comment_action not in {"skip", "defer_until_detail"}:
            comments, coverage = self._fetch_comments(
                transport,
                keyword=keyword,
                content=content,
                action=decision.comment_action,
                target=(
                    None
                    if self.account_mode and self.comment_mode == "all"
                    else decision.comment_target or self.limits.max_comments_per_content
                ),
            )

        self.state.remember_content(
            self.platform,
            content_id,
            comment_count=content.metrics.comment_count,
        )
        self._blocks.append(
            UnifiedDataExcelV1(
                content=project_canonical_content(
                    content,
                    coverage=coverage,
                    raw_locator=content_raw_locator,
                ),
                comments=tuple(comments),
            )
        )

    def _decide(
        self,
        *,
        content: CanonicalContentV1,
        previous_exists: bool,
        previous_count: int | None,
        after_detail: bool,
    ) -> CollectionDecisionV1:
        current_count = content.metrics.comment_count
        previous = PreviousContentStateV1(comment_count=previous_count) if previous_exists else None
        context = CollectionDecisionContextV1(
            scheduled_refresh_checkpoint=(
                self._full_refresh_requested() and not after_detail
            ),
        )
        if after_detail and previous is None:
            # Detail 已执行后，以“已有但评论计数未知”的最小快照进入第二次纯决策，
            # 让 Decision Service 决定 known count 的目标或 unknown count 的首屏 Probe。
            previous = PreviousContentStateV1(comment_count=None)
        return self.decision_service.decide(
            CollectionDecisionRequestV1(
                current=ContentObservationV1(
                    comment_count=current_count,
                    comments_available=None,
                    search_missing_required_fields=(not after_detail and current_count is None),
                    business_changed=(
                        not after_detail and previous_exists and previous_count != current_count
                    ),
                ),
                previous=previous,
                context=context,
                policy=self._policy(),
                capability=self.capability,
            )
        )

    def _apply_comment_mode(self, decision: CollectionDecisionV1) -> CollectionDecisionV1:
        if not self.account_mode or self.comment_mode != "all":
            return decision
        if decision.comment_action == "skip":
            if (
                self._strict_kuaishou_comment_mode()
                and self.include_comments
                and decision.comment_reason == "provider_reported_zero"
            ):
                # 快手全量账号模式会对每条范围内作品同时探测 App/Web；不因作品
                # 列表或详情中的瞬时 0 计数跳过真实评论分页。
                return decision.model_copy(
                    update={
                        "comment_action": "fetch_adaptive",
                        "comment_target": None,
                        "reply_target_per_root": None,
                    }
                )
            # Preserve provider_reported_zero, comments_unavailable and unchanged
            # state decisions; forcing a request here can turn a valid zero-comment
            # post into a spurious extra request and drop the content block.
            return decision
        if not self.include_comments:
            return decision.model_copy(
                update={
                    "comment_action": "skip",
                    "comment_reason": "comments_disabled",
                    "comment_target": None,
                    "reply_target_per_root": None,
                }
            )
        return decision.model_copy(
            update={
                "comment_action": "fetch_adaptive",
                "comment_target": None,
                "reply_target_per_root": None,
            }
        )

    def _policy(self) -> CollectionDecisionPolicyV1:
        return CollectionDecisionPolicyV1(
            comments_enabled=self.include_comments,
            full_fetch_threshold=self.limits.max_comments_per_content,
            sample_target=self.limits.max_comments_per_content,
            reply_target_per_root=self.limits.max_replies_per_root,
            comment_refresh_when_count_unchanged=self._full_refresh_requested(),
        )

    def _full_refresh_requested(self) -> bool:
        # “全部评论”描述的是本次导出，而不是历史增量。即使 state.json 已有
        # 相同作品和评论计数，也必须重新抓详情、一级评论和全部二级回复；否则
        # 新一轮 Excel 只会得到内容块和表头，无法包含历史运行中的评论。
        return self.force_refresh or self._strict_full_comment_mode()

    def _strict_full_comment_mode(self) -> bool:
        return (
            self.platform in {"douyin", "kuaishou", "weibo", "bilibili"}
            and self.account_mode
            and self.comment_mode == "all"
        )

    def _strict_douyin_comment_mode(self) -> bool:
        return self.platform == "douyin" and self.account_mode and self.comment_mode == "all"

    def _strict_kuaishou_comment_mode(self) -> bool:
        return self.platform == "kuaishou" and self.account_mode and self.comment_mode == "all"

    def _strict_weibo_comment_mode(self) -> bool:
        return self.platform == "weibo" and self.account_mode and self.comment_mode == "all"

    def _strict_bilibili_comment_mode(self) -> bool:
        return self.platform == "bilibili" and self.account_mode and self.comment_mode == "all"

    def _douyin_web_page_size(self) -> int:
        value = self.account_feed_config.get("web_comment_page_size", 50)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("web_comment_page_size 必须是正整数")
        if value > 50:
            raise ValueError("web_comment_page_size 不能大于 TikHub 抖音 Web 接口上限 50")
        return value

    def _douyin_douplus_post_page_size(self) -> int:
        value = self.account_feed_config.get("douplus_post_page_size", 10)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("douplus_post_page_size 必须是正整数")
        return value

    def _map_root_comment_items(
        self,
        *,
        content_id: str,
        call: tikhub_runtime.TikHubOperationCall,
        raw_record: RawOutputRecord,
        items: tuple[dict[str, Any], ...],
        page_no: int,
        locator_group: str,
    ) -> tuple[
        list[UnifiedDataExcelCommentV1],
        list[CanonicalCommentV1],
        list[str],
    ]:
        rows: list[UnifiedDataExcelCommentV1] = []
        roots: list[CanonicalCommentV1] = []
        page_comment_ids: list[str] = []
        for item_index, raw_item in enumerate(items):
            item_locator = f"{locator_group}.page[{page_no}].items[{item_index}]"
            candidate_id = self._discover_candidate(
                raw_record=raw_record,
                item_kind="comment",
                item_locator=item_locator,
            )
            try:
                comment = tikhub_runtime.map_comment(
                    platform=self.platform,
                    raw=raw_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=raw_record.request_id,
                        provider_attempt_id=raw_record.attempt_id,
                        raw_artifact_id=raw_record.artifact_id,
                        operation=call.operation,
                        source_type="content",
                        source_value=content_id,
                        observed_at=raw_record.observed_at,
                        external_content_id=content_id,
                    ),
                    item_locator=item_locator,
                    is_root=True,
                )
            except Exception as exc:
                self._record_candidate_failure(
                    candidate_id=candidate_id,
                    raw_record=raw_record,
                    error=exc,
                )
                raise
            page_comment_ids.append(comment.external_comment_id)
            key = (content_id, comment.external_comment_id)
            is_new = key not in self._seen_comments
            if is_new:
                self._seen_comments.add(key)
                self.store.append_canonical("comments", comment)
            self._ingest_comment(comment, candidate_id=candidate_id)
            if not is_new:
                continue
            self.state.remember_comment(
                self.platform,
                content_id,
                comment.external_comment_id,
            )
            locator = f"{self.store.relative_path(raw_record.path)}#{item_locator}"
            rows.append(project_canonical_comment(comment, level="一级", raw_locator=locator))
            roots.append(comment)
            self._root_comment_count += 1
        return rows, roots, page_comment_ids

    def _fetch_comments(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        action: str,
        target: int | None,
    ) -> tuple[list[UnifiedDataExcelCommentV1], str]:
        content_id = content.external_content_id
        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        root_total = 0
        reply_total = 0
        reported_comment_count: int | None = None
        reported_comment_count_l1: int | None = None
        reported_comment_count_requires_fix = False
        provider_exhausted = False
        attempted_cursors: set[int] = {0}
        progressless_pages = 0
        known_comment_ids = (
            self.state.known_comment_ids(self.platform, content_id)
            if action == "fetch_incremental"
            else frozenset()
        )
        page_no = 0
        while (
            self.limits.max_comment_pages_per_content is None
            or page_no < self.limits.max_comment_pages_per_content
        ):
            page_no += 1
            if pagination is not None:
                current_cursor = pagination.get("cursor")
                if isinstance(current_cursor, int) and not isinstance(current_cursor, bool):
                    attempted_cursors.add(current_cursor)
            call = tikhub_runtime.build_comments_call(
                platform=self.platform,
                external_content_id=content_id,
                alternate_ids=content.alternate_ids,
                state=pagination,
            )
            try:
                body, raw_record = self._send(transport, call, keyword=keyword)
            except _TikHubHttpStatusError as exc:
                if self._continue_after_item_http_error:
                    self._record_content_http_failure(
                        content_id=content_id,
                        stage="comments",
                        error=exc,
                    )
                    expected = (
                        str(content.metrics.comment_count)
                        if content.metrics.comment_count is not None
                        else "unknown"
                    )
                    return mapped_rows, f"partial {root_total}/{expected} (http_{exc.status_code})"
                if not self._strict_full_comment_mode():
                    raise
                # 严格全量模式会继续使用 Web 接口补采；同时保留此前已映射的
                # App 评论，不能因为后续某一页失败而丢掉整个作品的数据。
                provider_exhausted = False
                break
            items = tikhub_runtime.extract_comment_items(self.platform, body)
            page_comment_count, page_comment_count_l1 = tikhub_runtime.extract_comment_counts(
                self.platform,
                body,
            )
            if _douyin_comment_total_requires_fix(body):
                reported_comment_count_requires_fix = True
            if items:
                reported_comment_count = _maximum_known_count(
                    reported_comment_count,
                    page_comment_count,
                )
                reported_comment_count_l1 = _maximum_known_count(
                    reported_comment_count_l1,
                    page_comment_count_l1,
                )
            page_rows, mapped_roots, page_comment_ids = self._map_root_comment_items(
                content_id=content_id,
                call=call,
                raw_record=raw_record,
                items=items,
                page_no=page_no,
                locator_group=(
                    "comments.app_v3" if self.platform == "douyin" else "comments.app"
                ),
            )
            mapped_rows.extend(page_rows)
            root_total += len(mapped_roots)
            if mapped_roots:
                progressless_pages = 0
            else:
                progressless_pages += 1

            if self.include_replies:
                for root in mapped_roots:
                    reply_rows = self._fetch_replies(
                        transport,
                        keyword=keyword,
                        content=content,
                        root=root,
                    )
                    mapped_rows.extend(reply_rows)
                    reply_total += len(reply_rows)

            advance = tikhub_runtime.advance_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            if not advance.should_continue:
                stalled = self._strict_douyin_comment_mode() and progressless_pages >= 2
                resume_state = None
                if self.platform == "douyin" and not stalled:
                    resume_state = _resume_douyin_comment_state(
                        advance,
                        observed_count=root_total + reply_total,
                        expected_count=(
                            expected_comment_count
                            if self._strict_douyin_comment_mode()
                            else reported_comment_count or content.metrics.comment_count
                        ),
                        attempted_cursors=attempted_cursors,
                    )
                if resume_state is not None:
                    pagination = resume_state
                    provider_exhausted = False
                    continue
                provider_exhausted = not stalled
                break
            if self._strict_douyin_comment_mode() and progressless_pages >= 2:
                provider_exhausted = False
                break
            if action == "fetch_incremental" and known_comment_boundary_reached(
                page_comment_ids, known_comment_ids
            ):
                expected = (
                    str(content.metrics.comment_count)
                    if content.metrics.comment_count is not None
                    else "unknown"
                )
                return mapped_rows, f"partial {root_total}/{expected} (known_comment_reached)"
            if target is not None and root_total >= target:
                break
            pagination = cast(dict[str, object], advance.next_state)

        if self._strict_kuaishou_comment_mode():
            (
                web_rows,
                web_root_total,
                web_reply_total,
                web_reported_comment_count,
                web_exhausted,
            ) = self._fetch_kuaishou_web_comments(
                transport,
                keyword=keyword,
                content=content,
            )
            mapped_rows.extend(web_rows)
            root_total += web_root_total
            reply_total += web_reply_total
            reported_comment_count = _maximum_known_count(
                reported_comment_count,
                web_reported_comment_count,
            )
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            sources_exhausted = provider_exhausted and web_exhausted
            observed_comment_count = root_total + reply_total
            comments_complete = (
                observed_comment_count >= expected_comment_count
                if expected_comment_count is not None
                else sources_exhausted
            )
            if not comments_complete:
                self._partial_content_ids.add(content_id)
                self._comment_coverage_failures.append(
                    {
                        "content_id": content_id,
                        "kind": "comments",
                        "expected": expected_comment_count,
                        "collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "sources": ["app", "web"],
                        "app_exhausted": provider_exhausted,
                        "web_exhausted": web_exhausted,
                    }
                )
            status = "complete" if content_id not in self._partial_content_ids else "partial"
            expected_text = (
                str(expected_comment_count)
                if expected_comment_count is not None
                else "unknown"
            )
            return (
                mapped_rows,
                f"{status} {observed_comment_count}/{expected_text} "
                f"(一级 {root_total}，二级 {reply_total}，App/Web 已合并)",
            )

        if self._strict_douyin_comment_mode():
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            if not provider_exhausted or (
                expected_comment_count is not None
                and root_total + reply_total < expected_comment_count
            ):
                (
                    web_rows,
                    web_root_total,
                    web_reply_total,
                    web_reported_comment_count,
                    web_exhausted,
                    web_reported_count_requires_fix,
                ) = self._fetch_douyin_web_comments(
                    transport,
                    keyword=keyword,
                    content=content,
                    already_collected=root_total + reply_total,
                    expected_count=expected_comment_count,
                )
                mapped_rows.extend(web_rows)
                root_total += web_root_total
                reply_total += web_reply_total
                reported_comment_count = _maximum_known_count(
                    reported_comment_count,
                    web_reported_comment_count,
                )
                reported_comment_count_requires_fix = (
                    reported_comment_count_requires_fix
                    or web_reported_count_requires_fix
                )
                if web_exhausted and web_reported_comment_count is not None:
                    # 详情/App 计数会短暂保留已删除或审核不可见评论。Web 已完整
                    # 结束时，它的 total 是当前可访问评论快照的最终计数。
                    expected_comment_count = web_reported_comment_count
                else:
                    expected_comment_count = _maximum_known_count(
                        content.metrics.comment_count,
                        reported_comment_count,
                    )
                provider_exhausted = provider_exhausted and web_exhausted

            observed_comment_count = root_total + reply_total
            comments_complete = (
                observed_comment_count >= expected_comment_count
                if expected_comment_count is not None
                else provider_exhausted
            )
            provider_count_discrepancy = (
                not comments_complete
                and provider_exhausted
                and expected_comment_count is not None
                and reported_comment_count_requires_fix
            )
            if provider_count_discrepancy:
                # 抖音 App 会用 need_fix_total=true 明确标记 total 不可靠。
                # App、Web 与重叠窗口都已耗尽且每个根评论的回复数均已对齐时，
                # 少于该陈旧 total 的差额不应被误报为采集器失败。
                self._comment_count_discrepancies.append(
                    {
                        "content_id": content_id,
                        "reported_total": expected_comment_count,
                        "accessible_collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "reason": "provider_total_marked_need_fix",
                        "sources_exhausted": ["app_v3", "web", "web_overlap"],
                    }
                )
                comments_complete = True
            if not comments_complete:
                self._partial_content_ids.add(content_id)
                self._comment_coverage_failures.append(
                    {
                        "content_id": content_id,
                        "kind": "comments",
                        "expected": expected_comment_count,
                        "collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "sources": ["app_v3", "web"],
                    }
                )
            status = "complete" if content_id not in self._partial_content_ids else "partial"
            expected_text = (
                str(expected_comment_count) if expected_comment_count is not None else "unknown"
            )
            return (
                mapped_rows,
                f"{status} {observed_comment_count}/{expected_text} "
                f"(一级 {root_total}，二级 {reply_total}"
                f"{'，Provider 总数标记需修正' if provider_count_discrepancy else ''})",
            )

        if self._strict_bilibili_comment_mode():
            observed_comment_count = root_total + reply_total
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            comments_complete = (
                observed_comment_count >= expected_comment_count
                if expected_comment_count is not None
                else provider_exhausted
            )
            if (
                not comments_complete
                and provider_exhausted
                and expected_comment_count is not None
            ):
                # B站详情的 stat.reply 会包含删除、审核或权限不可见的评论；当
                # 当前评论接口明确 is_end=true 时，已无合法游标可继续请求。保留
                # 差额审计，但将“接口可访问的全部评论”视为完整采集。
                self._comment_count_discrepancies.append(
                    {
                        "content_id": content_id,
                        "reported_total": expected_comment_count,
                        "accessible_collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "reason": "provider_reported_total_exceeds_accessible_completed_pagination",
                        "sources_exhausted": ["app"],
                    }
                )
                comments_complete = True
            if not comments_complete:
                self._partial_content_ids.add(content_id)
                self._comment_coverage_failures.append(
                    {
                        "content_id": content_id,
                        "kind": "comments",
                        "expected": expected_comment_count,
                        "collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "sources": ["app"],
                        "app_exhausted": provider_exhausted,
                    }
                )
            status = "complete" if comments_complete else "partial"
            expected_text = (
                str(expected_comment_count) if expected_comment_count is not None else "unknown"
            )
            return (
                mapped_rows,
                f"{status} {observed_comment_count}/{expected_text} "
                f"(一级 {root_total}，二级 {reply_total}，App 已分页结束)",
            )

        observed = root_total + reply_total
        provider_count = (
            reported_comment_count
            if reported_comment_count is not None
            else content.metrics.comment_count
        )
        provider_root_count = reported_comment_count_l1
        if provider_exhausted and provider_count is not None and observed >= provider_count:
            root_coverage = (
                f"一级 {root_total}/{provider_root_count}"
                if provider_root_count is not None
                else f"一级 {root_total}/unknown"
            )
            return mapped_rows, f"complete {observed}/{provider_count} ({root_coverage})"
        if provider_exhausted and provider_count is None:
            root_coverage = (
                f"一级 {root_total}/{provider_root_count}"
                if provider_root_count is not None
                else f"一级 {root_total}/unknown"
            )
            return mapped_rows, f"complete {observed}/unknown ({root_coverage})"
        expected = str(provider_count) if provider_count is not None else "unknown"
        root_expected = (
            str(provider_root_count) if provider_root_count is not None else "unknown"
        )
        return mapped_rows, f"partial {observed}/{expected} (一级 {root_total}/{root_expected})"

    def _fetch_kuaishou_web_comments(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
    ) -> tuple[list[UnifiedDataExcelCommentV1], int, int, int | None, bool]:
        """遍历快手 Web 一级评论，并与 App 结果按稳定评论 ID 合并。"""

        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        root_total = 0
        reply_total = 0
        reported_comment_count: int | None = None
        provider_exhausted = False
        page_no = 0
        while (
            self.limits.max_comment_pages_per_content is None
            or page_no < self.limits.max_comment_pages_per_content
        ):
            page_no += 1
            call = tikhub_runtime.build_kuaishou_web_comments_call(
                external_content_id=content.external_content_id,
                alternate_ids=content.alternate_ids,
                state=pagination,
            )
            try:
                body, raw_record = self._send(transport, call, keyword=keyword)
            except _TikHubHttpStatusError:
                return (
                    mapped_rows,
                    root_total,
                    reply_total,
                    reported_comment_count,
                    False,
                )
            items = tikhub_runtime.extract_comment_items("kuaishou", body)
            page_reported_count, _ = tikhub_runtime.extract_comment_counts(
                "kuaishou",
                body,
            )
            if items:
                reported_comment_count = _maximum_known_count(
                    reported_comment_count,
                    page_reported_count,
                )
            page_rows, mapped_roots, _ = self._map_root_comment_items(
                content_id=content.external_content_id,
                call=call,
                raw_record=raw_record,
                items=items,
                page_no=page_no,
                locator_group="comments.web",
            )
            mapped_rows.extend(page_rows)
            root_total += len(mapped_roots)
            if self.include_replies:
                for root in mapped_roots:
                    reply_rows = self._fetch_replies(
                        transport,
                        keyword=keyword,
                        content=content,
                        root=root,
                    )
                    mapped_rows.extend(reply_rows)
                    reply_total += len(reply_rows)

            advance = tikhub_runtime.advance_comments(
                platform="kuaishou",
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                provider_exhausted = True
                break
            pagination = cast(dict[str, object], advance.next_state)
        return (
            mapped_rows,
            root_total,
            reply_total,
            reported_comment_count,
            provider_exhausted,
        )

    def _fetch_douyin_web_comments(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        already_collected: int,
        expected_count: int | None,
    ) -> tuple[list[UnifiedDataExcelCommentV1], int, int, int | None, bool, bool]:
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        root_total = 0
        reply_total = 0
        reported_comment_count: int | None = None
        reported_comment_count_requires_fix = False
        provider_exhausted = False
        progressless_pages = 0
        page_no = 0
        page_size = self._douyin_web_page_size()
        attempted_cursors: set[int] = set()

        def collect_page(cursor: int) -> tuple[dict[str, Any], int]:
            nonlocal page_no, reported_comment_count
            nonlocal reported_comment_count_requires_fix, root_total, reply_total
            page_no += 1
            call = tikhub_runtime.build_douyin_web_comments_call(
                external_content_id=content.external_content_id,
                state={"cursor": cursor},
                count=page_size,
            )
            body, raw_record = self._send(transport, call, keyword=keyword)
            items = tikhub_runtime.extract_comment_items("douyin", body)
            page_comment_count, _ = tikhub_runtime.extract_comment_counts("douyin", body)
            if _douyin_comment_total_requires_fix(body):
                reported_comment_count_requires_fix = True
            if items:
                reported_comment_count = _maximum_known_count(
                    reported_comment_count,
                    page_comment_count,
                )
            page_rows, mapped_roots, _ = self._map_root_comment_items(
                content_id=content.external_content_id,
                call=call,
                raw_record=raw_record,
                items=items,
                page_no=page_no,
                locator_group="comments.web_fallback",
            )
            mapped_rows.extend(page_rows)
            root_total += len(mapped_roots)
            if self.include_replies:
                for root in mapped_roots:
                    reply_rows = self._fetch_replies(
                        transport,
                        keyword=keyword,
                        content=content,
                        root=root,
                    )
                    mapped_rows.extend(reply_rows)
                    reply_total += len(reply_rows)
            return body, len(mapped_roots)

        current_cursor = 0
        while (
            self.limits.max_comment_pages_per_content is None
            or page_no < self.limits.max_comment_pages_per_content
        ):
            attempted_cursors.add(current_cursor)
            try:
                body, new_root_count = collect_page(current_cursor)
            except _TikHubHttpStatusError:
                # Raw 已由 _send_once 落盘。返回当前累计结果并标记未耗尽，
                # 让上层导出 partial，而不是丢弃该作品已经采到的评论。
                provider_exhausted = False
                break
            if new_root_count:
                progressless_pages = 0
            else:
                progressless_pages += 1
            advance = tikhub_runtime.advance_comments(
                platform="douyin",
                state={"cursor": current_cursor},
                body=body,
            )
            if not advance.should_continue:
                provider_exhausted = True
                break
            if progressless_pages >= 2:
                provider_exhausted = False
                break
            next_state = cast(dict[str, object], advance.next_state)
            next_cursor = next_state.get("cursor")
            if (
                isinstance(next_cursor, bool)
                or not isinstance(next_cursor, int)
                or next_cursor in attempted_cursors
            ):
                provider_exhausted = False
                break
            current_cursor = next_cursor

        observed_count = already_collected + root_total + reply_total
        if (
            provider_exhausted
            and expected_count is not None
            and observed_count < expected_count
        ):
            # Web 接口的评论顺序并不稳定，页边界会重复旧评论。正常分页结束后
            # 以半页步长补查重叠窗口，并继续按评论 ID 去重，填补被边界跳过的项。
            overlap_step = max(page_size // 2, 1)
            horizon = max(expected_count, reported_comment_count or 0)
            for cursor in range(overlap_step, horizon + 1, overlap_step):
                if cursor in attempted_cursors:
                    continue
                if (
                    self.limits.max_comment_pages_per_content is not None
                    and page_no >= self.limits.max_comment_pages_per_content
                ):
                    provider_exhausted = False
                    break
                attempted_cursors.add(cursor)
                try:
                    collect_page(cursor)
                except _TikHubHttpStatusError:
                    provider_exhausted = False
                    break
                observed_count = already_collected + root_total + reply_total
                if observed_count >= expected_count:
                    break
        return (
            mapped_rows,
            root_total,
            reply_total,
            reported_comment_count,
            provider_exhausted,
            reported_comment_count_requires_fix,
        )

    def _fetch_replies(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
        fetch_all: bool = False,
    ) -> list[UnifiedDataExcelCommentV1]:
        strict_douyin = self._strict_douyin_comment_mode()
        strict_kuaishou = self._strict_kuaishou_comment_mode()
        strict_weibo = self._strict_weibo_comment_mode()
        strict_bilibili = self._strict_bilibili_comment_mode()
        strict_full = strict_douyin or strict_kuaishou or strict_weibo or strict_bilibili
        full_fetch_requested = strict_full or fetch_all
        if full_fetch_requested:
            if not self.include_replies or not self.capability.operation("sub_comments"):
                return []
            if root.metrics.reply_count == 0:
                return []
            target: int | None = None
        else:
            reply_decision = self.decision_service.decide_reply(
                ReplyDecisionRequestV1(
                    reply_count=root.metrics.reply_count,
                    policy=self._policy(),
                    capability=self.capability,
                )
            )
            if reply_decision.action == "skip":
                return []
            target = reply_decision.target or self.limits.max_replies_per_root

        app_rows, app_count, app_reported, app_exhausted = self._fetch_reply_pages(
            transport,
            keyword=keyword,
            content=content,
            root=root,
            target=target,
            use_web=False,
            already_collected=0,
        )
        mapped_rows = list(app_rows)
        mapped_count = app_count
        expected_replies = _maximum_known_count(root.metrics.reply_count, app_reported)
        provider_exhausted = app_exhausted

        should_fetch_web = strict_kuaishou or (
            strict_douyin
            and (
                not app_exhausted
                or (expected_replies is not None and mapped_count < expected_replies)
            )
        )
        if should_fetch_web:
            web_rows, web_count, web_reported, web_exhausted = self._fetch_reply_pages(
                transport,
                keyword=keyword,
                content=content,
                root=root,
                target=None,
                use_web=True,
                already_collected=mapped_count,
            )
            mapped_rows.extend(web_rows)
            mapped_count += web_count
            expected_replies = _maximum_known_count(expected_replies, web_reported)
            provider_exhausted = app_exhausted and web_exhausted

        replies_complete = (
            mapped_count >= expected_replies
            if expected_replies is not None
            else provider_exhausted
        )
        if strict_full and not replies_complete:
            self._partial_content_ids.add(content.external_content_id)
            self._comment_coverage_failures.append(
                {
                    "content_id": content.external_content_id,
                    "kind": "replies",
                    "root_comment_id": root.external_comment_id,
                    "expected": expected_replies,
                    "collected": mapped_count,
                    "sources": (
                        ["app_v3", "web"]
                        if strict_douyin
                        else ["app", "web"]
                        if strict_kuaishou
                        else ["app"]
                    ),
                    "app_exhausted": app_exhausted,
                    "web_exhausted": (
                        web_exhausted if should_fetch_web else None
                    ),
                }
            )
        return mapped_rows

    def _fetch_reply_pages(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
        target: int | None,
        use_web: bool,
        already_collected: int,
    ) -> tuple[list[UnifiedDataExcelCommentV1], int, int | None, bool]:
        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        mapped_count = 0
        reported_count: int | None = None
        provider_exhausted = False
        attempted_cursors: set[int] = {0}
        progressless_pages = 0
        page_no = 0
        while (
            self.limits.max_reply_pages_per_root is None
            or page_no < self.limits.max_reply_pages_per_root
        ):
            page_no += 1
            if pagination is not None:
                current_cursor = pagination.get("cursor")
                if isinstance(current_cursor, int) and not isinstance(current_cursor, bool):
                    attempted_cursors.add(current_cursor)
            if use_web:
                if self.platform == "kuaishou":
                    call = tikhub_runtime.build_kuaishou_web_sub_comments_call(
                        external_content_id=content.external_content_id,
                        root_comment_id=root.external_comment_id,
                        alternate_ids=content.alternate_ids,
                        state=pagination,
                    )
                    locator_group = "replies.web"
                else:
                    call = tikhub_runtime.build_douyin_web_sub_comments_call(
                        external_content_id=content.external_content_id,
                        root_comment_id=root.external_comment_id,
                        state=pagination,
                        count=self._douyin_web_page_size(),
                    )
                    locator_group = "replies.web_fallback"
            else:
                call = tikhub_runtime.build_sub_comments_call(
                    platform=self.platform,
                    external_content_id=content.external_content_id,
                    root_comment_id=root.external_comment_id,
                    alternate_ids=content.alternate_ids,
                    state=pagination,
                )
                locator_group = (
                    "replies.app_v3" if self.platform == "douyin" else "replies.app"
                )
            try:
                body, raw_record = self._send(transport, call, keyword=keyword)
            except _TikHubHttpStatusError as exc:
                if self._continue_after_item_http_error:
                    self._record_content_http_failure(
                        content_id=content.external_content_id,
                        stage="replies",
                        error=exc,
                    )
                    return mapped_rows, mapped_count, reported_count, False
                if not self._strict_full_comment_mode():
                    raise
                # 与一级评论相同：保留此前已采回复，并允许 App 失败后转 Web。
                return mapped_rows, mapped_count, reported_count, False
            items = tikhub_runtime.extract_sub_comment_items(self.platform, body)
            if self.platform in {"douyin", "kuaishou"} and items:
                page_reported_count, _ = tikhub_runtime.extract_comment_counts(
                    self.platform,
                    body,
                )
                reported_count = _maximum_known_count(reported_count, page_reported_count)
            page_new_count = 0
            for item_index, raw_item in enumerate(items):
                item_locator = f"{locator_group}.page[{page_no}].items[{item_index}]"
                candidate_id = self._discover_candidate(
                    raw_record=raw_record,
                    item_kind="comment",
                    item_locator=item_locator,
                )
                try:
                    comment = tikhub_runtime.map_comment(
                        platform=self.platform,
                        raw=raw_item,
                        context=tikhub_runtime.mapping_context(
                            provider_request_id=raw_record.request_id,
                            provider_attempt_id=raw_record.attempt_id,
                            raw_artifact_id=raw_record.artifact_id,
                            operation=call.operation,
                            source_type="comment",
                            source_value=root.external_comment_id,
                            observed_at=raw_record.observed_at,
                            external_content_id=content.external_content_id,
                            root_comment_id=root.external_comment_id,
                        ),
                        item_locator=item_locator,
                        is_root=False,
                    )
                except Exception as exc:
                    self._record_candidate_failure(
                        candidate_id=candidate_id,
                        raw_record=raw_record,
                        error=exc,
                    )
                    raise
                key = (content.external_content_id, comment.external_comment_id)
                is_new = key not in self._seen_comments
                if is_new:
                    self._seen_comments.add(key)
                    self.store.append_canonical("comments", comment)
                self._ingest_comment(comment, candidate_id=candidate_id)
                if not is_new:
                    continue
                self.state.remember_comment(
                    self.platform,
                    content.external_content_id,
                    comment.external_comment_id,
                )
                locator = f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                mapped_rows.append(
                    project_canonical_comment(comment, level="二级", raw_locator=locator)
                )
                mapped_count += 1
                page_new_count += 1
                self._reply_count += 1
            if page_new_count:
                progressless_pages = 0
            else:
                progressless_pages += 1

            advance = tikhub_runtime.advance_sub_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                resume_state = None
                stalled = self.platform == "douyin" and progressless_pages >= 2
                if self.platform == "douyin" and not use_web and not stalled:
                    resume_state = _resume_douyin_comment_state(
                        advance,
                        observed_count=already_collected + mapped_count,
                        expected_count=_maximum_known_count(
                            root.metrics.reply_count,
                            reported_count,
                        ),
                        attempted_cursors=attempted_cursors,
                    )
                if resume_state is not None:
                    pagination = resume_state
                    provider_exhausted = False
                    continue
                provider_exhausted = not stalled
                break
            if self.platform == "douyin" and progressless_pages >= 2:
                provider_exhausted = False
                break
            if target is not None and mapped_count >= target:
                break
            pagination = cast(dict[str, object], advance.next_state)
        return mapped_rows, mapped_count, reported_count, provider_exhausted

    def _send(
        self,
        transport: TikHubHttpTransport,
        call: tikhub_runtime.TikHubOperationCall,
        *,
        keyword: str,
    ) -> tuple[dict[str, Any], RawOutputRecord]:
        """对 TikHub 明确声明“不扣费、请重试”的失败做有限退避重试。"""
        delays = (0.0, 1.0, 3.0)
        for attempt_no, delay in enumerate(delays):
            if delay:
                time.sleep(delay)
            try:
                return self._send_once(
                    transport,
                    call,
                    keyword=keyword,
                )
            except _TikHubHttpStatusError as exc:
                if (
                    not exc.retryable
                    or not (
                        call.platform == "xiaohongshu"
                        or (
                            call.platform == "kuaishou"
                            and self._strict_kuaishou_comment_mode()
                        )
                        or (
                            call.platform == "weibo"
                            and self._strict_weibo_comment_mode()
                        )
                        or (
                            call.platform == "bilibili"
                            and self._strict_bilibili_comment_mode()
                        )
                        or (
                            call.platform == "douyin"
                            and (
                                call.operation == "fetch_user_post_videos"
                                or self._strict_douyin_comment_mode()
                            )
                        )
                    )
                    or attempt_no == len(delays) - 1
                ):
                    raise
        raise AssertionError("TikHub 重试循环意外退出")

    def _send_once(
        self,
        transport: TikHubHttpTransport,
        call: tikhub_runtime.TikHubOperationCall,
        *,
        keyword: str,
    ) -> tuple[dict[str, Any], RawOutputRecord]:
        self._request_no += 1
        if self._database is None:
            response = transport.send(call.transport_request(self.provider_config.api_key))
            raw_record = self.store.save_raw(
                operation=call.operation,
                body=response.body,
                request_no=self._request_no,
                status_code=response.status_code,
                external_request_id=response.external_request_id,
            )
        else:
            mirrored_record: RawOutputRecord | None = None

            def mirror_response(response: object) -> None:
                nonlocal mirrored_record
                status_code = getattr(response, "status_code", None)
                external_request_id = getattr(response, "external_request_id", None)
                body = getattr(response, "body", None)
                mirrored_record = self.store.save_raw(
                    operation=call.operation,
                    body=body,
                    request_no=self._request_no,
                    status_code=status_code if isinstance(status_code, int) else None,
                    external_request_id=(
                        external_request_id if isinstance(external_request_id, str) else None
                    ),
                )

            dispatch = self._database.dispatch(
                keyword=keyword,
                call=call,
                transport=transport,
                mirror_response=mirror_response,
            )
            response = dispatch.response
            if mirrored_record is None:
                raise RuntimeError("TikHub 数据库模式没有生成本地 Raw 镜像")
            raw_record = RawOutputRecord(
                artifact_id=dispatch.raw_artifact_id,
                request_id=str(dispatch.provider_request_id),
                attempt_id=str(dispatch.provider_attempt_id),
                operation=call.operation,
                request_no=self._request_no,
                path=mirrored_record.path,
                observed_at=dispatch.observed_at,
                status_code=response.status_code,
                external_request_id=response.external_request_id,
            )

        raw_file = self.store.relative_path(raw_record.path)
        self._requests.append(
            {
                "request_no": self._request_no,
                "business_operation": call.business_operation,
                "operation": call.operation,
                "method": call.method,
                "path": call.path,
                "status_code": response.status_code,
                "external_request_id": response.external_request_id,
                "raw_file": raw_file,
            }
        )
        status_code = response.status_code
        if status_code is not None and status_code >= 400:
            message = f"TikHub {self.platform} {call.operation} 返回 HTTP {status_code}"
            retryable = _tikhub_response_requests_retry(response.body)
            raise _TikHubHttpStatusError(
                message,
                status_code=status_code,
                operation=call.operation,
                external_request_id=response.external_request_id,
                raw_file=raw_file,
                retryable=retryable,
            )
        if not isinstance(response.body, dict):
            raise RuntimeError(f"TikHub {self.platform} {call.operation} 返回 JSON 顶层不是对象")
        return cast(dict[str, Any], response.body), raw_record

    def _record_content_http_failure(
        self,
        *,
        content_id: str,
        stage: Literal["detail", "comments", "replies"],
        error: _TikHubHttpStatusError,
    ) -> None:
        """记录已落盘的内容级 HTTP 失败，供容错运行保留安全诊断信息。"""
        self._content_failures.append(
            {
                "external_content_id": content_id,
                "stage": stage,
                "operation": error.operation,
                "status_code": error.status_code,
                "external_request_id": error.external_request_id,
                "raw_file": error.raw_file,
            }
        )

    def _discover_candidate(
        self,
        *,
        raw_record: RawOutputRecord,
        item_kind: Literal["content", "comment"],
        item_locator: str,
    ) -> UUID | None:
        if self._database is None:
            return None
        try:
            attempt_id = UUID(raw_record.attempt_id)
        except ValueError as exc:
            raise RuntimeError("TikHub 数据库模式 Attempt ID 不是 UUID") from exc
        return self._database.discover_candidate(
            provider_attempt_id=attempt_id,
            raw_artifact_id=raw_record.artifact_id,
            item_kind=item_kind,
            item_locator=item_locator,
            discovered_at=raw_record.observed_at,
        )

    def _record_candidate_failure(
        self,
        *,
        candidate_id: UUID | None,
        raw_record: RawOutputRecord,
        error: Exception,
    ) -> None:
        if self._database is None or candidate_id is None:
            return
        try:
            attempt_id = UUID(raw_record.attempt_id)
        except ValueError as exc:
            raise RuntimeError("TikHub 数据库模式 Attempt ID 不是 UUID") from exc
        self._database.record_candidate_failure(
            candidate_id=candidate_id,
            provider_attempt_id=attempt_id,
            error_code=type(error).__name__,
        )

    def _ingest_content(
        self,
        content: CanonicalContentV1,
        *,
        candidate_id: UUID | None,
    ) -> None:
        if self._database is None:
            return
        if candidate_id is None:
            raise RuntimeError("TikHub 数据库模式 Content 缺少 Candidate")
        self._database.ingest_content(content, candidate_id=candidate_id)

    def _ingest_comment(
        self,
        comment: CanonicalCommentV1,
        *,
        candidate_id: UUID | None,
    ) -> None:
        if self._database is None:
            return
        if candidate_id is None:
            raise RuntimeError("TikHub 数据库模式 Comment 缺少 Candidate")
        self._database.ingest_comment(comment, candidate_id=candidate_id)

    def _remember_keyword(self, content_id: str, keyword: str) -> None:
        matched = self._matched_keywords.setdefault(content_id, [])
        if keyword not in matched:
            matched.append(keyword)

    def _blocks_with_keywords(self) -> tuple[UnifiedDataExcelV1, ...]:
        return tuple(
            block.model_copy(
                update={
                    "content": block.content.model_copy(
                        update={
                            "matched_keywords": tuple(
                                self._matched_keywords.get(
                                    block.content.external_content_id,
                                    (),
                                )
                            )
                        }
                    )
                }
            )
            for block in self._blocks
        )

    def _content_limit_reached(self) -> bool:
        return (
            self.limits.max_contents is not None and len(self._blocks) >= self.limits.max_contents
        )

    def _coverage_for_skipped_comments(self, action: str, reason: str) -> str:
        if not self.include_comments or reason == "comments_disabled":
            return "not_requested"
        if reason in {"comments_operation_unavailable", "comments_unavailable"}:
            return "unavailable"
        if reason == "provider_reported_zero":
            return "complete 0/0"
        if action == "skip":
            return f"not_requested ({reason})"
        return f"partial 0/unknown ({reason})"

    def _run_summary(self, error: Exception | None) -> dict[str, object]:
        status = "failed" if error is not None else "completed"
        if error is None and self._content_failures:
            status = "completed_with_errors"
        account_failures = sum(
            result.get("status") != "completed" for result in self._account_results
        )
        if error is None and self.account_mode and account_failures:
            status = (
                "partial_success"
                if account_failures < len(self._account_results)
                else "failed"
            )
        if error is None and self._partial_content_ids and status != "failed":
            status = "partial_success"
        return {
            "schema_version": "tikhub-test-run.v1",
            "operations": self.platform,
            "mode": (
                f"{self.platform}_accounts"
                if self.account_mode
                else "keyword_search"
            ),
            "keyword": self.keywords[0] if len(self.keywords) == 1 else None,
            "keywords": list(self.keywords),
            "matched_keywords": self._matched_keywords,
            "write_to_database": self.write_to_database,
            "provider_config_id": (
                str(self.provider_config_id) if self.provider_config_id is not None else None
            ),
            "status": status,
            "request_count": self._request_no,
            "content_count": len(self._blocks),
            "root_comment_count": self._root_comment_count,
            "reply_count": self._reply_count,
            "search_stop_reasons": self._search_stop_reasons,
            "requests": self._requests,
            "content_failures": self._content_failures,
            "comment_coverage_failures": self._comment_coverage_failures,
            "comment_count_discrepancies": self._comment_count_discrepancies,
            "partial_content_count": len(self._partial_content_ids),
            "comment_mode": self.comment_mode,
            "account_date_range": (
                {
                    "start": self.start_date.isoformat(),
                    "end": self.end_date.isoformat(),
                    "timezone": "Asia/Shanghai",
                    "inclusive": True,
                }
                if self.account_mode and self.start_date is not None and self.end_date is not None
                else None
            ),
            "accounts_total": len(self._account_results) if self.account_mode else None,
            "accounts_success": (
                sum(result.get("status") == "completed" for result in self._account_results)
                if self.account_mode
                else None
            ),
            "accounts_failed": account_failures if self.account_mode else None,
            "accounts": self._account_results if self.account_mode else [],
            "error_type": type(error).__name__ if error is not None else None,
            "error_summary": str(error) if error is not None else None,
        }


def run_platform(
    *,
    platform: tikhub_runtime.TikHubPlatform,
    keyword: str | None = None,
    keywords: str | Sequence[str] | None = None,
    search_config: dict[str, object] | None = None,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_search_pages: int = 20,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    force_refresh: bool = False,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """执行一个平台的人工调试；数据库写入必须显式 opt-in。"""
    normalized_keywords = _normalize_keywords(keyword=keyword, keywords=keywords)
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    actual_search_config = search_config or {}
    return _TikHubDebugRunner(
        platform=platform,
        keywords=normalized_keywords,
        search_config=actual_search_config,
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
        limits=_RunLimits(
            max_search_pages=max_search_pages,
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
    ).run()


def run_xiaohongshu_accounts(
    *,
    accounts: Sequence[XiaohongshuAccountTarget | Mapping[str, object]] | str | bytes,
    start_date: str | date,
    end_date: str | date,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_user_note_pages: int = 100,
    max_account_search_pages: int = 5,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    comment_mode: Literal["limited", "all"] = "all",
    force_refresh: bool = False,
    force_resolve_accounts: bool = False,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """按指定账号和包含式北京时间日期范围执行小红书人工采集。"""
    normalized_accounts = _normalize_account_targets(accounts)
    normalized_start = _normalize_date(start_date, "start_date")
    normalized_end = _normalize_date(end_date, "end_date")
    if normalized_start > normalized_end:
        raise ValueError("start_date 不能晚于 end_date")
    if comment_mode not in {"limited", "all"}:
        raise ValueError("comment_mode 只能是 limited 或 all")
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    labels = tuple(target.label for target in normalized_accounts)
    return _TikHubDebugRunner(
        platform="xiaohongshu",
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
        max_user_note_pages=max_user_note_pages,
        force_resolve_accounts=force_resolve_accounts,
    ).run()


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
    douplus_posts_fallback_enabled: bool = True,
    douplus_post_page_size: int = 10,
    web_comment_page_size: int = 50,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """按指定抖音账号和包含式北京时间日期范围执行全量评论采集。"""

    normalized_accounts = _normalize_douyin_account_targets(accounts)
    normalized_start = _normalize_date(start_date, "start_date")
    normalized_end = _normalize_date(end_date, "end_date")
    if normalized_start > normalized_end:
        raise ValueError("start_date 不能晚于 end_date")
    if comment_mode not in {"limited", "all"}:
        raise ValueError("comment_mode 只能是 limited 或 all")
    if comment_mode == "all" and (not include_comments or not include_replies):
        raise ValueError("comment_mode='all' 时 include_comments 和 include_replies 必须为 True")
    if not isinstance(douplus_posts_fallback_enabled, bool):
        raise ValueError("douplus_posts_fallback_enabled 必须是布尔值")
    if (
        isinstance(douplus_post_page_size, bool)
        or not isinstance(douplus_post_page_size, int)
        or douplus_post_page_size < 1
    ):
        raise ValueError("douplus_post_page_size 必须是正整数")
    if (
        isinstance(web_comment_page_size, bool)
        or not isinstance(web_comment_page_size, int)
        or web_comment_page_size < 1
        or web_comment_page_size > 50
    ):
        raise ValueError("web_comment_page_size 必须是 1 到 50 的整数")
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
        "douplus_posts_fallback_enabled": douplus_posts_fallback_enabled,
        "douplus_post_page_size": douplus_post_page_size,
        "web_comment_page_size": web_comment_page_size,
    }
    return _TikHubDebugRunner(
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
    return _TikHubDebugRunner(
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
    return _TikHubDebugRunner(
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
    return _TikHubDebugRunner(
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


def _normalize_account_targets(
    accounts: Sequence[XiaohongshuAccountTarget | Mapping[str, object]] | str | bytes,
) -> tuple[XiaohongshuAccountTarget, ...]:
    if isinstance(accounts, (str, bytes)):
        raise ValueError("accounts 必须是账号配置序列")
    normalized = tuple(
        XiaohongshuAccountTarget.from_value(dict(value) if isinstance(value, Mapping) else value)
        for value in accounts
    )
    if not normalized:
        raise ValueError("accounts 至少包含一个账号")
    keys = [target.cache_key for target in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("accounts 不能包含重复账号配置")
    return normalized


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
        KuaishouAccountTarget.from_value(
            dict(value) if isinstance(value, Mapping) else value
        )
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


def _as_xiaohongshu_account_target(
    target: XiaohongshuAccountTarget
    | DouyinAccountTarget
    | KuaishouAccountTarget
    | WeiboAccountTarget
    | BilibiliAccountTarget,
) -> XiaohongshuAccountTarget:
    if not isinstance(target, XiaohongshuAccountTarget):
        raise ValueError("小红书账号采集不能使用其他平台的账号配置")
    return target


def _as_douyin_account_target(
    target: XiaohongshuAccountTarget
    | DouyinAccountTarget
    | KuaishouAccountTarget
    | WeiboAccountTarget
    | BilibiliAccountTarget,
) -> DouyinAccountTarget:
    if not isinstance(target, DouyinAccountTarget):
        raise ValueError("抖音账号采集不能使用其他平台的账号配置")
    return target


def _as_kuaishou_account_target(
    target: XiaohongshuAccountTarget
    | DouyinAccountTarget
    | KuaishouAccountTarget
    | WeiboAccountTarget
    | BilibiliAccountTarget,
) -> KuaishouAccountTarget:
    if not isinstance(target, KuaishouAccountTarget):
        raise ValueError("快手账号采集不能使用其他平台的账号配置")
    return target


def _as_weibo_account_target(
    target: XiaohongshuAccountTarget
    | DouyinAccountTarget
    | KuaishouAccountTarget
    | WeiboAccountTarget
    | BilibiliAccountTarget,
) -> WeiboAccountTarget:
    if not isinstance(target, WeiboAccountTarget):
        raise ValueError("微博账号采集不能使用其他平台的账号配置")
    return target


def _as_bilibili_account_target(
    target: XiaohongshuAccountTarget
    | DouyinAccountTarget
    | KuaishouAccountTarget
    | WeiboAccountTarget
    | BilibiliAccountTarget,
) -> BilibiliAccountTarget:
    if not isinstance(target, BilibiliAccountTarget):
        raise ValueError("B站账号采集不能使用其他平台的账号配置")
    return target


def _resume_douyin_comment_state(
    advance: tikhub_runtime.TikHubPageAdvance,
    *,
    observed_count: int,
    expected_count: int | None,
    attempted_cursors: set[int],
) -> dict[str, object] | None:
    """在 TikHub 提前宣称结束但评论总数未对齐时恢复下一页探测。"""

    if expected_count is None or observed_count >= expected_count:
        return None
    resume_state = advance.resume_state
    if resume_state is None:
        return None
    candidate = resume_state.get("cursor")
    if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 0:
        return None
    if candidate in attempted_cursors:
        return None
    attempted_cursors.add(candidate)
    return dict(resume_state)


def _maximum_known_count(*values: int | None) -> int | None:
    known = [value for value in values if value is not None]
    return max(known) if known else None


def _douyin_content_matches_account(
    content: CanonicalContentV1,
    target: DouyinAccountTarget,
    *,
    resolved_sec_uid: str | None = None,
) -> bool:
    author = content.author
    if author is None:
        return True
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
    return True


def _kuaishou_reference_from_homepage(homepage_url: str) -> str:
    parsed = urlparse(homepage_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _AccountResolutionError("快手 homepage_url 必须是完整的 http/https 主页地址")
    query = parse_qs(parsed.query)
    for key in ("userId", "user_id", "eid"):
        values = query.get(key)
        if values and values[0].strip():
            return values[0].strip()
    parts = [part for part in parsed.path.split("/") if part]
    for marker in ("profile", "user"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts) and parts[index + 1].strip():
                return parts[index + 1].strip()
    raise _AccountResolutionError(
        "快手 homepage_url 中没有可识别的 /profile/<eid>；请直接填写 eid 或数字 user_id"
    )


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


def _kuaishou_account_candidate_matches(
    target: KuaishouAccountTarget,
    candidate: Mapping[str, str],
    *,
    query: str,
) -> bool:
    candidate_nickname = candidate.get("nickname")
    if target.kuaishou_id:
        return candidate.get("kuaishou_id") == target.kuaishou_id
    if target.eid:
        return (
            candidate.get("eid") == target.eid
            or candidate.get("kuaishou_id") == target.eid
        )
    return (
        candidate.get("kuaishou_id") == query
        or candidate.get("eid") == query
        or candidate_nickname == query
    )


def _kuaishou_content_matches_account(
    content: CanonicalContentV1,
    *,
    resolved_user_id: str,
) -> bool:
    author = content.author
    if author is None:
        return True
    if (
        author.external_account_id
        and author.external_account_id != resolved_user_id
    ):
        return False
    return True


def _weibo_uid_from_homepage(homepage_url: str) -> str:
    parsed = urlparse(homepage_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _AccountResolutionError("微博 homepage_url 必须是完整的 http/https 主页地址")
    query = parse_qs(parsed.query)
    for key in ("uid", "user_id", "id"):
        values = query.get(key)
        if values and values[0].strip():
            return values[0].strip()
    parts = [part for part in parsed.path.split("/") if part]
    for part in reversed(parts):
        if part.isdigit():
            return part
    raise _AccountResolutionError(
        "微博 homepage_url 中没有可识别的数字 UID；请直接填写 uid"
    )


def _bilibili_uid_from_homepage(homepage_url: str) -> str:
    parsed = urlparse(homepage_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _AccountResolutionError("B站 homepage_url 必须是完整的 http/https 主页地址")
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.casefold().endswith("space.bilibili.com") and parts and parts[0].isdigit():
        return parts[0]
    query = parse_qs(parsed.query)
    for key in ("uid", "mid", "user_id"):
        values = query.get(key)
        if values and values[0].strip().isdigit():
            return values[0].strip()
    raise _AccountResolutionError(
        "B站 homepage_url 中没有可识别的数字 UID；请直接填写 uid"
    )


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
        return True
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


def _identity_from_mapping(raw: Mapping[str, object]) -> dict[str, str]:
    """从用户候选的常见 envelope 中取出可比对身份字段。"""
    queue: list[Mapping[str, object]] = [raw]
    seen: set[int] = set()
    result: dict[str, str] = {}
    while queue and len(seen) < 16:
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        for result_key, source_keys in {
            "user_id": ("user_id", "userid", "userId", "id"),
            "red_id": ("red_id", "redId", "redid"),
            "nickname": ("nickname", "nick_name", "display_name", "name"),
        }.items():
            if result_key in result:
                continue
            for source_key in source_keys:
                value = current.get(source_key)
                if value is not None and str(value).strip():
                    result[result_key] = str(value).strip()
                    break
        for key in (
            "user",
            "user_info",
            "userInfo",
            "user_card",
            "userCard",
            "profile",
            "account",
            "data",
        ):
            nested = current.get(key)
            if isinstance(nested, Mapping):
                queue.append(nested)
    return result


def _account_candidate_matches(
    target: XiaohongshuAccountTarget,
    candidate: Mapping[str, str],
) -> bool:
    if target.red_id is not None and candidate.get("red_id") != target.red_id:
        return False
    if target.nickname is not None:
        candidate_nickname = candidate.get("nickname")
        if target.red_id is None and candidate_nickname != target.nickname:
            return False
        if candidate_nickname is not None and candidate_nickname != target.nickname:
            return False
    return bool(candidate.get("user_id"))


def _validate_account_identity(
    target: XiaohongshuAccountTarget,
    observed: Mapping[str, str],
) -> None:
    if target.user_id and observed.get("user_id") and observed["user_id"] != target.user_id:
        raise _AccountResolutionError(
            f"账号 {target.label} user_id 身份不一致"
        )
    if target.red_id and observed.get("red_id") != target.red_id:
        raise _AccountResolutionError(
            f"账号 {target.label} red_id 身份不一致或响应缺失"
        )
    if target.nickname and observed.get("nickname") not in {None, target.nickname}:
        raise _AccountResolutionError(
            f"账号 {target.label} nickname 身份不一致"
        )
    if not observed.get("user_id"):
        raise _AccountResolutionError(f"账号 {target.label} 响应缺少 user_id")


def _load_resolved_account_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    values: object
    if isinstance(raw, dict) and isinstance(raw.get("accounts"), list):
        values = raw["accounts"]
    elif isinstance(raw, dict):
        values = list(raw.values())
    else:
        return {}
    if not isinstance(values, list):
        return {}
    result: dict[str, dict[str, object]] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        try:
            nickname = _optional_config_text(item.get("nickname"), "cached nickname")
            red_id = _optional_config_text(item.get("red_id"), "cached red_id")
            user_id = _optional_config_text(item.get("user_id"), "cached user_id")
        except ValueError:
            continue
        if user_id is None:
            continue
        entry = {
            "nickname": nickname,
            "red_id": red_id,
            "user_id": user_id,
            "resolved_at": item.get("resolved_at"),
            "resolution_method": item.get("resolution_method"),
        }
        result["|".join((nickname or "", red_id or "", user_id or ""))] = entry
        # Cache lookup is keyed by the configured identity, not only the resolved ID.
        result["|".join((nickname or "", red_id or "", ""))] = entry
    return result


def _save_resolved_account_cache(
    path: Path,
    cache: Mapping[str, Mapping[str, object]],
) -> None:
    unique: dict[str, Mapping[str, object]] = {}
    for entry in cache.values():
        user_id = entry.get("user_id")
        nickname = entry.get("nickname")
        red_id = entry.get("red_id")
        if not isinstance(user_id, str) or not user_id:
            continue
        key = "|".join(
            item if isinstance(item, str) else ""
            for item in (nickname, red_id, user_id)
        )
        unique[key] = entry
    payload = {
        "schema_version": "tikhub-test-resolved-accounts.v1",
        "accounts": list(unique.values()),
    }
    assert_secret_free(payload, path="tikhub_test.resolved_accounts")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _tikhub_response_requests_retry(body: object) -> bool:
    """识别 TikHub 明确提示可重试且本次不扣费的响应。"""
    if not isinstance(body, Mapping):
        return False
    detail = body.get("detail")
    if not isinstance(detail, Mapping):
        return False
    message = " ".join(
        str(detail.get(key, ""))
        for key in ("message", "message_zh")
    ).lower()
    return "retry" in message or "重试" in message


def _douyin_comment_total_requires_fix(body: object) -> bool:
    """识别抖音响应明确声明当前评论 total 需要修正的标志。"""
    if not isinstance(body, Mapping):
        return False
    data = body.get("data")
    if not isinstance(data, Mapping):
        return False
    value = data.get("need_fix_total")
    return value is True or value == 1 or value == "1" or value == "true"


def _normalize_keywords(
    *,
    keyword: str | None,
    keywords: str | Sequence[str] | None,
) -> tuple[str, ...]:
    if keyword is not None and keywords is not None:
        raise ValueError("keyword 与 keywords 不能同时传入")
    if keyword is not None:
        raw_values: tuple[str, ...] = (keyword,)
    elif keywords is None:
        raw_values = ("爱玛",)
    elif isinstance(keywords, str):
        raw_values = (keywords,)
    else:
        raw_values = tuple(keywords)

    normalized: list[str] = []
    for value in raw_values:
        if not isinstance(value, str):
            raise ValueError("keywords 只能包含字符串")
        stripped = value.strip()
        if not stripped:
            raise ValueError("keywords 不能包含空字符串")
        if stripped not in normalized:
            normalized.append(stripped)
    if not normalized:
        raise ValueError("keywords 至少包含一个关键词")
    return tuple(normalized)


__all__ = [
    "BilibiliAccountTarget",
    "DouyinAccountTarget",
    "KuaishouAccountTarget",
    "TikHubTestRunResult",
    "WeiboAccountTarget",
    "XiaohongshuAccountTarget",
    "run_platform",
    "run_bilibili_accounts",
    "run_douyin_accounts",
    "run_kuaishou_accounts",
    "run_weibo_accounts",
    "run_xiaohongshu_accounts",
]

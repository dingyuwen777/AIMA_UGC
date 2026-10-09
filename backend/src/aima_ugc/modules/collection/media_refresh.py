"""只刷新一个既有小红书视频 URL 的冻结执行协议。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aima_ugc.contracts.collection import CollectionDecisionPolicyV1
from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot
from aima_ugc.modules.content.media_playback import ContentPlaybackSource
from aima_ugc.modules.system.models import ProviderConfig

MEDIA_REFRESH_SCHEMA = "collection-run-config.v6"


class MediaRefreshTarget(BaseModel):
    """内容与来源身份在发送前冻结；用户输入不能扩展请求或费用预算。"""

    model_config = ConfigDict(extra="forbid")
    content_id: UUID
    position: int = Field(ge=0)
    note_id: str = Field(min_length=1, max_length=128)
    identity_token: str = Field(min_length=1, max_length=128)
    expected_source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation: int = Field(ge=1)
    max_sent_attempts: Literal[1] = 1


def media_refresh_snapshot(
    source: ContentPlaybackSource, provider: ProviderConfig
) -> dict[str, object]:
    """单请求 Deadline 不套用普通采集的三百页预算。"""
    target = MediaRefreshTarget(
        content_id=source.content_id,
        position=source.position,
        note_id=source.note_id,
        identity_token=source.identity_token,
        expected_source_revision=source.source_revision,
        generation=source.generation + 1,
    )
    return {
        "schema_version": MEDIA_REFRESH_SCHEMA,
        "mode": "media_refresh",
        "plan_type": "tikhub",
        "include_comments": False,
        "include_sub_comments": False,
        "detail_policy": "on_change",
        "comment_policy": "adaptive",
        "decision_policy": CollectionDecisionPolicyV1(comments_enabled=False).model_dump(
            mode="json"
        ),
        "media_refresh": target.model_dump(mode="json"),
        "platforms": [provider_run_snapshot(provider, platform="xiaohongshu")],
        "job_timeout_seconds": int(provider.timeout_seconds) + 30,
    }


def validate_media_refresh_snapshot(snapshot: Mapping[str, object]) -> MediaRefreshTarget:
    """v6 是独立且封闭的执行分支，不放宽历史 v4/v5 或公共创建请求。"""
    if set(snapshot) != {
        "schema_version",
        "mode",
        "plan_type",
        "include_comments",
        "include_sub_comments",
        "detail_policy",
        "comment_policy",
        "decision_policy",
        "media_refresh",
        "platforms",
        "job_timeout_seconds",
    } or (
        snapshot.get("schema_version") != MEDIA_REFRESH_SCHEMA
        or snapshot.get("mode") != "media_refresh"
        or snapshot.get("plan_type") != "tikhub"
        or snapshot.get("include_comments") is not False
        or snapshot.get("include_sub_comments") is not False
        or snapshot.get("detail_policy") != "on_change"
        or snapshot.get("comment_policy") != "adaptive"
    ):
        raise ValueError("media_refresh 必须使用封闭的 collection-run-config.v6")
    policy = CollectionDecisionPolicyV1.model_validate(snapshot["decision_policy"])
    if policy != CollectionDecisionPolicyV1(comments_enabled=False):
        raise ValueError("media_refresh 禁止评论与普通采集策略")
    platforms = snapshot["platforms"]
    if not isinstance(platforms, list) or len(platforms) != 1 or not isinstance(platforms[0], dict):
        raise ValueError("media_refresh 必须冻结唯一小红书 Provider")
    provider = platforms[0]
    if (
        provider.get("platform") != "xiaohongshu"
        or provider.get("provider") != "tikhub"
        or provider.get("provider_kind") != "collection"
        or provider.get("config") != {}
        or not all(
            provider.get(key) is not None
            for key in (
                "provider_config_id",
                "base_url",
                "secret_ref",
                "timeout_seconds",
                "max_retries",
                "max_concurrency",
                "revision",
                "extra_config",
            )
        )
    ):
        raise ValueError("media_refresh Provider 快照不完整或类型不符")
    UUID(str(provider["provider_config_id"]))
    timeout = provider["timeout_seconds"]
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or timeout <= 0
        or snapshot["job_timeout_seconds"] != timeout + 30
    ):
        raise ValueError("media_refresh Deadline 必须只覆盖一次请求与收敛余量")
    return MediaRefreshTarget.model_validate(snapshot["media_refresh"])

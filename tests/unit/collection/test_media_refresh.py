"""播放准备冻结协议不允许扩大评论、请求预算或公开采集创建权限。"""

from copy import deepcopy
from uuid import uuid4

import pytest
from aima_ugc.contracts.http import CollectionRunCreateRequest
from aima_ugc.modules.collection.media_refresh import (
    media_refresh_snapshot,
    validate_media_refresh_snapshot,
)
from aima_ugc.modules.collection.run_policy import (
    validate_new_run_snapshot,
    validate_run_decision_policy,
)
from aima_ugc.modules.content.media_playback import ContentPlaybackSource
from aima_ugc.modules.system.models import ProviderConfig
from pydantic import ValidationError


def _snapshot():
    """一次短请求复用真实 Provider 快照生成器。"""
    return media_refresh_snapshot(
        ContentPlaybackSource(
            content_id=uuid4(),
            position=0,
            note_id="note",
            identity_token="token",
            source_revision="a" * 64,
            url=None,
            generation=2,
        ),
        ProviderConfig(
            id=uuid4(),
            provider="tikhub",
            display_name="fixture",
            base_url="https://api.tikhub.io",
            secret_ref="fixture/key",
            enabled=True,
            timeout_seconds=7,
            max_retries=5,
        ),
    )


def test_v6_is_single_request_bounded_and_cannot_be_created_as_public_collection():
    snapshot = _snapshot()
    target = validate_media_refresh_snapshot(snapshot)
    assert target.generation == 3 and target.max_sent_attempts == 1
    assert snapshot["job_timeout_seconds"] == 37
    validate_new_run_snapshot(snapshot)
    with pytest.raises(ValidationError):
        CollectionRunCreateRequest.model_validate(
            {"mode": "media_refresh", "platforms": [{"platform": "xiaohongshu"}]}
        )


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "collection-run-config.v4"},
        {"mode": "content_supplement"},
        {"include_comments": True},
        {"include_sub_comments": True},
        {"comment_policy": "full"},
        {"job_timeout_seconds": 9000},
        {"unexpected": True},
    ],
)
def test_v6_cannot_mutate_frozen_mode_comments_or_deadline(change):
    snapshot = _snapshot()
    snapshot.update(change)
    with pytest.raises(ValueError):
        validate_run_decision_policy(snapshot)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_sent_attempts", 2),
        ("position", -1),
        ("generation", 0),
        ("expected_source_revision", "wrong"),
        ("url", "https://evil.test"),
    ],
)
def test_v6_target_is_closed_and_budget_is_one(field, value):
    snapshot = deepcopy(_snapshot())
    snapshot["media_refresh"][field] = value
    with pytest.raises(ValueError):
        validate_media_refresh_snapshot(snapshot)

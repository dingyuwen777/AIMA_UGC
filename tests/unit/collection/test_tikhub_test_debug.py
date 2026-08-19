"""TikHub 五平台无数据库测试/调试工具行为测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import aima_ugc.adapters.providers.tikhub_test.core.config as tikhub_test_config
from aima_ugc.adapters.providers.tikhub_test import (
    run_bilibili,
    run_douyin,
    run_kuaishou,
    run_weibo,
    run_xiaohongshu,
)
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import DebugState, RunOutputStore


def test_default_env_file_stays_at_tikhub_test_root() -> None:
    expected = Path(tikhub_test_config.__file__).resolve().parent.parent / ".env"

    assert tikhub_test_config._DEFAULT_ENV_FILE == expected


def test_local_env_loads_tikhub_secret_without_exposing_value(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "TIKHUB_API_KEY=super-secret-debug-key\n"
        "TIKHUB_TIMEOUT_SECONDS=12.5\n",
        encoding="utf-8",
    )

    config = TikHubTestConfig.load(env_file)

    assert config.base_url == "https://api.tikhub.io"
    assert config.api_key.get_secret_value() == "super-secret-debug-key"
    assert config.timeout_seconds == 12.5
    assert "super-secret-debug-key" not in repr(config)
    assert "super-secret-debug-key" not in str(config)


def test_local_env_requires_api_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TIKHUB_BASE_URL=https://api.tikhub.io\n", encoding="utf-8")

    with pytest.raises(ValueError, match="TIKHUB_API_KEY"):
        TikHubTestConfig.load(env_file)


def test_debug_state_persists_content_and_comment_deduplication(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state = DebugState.load(state_file)

    assert state.should_refresh_comments("xhs", "note-1", 3) is True
    assert state.is_known_comment("xhs", "note-1", "comment-1") is False

    state.remember_content("xhs", "note-1", comment_count=3)
    state.remember_comment("xhs", "note-1", "comment-1")
    state.save()

    reloaded = DebugState.load(state_file)
    assert reloaded.should_refresh_comments("xhs", "note-1", 3) is False
    assert reloaded.should_refresh_comments("xhs", "note-1", 4) is True
    assert reloaded.should_refresh_comments("xhs", "note-1", 3, force=True) is True
    assert reloaded.is_known_comment("xhs", "note-1", "comment-1") is True


def test_run_output_store_keeps_raw_and_canonical_without_database(tmp_path: Path) -> None:
    store = RunOutputStore.create(
        output_root=tmp_path,
        platform="xhs",
        run_id="20260817T120000Z-test",
    )
    raw_body = {"data": {"items": [{"id": "note-1"}]}}

    raw = store.save_raw(operation="search_notes", body=raw_body, request_no=1)
    store.append_canonical("contents", {"platform": "xhs", "external_content_id": "note-1"})
    store.append_canonical(
        "comments",
        {
            "platform": "xhs",
            "external_content_id": "note-1",
            "external_comment_id": "comment-1",
        },
    )
    run_summary_path = store.write_run_summary({"platform": "xhs", "requests": 1})

    assert json.loads(raw.path.read_text(encoding="utf-8")) == raw_body
    assert raw.artifact_id
    assert json.loads((store.canonical_dir / "contents.jsonl").read_text(encoding="utf-8")) == {
        "platform": "xhs",
        "external_content_id": "note-1",
    }
    assert (
        json.loads((store.canonical_dir / "comments.jsonl").read_text(encoding="utf-8"))[
            "external_comment_id"
        ]
        == "comment-1"
    )
    assert json.loads(run_summary_path.read_text(encoding="utf-8"))["requests"] == 1
    assert not any("postgres" in part.lower() for part in store.run_dir.parts)


def test_all_five_platforms_expose_python_function_entrypoints_without_cli() -> None:
    functions = (
        run_xiaohongshu,
        run_douyin,
        run_weibo,
        run_bilibili,
        run_kuaishou,
    )

    assert all(callable(function) for function in functions)
    assert [function.__name__ for function in functions] == [
        "run_xiaohongshu",
        "run_douyin",
        "run_weibo",
        "run_bilibili",
        "run_kuaishou",
    ]

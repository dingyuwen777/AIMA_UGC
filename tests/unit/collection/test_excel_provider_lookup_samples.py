from __future__ import annotations

import json
from pathlib import Path

from aima_ugc.adapters.providers.imports.identity import resolve_content_identity

_FIXTURE = Path("tests/fixtures/imports/excel_provider_lookup_samples.json")
_LOOKUP_TYPES = {
    "xiaohongshu": ("note_id",),
    "douyin": ("aweme_id",),
    "weibo": ("status_id",),
    "bilibili": ("av_id", "bv_id"),
    "kuaishou": ("photo_id",),
}


def test_uploaded_excel_fixture_is_bound_to_source_file_and_all_samples_are_typed() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    assert payload["source"] == "惠科data(0817-0819).xlsx"
    assert payload["source_sha256"] == (
        "8199f1b025a556998c8daa3c8b087f43494a1b84b13d932c1b3fb392f61ef37b"
    )
    assert set(payload["platforms"]) == set(_LOOKUP_TYPES)

    for platform, samples in payload["platforms"].items():
        assert len(samples) >= 6
        for sample in samples:
            identity = resolve_content_identity(
                platform=platform,
                canonical_url=sample["url"],
                source_article_id=sample["article_id"],
            )
            assert identity.alternate_ids["source_article_id"] == sample["article_id"]
            assert any(identity.alternate_ids.get(key) for key in _LOOKUP_TYPES[platform])

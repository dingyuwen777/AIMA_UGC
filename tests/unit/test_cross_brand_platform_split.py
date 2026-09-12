"""跨品牌车型共现帖子五平台拆分的直接行为测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.adapters.providers.imports_test.cross_brand_platform_split.split_by_platform import (
    split_by_platform,
)
from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehicleModelMention,
    VehicleModelReference,
    VehiclePairRecordV1,
    VehiclePairReference,
)
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.contracts.platform import PLATFORM_NAMES, PlatformName


def _vehicle_pair_record(
    *,
    platform: PlatformName,
    external_id: str,
    multi_pair: bool = False,
) -> VehiclePairRecordV1:
    """构造一条最小合法且可带多个 pair 的第二阶段输出记录。"""

    observed_at = datetime(2026, 9, 12, 0, 0, tzinfo=UTC)
    content = CanonicalContentV1(
        platform=platform,
        external_content_id=external_id,
        content_type="note",
        title="元宇宙和Q3对比",
        text="同一帖子中的车型共现",
        observed_at=observed_at,
        observed_fields=["title", "text"],
        source=CanonicalSourceV1(
            provider_name="manual",
            source_type="test",
            source_value="cross-brand-platform-split-test",
            observed_at=observed_at,
        ),
    )
    record = UnifiedContentRecordV1(
        content=content,
        matched_keywords=["元宇宙", "Q3"],
    )
    competitor_models = [VehicleModelReference(brand="九号", model="Q3")]
    pairs = [
        VehiclePairReference(
            target_model="元宇宙",
            competitor_brand="九号",
            competitor_model="Q3",
        )
    ]
    mentions = [
        VehicleModelMention(
            brand="爱玛",
            model="元宇宙",
            fields=("title",),
            matched_aliases=("元宇宙",),
        ),
        VehicleModelMention(
            brand="九号",
            model="Q3",
            fields=("title",),
            matched_aliases=("Q3",),
        ),
    ]
    if multi_pair:
        competitor_models.append(VehicleModelReference(brand="雅迪", model="莱茵"))
        pairs.append(
            VehiclePairReference(
                target_model="元宇宙",
                competitor_brand="雅迪",
                competitor_model="莱茵",
            )
        )
        mentions.append(
            VehicleModelMention(
                brand="雅迪",
                model="莱茵",
                fields=("text",),
                matched_aliases=("莱茵",),
            )
        )

    return VehiclePairRecordV1(
        record=record,
        matched_target_models=("元宇宙",),
        matched_competitor_models=tuple(competitor_models),
        matched_pairs=tuple(pairs),
        model_mentions=tuple(mentions),
    )


def _raw_line(record: VehiclePairRecordV1, *, windows_newline: bool = False) -> bytes:
    """生成带显式空格风格的 JSON，以验证第三阶段不会重新序列化 payload。"""

    payload = json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(", ", ": "),
    ).encode("utf-8")
    return payload + (b"\r\n" if windows_newline else b"\n")


def test_split_routes_all_five_platforms_and_preserves_raw_payload(tmp_path: Path) -> None:
    """五个平台各自路由，且多 pair 帖子仍只占一行并保持原始 bytes。"""

    input_path = tmp_path / "comparison_posts.jsonl"
    raw_by_platform: dict[PlatformName, bytes] = {}
    lines: list[bytes] = []
    for index, platform in enumerate(PLATFORM_NAMES):
        raw = _raw_line(
            _vehicle_pair_record(
                platform=platform,
                external_id=f"post-{index}",
                multi_pair=platform == "xiaohongshu",
            ),
            windows_newline=index % 2 == 1,
        )
        raw_by_platform[platform] = raw
        lines.append(raw)
    input_path.write_bytes(b"".join(lines))

    summary = split_by_platform(
        input_path=input_path,
        output_root=tmp_path / "output",
        run_id="all-platforms",
    )

    assert summary.rows_seen == 5
    assert summary.platform_counts == {platform: 1 for platform in PLATFORM_NAMES}
    assert sum(summary.platform_counts.values()) == summary.rows_seen
    for platform in PLATFORM_NAMES:
        output_path = summary.output_paths[platform]
        assert output_path.is_file()
        assert output_path.read_bytes() == raw_by_platform[platform]

    xhs_lines = [
        line
        for line in summary.output_paths["xiaohongshu"].read_bytes().splitlines()
        if line.strip()
    ]
    assert len(xhs_lines) == 1
    xhs_record = VehiclePairRecordV1.model_validate_json(xhs_lines[0])
    assert len(xhs_record.matched_pairs) == 2

    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["rows_seen"] == 5
    assert payload["platform_counts"] == {platform: 1 for platform in PLATFORM_NAMES}


def test_split_always_creates_empty_files_for_platforms_without_rows(tmp_path: Path) -> None:
    """没有数据的平台也必须生成固定空 JSONL，方便下游使用固定路径。"""

    input_path = tmp_path / "comparison_posts.jsonl"
    input_path.write_bytes(
        _raw_line(_vehicle_pair_record(platform="xiaohongshu", external_id="only-xhs"))
    )

    summary = split_by_platform(
        input_path=input_path,
        output_root=tmp_path / "output",
        run_id="empty-platforms",
    )

    assert summary.rows_seen == 1
    assert summary.platform_counts["xiaohongshu"] == 1
    for platform in PLATFORM_NAMES:
        assert summary.output_paths[platform].is_file()
        if platform != "xiaohongshu":
            assert summary.platform_counts[platform] == 0
            assert summary.output_paths[platform].read_bytes() == b""


def test_invalid_vehicle_pair_jsonl_does_not_publish_partial_run(tmp_path: Path) -> None:
    """输入中途损坏时应清理 staging，不能留下半截正式五平台输出。"""

    input_path = tmp_path / "comparison_posts.jsonl"
    input_path.write_bytes(
        _raw_line(_vehicle_pair_record(platform="xiaohongshu", external_id="valid"))
        + b"{broken-json\n"
    )
    output_root = tmp_path / "output"

    with pytest.raises(ValueError, match="第 2 行"):
        split_by_platform(
            input_path=input_path,
            output_root=output_root,
            run_id="broken-run",
        )

    assert not (output_root / "runs" / "broken-run").exists()
    assert not (output_root / ".staging-broken-run").exists()


def test_invalid_platform_fails_closed_without_publishing_run(tmp_path: Path) -> None:
    """绕过类型系统构造的非五平台 payload 应被 VehiclePairRecordV1 拒绝。"""

    record = _vehicle_pair_record(platform="xiaohongshu", external_id="bad-platform")
    payload = record.model_dump(mode="json")
    payload["record"]["content"]["platform"] = "wechat"
    input_path = tmp_path / "comparison_posts.jsonl"
    input_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    output_root = tmp_path / "output"

    with pytest.raises(ValueError, match="第 1 行"):
        split_by_platform(
            input_path=input_path,
            output_root=output_root,
            run_id="bad-platform",
        )

    assert not (output_root / "runs" / "bad-platform").exists()
    assert not (output_root / ".staging-bad-platform").exists()

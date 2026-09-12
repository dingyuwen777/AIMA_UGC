"""车型共现二次筛选工具的直接行为测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehiclePairRecordV1,
    filter_vehicle_pairs,
    load_vehicle_catalog,
)
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1


def _record(
    *,
    external_id: str,
    title: str | None,
    text: str | None,
) -> UnifiedContentRecordV1:
    """构造最小合法 UnifiedContentRecordV1 测试输入。"""

    observed_at = datetime(2026, 9, 12, 0, 0, tzinfo=UTC)
    content = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_id,
        content_type="note",
        title=title,
        text=text,
        observed_at=observed_at,
        observed_fields=["title", "text"],
        source=CanonicalSourceV1(
            provider_name="manual",
            source_type="test",
            source_value="vehicle-pair-filter-test",
            observed_at=observed_at,
        ),
    )
    return UnifiedContentRecordV1(
        content=content,
        matched_keywords=["爱玛"],
    )


def _write_jsonl(path: Path, records: list[UnifiedContentRecordV1]) -> None:
    """把测试记录写为逐行 UnifiedContentRecordV1 JSONL。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{record.model_dump_json()}\n" for record in records),
        encoding="utf-8",
    )


def _write_catalog(path: Path) -> None:
    """写入覆盖多个爱玛车型和竞品车型的最小目录。"""

    payload = {
        "schema_version": "vehicle-pair-catalog.v1",
        "target_brand": "爱玛",
        "brands": [
            {
                "name": "爱玛",
                "models": [
                    {"name": "元宇宙", "aliases": ["爱玛元宇宙"]},
                    {"name": "墩墩", "aliases": ["爱玛墩墩"]},
                ],
            },
            {
                "name": "雅迪",
                "models": [{"name": "莱茵", "aliases": ["雅迪莱茵"]}],
            },
            {
                "name": "九号",
                "models": [{"name": "Q3", "aliases": ["九号Q3"]}],
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_outputs(path: Path) -> list[VehiclePairRecordV1]:
    """读取并按二次筛选输出模型校验 JSONL。"""

    return [
        VehiclePairRecordV1.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line.strip()
    ]


def test_vehicle_alias_match_does_not_require_brand_name_and_builds_local_cartesian_product(
    tmp_path: Path,
) -> None:
    """只出现车型词也应归属品牌，多车型只在单帖内生成实际笛卡尔积。"""

    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    catalog_path = tmp_path / "vehicle_catalog.json"
    _write_catalog(catalog_path)
    _write_jsonl(
        input_path,
        [
            _record(
                external_id="post-1",
                title="元 宇 宙和墩墩怎么选",
                text="莱茵和q-3我都试过",
            ),
            _record(
                external_id="post-2",
                title="爱玛、雅迪、九号最近都很热门",
                text="这里只提品牌，不提具体车型",
            ),
            _record(external_id="post-3", title="元宇宙不错", text="只有爱玛车型"),
            _record(external_id="post-4", title="Q3不错", text="只有竞品车型"),
            _record(
                external_id="post-5",
                title="爱玛元宇宙通勤体验",
                text="和九号Q3相比各有优点",
            ),
        ],
    )

    summary = filter_vehicle_pairs(
        input_path=input_path,
        catalog_path=catalog_path,
        output_root=tmp_path / "output",
        run_id="case-main",
    )

    assert summary.rows_seen == 5
    assert summary.rows_with_target_model == 3
    assert summary.rows_with_competitor_model == 3
    assert summary.rows_with_cross_brand_pair == 2
    assert summary.rows_filtered_out == 3
    assert summary.target_model_counts == {"元宇宙": 2, "墩墩": 1}
    assert summary.competitor_model_counts == {"九号/Q3": 2, "雅迪/莱茵": 1}
    assert summary.pair_counts == {
        "元宇宙|九号|Q3": 2,
        "元宇宙|雅迪|莱茵": 1,
        "墩墩|九号|Q3": 1,
        "墩墩|雅迪|莱茵": 1,
    }

    outputs = _read_outputs(summary.output_path)
    assert [item.record.content.external_content_id for item in outputs] == ["post-1", "post-5"]
    first = outputs[0]
    assert first.matched_target_models == ("元宇宙", "墩墩")
    assert [(item.brand, item.model) for item in first.matched_competitor_models] == [
        ("雅迪", "莱茵"),
        ("九号", "Q3"),
    ]
    assert [
        (item.target_model, item.competitor_brand, item.competitor_model)
        for item in first.matched_pairs
    ] == [
        ("元宇宙", "雅迪", "莱茵"),
        ("元宇宙", "九号", "Q3"),
        ("墩墩", "雅迪", "莱茵"),
        ("墩墩", "九号", "Q3"),
    ]
    assert len(outputs) == 2

    mentions = {(item.brand, item.model): item for item in first.model_mentions}
    assert mentions[("爱玛", "元宇宙")].fields == ("title",)
    assert mentions[("爱玛", "墩墩")].fields == ("title",)
    assert mentions[("雅迪", "莱茵")].fields == ("text",)
    assert mentions[("九号", "Q3")].fields == ("text",)
    assert "Q3" in mentions[("九号", "Q3")].matched_aliases

    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["rows_seen"] == 5
    assert payload["rows_with_cross_brand_pair"] == 2
    assert payload["rows_filtered_out"] == 3
    assert payload["rows_seen"] == (
        payload["rows_with_cross_brand_pair"] + payload["rows_filtered_out"]
    )


def test_vehicle_pair_filter_can_match_target_in_title_and_competitor_in_text(tmp_path: Path) -> None:
    """目标车型和竞品车型可以分别出现在标题、正文，仍视为同帖共现。"""

    input_path = tmp_path / "contents.jsonl"
    catalog_path = tmp_path / "vehicle_catalog.json"
    _write_catalog(catalog_path)
    _write_jsonl(
        input_path,
        [_record(external_id="cross-field", title="墩墩实际体验", text="莱茵的骑感也不错")],
    )

    summary = filter_vehicle_pairs(
        input_path=input_path,
        catalog_path=catalog_path,
        output_root=tmp_path / "output",
        run_id="cross-field",
    )

    output = _read_outputs(summary.output_path)[0]
    assert output.matched_target_models == ("墩墩",)
    assert [(item.brand, item.model) for item in output.matched_competitor_models] == [
        ("雅迪", "莱茵")
    ]
    mentions = {(item.brand, item.model): item for item in output.model_mentions}
    assert mentions[("爱玛", "墩墩")].fields == ("title",)
    assert mentions[("雅迪", "莱茵")].fields == ("text",)


def test_catalog_rejects_alias_that_maps_to_multiple_models(tmp_path: Path) -> None:
    """同一规范化 alias 跨车型冲突时必须 fail closed。"""

    catalog_path = tmp_path / "ambiguous.json"
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "vehicle-pair-catalog.v1",
                "target_brand": "爱玛",
                "brands": [
                    {"name": "爱玛", "models": [{"name": "A1", "aliases": []}]},
                    {"name": "雅迪", "models": [{"name": "A-1", "aliases": []}]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="不能同时归属于多个车型"):
        load_vehicle_catalog(catalog_path)


def test_invalid_input_jsonl_does_not_publish_partial_output(tmp_path: Path) -> None:
    """输入中途损坏时不得留下半截 comparison_posts.jsonl 或失败 run 目录。"""

    input_path = tmp_path / "contents.jsonl"
    catalog_path = tmp_path / "vehicle_catalog.json"
    _write_catalog(catalog_path)
    valid = _record(external_id="valid", title="元宇宙", text="Q3")
    input_path.write_bytes(valid.model_dump_json().encode("utf-8") + b"\n{broken-json\n")
    output_root = tmp_path / "output"

    with pytest.raises(ValueError, match="第 2 行"):
        filter_vehicle_pairs(
            input_path=input_path,
            catalog_path=catalog_path,
            output_root=output_root,
            run_id="broken-run",
        )

    assert not (output_root / "runs" / "broken-run").exists()


def test_shipped_catalog_is_valid() -> None:
    """仓库默认车型目录自身必须持续满足严格配置约束。"""

    catalog_path = (
        Path(__file__).parents[2]
        / "backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/vehicle_catalog.json"
    )
    catalog = load_vehicle_catalog(catalog_path)

    assert catalog.target_brand == "爱玛"
    assert any(brand.name != "爱玛" for brand in catalog.brands)

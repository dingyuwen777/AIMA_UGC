from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import aima_ugc.modules.analysis.offline_labeling as offline_labeling
import pytest
from aima_ugc.contracts.analysis import (
    ContentLabelAnalysisV3,
    ContentLabelPairV2,
    UnifiedContentRecordV1,
)
from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    PROMPT_VERSION,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomyLoader,
    label_unified_content_jsonl,
)
from pydantic import ValidationError

OBSERVED_AT = datetime(2026, 8, 21, 11, 30, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _content(
    *,
    external_content_id: str = "voice-v3-content",
    title: str = "爱玛骑了一年，续航还可以",
    text: str = "我每天通勤骑，冬天续航会短一些，但总体够用。",
) -> CanonicalContentV1:
    return CanonicalContentV1(
        observed_fields=[
            "title",
            "text",
            "author.display_name",
            "author.bio",
            "author.verification_label",
        ],
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="note",
        title=title,
        text=text,
        author=CanonicalAuthorV1(
            display_name="通勤小林",
            bio="分享日常通勤和骑行体验",
            verification_label="",
        ),
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _record(content: CanonicalContentV1) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(content=content, matched_keywords=["爱玛"])


def _base_fields() -> dict[str, object]:
    return {
        "prompt_version": "content-labeling.v3",
        "prompt_sha256": HASH_A,
        "taxonomy_sha256": HASH_B,
        "model_provider": "fake",
        "model": "fake-v3",
        "input_hash": HASH_C,
        "analyzed_at": OBSERVED_AT,
    }


def _model_response(
    *,
    relevance: str,
    voice_type: str,
    sentiment: str | None,
    primary_label: str | None = None,
    secondary_label: str | None = None,
) -> str:
    labels: list[dict[str, str]] = []
    if primary_label is not None and secondary_label is not None:
        labels.append(
            {
                "primary_label": primary_label,
                "secondary_label": secondary_label,
            }
        )
    return json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": relevance,
                    "voice_type": voice_type,
                    "sentiment": sentiment,
                    "labels": labels,
                }
            ]
        },
        ensure_ascii=False,
    )


def _write_records(path: Path, records: tuple[UnifiedContentRecordV1, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{record.model_dump_json()}\n" for record in records),
        encoding="utf-8",
    )


def test_v3_contract_enforces_relevance_dependent_shape_and_voice_type() -> None:
    relevant = ContentLabelAnalysisV3(
        relevance="relevant",
        voice_type="user_voice",
        sentiment="正面",
        labels=(
            ContentLabelPairV2(
                primary_label="电池、续航与充电",
                secondary_label="实际续航表现",
            ),
        ),
        **_base_fields(),
    )
    irrelevant = ContentLabelAnalysisV3(
        relevance="irrelevant",
        voice_type="media_information",
        sentiment=None,
        labels=(),
        **_base_fields(),
    )

    assert relevant.schema_version == "content-label-analysis.v3"
    assert relevant.is_relevant is True
    assert relevant.is_user_voice is True
    assert irrelevant.is_relevant is False
    assert irrelevant.is_user_voice is False

    record = UnifiedContentRecordV1(
        content=_content(),
        matched_keywords=["爱玛"],
        analysis=irrelevant,
    )
    assert UnifiedContentRecordV1.model_validate_json(record.model_dump_json()) == record

    with pytest.raises(ValidationError):
        ContentLabelAnalysisV3(
            relevance="irrelevant",
            voice_type="unknown",
            sentiment="中性",
            labels=(),
            **_base_fields(),
        )
    with pytest.raises(ValidationError):
        ContentLabelAnalysisV3(
            relevance="relevant",
            voice_type="not-a-real-type",
            sentiment="中性",
            labels=(ContentLabelPairV2(primary_label="品牌评价", secondary_label="口碑与信任"),),
            **_base_fields(),
        )


def test_service_returns_v3_and_sends_only_approved_public_author_context() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    fake = FakeContentLabelingLLM(
        responses=[
            _model_response(
                relevance="relevant",
                voice_type="user_voice",
                sentiment=taxonomy.sentiments[0],
                primary_label=primary,
                secondary_label=secondary,
            )
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    analysis = result.items[0].analysis
    assert result.items[0].analysis_status == "succeeded"
    assert isinstance(analysis, ContentLabelAnalysisV3)
    assert analysis.relevance == "relevant"
    assert analysis.voice_type == "user_voice"
    assert PROMPT_VERSION == "content-labeling.v3"
    assert CONTENT_LABELING_PROMPT_PATH.name == "content_labeling_v3.md"

    payload = fake.calls[0].model_payload()[0]
    assert payload == {
        "item_no": 1,
        "title": "爱玛骑了一年，续航还可以",
        "text": "我每天通勤骑，冬天续航会短一些，但总体够用。",
        "author": {
            "display_name": "通勤小林",
            "bio": "分享日常通勤和骑行体验",
            "verification_label": "",
        },
    }


def test_service_accepts_irrelevant_without_forcing_sentiment_or_labels() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    fake = FakeContentLabelingLLM(
        responses=[
            _model_response(
                relevance="irrelevant",
                voice_type="media_information",
                sentiment=None,
            )
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    analysis = result.items[0].analysis
    assert result.items[0].analysis_status == "succeeded"
    assert isinstance(analysis, ContentLabelAnalysisV3)
    assert analysis.relevance == "irrelevant"
    assert analysis.sentiment is None
    assert analysis.labels == ()


def test_offline_labeling_removes_irrelevant_rows_after_durable_checkpoint(tmp_path: Path) -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    source_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(
        source_path,
        (
            _record(_content(external_content_id="relevant-1")),
            _record(
                _content(
                    external_content_id="irrelevant-1",
                    title="爱玛是一个人的名字",
                    text="这篇文章讨论的是同名人物，与电动车品牌没有关系。",
                )
            ),
        ),
    )
    fake = FakeContentLabelingLLM(
        responses=[
            _model_response(
                relevance="relevant",
                voice_type="user_voice",
                sentiment=taxonomy.sentiments[0],
                primary_label=primary,
                secondary_label=secondary,
            ),
            _model_response(
                relevance="irrelevant",
                voice_type="media_information",
                sentiment=None,
            ),
        ]
    )
    service = ContentLabelingService(prompt_loader=loader, llm=fake)

    summary = label_unified_content_jsonl(
        input_path=source_path,
        analysis_dir=analysis_dir,
        service=service,
        max_validation_retries=0,
        max_concurrency=1,
        recovery_taxonomy=taxonomy,
    )

    assert summary.rows_seen == 2
    assert summary.rows_succeeded == 2
    assert summary.rows_irrelevant_removed == 1
    records = [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record.content.external_content_id for record in records] == ["relevant-1"]
    assert isinstance(records[0].analysis, ContentLabelAnalysisV3)
    assert records[0].analysis.is_relevant is True

    checkpoints = [
        json.loads(line)
        for line in (analysis_dir / "checkpoints.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(checkpoints) == 2
    by_content_id = {item["external_content_id"]: item["analysis"] for item in checkpoints}
    assert by_content_id["relevant-1"]["relevance"] == "relevant"
    assert by_content_id["irrelevant-1"]["relevance"] == "irrelevant"


def test_irrelevant_checkpoint_recovers_without_second_llm_call_after_atomic_rewrite_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    source_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(
        source_path,
        (
            _record(_content(external_content_id="recover-relevant")),
            _record(_content(external_content_id="recover-irrelevant")),
        ),
    )
    first_fake = FakeContentLabelingLLM(
        responses=[
            _model_response(
                relevance="relevant",
                voice_type="user_voice",
                sentiment=taxonomy.sentiments[0],
                primary_label=primary,
                secondary_label=secondary,
            ),
            _model_response(
                relevance="irrelevant",
                voice_type="unknown",
                sentiment=None,
            ),
        ]
    )
    original_replace = offline_labeling.os.replace
    monkeypatch.setattr(
        offline_labeling.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("simulated replace crash")),
    )
    with pytest.raises(RuntimeError, match="simulated replace crash"):
        label_unified_content_jsonl(
            input_path=source_path,
            analysis_dir=analysis_dir,
            service=ContentLabelingService(prompt_loader=loader, llm=first_fake),
            max_validation_retries=0,
            max_concurrency=1,
            recovery_taxonomy=taxonomy,
        )
    assert len(first_fake.calls) == 2
    assert len(source_path.read_text(encoding="utf-8").splitlines()) == 2
    assert len((analysis_dir / "checkpoints.jsonl").read_text(encoding="utf-8").splitlines()) == 2

    monkeypatch.setattr(offline_labeling.os, "replace", original_replace)
    recovery_fake = FakeContentLabelingLLM(responses=[])
    summary = label_unified_content_jsonl(
        input_path=source_path,
        analysis_dir=analysis_dir,
        service=ContentLabelingService(prompt_loader=loader, llm=recovery_fake),
        max_validation_retries=0,
        max_concurrency=1,
        recovery_taxonomy=taxonomy,
    )

    assert recovery_fake.calls == []
    assert summary.rows_recovered == 2
    assert summary.rows_succeeded == 0
    assert summary.rows_irrelevant_removed == 1
    records = [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record.content.external_content_id for record in records] == ["recover-relevant"]

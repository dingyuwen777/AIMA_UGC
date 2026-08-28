"""Analysis V3 持久化模型保留相关性、发声类型与全部有序标签。"""

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.contracts.analysis import ContentLabelAnalysisV3, ContentLabelPairV2
from aima_ugc.modules.analysis.persistence import AnalysisContentResult


def test_analysis_persistence_model_preserves_relevance_voice_and_ordered_labels() -> None:
    content_id = uuid4()
    job_id = uuid4()
    analysis = ContentLabelAnalysisV3(
        relevance="relevant",
        voice_type="真实用户发声",
        sentiment="负面",
        labels=(
            ContentLabelPairV2(primary_label="产品体验", secondary_label="续航表现"),
            ContentLabelPairV2(primary_label="服务体验", secondary_label="门店服务"),
        ),
        prompt_version="v3",
        prompt_sha256="a" * 64,
        taxonomy_sha256="b" * 64,
        model_provider="fake",
        model="fake-v1",
        input_hash="c" * 64,
        analyzed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    result = AnalysisContentResult.from_analysis(
        result_id=uuid4(),
        content_id=content_id,
        content_version=3,
        analysis_run_id=uuid4(),
        job_id=job_id,
        generation_config_hash="d" * 64,
        analysis=analysis,
    )

    assert result.content_id == content_id
    assert result.content_version == 3
    assert result.job_id == job_id
    assert result.relevance == "relevant"
    assert result.voice_type == "真实用户发声"
    assert result.sentiment == "负面"
    assert [(item.primary_label, item.secondary_label) for item in result.labels] == [
        ("产品体验", "续航表现"),
        ("服务体验", "门店服务"),
    ]

from __future__ import annotations

import json
from pathlib import Path

from aima_ugc.bootstrap.analysis_taxonomy_http import (
    install_content_analysis_taxonomy_route,
)
from aima_ugc.bootstrap.api import create_app as create_base_app
from aima_ugc.entrypoints.api_main import create_app
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PromptTaxonomyLoader
from aima_ugc.platform.health import ReadinessReport
from fastapi.testclient import TestClient


def _readiness() -> ReadinessReport:
    return ReadinessReport(database="ok", artifact_store="ok", log_directory="ok")


def test_analysis_taxonomy_returns_safe_prompt_projection() -> None:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    response = TestClient(create_app(readiness_check=_readiness)).get(
        "/api/v1/content-analysis-taxonomy"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "prompt_version": taxonomy.prompt_version,
        "prompt_sha256": taxonomy.prompt_sha256,
        "schema_version": taxonomy.schema_version,
        "taxonomy_sha256": taxonomy.taxonomy_sha256,
        "sentiments": list(taxonomy.sentiments),
        "voice_types": list(taxonomy.voice_types),
        "labels": [
            {
                "primary_label": primary,
                "secondary_labels": list(taxonomy.labels[primary]),
            }
            for primary in taxonomy.primary_labels
        ],
    }
    assert taxonomy.prompt_text not in response.text
    for forbidden in ("prompt_text", "base_url", "api_key", "model_provider", "generation_config"):
        assert forbidden not in payload


def test_analysis_taxonomy_fails_closed_with_unified_error(
    tmp_path: Path,
) -> None:
    invalid_prompt = tmp_path / "invalid-taxonomy.md"
    invalid_prompt.write_text("缺少机器 Taxonomy 标记", encoding="utf-8")
    application = create_base_app(readiness_check=_readiness)
    install_content_analysis_taxonomy_route(
        application,
        taxonomy_loader=PromptTaxonomyLoader(invalid_prompt),
    )

    response = TestClient(application, raise_server_exceptions=False).get(
        "/api/v1/content-analysis-taxonomy"
    )

    assert response.status_code == 503
    assert response.json() == {
        "type": "https://aima.example/problems/content_analysis_taxonomy_unavailable",
        "title": "AI 分类配置暂不可用",
        "status": 503,
        "detail": "当前 Prompt Taxonomy 无法安全读取或校验。",
        "request_id": response.headers["x-request-id"],
        "errors": [
            {
                "field": "taxonomy",
                "code": "content_analysis_taxonomy_unavailable",
                "message": "请检查服务端 Prompt Taxonomy 配置和日志。",
            }
        ],
    }


def test_analysis_taxonomy_fails_closed_when_http_projection_is_invalid(
    tmp_path: Path,
) -> None:
    primary_label = "过长标签" * 65
    prompt = tmp_path / "projection-invalid-taxonomy.md"
    prompt.write_text(
        "\n".join(
            (
                "# 测试 Prompt",
                "<!-- AIMA_TAXONOMY_START -->",
                "```json",
                json.dumps(
                    {
                        "schema_version": "aima-content-taxonomy.v2",
                        "sentiments": ["中性"],
                        "voice_types": ["真实用户发声"],
                        "labels": {primary_label: ["测试二级标签"]},
                    },
                    ensure_ascii=False,
                ),
                "```",
                "<!-- AIMA_TAXONOMY_END -->",
            )
        ),
        encoding="utf-8",
    )
    application = create_base_app(readiness_check=_readiness)
    install_content_analysis_taxonomy_route(
        application,
        taxonomy_loader=PromptTaxonomyLoader(prompt),
    )

    response = TestClient(application, raise_server_exceptions=False).get(
        "/api/v1/content-analysis-taxonomy"
    )

    assert response.status_code == 503
    assert response.json()["errors"] == [
        {
            "field": "taxonomy",
            "code": "content_analysis_taxonomy_unavailable",
            "message": "请检查服务端 Prompt Taxonomy 配置和日志。",
        }
    ]

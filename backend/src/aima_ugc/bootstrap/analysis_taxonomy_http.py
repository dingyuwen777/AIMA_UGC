"""当前 Prompt Taxonomy 的安全只读 HTTP 装配。"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import ValidationError

from aima_ugc.contracts.http import (
    ContentAnalysisTaxonomyLabelResponse,
    ContentAnalysisTaxonomyResponse,
)
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    PromptTaxonomyError,
    PromptTaxonomyLoader,
)


class ContentAnalysisTaxonomyUnavailable(RuntimeError):
    """当前 Prompt Taxonomy 无法形成安全只读投影。"""


def content_analysis_taxonomy_response(
    taxonomy_loader: PromptTaxonomyLoader,
) -> ContentAnalysisTaxonomyResponse:
    """读取唯一 Prompt 事实源，并只返回页面需要的分类目录。"""

    taxonomy = taxonomy_loader.load()
    return ContentAnalysisTaxonomyResponse(
        prompt_version=taxonomy.prompt_version,
        prompt_sha256=taxonomy.prompt_sha256,
        schema_version=taxonomy.schema_version,
        taxonomy_sha256=taxonomy.taxonomy_sha256,
        sentiments=taxonomy.sentiments,
        voice_types=taxonomy.voice_types,
        labels=tuple(
            ContentAnalysisTaxonomyLabelResponse(
                primary_label=primary,
                secondary_labels=taxonomy.labels[primary],
            )
            for primary in taxonomy.primary_labels
        ),
    )


def install_content_analysis_taxonomy_route(
    application: FastAPI,
    *,
    taxonomy_loader: PromptTaxonomyLoader | None = None,
) -> None:
    """把当前 Prompt Taxonomy 的安全只读端点安装到最终 API。"""

    loader = taxonomy_loader or PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)

    @application.get(
        "/api/v1/content-analysis-taxonomy",
        operation_id="getContentAnalysisTaxonomy",
        response_model=ContentAnalysisTaxonomyResponse,
        tags=["contents"],
    )
    def get_content_analysis_taxonomy() -> ContentAnalysisTaxonomyResponse:
        try:
            return content_analysis_taxonomy_response(loader)
        except (PromptTaxonomyError, ValidationError) as exc:
            raise ContentAnalysisTaxonomyUnavailable from exc


__all__ = [
    "ContentAnalysisTaxonomyUnavailable",
    "content_analysis_taxonomy_response",
    "install_content_analysis_taxonomy_route",
]

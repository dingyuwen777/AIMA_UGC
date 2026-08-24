"""Analysis Owner 的人工相关性复核 PostgreSQL Repository。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.relevance_review import (
    ContentRelevanceReviewConflict,
    ContentRelevanceReviewWriteSummary,
)
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.tables import analysis_content_results_table
from aima_ugc.modules.content.tables import contents_table


class PostgresContentRelevanceReviewRepository:
    """原子验证当前版本的 AI irrelevant，并保存幂等人工 relevant 决定。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def review_irrelevant_as_relevant(
        self,
        *,
        content_ids: tuple[UUID, ...],
        analysis_identity: AnalysisConfigurationIdentity | None,
        request_id: str,
    ) -> ContentRelevanceReviewWriteSummary:
        if not content_ids:
            raise ValueError("人工相关性复核至少需要一个 Content")
        if len(content_ids) != len(set(content_ids)):
            raise ValueError("人工相关性复核 Content ID 不得重复")
        if not request_id:
            raise ValueError("人工相关性复核 request_id 不能为空")

        content_rows = tuple(
            self._session.execute(
                select(contents_table.c.id, contents_table.c.current_version)
                .where(contents_table.c.id.in_(content_ids))
                .order_by(contents_table.c.id)
                .with_for_update()
            ).mappings()
        )
        if len(content_rows) != len(content_ids):
            raise ContentRelevanceReviewConflict

        current_versions: dict[UUID, int] = {
            cast(UUID, row["id"]): cast(int, row["current_version"]) for row in content_rows
        }
        existing_rows = tuple(
            self._session.execute(
                select(
                    analysis_content_relevance_reviews_table.c.content_id,
                    analysis_content_relevance_reviews_table.c.content_version,
                ).where(analysis_content_relevance_reviews_table.c.content_id.in_(content_ids))
            ).mappings()
        )
        already_reviewed: set[UUID] = {
            cast(UUID, row["content_id"])
            for row in existing_rows
            if current_versions.get(cast(UUID, row["content_id"]))
            == cast(int, row["content_version"])
        }
        to_review = tuple(
            content_id for content_id in content_ids if content_id not in already_reviewed
        )

        if to_review:
            if analysis_identity is None:
                raise ContentRelevanceReviewConflict
            result = analysis_content_results_table
            result_rows = tuple(
                self._session.execute(
                    select(
                        result.c.content_id,
                        result.c.content_version,
                        result.c.relevance,
                        result.c.analyzed_at,
                        result.c.id,
                    )
                    .where(
                        result.c.content_id.in_(to_review),
                        result.c.prompt_version == analysis_identity.prompt_version,
                        result.c.prompt_sha256 == analysis_identity.prompt_sha256,
                        result.c.taxonomy_sha256 == analysis_identity.taxonomy_sha256,
                        result.c.model_provider == analysis_identity.model_provider,
                        result.c.model == analysis_identity.model,
                    )
                    .order_by(
                        result.c.content_id,
                        result.c.analyzed_at.desc(),
                        result.c.id.desc(),
                    )
                ).mappings()
            )
            latest_by_content: dict[UUID, RowMapping] = {}
            for row in result_rows:
                latest_by_content.setdefault(cast(UUID, row["content_id"]), row)
            for content_id in to_review:
                row = latest_by_content.get(content_id)
                if row is None:
                    raise ContentRelevanceReviewConflict
                current_version = current_versions[content_id]
                if (
                    cast(int, row["content_version"]) != current_version
                    or cast(str, row["relevance"]) != "irrelevant"
                ):
                    raise ContentRelevanceReviewConflict

            reviewed_at = datetime.now(UTC)
            self._session.execute(
                insert(analysis_content_relevance_reviews_table),
                [
                    {
                        "id": uuid4(),
                        "content_id": content_id,
                        "content_version": current_versions[content_id],
                        "decision": "relevant",
                        "request_id": request_id,
                        "reviewed_at": reviewed_at,
                    }
                    for content_id in to_review
                ],
            )

        return ContentRelevanceReviewWriteSummary(
            requested_count=len(content_ids),
            reviewed_count=len(to_review),
            already_reviewed_count=len(already_reviewed),
        )


__all__ = ["PostgresContentRelevanceReviewRepository"]

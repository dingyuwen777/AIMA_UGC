"""Analysis Owner 的人工相关性复核 PostgreSQL Repository。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
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

ReviewDecision = Literal["relevant", "irrelevant", "inherit_ai"]
_OVERRIDE_DECISIONS = frozenset({"relevant", "irrelevant"})


class PostgresContentRelevanceReviewRepository:
    """原子保存双向人工相关性覆盖或撤销事件，不改写 AI 原始结果。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def review_relevance(
        self,
        *,
        content_ids: tuple[UUID, ...],
        decision: ReviewDecision,
        analysis_identity: AnalysisConfigurationIdentity | None,
        request_id: str,
    ) -> ContentRelevanceReviewWriteSummary:
        if not content_ids:
            raise ValueError("人工相关性复核至少需要一个 Content")
        if len(content_ids) != len(set(content_ids)):
            raise ValueError("人工相关性复核 Content ID 不得重复")
        if decision not in {"relevant", "irrelevant", "inherit_ai"}:
            raise ValueError("人工相关性复核 decision 不合法")
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
        review = analysis_content_relevance_reviews_table
        review_rows = tuple(
            self._session.execute(
                select(
                    review.c.id,
                    review.c.content_id,
                    review.c.content_version,
                    review.c.analysis_result_id,
                    review.c.review_no,
                    review.c.decision,
                )
                .where(review.c.content_id.in_(content_ids))
                .order_by(
                    review.c.content_id,
                    review.c.content_version,
                    review.c.review_no.desc(),
                    review.c.reviewed_at.desc(),
                    review.c.id.desc(),
                )
            ).mappings()
        )
        latest_review_by_content: dict[UUID, RowMapping] = {}
        for row in review_rows:
            content_id = cast(UUID, row["content_id"])
            if cast(int, row["content_version"]) != current_versions.get(content_id):
                continue
            latest_review_by_content.setdefault(content_id, row)

        needs_ai_result: list[UUID] = []
        for content_id in content_ids:
            latest = latest_review_by_content.get(content_id)
            latest_decision = cast(str, latest["decision"]) if latest is not None else None
            active_override = latest_decision if latest_decision in _OVERRIDE_DECISIONS else None
            if decision == "inherit_ai":
                continue
            if active_override is None:
                needs_ai_result.append(content_id)

        current_ai_by_content: dict[UUID, RowMapping] = {}
        if needs_ai_result:
            if analysis_identity is None:
                raise ContentRelevanceReviewConflict
            result = analysis_content_results_table
            result_rows = tuple(
                self._session.execute(
                    select(
                        result.c.id,
                        result.c.content_id,
                        result.c.content_version,
                        result.c.relevance,
                        result.c.analyzed_at,
                    )
                    .where(
                        result.c.content_id.in_(needs_ai_result),
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
            for row in result_rows:
                content_id = cast(UUID, row["content_id"])
                current_ai_by_content.setdefault(content_id, row)

        planned_events: list[dict[str, object]] = []
        unchanged_count = 0
        reviewed_at = datetime.now(UTC)
        for content_id in content_ids:
            latest = latest_review_by_content.get(content_id)
            latest_decision = cast(str, latest["decision"]) if latest is not None else None
            active_override = latest_decision if latest_decision in _OVERRIDE_DECISIONS else None
            next_review_no = cast(int, latest["review_no"]) + 1 if latest is not None else 1

            if decision == "inherit_ai":
                if active_override is None or latest is None:
                    unchanged_count += 1
                    continue
                analysis_result_id = cast(UUID, latest["analysis_result_id"])
            elif active_override is not None:
                if active_override == decision:
                    unchanged_count += 1
                    continue
                raise ContentRelevanceReviewConflict
            else:
                current_result = current_ai_by_content.get(content_id)
                if current_result is None:
                    raise ContentRelevanceReviewConflict
                if cast(int, current_result["content_version"]) != current_versions[content_id]:
                    raise ContentRelevanceReviewConflict
                if cast(str, current_result["relevance"]) == decision:
                    unchanged_count += 1
                    continue
                analysis_result_id = cast(UUID, current_result["id"])

            planned_events.append(
                {
                    "id": uuid4(),
                    "content_id": content_id,
                    "content_version": current_versions[content_id],
                    "analysis_result_id": analysis_result_id,
                    "review_no": next_review_no,
                    "decision": decision,
                    "request_id": request_id,
                    "reviewed_at": reviewed_at,
                }
            )

        if planned_events:
            self._session.execute(insert(review), planned_events)

        return ContentRelevanceReviewWriteSummary(
            requested_count=len(content_ids),
            changed_count=len(planned_events),
            unchanged_count=unchanged_count,
        )


__all__ = ["PostgresContentRelevanceReviewRepository"]

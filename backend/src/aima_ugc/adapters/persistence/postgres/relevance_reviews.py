"""Analysis Owner 的人工相关性复核 PostgreSQL Repository。"""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis_effective import load_effective_analysis
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.relevance_review import (
    ContentRelevanceReviewConflict,
    ContentRelevanceReviewWriteSummary,
)
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.time import beijing_now

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

        del analysis_identity
        current_ai_by_content = load_effective_analysis(self._session, current_versions)
        reviews_by_id = {row["id"]: row for row in review_rows}
        effective_reviews = {
            content_id: reviews_by_id.get(result["relevance_review_id"])
            for content_id, result in current_ai_by_content.items()
        }

        planned_events: list[dict[str, object]] = []
        unchanged_count = 0
        reviewed_at = beijing_now()
        for content_id in content_ids:
            direct_latest = latest_review_by_content.get(content_id)
            latest = effective_reviews.get(content_id)
            latest_decision = cast(str, latest["decision"]) if latest is not None else None
            active_override = latest_decision if latest_decision in _OVERRIDE_DECISIONS else None
            next_review_no = (
                cast(int, direct_latest["review_no"]) + 1 if direct_latest is not None else 1
            )

            if decision == "inherit_ai":
                if active_override is None or latest is None:
                    unchanged_count += 1
                    continue
                analysis_result_id = cast(UUID, current_ai_by_content[content_id]["id"])
            elif active_override is not None:
                if active_override == decision:
                    unchanged_count += 1
                    continue
                raise ContentRelevanceReviewConflict
            else:
                current_result = current_ai_by_content.get(content_id)
                if current_result is None:
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

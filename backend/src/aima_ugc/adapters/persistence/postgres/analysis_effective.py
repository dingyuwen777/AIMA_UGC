"""各读取入口共用明确目标版本的有效 Analysis 来源。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Integer, Uuid, and_, case, column, func, literal, select, true, values
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.manual_override_tables import analysis_content_manual_overrides_table
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_results_table,
    analysis_content_runs_table,
)


def effective_analysis_source(content_id: Any, version: Any, scheme: Any = None) -> Any:
    """数据库规则保证至多一条真实结果；可选 Scheme 只用于已有工作台口径。"""
    return (
        func.effective_analysis_source(content_id, version, scheme)
        .table_valued(
            column("analysis_result_id", Uuid()),
            column("source_content_version", Integer()),
            column("manual_override_version", Integer()),
            column("relevance_review_id", Uuid()),
        )
        .lateral()
    )


def load_effective_analysis(session: Session, versions: dict[UUID, int]) -> dict[UUID, RowMapping]:
    """批量读取冻结目标版本及人工来源，导出和报告不得改用 Current。"""
    if not versions:
        return {}
    targets = (
        values(column("content_id", Uuid()), column("version", Integer()))
        .data(tuple(versions.items()))
        .alias("analysis_targets")
    )
    source = effective_analysis_source(targets.c.content_id, targets.c.version)
    result, run = analysis_content_results_table, analysis_content_runs_table
    manual, review = (
        analysis_content_manual_overrides_table,
        analysis_content_relevance_reviews_table,
    )
    pairs = analysis_content_label_pairs_table
    labels = (
        select(
            func.jsonb_agg(
                aggregate_order_by(
                    func.jsonb_build_object(
                        "primary_label",
                        pairs.c.primary_label,
                        "secondary_label",
                        pairs.c.secondary_label,
                    ),
                    pairs.c.ordinal,
                )
            )
        )
        .where(pairs.c.analysis_result_id == result.c.id)
        .correlate(result)
        .scalar_subquery()
    )
    rows = session.execute(
        select(
            result,
            targets.c.content_id.label("target_content_id"),
            targets.c.version.label("target_content_version"),
            run.c.analysis_scheme_version_id,
            source.c.manual_override_version,
            source.c.relevance_review_id,
            case(
                (review.c.decision.in_(("relevant", "irrelevant")), review.c.decision),
                else_=result.c.relevance,
            ).label("effective_relevance"),
            case(
                (manual.c.voice_type_locked, manual.c.voice_type), else_=result.c.voice_type
            ).label("effective_voice_type"),
            case((manual.c.sentiment_locked, manual.c.sentiment), else_=result.c.sentiment).label(
                "effective_sentiment"
            ),
            case(
                (manual.c.labels_locked, manual.c.labels),
                else_=func.coalesce(labels, literal("[]").cast(manual.c.labels.type)),
            ).label("effective_labels"),
            manual.c.voice_type_locked,
            manual.c.sentiment_locked,
            manual.c.labels_locked,
            case(
                (
                    manual.c.content_version.is_not(None),
                    func.jsonb_build_object(
                        "content_id",
                        manual.c.content_id,
                        "content_version",
                        manual.c.content_version,
                        "voice_type",
                        manual.c.voice_type,
                        "sentiment",
                        manual.c.sentiment,
                        "labels",
                        manual.c.labels,
                        "voice_type_locked",
                        manual.c.voice_type_locked,
                        "sentiment_locked",
                        manual.c.sentiment_locked,
                        "labels_locked",
                        manual.c.labels_locked,
                        "actor_ref",
                        manual.c.actor_ref,
                        "updated_at",
                        manual.c.updated_at,
                    ),
                ),
                else_=None,
            ).label("manual_override"),
        ).select_from(
            targets.join(source, true())
            .join(result, result.c.id == source.c.analysis_result_id)
            .join(run, run.c.id == result.c.analysis_run_id)
            .outerjoin(
                manual,
                and_(
                    manual.c.content_id == targets.c.content_id,
                    manual.c.content_version == source.c.manual_override_version,
                ),
            )
            .outerjoin(review, review.c.id == source.c.relevance_review_id)
        )
    ).mappings()
    return {row["target_content_id"]: row for row in rows}

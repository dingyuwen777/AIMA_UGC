"""Analysis Owner 的确定性输入证明和版本复用写入；不创建模型执行。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import exists, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis import canonical_analysis_content_from_row
from aima_ugc.modules.analysis.content_labeling import content_labeling_input_hash
from aima_ugc.modules.analysis.manual_override_tables import analysis_content_manual_overrides_table
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_results_table,
    analysis_content_runs_table,
    analysis_content_version_reuses_table,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.platform.time import beijing_now

_ALGORITHM = "content-labeling-input-sha256-v1"
_KNOWN_SCHEMAS = frozenset(
    {"content-label-analysis.v1", "content-label-analysis.v2", "content-label-analysis.v3"}
)


@dataclass(frozen=True, slots=True)
class AnalysisContentVersionReusePlan:
    """只读预检结果也用作正式写入依据，避免修复任务另造判定。"""

    content_id: UUID
    target_content_version: int
    reason: str
    input_hash: str | None = None
    source_analysis_result_id: UUID | None = None
    source_content_version: int | None = None
    manual_override_source_version: int | None = None
    relevance_review_source_version: int | None = None


@dataclass(frozen=True, slots=True)
class AnalysisContentVersionReuseOutcome:
    """幂等收敛状态和同一份可审计预检。"""

    plan: AnalysisContentVersionReusePlan
    status: str


class PostgresAnalysisReuseRepository:
    """与 Content/Evidence 使用调用方同一个事务；显式目标页限定所有查询。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def plan_reuses(
        self, pairs: tuple[tuple[UUID, int], ...]
    ) -> tuple[AnalysisContentVersionReusePlan, ...]:
        """只读批量证明：实际成功 Hash 必须等于源不可变快照和目标输入的生产 Hash。"""
        pairs = tuple(dict.fromkeys(pairs))
        if not pairs:
            return ()
        ids = tuple(sorted({pair[0] for pair in pairs}))
        versions = self._version_inputs(ids)
        hashes = {
            key: content_labeling_input_hash(
                canonical_analysis_content_from_row(row, model_input_only=True)
            )
            for key, row in versions.items()
        }
        result, run, reuse = (
            analysis_content_results_table,
            analysis_content_runs_table,
            analysis_content_version_reuses_table,
        )
        # Content 前缀索引限定页内历史，且只取与该页目标 Hash 相等的成功结果。
        target_hashes = tuple({hashes[pair] for pair in pairs if pair in hashes})
        rows = tuple(
            self._session.execute(
                select(result, run.c.sequence_no)
                .join(run, run.c.id == result.c.analysis_run_id)
                .where(
                    result.c.content_id.in_(ids),
                    or_(
                        result.c.input_hash.in_(target_hashes),
                        tuple_(result.c.content_id, result.c.content_version).in_(pairs),
                    ),
                )
                .order_by(run.c.sequence_no.desc(), result.c.id.desc())
            ).mappings()
        )
        any_success = set(
            self._session.scalars(
                select(contents_table.c.id).where(
                    contents_table.c.id.in_(ids),
                    exists(select(result.c.id).where(result.c.content_id == contents_table.c.id)),
                )
            )
        )
        relations = {
            (row["content_id"], row["target_content_version"]): row
            for row in self._session.execute(
                select(reuse).where(reuse.c.content_id.in_(ids))
            ).mappings()
        }
        manuals = {
            tuple(row)
            for row in self._session.execute(
                select(
                    analysis_content_manual_overrides_table.c.content_id,
                    analysis_content_manual_overrides_table.c.content_version,
                ).where(analysis_content_manual_overrides_table.c.content_id.in_(ids))
            )
        }
        reviews = {
            tuple(row)
            for row in self._session.execute(
                select(
                    analysis_content_relevance_reviews_table.c.content_id,
                    analysis_content_relevance_reviews_table.c.content_version,
                ).where(analysis_content_relevance_reviews_table.c.content_id.in_(ids))
            )
        }
        plans = []
        for content_id, target in pairs:
            key = content_id, target
            target_hash = hashes.get(key)
            base: dict[str, Any] = {
                "content_id": content_id,
                "target_content_version": target,
                "input_hash": target_hash,
            }
            if target_hash is None:
                plans.append(AnalysisContentVersionReusePlan(**base, reason="target_missing"))
                continue
            matching = [
                row
                for row in rows
                if row["content_id"] == content_id and row["input_hash"] == target_hash
            ]
            direct = next(
                (
                    row
                    for row in rows
                    if row["content_id"] == content_id and row["content_version"] == target
                ),
                None,
            )
            if direct is not None:
                plans.append(
                    AnalysisContentVersionReusePlan(
                        **base,
                        reason="direct",
                        source_analysis_result_id=direct["id"],
                        source_content_version=target,
                    )
                )
                continue
            valid = [
                row
                for row in matching
                if row["content_version"] < target
                and row["schema_version"] in _KNOWN_SCHEMAS
                and hashes.get((content_id, row["content_version"])) == row["input_hash"]
            ]
            existing = relations.get(key)
            source = next(
                (
                    row
                    for row in valid
                    if existing is not None and row["id"] == existing["source_analysis_result_id"]
                ),
                valid[0] if valid else None,
            )
            if source is None:
                reason = (
                    "unknown_protocol"
                    if matching
                    else ("input_mismatch" if content_id in any_success else "no_success")
                )
                plans.append(AnalysisContentVersionReusePlan(**base, reason=reason))
                continue
            compatible_versions = {cast(int, row["content_version"]) for row in valid}
            compatible_versions.update(
                version
                for (cid, version), relation in relations.items()
                if cid == content_id
                and version < target
                and relation["input_hash"] == target_hash
                and any(row["id"] == relation["source_analysis_result_id"] for row in valid)
            )
            manual_source = review_source = None
            for version in sorted(compatible_versions, reverse=True):
                relation = relations.get((content_id, version))
                if manual_source is None:
                    manual_source = (
                        version
                        if (content_id, version) in manuals
                        else (relation["manual_override_source_version"] if relation else None)
                    )
                if review_source is None:
                    review_source = (
                        version
                        if (content_id, version) in reviews
                        else (relation["relevance_review_source_version"] if relation else None)
                    )
            plans.append(
                AnalysisContentVersionReusePlan(
                    **base,
                    reason="equivalent",
                    source_analysis_result_id=source["id"],
                    source_content_version=source["content_version"],
                    manual_override_source_version=manual_source,
                    relevance_review_source_version=review_source,
                )
            )
        return tuple(plans)

    def converge_reuses(
        self, pairs: tuple[tuple[UUID, int], ...]
    ) -> tuple[AnalysisContentVersionReuseOutcome, ...]:
        """Content UUID 锁后重算证明并幂等插入，失败由调用方整事务回滚。"""
        if not pairs:
            return ()
        current = {
            cast(UUID, row[0]): cast(int, row[1])
            for row in self._session.execute(
                select(contents_table.c.id, contents_table.c.current_version)
                .where(contents_table.c.id.in_(tuple({pair[0] for pair in pairs})))
                .order_by(contents_table.c.id)
                .with_for_update()
            )
        }
        plans = self.plan_reuses(pairs)
        applicable = [
            plan
            for plan in plans
            if plan.reason == "equivalent"
            and current.get(plan.content_id) == plan.target_content_version
        ]
        inserted = set()
        if applicable:
            table = analysis_content_version_reuses_table
            inserted = set(
                self._session.execute(
                    pg_insert(table)
                    .values(
                        [
                            {
                                "content_id": plan.content_id,
                                "target_content_version": plan.target_content_version,
                                "source_analysis_result_id": plan.source_analysis_result_id,
                                "source_content_version": plan.source_content_version,
                                "input_hash": plan.input_hash,
                                "input_hash_algorithm": _ALGORITHM,
                                "manual_override_source_version": (
                                    plan.manual_override_source_version
                                ),
                                "relevance_review_source_version": (
                                    plan.relevance_review_source_version
                                ),
                                "created_at": beijing_now(),
                            }
                            for plan in applicable
                        ]
                    )
                    .on_conflict_do_nothing()
                    .returning(table.c.content_id, table.c.target_content_version)
                ).all()
            )
        return tuple(
            AnalysisContentVersionReuseOutcome(
                plan,
                "inserted"
                if (plan.content_id, plan.target_content_version) in inserted
                else "existing"
                if plan.reason == "direct" or plan in applicable
                else "rejected",
            )
            for plan in plans
        )

    def _version_inputs(self, content_ids: tuple[UUID, ...]) -> dict[tuple[UUID, int], RowMapping]:
        version, content = content_versions_table, contents_table
        attempt, request = provider_request_attempts_table, provider_requests_table
        rows = self._session.execute(
            select(
                version,
                version.c.status.label("content_status"),
                content.c.platform,
                content.c.external_content_id,
                request.c.provider,
                request.c.operation,
                request.c.id.label("provider_request_id"),
            )
            .select_from(
                version.join(content, content.c.id == version.c.content_id)
                .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                .join(request, request.c.id == attempt.c.provider_request_id)
            )
            .where(version.c.content_id.in_(content_ids))
        ).mappings()
        return {(row["content_id"], row["version_no"]): row for row in rows}

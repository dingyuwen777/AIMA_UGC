"""为 Stage 8F 双向人工相关性复核 Golden Path 建立真实数据库前置事实。"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.analysis import PostgresAnalysisRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.analysis_identity import (
    active_analysis_configuration,
    current_analysis_generation_config,
)
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3, ContentLabelPairV2
from aima_ugc.contracts.http import KeywordPackCreateRequest, KeywordPackKeywordCreateRequest
from aima_ugc.modules.analysis import content_labeling_input_hash
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    ContentAnalysisJobPayload,
)
from aima_ugc.modules.analysis.tables import analysis_content_run_targets_table
from aima_ugc.modules.content.query import ContentTarget
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs import JobExecutionFence
from sqlalchemy import insert, select

_IRRELEVANT_EXTERNAL_CONTENT_ID = "stage8f-manual-review-content-1"
_RELEVANT_EXTERNAL_CONTENT_ID = "stage8f-manual-review-content-2"
_EXPECTED_EXTERNAL_IDS = (
    _IRRELEVANT_EXTERNAL_CONTENT_ID,
    _RELEVANT_EXTERNAL_CONTENT_ID,
)


def _analysis_for(
    *,
    content_id: UUID,
    irrelevant_content_id: UUID,
    identity,
    input_hash: str,
) -> ContentLabelAnalysisV3:  # type: ignore[no-untyped-def]
    if content_id == irrelevant_content_id:
        return ContentLabelAnalysisV3(
            relevance="irrelevant",
            voice_type="媒体机构发声",
            sentiment=None,
            labels=(),
            prompt_version=identity.prompt_version,
            prompt_sha256=identity.prompt_sha256,
            taxonomy_sha256=identity.taxonomy_sha256,
            model_provider=identity.model_provider,
            model=identity.model,
            input_hash=input_hash,
            analyzed_at=datetime.now(UTC),
        )
    return ContentLabelAnalysisV3(
        relevance="relevant",
        voice_type="真实用户发声",
        sentiment="中性",
        labels=(ContentLabelPairV2(primary_label="骑行性能", secondary_label="舒适性"),),
        prompt_version=identity.prompt_version,
        prompt_sha256=identity.prompt_sha256,
        taxonomy_sha256=identity.taxonomy_sha256,
        model_provider=identity.model_provider,
        model=identity.model,
        input_hash=input_hash,
        analyzed_at=datetime.now(UTC),
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(
            "用法: python tests/fullstack/seed_stage8f_manual_relevance_review.py <fixture.xlsx>"
        )
    fixture = Path(sys.argv[1])
    if not fixture.is_file():
        raise FileNotFoundError(fixture)

    runtime = create_worker_runtime()
    try:
        import_service = PostgresImportHttpService(runtime)
        pack = import_service.create_keyword_pack(
            KeywordPackCreateRequest(name=f"Stage8F 人工复核 {uuid4()}")
        )
        import_service.add_keyword(
            pack.id,
            KeywordPackKeywordCreateRequest(text="爱玛", priority=10),
        )
        created = import_service.create_import(
            filename=fixture.name,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            source=BytesIO(fixture.read_bytes()),
            keyword_pack_ids=(pack.id,),
            request_id="stage8f-manual-review-import",
        )
        import_worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage8f-manual-review-import",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        if not import_worker.run_once():
            raise RuntimeError("Stage8F 人工复核前置 Excel Import Job 未被执行")

        generation_config, generation_config_hash = current_analysis_generation_config()

        session = runtime.database.new_session()
        try:
            with session.begin():
                identity = active_analysis_configuration(session, runtime.settings).identity
                if identity is None:
                    raise RuntimeError("Stage8F 人工复核必须配置测试 Analysis identity")
                rows = tuple(
                    session.execute(
                        select(
                            contents_table.c.id,
                            contents_table.c.current_version,
                            contents_table.c.external_content_id,
                        )
                        .where(contents_table.c.external_content_id.in_(_EXPECTED_EXTERNAL_IDS))
                        .order_by(contents_table.c.external_content_id)
                    )
                )
                if len(rows) != 2:
                    raise RuntimeError("Stage8F 双向人工复核前置 Content 数量异常")
                by_external_id = {row.external_content_id: row for row in rows}
                irrelevant_content_id = by_external_id[_IRRELEVANT_EXTERNAL_CONTENT_ID].id
                relevant_content_id = by_external_id[_RELEVANT_EXTERNAL_CONTENT_ID].id
                analysis_request_id = uuid4()
                analysis_run_id = uuid4()
                job = PostgresJobRepository(session).enqueue(
                    job_type=CONTENT_ANALYSIS_JOB_TYPE,
                    payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
                    payload=ContentAnalysisJobPayload(
                        request_id=analysis_request_id,
                        run_id=analysis_run_id,
                        shard_no=0,
                    ).model_dump(mode="json"),
                    internal_idempotency_key=f"stage8f-manual-review:{analysis_request_id}",
                    request_id="stage8f-manual-review-analysis",
                    priority=0,
                    max_attempts=CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
                    timeout_seconds=CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
                )
                repository = PostgresAnalysisRepository(session)
                repository.create_run_header(
                    run_id=analysis_run_id,
                    client_idempotency_key=f"stage8f-manual-review:{analysis_run_id}",
                    planner_job_id=job.id,
                    run_intent="initial_analysis",
                    scope="selected",
                    filter_snapshot={
                        "content_ids": [str(irrelevant_content_id), str(relevant_content_id)]
                    },
                    target_count=2,
                    shard_count=1,
                    shard_size=2,
                    identity=identity,
                    generation_config=generation_config,
                    generation_config_hash=generation_config_hash,
                )
                session.execute(
                    insert(analysis_content_run_targets_table),
                    [
                        {
                            "run_id": analysis_run_id,
                            "target_ordinal": ordinal,
                            "content_id": row.id,
                            "content_version": row.current_version,
                        }
                        for ordinal, row in enumerate(rows)
                    ],
                )
                repository.create_request(
                    request_id=analysis_request_id,
                    run_id=analysis_run_id,
                    shard_no=0,
                    job_id=job.id,
                    scope="selected",
                    filter_snapshot={
                        "content_ids": [str(irrelevant_content_id), str(relevant_content_id)]
                    },
                    targets=tuple(
                        ContentTarget(content_id=row.id, content_version=row.current_version)
                        for row in rows
                    ),
                )
        finally:
            session.close()

        claim_session = runtime.database.new_session()
        try:
            with claim_session.begin():
                claimed = PostgresJobRepository(claim_session).claim_next(
                    supported_job_types=(CONTENT_ANALYSIS_JOB_TYPE,),
                    worker_id="stage8f-manual-review-analysis",
                    lease_seconds=120,
                )
                if claimed is None or claimed.lease_token is None:
                    raise RuntimeError("Stage8F 人工复核前置 Analysis Job 无法认领")
                fence = JobExecutionFence(
                    job_id=claimed.id,
                    lease_token=claimed.lease_token,
                )
        finally:
            claim_session.close()

        persist_session = runtime.database.new_session()
        try:
            with persist_session.begin():
                repository = PostgresAnalysisRepository(persist_session)
                pending = repository.load_pending(analysis_request_id, limit=10)
                if len(pending) != 2:
                    raise RuntimeError("Stage8F 双向人工复核前置 Analysis Target 数量异常")
                for work_item in pending:
                    repository.persist_success(
                        fence=fence,
                        work_item=work_item,
                        analysis=_analysis_for(
                            content_id=work_item.content_id,
                            irrelevant_content_id=irrelevant_content_id,
                            identity=identity,
                            input_hash=content_labeling_input_hash(work_item.content),
                        ),
                    )
                PostgresJobRepository(persist_session).succeed(
                    job_id=fence.job_id,
                    lease_token=fence.lease_token,
                    result={
                        "request_id": str(analysis_request_id),
                        "succeeded": 2,
                        "failed": 0,
                        "stale": 0,
                    },
                )
                repository.refresh_run(analysis_run_id)
        finally:
            persist_session.close()

        print(str(irrelevant_content_id))
        print(str(relevant_content_id))
        print(str(created.batch_id))
        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())

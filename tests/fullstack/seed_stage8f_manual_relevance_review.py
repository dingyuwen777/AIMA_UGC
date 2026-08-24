"""为 Stage 8F 人工相关性复核 Golden Path 建立真实数据库前置事实。"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from aima_ugc.adapters.persistence.postgres.analysis import PostgresAnalysisRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.analysis_identity import current_analysis_identity
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.contracts.http import KeywordPackCreateRequest, KeywordPackKeywordCreateRequest
from aima_ugc.modules.analysis import content_labeling_input_hash
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    ContentAnalysisJobPayload,
)
from aima_ugc.modules.content.query import ContentTarget
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs import JobExecutionFence

_EXTERNAL_CONTENT_ID = "stage8f-manual-review-content-1"


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

        session = runtime.database.new_session()
        try:
            with session.begin():
                content_row = session.execute(
                    select(contents_table.c.id, contents_table.c.current_version).where(
                        contents_table.c.external_content_id == _EXTERNAL_CONTENT_ID
                    )
                ).one()
                content_id = content_row.id
                content_version = content_row.current_version
                analysis_request_id = uuid4()
                job = PostgresJobRepository(session).enqueue(
                    job_type=CONTENT_ANALYSIS_JOB_TYPE,
                    payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
                    payload=ContentAnalysisJobPayload(request_id=analysis_request_id).model_dump(
                        mode="json"
                    ),
                    internal_idempotency_key=f"stage8f-manual-review:{content_id}",
                    request_id="stage8f-manual-review-analysis",
                    priority=0,
                    max_attempts=CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
                    timeout_seconds=CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
                )
                PostgresAnalysisRepository(session).create_request(
                    request_id=analysis_request_id,
                    job_id=job.id,
                    scope="selected",
                    filter_snapshot={"content_ids": [str(content_id)]},
                    targets=(
                        ContentTarget(
                            content_id=content_id,
                            content_version=content_version,
                        ),
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

        identity = current_analysis_identity(runtime.settings)
        if identity is None:
            raise RuntimeError("Stage8F 人工复核必须配置测试 Analysis identity")
        persist_session = runtime.database.new_session()
        try:
            with persist_session.begin():
                repository = PostgresAnalysisRepository(persist_session)
                pending = repository.load_pending(analysis_request_id, limit=10)
                if len(pending) != 1:
                    raise RuntimeError("Stage8F 人工复核前置 Analysis Target 数量异常")
                repository.persist_success(
                    fence=fence,
                    work_item=pending[0],
                    analysis=ContentLabelAnalysisV3(
                        relevance="irrelevant",
                        voice_type="media_information",
                        sentiment=None,
                        labels=(),
                        prompt_version=identity.prompt_version,
                        prompt_sha256=identity.prompt_sha256,
                        taxonomy_sha256=identity.taxonomy_sha256,
                        model_provider=identity.model_provider,
                        model=identity.model,
                        input_hash=content_labeling_input_hash(pending[0].content),
                        analyzed_at=datetime.now(UTC),
                    ),
                )
                PostgresJobRepository(persist_session).succeed(
                    job_id=fence.job_id,
                    lease_token=fence.lease_token,
                    result={
                        "request_id": str(analysis_request_id),
                        "succeeded": 1,
                        "failed": 0,
                        "stale": 0,
                    },
                )
        finally:
            persist_session.close()

        print(str(content_id))
        print(str(created.batch_id))
        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""报告预检、完整快照、下载与恢复的 PostgreSQL 应用服务。"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from datetime import datetime, time, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.content_queries import PostgresContentQueryRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider_lifecycle import (
    PostgresProviderConfigLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.report_runs import PostgresReportRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.contracts.reports import (
    ReportArtifactResponse,
    ReportJobResponse,
    ReportListResponse,
    ReportPreflightResponse,
    ReportResponse,
    ReportSubmitRequest,
)
from aima_ugc.modules.analysis.representative_advice import report_advice_prompt
from aima_ugc.modules.reporting.http import ArtifactDownload
from aima_ugc.modules.reporting.report_jobs import (
    REPORT_GENERATION_JOB,
    REPORT_JOB_TIMEOUT_SECONDS,
    REPORT_PUBLICATION_JOB,
    ReportGenerationPayload,
    ReportPublicationPayload,
)
from aima_ugc.modules.reporting.report_tables import report_runs_table
from aima_ugc.modules.vehicles.tables import vehicle_brands_table, vehicle_models_table
from aima_ugc.platform.jobs.models import JobRecord
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.reporting.excel_report import DEFAULT_REPORT_TEMPLATE_PATH
from aima_ugc.platform.time import beijing_now

from .analysis_identity import active_analysis_configuration
from .runtime import PlatformRuntime

_SELECTION_PROMPT = (
    Path(__file__).resolve().parents[1] / "modules/analysis/prompts/zhengfu_shaixuan.md"
)


class ReportRequestError(ValueError):
    """错误码只包含安全业务语义，HTTP 不回显第三方信息。"""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(message)


class PostgresReportHttpService:
    """管理员报告流程共用父事实，外部 I/O 始终位于事务外。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def preflight(self, body: ReportSubmitRequest) -> ReportPreflightResponse:
        """显示实时数量及模型身份，不保存报告或触发模型。"""
        with self._runtime.database.new_session() as session, session.begin():
            self._validate_catalog(session, body)
            config = active_analysis_configuration(session, self._runtime.settings)
            reader = PostgresContentQueryRepository(session, analysis_identity=config.identity)
            current = reader.freeze_target_statement(filters=self._filters(body))
            previous = reader.freeze_target_statement(filters=self._filters(body, previous=True))
            target = current.subquery()
            count = int(session.scalar(select(func.count()).select_from(target)) or 0)
            previous_count = int(
                session.scalar(select(func.count()).select_from(previous.subquery())) or 0
            )
            # 预检与冻结使用相同生产投影，当前页只用于各数量聚合。
            from aima_ugc.adapters.persistence.postgres.reporting import (
                PostgresDataExportRepository,
            )

            projection = select(
                target.c.content_id,
                target.c.content_version,
                target.c.target_ordinal.label("ordinal"),
            )
            analyzed = users = comments = 0
            after = -1
            while page := PostgresDataExportRepository(session).load_target_page(
                projection, after_ordinal=after, limit=200
            ):
                for _, record in page:
                    comments += len(record.comments)
                    if record.content.analysis:
                        analyzed += 1
                        users += record.content.analysis.voice_type == "真实用户发声"
                after = page[-1][0]
            warnings = []
            if not count:
                warnings.append("所选品牌、车型和日期没有可报告内容")
            if analyzed < count:
                warnings.append(f"{count - analyzed} 条内容尚无分析结果，仅参与全量声量统计")
            if not previous_count:
                warnings.append("上期没有内容，报告将显示零声量及可计算的环比")
            if config.llm_provider is None:
                warnings.append("尚未配置可用的管理员 AI 模型")
            return ReportPreflightResponse(
                content_count=count,
                previous_content_count=previous_count,
                analyzed_count=analyzed,
                real_user_count=users,
                comment_count=comments,
                model=config.llm_provider.model if config.llm_provider else None,
                provider=config.llm_provider.provider if config.llm_provider else None,
                prompt_version=config.taxonomy.prompt_version,
                taxonomy_sha256=config.taxonomy.taxonomy_sha256,
                ready=bool(count and config.llm_provider),
                warnings=tuple(warnings),
            )

    def create(
        self, body: ReportSubmitRequest, *, actor_ref: str, request_id: str
    ) -> ReportResponse:
        """在一致读事务中原子保存报告、全部数据、配置与生成 Job。"""
        report_id = uuid4()
        with self._runtime.database.new_session() as session, session.begin():
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            brand = self._validate_catalog(session, body)
            config = active_analysis_configuration(session, self._runtime.settings)
            provider = config.llm_provider
            if provider is None:
                raise ReportRequestError("report_model_unavailable", "请先配置管理员 AI 模型")
            # 与归档/删除共用 Provider 行锁，直到冻结报告的历史引用在提交后可见。
            # 环境配置没有数据库行；数据库尚未接管 LLM 时保留既有环境回退。
            locked_provider = PostgresProviderConfigLifecycleRepository(session).get_for_update(
                provider.id
            )
            if (
                locked_provider is not None
                and locked_provider != provider
                or locked_provider is None
                and PostgresProviderConfigRepository(session).list_all(
                    provider_kind="llm", include_archived=True
                )
            ):
                raise ReportRequestError("report_model_changed", "模型配置已变化，请重新预检后创建")
            template = DEFAULT_REPORT_TEMPLATE_PATH.read_text(encoding="utf-8")
            template = template.replace(
                "# 爱玛品牌舆情分析报告", f"# {brand['display_name']}品牌舆情分析报告", 1
            )
            keyword_basis = (
                "关键词口径：数据库中该内容版本的有效品牌、车型命中证据，"
                "按标准名称合并别名（车型沿用目录合并映射）。"
                "每条内容内同一名称只计一次，内容占比以本期全部内容为分母。"
                "名称与命中结果在报告创建时冻结。"
            )
            template = template.replace(
                "## 5. 热点关键词\n", f"## 5. 热点关键词\n\n{keyword_basis}\n", 1
            )
            selection_prompt = _SELECTION_PROMPT.read_text(encoding="utf-8").replace(
                "爱玛", str(brand["display_name"])
            )
            snapshot = {
                "schema_version": "report-dataset.v1",
                "keyword_source": "brand_vehicle_evidence.v1",
                "keyword_basis": keyword_basis,
                "provider": provider.safe_runtime_snapshot(),
                "scheme_version_id": str(config.scheme.id),
                "prompt_version": config.taxonomy.prompt_version,
                "prompt_sha256": config.taxonomy.prompt_sha256,
                "taxonomy_sha256": config.taxonomy.taxonomy_sha256,
                "template_text": template,
                "selection_prompt_text": selection_prompt,
                "selection_prompt_sha256": hashlib.sha256(selection_prompt.encode()).hexdigest(),
                "advice_prompt_text": report_advice_prompt(),
                "retention_days": self._runtime.settings.report_artifact_retention_days,
                "request_timeout_seconds": min(provider.timeout_seconds, 120.0),
            }
            job = self._enqueue(
                session, report_id, "generation", request_id, max_attempts=provider.max_retries + 1
            )
            repository = PostgresReportRepository(session)
            repository.create(
                {
                    "id": report_id,
                    "name": f"{brand['display_name']}舆情报告 {body.start_date}—{body.end_date}",
                    "brand_id": body.brand_id,
                    "vehicle_model_ids": [str(value) for value in body.vehicle_model_ids],
                    "start_date": body.start_date,
                    "end_date": body.end_date,
                    "generation_job_id": job.id,
                    "publication_job_id": None,
                    "snapshot": snapshot,
                    "generation_checkpoint": {},
                    "publication_checkpoint": {},
                    "created_by": actor_ref,
                    "created_at": beijing_now(),
                }
            )
            reader = PostgresContentQueryRepository(session, analysis_identity=config.identity)
            counts = repository.freeze(
                report_id, "current", reader.freeze_target_statement(filters=self._filters(body))
            )
            if not counts["content_count"]:
                raise ReportRequestError("report_empty", "当前范围没有可报告内容", 422)
            previous = repository.freeze(
                report_id,
                "previous",
                reader.freeze_target_statement(filters=self._filters(body, previous=True)),
            )
            analysis_bases = repository.summarize_analysis_bases(report_id)
            session.execute(
                update(report_runs_table)
                .where(report_runs_table.c.id == report_id)
                .values(
                    snapshot={
                        **snapshot,
                        "counts": counts,
                        "previous_counts": previous,
                        "analysis_bases": analysis_bases,
                    }
                )
            )
        log_event(
            self._runtime.logger,
            logging.INFO,
            "report.snapshot.created",
            "已冻结报告数据与模型配置",
            report_run_id=str(report_id),
            job_id=str(job.id),
            request_id=request_id,
            content_count=counts["content_count"],
            previous_content_count=previous["content_count"],
            model=provider.model,
        )
        return self.get(report_id)

    def get(self, report_id: UUID) -> ReportResponse:
        """查询报告和两个独立任务状态。"""
        with self._runtime.database.new_session() as session, session.begin():
            return self._response(session, PostgresReportRepository(session).get(report_id))

    def list_recent(self) -> ReportListResponse:
        """保留过期历史，下载状态按绝对期限计算。"""
        with self._runtime.database.new_session() as session, session.begin():
            return ReportListResponse(
                items=tuple(
                    self._response(session, row)
                    for row in PostgresReportRepository(session).list_recent()
                )
            )

    def action(self, report_id: UUID, *, action: str, request_id: str) -> ReportResponse:
        """锁定父事实后取消或恢复，防止双击建立并行任务。"""
        with self._runtime.database.new_session() as session, session.begin():
            repository = PostgresReportRepository(session)
            row = repository.get(report_id, lock=True)
            jobs = PostgresJobRepository(session)
            if action == "cancel":
                for key in ("generation_job_id", "publication_job_id"):
                    if row[key] is not None:
                        job = jobs.get(row[key])
                        if job and job.status in {"queued", "running"}:
                            jobs.request_cancel(job.id)
            else:
                kind = "publication" if action == "publish" else "generation"
                if kind == "publication" and self._runtime.settings.feishu_dry_run:
                    raise ReportRequestError(
                        "report_publication_dry_run",
                        "飞书当前为预演模式。请在允许真实发布的环境关闭 Dry Run 后再发布；"
                        "报告文件仍可下载。",
                    )
                if row["expires_at"] and row["expires_at"] <= beijing_now():
                    raise ReportRequestError("report_expired", "报告文件已过期，请创建新报告", 410)
                if kind == "publication" and row["completed_at"] is None:
                    raise ReportRequestError("report_not_generated", "报告尚未生成")
                if kind == "generation" and row["completed_at"] is not None:
                    raise ReportRequestError("report_already_generated", "报告已经生成")
                existing = jobs.get(row[f"{kind}_job_id"]) if row[f"{kind}_job_id"] else None
                if existing is None or existing.status in {"failed", "cancelled"}:
                    attempts = (
                        row["snapshot"]["provider"]["max_retries"] + 1
                        if kind == "generation"
                        else 4
                    )
                    job = self._enqueue(session, report_id, kind, request_id, max_attempts=attempts)
                    repository.update_job(report_id, kind=kind, job_id=job.id)
        return self.get(report_id)

    def download(self, report_id: UUID, artifact_id: UUID) -> ArtifactDownload:
        """验证所属、生成完成与字节有效期后返回有界流。"""
        with self._runtime.database.new_session() as session, session.begin():
            repository = PostgresReportRepository(session)
            report = repository.get(report_id)
            if not report["completed_at"]:
                raise ReportRequestError("report_not_generated", "报告尚未生成")
            if report["expires_at"] <= beijing_now():
                raise ReportRequestError("report_expired", "报告文件已过期", 410)
            artifact = next(
                (row for row in repository.artifacts(report_id) if row["id"] == artifact_id), None
            )
            if artifact is None:
                raise ReportRequestError("report_artifact_not_found", "文件不属于当前报告", 404)
            if (
                artifact["storage_status"] != "linked"
                or artifact["storage_backend"] != self._runtime.artifact_store.backend_name
            ):
                raise ReportRequestError("report_artifact_unavailable", "报告文件已不可用", 410)
            filename, content_type, storage_key = (
                artifact["filename"],
                artifact["content_type"],
                artifact["storage_key"],
            )
        try:
            source = self._runtime.artifact_store.open_read(storage_key)
        except FileNotFoundError:
            raise ReportRequestError("report_artifact_missing", "报告文件已丢失", 410) from None

        def chunks() -> Iterator[bytes]:
            """客户端关闭时也释放文件句柄。"""
            try:
                while chunk := source.read(1024 * 1024):
                    yield chunk
            finally:
                source.close()

        return ArtifactDownload(
            filename=filename,
            content_type=content_type,
            byte_size=artifact["byte_size"],
            chunks=chunks(),
        )

    @staticmethod
    def _validate_catalog(session: Session, body: ReportSubmitRequest) -> RowMapping:
        """目录身份必须真实存在，且选定车型全部属于品牌。"""
        brand = (
            session.execute(
                select(vehicle_brands_table).where(vehicle_brands_table.c.id == body.brand_id)
            )
            .mappings()
            .one_or_none()
        )
        if brand is None or brand["status"] != "active":
            raise ReportRequestError("report_brand_invalid", "请选择有效品牌", 422)
        if body.vehicle_model_ids:
            count = session.scalar(
                select(func.count())
                .select_from(vehicle_models_table)
                .where(
                    vehicle_models_table.c.id.in_(body.vehicle_model_ids),
                    vehicle_models_table.c.brand_id == body.brand_id,
                    vehicle_models_table.c.status == "active",
                )
            )
            if count != len(body.vehicle_model_ids):
                raise ReportRequestError(
                    "report_vehicle_invalid", "车型必须有效且属于所选品牌", 422
                )
        return brand

    @staticmethod
    def _filters(body: ReportSubmitRequest, *, previous: bool = False) -> ContentFilterSnapshot:
        """本期与紧邻等长上期都使用正式声音广场过滤与来源可见性。"""
        start, end = body.start_date, body.end_date
        if previous:
            end = start - timedelta(days=1)
            start = end - (body.end_date - body.start_date)
        zone = ZoneInfo("Asia/Shanghai")
        return ContentFilterSnapshot(
            brand_ids=(body.brand_id,),
            vehicle_model_ids=body.vehicle_model_ids,
            published_from=datetime.combine(start, time.min, zone),
            published_to=datetime.combine(end, time.max, zone),
        )

    @staticmethod
    def _enqueue(
        session: Session, report_id: UUID, kind: str, request_id: str, *, max_attempts: int
    ) -> JobRecord:
        """恢复建新 Job，但沿用报告快照和成功断点。"""
        job_type = REPORT_GENERATION_JOB if kind == "generation" else REPORT_PUBLICATION_JOB
        payload = (
            ReportGenerationPayload(report_run_id=report_id)
            if kind == "generation"
            else ReportPublicationPayload(report_run_id=report_id)
        )
        return PostgresJobRepository(session).enqueue(
            job_type=job_type,
            payload_version=job_type,
            payload=payload.model_dump(mode="json"),
            internal_idempotency_key=f"{kind}:{report_id}:{uuid4()}",
            request_id=request_id,
            priority=0,
            max_attempts=max_attempts,
            timeout_seconds=REPORT_JOB_TIMEOUT_SECONDS,
        )

    def _response(self, session: Session, row: RowMapping) -> ReportResponse:
        """业务状态从持久 Job 与产物提交事实推导，不维护平行状态机。"""
        jobs = PostgresJobRepository(session)
        generation = jobs.get(row["generation_job_id"])
        publication = jobs.get(row["publication_job_id"]) if row["publication_job_id"] else None
        if generation is None:
            raise RuntimeError("报告生成 Job 缺失")
        expired = bool(row["expires_at"] and row["expires_at"] <= beijing_now())
        status = (
            "expired"
            if expired
            else "published"
            if publication and publication.status == "succeeded"
            else "generated"
            if row["completed_at"]
            else "generating"
            if generation.status == "running"
            else "failed"
            if generation.status == "succeeded"
            else generation.status
        )

        def job_response(job: JobRecord) -> ReportJobResponse:
            """保留重试时间和取消意图，不把内部 checkpoint 暴露为结果。"""
            return ReportJobResponse(
                id=job.id,
                job_type=job.job_type,
                status=job.status,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                progress=job.progress,
                error_code=job.error_code,
                created_at=job.created_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
                available_at=job.available_at,
                timeout_seconds=job.timeout_seconds,
                cancel_requested=job.cancel_requested_at is not None,
            )

        files = (
            ()
            if expired
            else tuple(
                ReportArtifactResponse(
                    artifact_id=item["id"],
                    artifact_type=item["artifact_type"],
                    filename=item["filename"],
                    content_type=item["content_type"],
                    byte_size=item["byte_size"],
                    download_url=f"/api/v1/reports/{row['id']}/artifacts/{item['id']}/download",
                )
                for item in PostgresReportRepository(session).artifacts(row["id"])
                if item["storage_status"] == "linked"
            )
        )
        result = publication.result if publication and isinstance(publication.result, dict) else {}
        return ReportResponse(
            id=row["id"],
            name=row["name"],
            brand_id=row["brand_id"],
            vehicle_model_ids=tuple(UUID(value) for value in row["vehicle_model_ids"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
            status=status,
            generation_job=job_response(generation),
            publication_job=job_response(publication) if publication else None,
            files=files,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            expires_at=row["expires_at"],
            model=row["snapshot"]["provider"]["model"],
            prompt_version=row["snapshot"]["prompt_version"],
            provider_config_id=row["snapshot"]["provider"]["provider_config_id"],
            provider_revision=row["snapshot"]["provider"]["revision"],
            scheme_version_id=row["snapshot"]["scheme_version_id"],
            prompt_sha256=row["snapshot"]["prompt_sha256"],
            taxonomy_sha256=row["snapshot"]["taxonomy_sha256"],
            selection_prompt_sha256=row["snapshot"]["selection_prompt_sha256"],
            analysis_bases=row["snapshot"].get("analysis_bases", ()),
            content_count=row["snapshot"]["counts"]["content_count"],
            publication_enabled=not self._runtime.settings.feishu_dry_run,
            native_document_url=result.get("native_document_url"),
            editable_chart_sheet_url=result.get("editable_chart_sheet_url"),
            representative_table_url=result.get("representative_table_url"),
        )

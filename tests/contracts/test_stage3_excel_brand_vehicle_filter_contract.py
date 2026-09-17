from __future__ import annotations

import inspect

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    HistoricalCampaignCreateRequest,
    LocalDataImportCampaignCreateRequest,
)
from aima_ugc.modules.ingestion import import_job


def _create_import_endpoint_parameters() -> set[str]:
    """读取公开 Import Endpoint 的参数名，直接约束 Stage 3 HTTP Contract。"""

    app = create_app(readiness_check=lambda: None)  # type: ignore[arg-type]
    route = next(
        item
        for item in app.routes
        if getattr(item, "path", None) == "/api/v1/import-batches"
        and "POST" in getattr(item, "methods", set())
    )
    return set(inspect.signature(route.endpoint).parameters)


def test_stage3_excel_import_public_contract_uses_brand_scope_only() -> None:
    """Excel Import 不再把 Keyword Pack 或单车型暴露为入库 Filter。"""

    parameters = _create_import_endpoint_parameters()
    assert "brand_ids" in parameters
    assert "keyword_pack_ids" not in parameters
    assert "vehicle_model_ids" not in parameters


def test_stage3_historical_contract_uses_brand_scope_only() -> None:
    """两种 Historical/Data Import 创建 Contract 必须与单文件 Import 使用同一 Brand Scope。"""

    for model in (HistoricalCampaignCreateRequest, LocalDataImportCampaignCreateRequest):
        assert "brand_ids" in model.model_fields
        assert "keyword_pack_ids" not in model.model_fields
        assert "vehicle_model_ids" not in model.model_fields


def test_stage3_single_file_job_only_accepts_brand_vehicle_v2() -> None:
    """无历史任务的 Stage 7 只保留 Brand/Vehicle 冻结快照语义。"""

    assert import_job.IMPORT_JOB_TYPE == "ingestion.import-excel.v2"
    assert import_job.IMPORT_JOB_PAYLOAD_VERSION == "ingestion.import-excel.v2"
    assert set(import_job.ImportJobPayload.model_fields) == {"schema_version", "filter_snapshot"}

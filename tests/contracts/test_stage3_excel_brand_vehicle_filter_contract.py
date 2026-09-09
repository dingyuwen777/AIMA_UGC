from __future__ import annotations

import inspect

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.stage3_import import (
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


def test_stage3_single_file_job_keeps_legacy_v1_and_creates_v2() -> None:
    """新 Worker 显式区分新旧 Job Type，不能用同一 v1 Payload 静默换语义。"""

    assert import_job.LEGACY_IMPORT_JOB_TYPE == "ingestion.import-excel.v1"
    assert import_job.BRAND_VEHICLE_IMPORT_JOB_TYPE == "ingestion.import-excel.v2"
    assert "keyword_selection" in import_job.ImportJobPayload.model_fields
    assert "filter_snapshot" in import_job.BrandVehicleImportJobPayload.model_fields

"""Stage 8B Import HTTP 与固定 Schema 契约测试。"""

from __future__ import annotations

from aima_ugc.entrypoints.api_main import create_app


def test_stage8b_openapi_exposes_stable_operations_and_error_contracts() -> None:
    spec = create_app().openapi()
    paths = spec["paths"]

    assert paths["/api/v1/import-batches"]["post"]["operationId"] == "createImportBatch"
    assert paths["/api/v1/import-batches/{batch_id}"]["get"]["operationId"] == ("getImportBatch")
    assert paths["/api/v1/jobs/{job_id}"]["get"]["operationId"] == "getJob"
    assert "/api/v1/relevance-config" not in paths
    assert paths["/api/v1/import-batches"]["post"]["responses"]["202"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/ImportBatchCreatedResponse")
    assert paths["/api/v1/import-batches"]["post"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/HttpErrorResponse")

    error_responses = (
        ("/api/v1/import-batches", "post", (409, 413, 422, 500)),
        ("/api/v1/import-batches/{batch_id}", "get", (404, 422, 500)),
        ("/api/v1/jobs/{job_id}", "get", (404, 422, 500)),
        ("/api/v1/keyword-packs", "post", (409, 422, 500)),
        ("/api/v1/keyword-packs/{pack_id}/keywords", "post", (404, 422, 500)),
        ("/api/v1/keyword-packs/{pack_id}", "get", (404, 422, 500)),
    )
    for path, method, status_codes in error_responses:
        for status_code in status_codes:
            schema = paths[path][method]["responses"][str(status_code)]["content"][
                "application/json"
            ]["schema"]
            assert schema["$ref"].endswith("/HttpErrorResponse")


def test_import_openapi_requires_file_and_exposes_optional_brand_scope() -> None:
    spec = create_app().openapi()
    request_schema = spec["paths"]["/api/v1/import-batches"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]
    body_schema = spec["components"]["schemas"][request_schema["$ref"].rsplit("/", 1)[-1]]

    assert set(body_schema["required"]) == {"file"}
    assert body_schema["properties"]["file"] == {
        "contentMediaType": "application/octet-stream",
        "title": "File",
        "type": "string",
    }
    brand_ids = body_schema["properties"]["brand_ids"]
    assert brand_ids["type"] == "array"
    assert brand_ids["items"]["format"] == "uuid"
    assert "keyword_pack_ids" not in body_schema["properties"]
    assert "vehicle_model_ids" not in body_schema["properties"]

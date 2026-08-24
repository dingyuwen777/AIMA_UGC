from __future__ import annotations

from aima_ugc.bootstrap.api import create_app


def test_stage8e_openapi_exposes_collection_runtime_productization() -> None:
    spec = create_app().openapi()
    paths = spec["paths"]

    assert paths["/api/v1/collection-capabilities"]["get"]["operationId"] == (
        "getCollectionCapabilities"
    )
    assert paths["/api/v1/collection-runs"]["post"]["operationId"] == "createCollectionRun"
    assert paths["/api/v1/collection-runs/{run_id}"]["get"]["operationId"] == ("getCollectionRun")
    assert paths["/api/v1/collection-runtime/runs"]["get"]["operationId"] == (
        "listCollectionRuntimeRuns"
    )
    assert paths["/api/v1/collection-runtime/summary"]["get"]["operationId"] == (
        "getCollectionRuntimeSummary"
    )


def test_stage8e_create_contract_is_strict_and_discriminates_two_modes() -> None:
    spec = create_app().openapi()
    schemas = spec["components"]["schemas"]
    request_schema = schemas["CollectionRunCreateRequest"]

    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {"mode", "platforms"}
    mode_schema_name = request_schema["properties"]["mode"]["$ref"].rsplit("/", 1)[-1]
    assert set(schemas[mode_schema_name]["enum"]) == {
        "discovery",
        "batch_supplement",
    }
    assert "keywords" not in request_schema["properties"]
    keyword_pack_ids = request_schema["properties"]["keyword_pack_ids"]
    array_schema = next(
        option for option in keyword_pack_ids["anyOf"] if option.get("type") == "array"
    )
    assert array_schema["minItems"] == 1
    assert array_schema["maxItems"] == 20
    assert array_schema["items"]["format"] == "uuid"
    assert request_schema["properties"]["platforms"]["maxItems"] == 5


def test_stage8e_routes_keep_the_unified_error_contract() -> None:
    spec = create_app().openapi()
    for path, method in (
        ("/api/v1/collection-runs", "post"),
        ("/api/v1/collection-runs/{run_id}", "get"),
        ("/api/v1/collection-runtime/runs", "get"),
    ):
        responses = spec["paths"][path][method]["responses"]
        assert responses["422"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/HttpErrorResponse"
        }


def test_stage8e_run_detail_exposes_fixed_scope_status_without_provider_pagination() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    run = schemas["CollectionRunResponse"]
    scope = schemas["CollectionScopeResponse"]

    assert {"stage", "scopes"} <= set(run["required"])
    assert scope["additionalProperties"] is False
    assert {
        "id",
        "platform",
        "source_type",
        "operation_group",
        "status",
        "progress",
        "stats",
    } <= set(scope["required"])
    assert "pagination_state" not in scope["properties"]

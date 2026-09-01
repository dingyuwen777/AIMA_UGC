from __future__ import annotations

from aima_ugc.bootstrap.api import create_app


def test_stage8f_openapi_exposes_collection_strategy_productization() -> None:
    spec = create_app().openapi()
    paths = spec["paths"]

    assert paths["/api/v1/keyword-packs"]["get"]["operationId"] == "listKeywordPacks"
    assert paths["/api/v1/keyword-packs/{pack_id}/enabled"]["put"]["operationId"] == (
        "updateKeywordPackEnabled"
    )
    assert paths["/api/v1/collection-plans"]["post"]["operationId"] == ("createCollectionPlan")
    assert paths["/api/v1/collection-plans"]["get"]["operationId"] == ("listCollectionPlans")
    assert paths["/api/v1/collection-plans/{plan_id}"]["get"]["operationId"] == (
        "getCollectionPlan"
    )
    assert paths["/api/v1/collection-plans/{plan_id}/enabled"]["put"]["operationId"] == (
        "updateCollectionPlanEnabled"
    )


def test_stage8f_plan_contract_only_accepts_periodic_business_configuration() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    request = schemas["CollectionPlanCreateRequest"]

    assert request["additionalProperties"] is False
    assert set(request["required"]) == {
        "name",
        "schedule_expr",
        "platforms",
    }
    assert request["properties"]["platforms"]["maxItems"] == 5
    assert request["properties"]["keyword_pack_ids"]["maxItems"] == 20
    assert request["properties"]["vehicle_model_ids"]["maxItems"] == 100
    assert "schedule_mode" not in request["properties"]
    assert "relevance_keyword_pack_id" not in request["properties"]
    assert "provider_config" not in request["properties"]
    platform_request = schemas["CollectionPlanPlatformRequest"]
    assert "search_config" in platform_request["properties"]
    assert "search_config" in platform_request["required"]
    assert "search_config" in schemas["CollectionPlanPlatformResponse"]["required"]


def test_stage8f_routes_keep_fixed_error_contracts() -> None:
    spec = create_app().openapi()
    for path, method in (
        ("/api/v1/keyword-packs", "get"),
        ("/api/v1/keyword-packs/{pack_id}/enabled", "put"),
        ("/api/v1/collection-plans", "post"),
        ("/api/v1/collection-plans", "get"),
        ("/api/v1/collection-plans/{plan_id}", "get"),
        ("/api/v1/collection-plans/{plan_id}/enabled", "put"),
    ):
        responses = spec["paths"][path][method]["responses"]
        assert responses["422"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/HttpErrorResponse"
        }

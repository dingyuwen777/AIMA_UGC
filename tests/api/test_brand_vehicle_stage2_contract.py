"""Stage 2 Brand/Vehicle HTTP 路由与 OpenAPI Contract 回归。"""

from __future__ import annotations

from aima_ugc.entrypoints.api_main import create_app


def test_brand_vehicle_stage2_routes_are_installed_on_formal_api() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    assert paths["/api/v1/vehicle-brands"]["post"]["operationId"] == "createVehicleBrand"
    assert paths["/api/v1/vehicle-brands"]["get"]["operationId"] == "listVehicleBrands"
    assert (
        paths["/api/v1/vehicle-models/{vehicle_model_id}/brand"]["put"]["operationId"]
        == "assignVehicleModelBrand"
    )
    assert (
        paths["/api/v1/vehicle-catalog/readiness"]["get"]["operationId"]
        == "getVehicleCatalogReadiness"
    )
    assert (
        paths["/api/v1/vehicle-catalog/snapshot"]["get"]["operationId"]
        == "getBrandVehicleCatalogSnapshot"
    )


def test_vehicle_contract_exposes_brand_id_and_snapshot_has_stage2_scope() -> None:
    schema = create_app().openapi()
    components = schema["components"]["schemas"]

    vehicle_create = components["VehicleModelCreateRequest"]
    vehicle_response = components["VehicleModelResponse"]
    snapshot = components["BrandVehicleCatalogSnapshotResponse"]

    assert "brand_id" in vehicle_create["properties"]
    assert "brand_id" in vehicle_response["properties"]
    assert {
        "catalog_version",
        "filter_scope",
        "selected_brand_ids",
        "brands",
        "brand_aliases",
        "vehicles",
        "vehicle_aliases",
        "unresolved_active_vehicle_ids",
    } <= set(snapshot["properties"])

"""最终 HTTP 路由的显式授权事实；新增接口必须在此经过语义归类。"""

from typing import Literal

RoutePermission = Literal["public", "authenticated", "administrator", "owner_or_administrator"]

ROUTE_POLICIES: dict[tuple[str, str], RoutePermission] = {
    ("GET", "/api/v1/content-data-revision"): "authenticated",
    ("GET", "/docs"): "administrator",  # FastAPI
    ("HEAD", "/docs"): "administrator",  # FastAPI
    ("GET", "/docs/oauth2-redirect"): "administrator",  # FastAPI
    ("HEAD", "/docs/oauth2-redirect"): "administrator",  # FastAPI
    ("GET", "/openapi.json"): "administrator",  # FastAPI
    ("HEAD", "/openapi.json"): "administrator",  # FastAPI
    ("GET", "/redoc"): "administrator",  # FastAPI
    ("HEAD", "/redoc"): "administrator",  # FastAPI
    (
        "GET",
        "/api/v1/content-analysis-capabilities",
    ): "authenticated",  # analysis_capability_http.py
    (
        "GET",
        "/api/v1/analysis-schemes/lifecycle/archived",
    ): "administrator",  # analysis_scheme_lifecycle_http.py
    (
        "DELETE",
        "/api/v1/analysis-schemes/{scheme_id}",
    ): "administrator",  # analysis_scheme_lifecycle_http.py
    (
        "POST",
        "/api/v1/analysis-schemes/{scheme_id}/archive",
    ): "administrator",  # analysis_scheme_lifecycle_http.py
    (
        "POST",
        "/api/v1/analysis-schemes/{scheme_id}/copy",
    ): "administrator",  # analysis_scheme_lifecycle_http.py
    (
        "GET",
        "/api/v1/analysis-schemes/{scheme_id}/delete-eligibility",
    ): "administrator",  # analysis_scheme_lifecycle_http.py
    (
        "POST",
        "/api/v1/analysis-schemes/{scheme_id}/restore",
    ): "administrator",  # analysis_scheme_lifecycle_http.py
    ("GET", "/api/v1/admin/feishu-publication-jobs/{job_id}"): "administrator",  # api.py
    ("POST", "/api/v1/admin/feishu-report-publications"): "administrator",  # api.py
    ("POST", "/api/v1/admin/feishu-representative-selections"): "administrator",  # api.py
    ("PUT", "/api/v1/analysis-scheme-versions/{version_id}"): "administrator",  # api.py
    ("POST", "/api/v1/analysis-scheme-versions/{version_id}/publish"): "administrator",  # api.py
    ("POST", "/api/v1/analysis-scheme-versions/{version_id}/rollback"): "administrator",  # api.py
    ("GET", "/api/v1/analysis-schemes"): "administrator",  # api.py
    ("POST", "/api/v1/analysis-schemes"): "administrator",  # api.py
    ("GET", "/api/v1/analysis/content-runs"): "administrator",  # api.py
    ("POST", "/api/v1/analysis/content-runs"): "administrator",  # api.py
    ("POST", "/api/v1/analysis/content-runs/preview"): "administrator",  # api.py
    ("GET", "/api/v1/analysis/content-runs/{run_id}"): "administrator",  # api.py
    ("POST", "/api/v1/analysis/content-runs/{run_id}/cancel"): "administrator",  # api.py
    ("GET", "/api/v1/audit-events"): "administrator",  # api.py
    ("POST", "/api/v1/canonical-replays"): "administrator",  # api.py
    ("POST", "/api/v1/canonical-replays/all"): "administrator",  # api.py
    (
        "POST",
        "/api/v1/canonical-replays/all/{replay_request_id}/cancel-and-revoke",
    ): "administrator",  # api.py
    ("POST", "/api/v1/canonical-replays/all/{replay_request_id}/revoke"): "administrator",  # api.py
    ("GET", "/api/v1/canonical-replays/{run_id}"): "administrator",  # api.py
    ("POST", "/api/v1/canonical-replays/{run_id}/cancel"): "administrator",  # api.py
    ("GET", "/api/v1/collection-capabilities"): "administrator",  # api.py
    ("GET", "/api/v1/collection-plans"): "administrator",  # api.py
    ("POST", "/api/v1/collection-plans"): "administrator",  # api.py
    ("GET", "/api/v1/collection-plans/{plan_id}"): "administrator",  # api.py
    ("PUT", "/api/v1/collection-plans/{plan_id}/enabled"): "administrator",  # api.py
    ("POST", "/api/v1/collection-runs"): "administrator",  # api.py
    ("GET", "/api/v1/collection-runs/{run_id}"): "administrator",  # api.py
    ("POST", "/api/v1/collection-runs/{run_id}/cancel"): "administrator",  # api.py
    ("POST", "/api/v1/collection-runs/{run_id}/retry-failed"): "administrator",  # api.py
    ("GET", "/api/v1/collection-runtime/runs"): "administrator",  # api.py
    ("GET", "/api/v1/collection-runtime/summary"): "administrator",  # api.py
    ("POST", "/api/v1/collection-supplements/preview"): "administrator",  # api.py
    ("GET", "/api/v1/content-analysis-jobs/{job_id}"): "administrator",  # api.py
    ("POST", "/api/v1/content-analysis-requests"): "administrator",  # api.py
    ("GET", "/api/v1/content-analysis-taxonomy"): "authenticated",  # api.py
    ("POST", "/api/v1/content-availability-observations"): "administrator",  # api.py
    ("GET", "/api/v1/content-filter-options"): "authenticated",  # api.py
    ("POST", "/api/v1/content-relevance-reviews"): "administrator",  # api.py
    ("GET", "/api/v1/contents"): "authenticated",  # api.py
    ("POST", "/api/v1/contents/count"): "authenticated",  # api.py
    ("GET", "/api/v1/contents/{content_id}"): "authenticated",  # api.py
    ("PUT", "/api/v1/contents/{content_id}/analysis-review"): "administrator",  # api.py
    ("GET", "/api/v1/contents/{content_id}/comments"): "authenticated",  # api.py
    ("PUT", "/api/v1/contents/{content_id}/vehicles"): "administrator",  # api.py
    ("GET", "/api/v1/data-exports"): "owner_or_administrator",  # api.py
    ("POST", "/api/v1/data-exports"): "authenticated",  # api.py
    ("GET", "/api/v1/data-exports/{export_id}"): "owner_or_administrator",  # api.py
    ("GET", "/api/v1/data-exports/{export_id}/download"): "owner_or_administrator",  # api.py
    ("GET", "/api/v1/data-import-campaigns"): "administrator",  # api.py
    ("POST", "/api/v1/data-import-campaigns/local"): "administrator",  # api.py
    ("POST", "/api/v1/data-import-campaigns/server"): "administrator",  # api.py
    ("GET", "/api/v1/data-import-campaigns/{campaign_id}"): "administrator",  # api.py
    ("POST", "/api/v1/data-import-campaigns/{campaign_id}/cancel"): "administrator",  # api.py
    ("GET", "/api/v1/data-import-campaigns/{campaign_id}/conflicts"): "administrator",  # api.py
    ("POST", "/api/v1/data-import-campaigns/{campaign_id}/finalize"): "administrator",  # api.py
    ("GET", "/api/v1/data-import-campaigns/{campaign_id}/items"): "administrator",  # api.py
    (
        "PUT",
        "/api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content",
    ): "administrator",  # api.py
    ("POST", "/api/v1/data-import-campaigns/{campaign_id}/retry-failed"): "administrator",  # api.py
    ("POST", "/api/v1/data-import-campaigns/{campaign_id}/start"): "administrator",  # api.py
    (
        "GET",
        "/api/v1/data-import-campaigns/{campaign_id}/supplement-eligibility",
    ): "administrator",  # api.py
    ("GET", "/api/v1/data-import-sources/server/directories"): "administrator",  # api.py
    ("GET", "/api/v1/export-columns"): "authenticated",  # api.py
    ("GET", "/api/v1/historical-import-campaigns"): "administrator",  # api.py
    ("POST", "/api/v1/historical-import-campaigns"): "administrator",  # api.py
    ("GET", "/api/v1/historical-import-campaigns/{campaign_id}"): "administrator",  # api.py
    ("POST", "/api/v1/historical-import-campaigns/{campaign_id}/cancel"): "administrator",  # api.py
    (
        "GET",
        "/api/v1/historical-import-campaigns/{campaign_id}/conflicts",
    ): "administrator",  # api.py
    ("GET", "/api/v1/historical-import-campaigns/{campaign_id}/items"): "administrator",  # api.py
    (
        "POST",
        "/api/v1/historical-import-campaigns/{campaign_id}/retry-failed",
    ): "administrator",  # api.py
    ("POST", "/api/v1/historical-import-campaigns/{campaign_id}/start"): "administrator",  # api.py
    ("GET", "/api/v1/historical-import/directories"): "administrator",  # api.py
    ("GET", "/api/v1/import-batches"): "administrator",  # api.py
    ("POST", "/api/v1/import-batches"): "administrator",  # api.py
    ("GET", "/api/v1/import-batches/summary"): "administrator",  # api.py
    ("GET", "/api/v1/import-batches/{batch_id}"): "administrator",  # api.py
    ("GET", "/api/v1/import-batches/{batch_id}/supplement-eligibility"): "administrator",  # api.py
    ("GET", "/api/v1/jobs/{job_id}"): "administrator",  # api.py
    ("GET", "/api/v1/keyword-packs"): "administrator",  # api.py
    ("POST", "/api/v1/keyword-packs"): "administrator",  # api.py
    ("GET", "/api/v1/keyword-packs/{pack_id}"): "administrator",  # api.py
    ("PUT", "/api/v1/keyword-packs/{pack_id}/enabled"): "administrator",  # api.py
    ("POST", "/api/v1/keyword-packs/{pack_id}/keywords"): "administrator",  # api.py
    ("GET", "/api/v1/me/export-column-default"): "authenticated",  # api.py
    ("PUT", "/api/v1/me/export-column-default"): "authenticated",  # api.py
    ("GET", "/api/v1/notifications"): "authenticated",  # api.py
    ("PUT", "/api/v1/notifications/read"): "authenticated",  # api.py
    ("GET", "/api/v1/principal"): "authenticated",  # api.py
    ("GET", "/api/v1/provider-configs"): "administrator",  # api.py
    ("POST", "/api/v1/provider-configs"): "administrator",  # api.py
    ("PUT", "/api/v1/provider-configs/{provider_config_id}"): "administrator",  # api.py
    ("GET", "/api/v1/vehicle-models"): "authenticated",  # api.py
    ("POST", "/api/v1/vehicle-models"): "administrator",  # api.py
    ("DELETE", "/api/v1/vehicle-models/{vehicle_model_id}"): "administrator",  # api.py
    ("GET", "/api/v1/vehicle-models/{vehicle_model_id}"): "authenticated",  # api.py
    ("PUT", "/api/v1/vehicle-models/{vehicle_model_id}"): "administrator",  # api.py
    ("POST", "/api/v1/vehicle-models/{vehicle_model_id}/merge"): "administrator",  # api.py
    ("GET", "/api/v1/workbench/layout"): "authenticated",  # api.py
    ("PUT", "/api/v1/workbench/layout"): "authenticated",  # api.py
    ("GET", "/api/v1/workbench/mind"): "authenticated",  # api.py
    ("GET", "/api/v1/workbench/stream"): "authenticated",  # api.py
    ("GET", "/api/v1/workbench/trend"): "authenticated",  # api.py
    ("GET", "/health/live"): "public",  # api.py
    ("GET", "/health/ready"): "public",  # api.py
    ("GET", "/api/v1/vehicle-brands"): "authenticated",  # brand_vehicle_http.py
    ("POST", "/api/v1/vehicle-brands"): "administrator",  # brand_vehicle_http.py
    ("DELETE", "/api/v1/vehicle-brands/{brand_id}"): "administrator",  # brand_vehicle_http.py
    ("GET", "/api/v1/vehicle-brands/{brand_id}"): "authenticated",  # brand_vehicle_http.py
    ("PUT", "/api/v1/vehicle-brands/{brand_id}"): "administrator",  # brand_vehicle_http.py
    ("POST", "/api/v1/vehicle-brands/{brand_id}/aliases"): "administrator",  # brand_vehicle_http.py
    (
        "DELETE",
        "/api/v1/vehicle-brands/{brand_id}/aliases/{alias_id}",
    ): "administrator",  # brand_vehicle_http.py
    ("GET", "/api/v1/vehicle-catalog/readiness"): "administrator",  # brand_vehicle_http.py
    ("GET", "/api/v1/vehicle-catalog/snapshot"): "authenticated",  # brand_vehicle_http.py
    (
        "PUT",
        "/api/v1/vehicle-models/{vehicle_model_id}/brand",
    ): "administrator",  # brand_vehicle_http.py
    (
        "GET",
        "/api/v1/contents/{content_id}/media/{position}",
    ): "authenticated",  # content_media_http.py
    (
        "POST",
        "/api/v1/contents/{content_id}/media/{position}/playback/prepare",
    ): "authenticated",  # content_playback_http.py
    (
        "GET",
        "/api/v1/contents/{content_id}/media/{position}/playback/stream",
    ): "authenticated",  # content_playback_http.py
    ("GET", "/api/v1/auth/connectors"): "public",  # feishu_auth_http.py
    ("GET", "/api/v1/auth/feishu/callback"): "public",  # feishu_auth_http.py
    ("GET", "/api/v1/auth/feishu/login"): "public",  # feishu_auth_http.py
    ("GET", "/api/v1/auth/feishu/{connector_code}/callback"): "public",  # feishu_auth_http.py
    ("GET", "/api/v1/auth/feishu/{connector_code}/login"): "public",  # feishu_auth_http.py
    ("POST", "/api/v1/auth/logout"): "authenticated",  # feishu_auth_http.py
    (
        "GET",
        "/api/v1/data-import-campaigns/{campaign_id}/revocation-preview",
    ): "administrator",  # import_revocation_http.py
    (
        "POST",
        "/api/v1/data-import-campaigns/{campaign_id}/revoke",
    ): "administrator",  # import_revocation_http.py
    (
        "GET",
        "/api/v1/provider-configs/lifecycle/archived",
    ): "administrator",  # provider_lifecycle_http.py
    (
        "DELETE",
        "/api/v1/provider-configs/{provider_config_id}",
    ): "administrator",  # provider_lifecycle_http.py
    (
        "POST",
        "/api/v1/provider-configs/{provider_config_id}/archive",
    ): "administrator",  # provider_lifecycle_http.py
    (
        "GET",
        "/api/v1/provider-configs/{provider_config_id}/delete-eligibility",
    ): "administrator",  # provider_lifecycle_http.py
    (
        "POST",
        "/api/v1/provider-configs/{provider_config_id}/restore",
    ): "administrator",  # provider_lifecycle_http.py
    (
        "POST",
        "/api/v1/provider-configs/{provider_config_id}/test-connection",
    ): "administrator",  # provider_lifecycle_http.py
    ("GET", "/api/v1/reports"): "administrator",  # report_routes.py
    ("POST", "/api/v1/reports"): "administrator",  # report_routes.py
    ("POST", "/api/v1/reports/preflight"): "administrator",  # report_routes.py
    ("GET", "/api/v1/reports/{report_id}"): "administrator",  # report_routes.py
    (
        "GET",
        "/api/v1/reports/{report_id}/artifacts/{artifact_id}/download",
    ): "administrator",  # report_routes.py
    ("POST", "/api/v1/reports/{report_id}/cancel"): "administrator",  # report_routes.py
    ("POST", "/api/v1/reports/{report_id}/publish"): "administrator",  # report_routes.py
    ("POST", "/api/v1/reports/{report_id}/retry"): "administrator",  # report_routes.py
    ("DELETE", "/api/v1/collection-plans/{plan_id}"): "administrator",  # resource_lifecycle_http.py
    ("PUT", "/api/v1/collection-plans/{plan_id}"): "administrator",  # resource_lifecycle_http.py
    (
        "POST",
        "/api/v1/collection-plans/{plan_id}/archive",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "POST",
        "/api/v1/collection-plans/{plan_id}/copy",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "GET",
        "/api/v1/collection-plans/{plan_id}/delete-eligibility",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "POST",
        "/api/v1/collection-plans/{plan_id}/restore",
    ): "administrator",  # resource_lifecycle_http.py
    ("DELETE", "/api/v1/keyword-packs/{pack_id}"): "administrator",  # resource_lifecycle_http.py
    ("PUT", "/api/v1/keyword-packs/{pack_id}"): "administrator",  # resource_lifecycle_http.py
    (
        "POST",
        "/api/v1/keyword-packs/{pack_id}/archive",
    ): "administrator",  # resource_lifecycle_http.py
    ("POST", "/api/v1/keyword-packs/{pack_id}/copy"): "administrator",  # resource_lifecycle_http.py
    (
        "GET",
        "/api/v1/keyword-packs/{pack_id}/delete-eligibility",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "PUT",
        "/api/v1/keyword-packs/{pack_id}/keywords/{keyword_id}",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "POST",
        "/api/v1/keyword-packs/{pack_id}/keywords/{keyword_id}/remove",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "POST",
        "/api/v1/keyword-packs/{pack_id}/restore",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "GET",
        "/api/v1/resource-lifecycle/collection-plans/archived",
    ): "administrator",  # resource_lifecycle_http.py
    (
        "GET",
        "/api/v1/resource-lifecycle/keyword-packs/archived",
    ): "administrator",  # resource_lifecycle_http.py
    ("GET", "/api/v1/wisersone-downloads"): "administrator",  # wisersone_routes.py
    ("POST", "/api/v1/wisersone-downloads"): "administrator",  # wisersone_routes.py
    ("GET", "/api/v1/wisersone-downloads/{download_id}"): "administrator",  # wisersone_routes.py
    (
        "POST",
        "/api/v1/wisersone-downloads/{download_id}/cancel",
    ): "administrator",  # wisersone_routes.py
    (
        "POST",
        "/api/v1/wisersone-downloads/{download_id}/retry",
    ): "administrator",  # wisersone_routes.py
}

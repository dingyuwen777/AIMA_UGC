"""最终 API assembly 必须把产品资源生命周期动作暴露给 OpenAPI/Orval。"""

from __future__ import annotations

from aima_ugc.entrypoints.api_main import create_app


def test_product_resource_lifecycle_routes_are_in_final_openapi() -> None:
    """Contract 生成脚本使用的最终 create_app 必须包含全部生命周期动作。"""

    document = create_app().openapi()
    operation_ids = {
        operation["operationId"]
        for path_item in document["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "delete", "patch"}
        and isinstance(operation, dict)
        and "operationId" in operation
    }

    expected = {
        "previewDataImportCampaignRevocation",
        "revokeDataImportCampaign",
        "updateKeywordPack",
        "updateKeywordInPack",
        "removeKeywordFromPack",
        "copyKeywordPack",
        "archiveKeywordPack",
        "restoreKeywordPack",
        "listArchivedKeywordPacks",
        "getKeywordPackDeleteEligibility",
        "deleteKeywordPack",
        "updateCollectionPlan",
        "copyCollectionPlan",
        "archiveCollectionPlan",
        "restoreCollectionPlan",
        "listArchivedCollectionPlans",
        "getCollectionPlanDeleteEligibility",
        "deleteCollectionPlan",
        "testProviderConfigConnection",
        "archiveProviderConfig",
        "restoreProviderConfig",
        "listArchivedProviderConfigs",
        "getProviderConfigDeleteEligibility",
        "deleteProviderConfig",
        "copyAnalysisScheme",
        "archiveAnalysisScheme",
        "restoreAnalysisScheme",
        "listArchivedAnalysisSchemes",
        "getAnalysisSchemeDeleteEligibility",
        "deleteAnalysisScheme",
    }
    assert expected <= operation_ids
    assert (
        "brand_ids"
        in document["components"]["schemas"]["CollectionPlanUpdateRequest"]["properties"]
    )

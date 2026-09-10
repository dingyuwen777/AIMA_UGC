import {
  archiveAnalysisScheme,
  archiveProviderConfig,
  addVehicleBrandAlias,
  copyAnalysisScheme,
  createAnalysisSchemeDraft,
  createProviderConfig,
  createVehicleBrand,
  createVehicleModel,
  deleteAnalysisScheme,
  deleteProviderConfig,
  deleteVehicleBrand,
  deleteVehicleBrandAlias,
  deleteVehicleModel,
  getAnalysisSchemeDeleteEligibility,
  getProviderConfigDeleteEligibility,
  listAnalysisSchemes,
  listArchivedAnalysisSchemes,
  listArchivedProviderConfigs,
  listAuditEvents,
  listVehicleBrands,
  listProviderConfigs,
  listVehicleModels,
  mergeVehicleModel,
  publishAnalysisScheme,
  restoreAnalysisScheme,
  restoreProviderConfig,
  rollbackAnalysisScheme,
  testProviderConfigConnection,
  updateAnalysisSchemeDraft,
  updateProviderConfig,
  updateVehicleBrand,
  updateVehicleModel,
  type AnalysisSchemeCopyRequest,
  type AnalysisSchemeCreateDraftRequest,
  type AnalysisSchemeListResponse,
  type AnalysisSchemeResponse,
  type AnalysisSchemeUpdateDraftRequest,
  type AuditEventListResponse,
  type BrandAliasCreateRequest,
  type BrandCreateRequest,
  type BrandListResponse,
  type BrandUpdateRequest,
  type ProviderConfigCreateRequest,
  type ProviderConfigListResponse,
  type ProviderConfigResponse,
  type ProviderConfigUpdateRequest,
  type ProviderConnectionTestResponse,
  type ResourceDeleteEligibilityResponse,
  type ResourceLifecycleListResponse,
  type VehicleModelCreateRequest,
  type VehicleModelListResponse,
  type VehicleModelMergeRequest,
  type VehicleModelUpdateRequest,
} from '../../generated/api/client'
import { unwrapResponse } from '../../shared/api/http'

/** 分页读取全部车型，避免管理配置在车型超过单页上限时截断。 */
export async function fetchVehicles(): Promise<VehicleModelListResponse> {
  const first = unwrapResponse(await listVehicleModels({ offset: 0, limit: 200 }))
  const items = [...first.items]
  let offset = items.length
  while (offset < first.total) {
    const page = unwrapResponse(await listVehicleModels({ offset, limit: 200 }))
    if (page.items.length === 0) break
    items.push(...page.items)
    offset += page.items.length
  }
  return { ...first, items, offset: 0 }
}

export async function fetchVehicleBrandsForAdmin(): Promise<BrandListResponse> {
  const first = unwrapResponse(await listVehicleBrands({ offset: 0, limit: 200 }))
  const items = [...first.items]
  let offset = items.length
  while (offset < first.total) {
    const page = unwrapResponse(await listVehicleBrands({ offset, limit: 200 }))
    if (page.items.length === 0) break
    items.push(...page.items)
    offset += page.items.length
  }
  return { ...first, items, offset: 0 }
}

export const addBrand = async (body: BrandCreateRequest) =>
  unwrapResponse(await createVehicleBrand(body))

export const editBrand = async (id: string, body: BrandUpdateRequest) =>
  unwrapResponse(await updateVehicleBrand(id, body))

export const removeBrand = async (id: string) =>
  unwrapResponse(await deleteVehicleBrand(id))

export const addBrandAlias = async (brandId: string, body: BrandAliasCreateRequest) =>
  unwrapResponse(await addVehicleBrandAlias(brandId, body))

export const removeBrandAlias = async (brandId: string, aliasId: string) =>
  unwrapResponse(await deleteVehicleBrandAlias(brandId, aliasId))

export const addVehicle = async (body: VehicleModelCreateRequest) =>
  unwrapResponse(await createVehicleModel(body))

export const editVehicle = async (id: string, body: VehicleModelUpdateRequest) =>
  unwrapResponse(await updateVehicleModel(id, body))

export const removeVehicle = async (id: string): Promise<void> =>
  unwrapResponse(await deleteVehicleModel(id))

export const mergeVehicle = async (id: string, body: VehicleModelMergeRequest) =>
  unwrapResponse(await mergeVehicleModel(id, body))

export const fetchSchemes = async (): Promise<AnalysisSchemeListResponse> =>
  unwrapResponse(await listAnalysisSchemes())

export const addSchemeDraft = async (body: AnalysisSchemeCreateDraftRequest): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await createAnalysisSchemeDraft(body))

export const editSchemeDraft = async (id: string, body: AnalysisSchemeUpdateDraftRequest): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await updateAnalysisSchemeDraft(id, body))

export const activateScheme = async (id: string, expectedVersion: number): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await publishAnalysisScheme(id, { expected_version: expectedVersion }))

export const restoreScheme = async (id: string, expectedVersion: number): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await rollbackAnalysisScheme(id, { expected_version: expectedVersion }))

export const copyScheme = async (
  schemeId: string,
  body: AnalysisSchemeCopyRequest,
): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await copyAnalysisScheme(schemeId, body))

export const archiveScheme = async (schemeId: string) =>
  unwrapResponse(await archiveAnalysisScheme(schemeId))

export const fetchArchivedSchemes = async (): Promise<ResourceLifecycleListResponse> =>
  unwrapResponse(await listArchivedAnalysisSchemes())

export const restoreArchivedScheme = async (schemeId: string): Promise<void> =>
  unwrapResponse(await restoreAnalysisScheme(schemeId))

export const fetchSchemeDeleteEligibility = async (
  schemeId: string,
): Promise<ResourceDeleteEligibilityResponse> =>
  unwrapResponse(await getAnalysisSchemeDeleteEligibility(schemeId))

export const deleteArchivedScheme = async (schemeId: string): Promise<void> =>
  unwrapResponse(await deleteAnalysisScheme(schemeId))

export const fetchAuditEvents = async (
  offset = 0,
  limit = 100,
): Promise<AuditEventListResponse> =>
  unwrapResponse(await listAuditEvents({ offset, limit }))

export const fetchProviderConfigs = async (
  providerKind: 'llm' | 'collection',
): Promise<ProviderConfigListResponse> =>
  unwrapResponse(await listProviderConfigs({ provider_kind: providerKind }))

export const addProviderConfig = async (
  body: ProviderConfigCreateRequest,
): Promise<ProviderConfigResponse> =>
  unwrapResponse(await createProviderConfig(body))

export const editProviderConfig = async (
  id: string,
  body: ProviderConfigUpdateRequest,
): Promise<ProviderConfigResponse> =>
  unwrapResponse(await updateProviderConfig(id, body))

export const testProviderConnection = async (
  id: string,
): Promise<ProviderConnectionTestResponse> =>
  unwrapResponse(await testProviderConfigConnection(id))

export const archiveProvider = async (id: string) =>
  unwrapResponse(await archiveProviderConfig(id))

export const fetchArchivedProviders = async (): Promise<ResourceLifecycleListResponse> =>
  unwrapResponse(await listArchivedProviderConfigs())

export const restoreArchivedProvider = async (id: string): Promise<void> =>
  unwrapResponse(await restoreProviderConfig(id))

export const fetchProviderDeleteEligibility = async (
  id: string,
): Promise<ResourceDeleteEligibilityResponse> =>
  unwrapResponse(await getProviderConfigDeleteEligibility(id))

export const deleteArchivedProvider = async (id: string): Promise<void> =>
  unwrapResponse(await deleteProviderConfig(id))

export type {
  ProviderConfigCreateRequest,
  ProviderConfigResponse,
  ProviderConfigUpdateRequest,
  ProviderConnectionTestResponse,
}

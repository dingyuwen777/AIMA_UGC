import {
  addKeywordToPack,
  archiveCollectionPlan,
  archiveKeywordPack,
  copyCollectionPlan,
  copyKeywordPack,
  createCollectionPlan,
  createKeywordPack,
  deleteCollectionPlan,
  deleteKeywordPack,
  getCollectionCapabilities,
  getCollectionPlan,
  getCollectionPlanDeleteEligibility,
  getGlobalRelevanceConfig,
  getKeywordPack,
  getKeywordPackDeleteEligibility,
  getVehicleModel,
  listArchivedCollectionPlans,
  listArchivedKeywordPacks,
  listCollectionPlans,
  listKeywordPacks,
  listVehicleModels,
  removeKeywordFromPack,
  restoreCollectionPlan,
  restoreKeywordPack,
  setGlobalRelevanceConfig,
  updateCollectionPlan,
  updateCollectionPlanEnabled,
  updateKeywordInPack,
  updateKeywordPack,
  updateKeywordPackEnabled,
  type CollectionCapabilitiesResponse,
  type CollectionPlanCopyRequest,
  type CollectionPlanCreateRequest,
  type CollectionPlanListResponse,
  type CollectionPlanResponse,
  type CollectionPlanUpdateRequest,
  type GlobalRelevanceConfigResponse,
  type HttpErrorResponse,
  type KeywordPackCopyRequest,
  type KeywordPackCreateRequest,
  type KeywordPackItemRemoveRequest,
  type KeywordPackItemUpdateRequest,
  type KeywordPackKeywordCreateRequest,
  type KeywordPackListResponse,
  type KeywordPackResponse,
  type KeywordPackSummaryResponse,
  type KeywordPackUpdateRequest,
  type ListCollectionPlansParams,
  type ListKeywordPacksParams,
  type ListVehicleModelsParams,
  type ResourceDeleteEligibilityResponse,
  type ResourceLifecycleListResponse,
  type VehicleModelListResponse,
  type VehicleModelResponse,
} from '../../generated/api/client'

export class CollectionStrategyApiError extends Error {
  readonly status: number
  readonly requestId: string

  constructor(response: HttpErrorResponse) {
    super(response.detail)
    this.name = 'CollectionStrategyApiError'
    this.status = response.status
    this.requestId = response.request_id
  }
}

function isHttpError(value: unknown): value is HttpErrorResponse {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.status === 'number' &&
    typeof candidate.detail === 'string' &&
    typeof candidate.request_id === 'string'
  )
}

function unwrap<T>(value: T): T {
  if (isHttpError(value)) throw new CollectionStrategyApiError(value)
  return value
}

/** 读取计划引用车型的完整当前配置，保留已停用或合并资源的可追溯信息。 */
export async function fetchVehicle(vehicleId: string): Promise<VehicleModelResponse> {
  return unwrap(await getVehicleModel(vehicleId))
}

export async function fetchKeywordPacks(
  params?: ListKeywordPacksParams,
): Promise<KeywordPackListResponse> {
  return unwrap(await listKeywordPacks(params))
}

export async function fetchVehicleModels(
  params?: ListVehicleModelsParams,
): Promise<VehicleModelListResponse> {
  return unwrap(await listVehicleModels(params))
}

export async function createPack(request: KeywordPackCreateRequest): Promise<KeywordPackResponse> {
  return unwrap(await createKeywordPack(request))
}

export async function fetchPack(packId: string): Promise<KeywordPackResponse> {
  return unwrap(await getKeywordPack(packId))
}

export async function updatePack(
  packId: string,
  request: KeywordPackUpdateRequest,
): Promise<KeywordPackResponse> {
  return unwrap(await updateKeywordPack(packId, request))
}

export async function addPackKeyword(
  packId: string,
  request: KeywordPackKeywordCreateRequest,
): Promise<KeywordPackResponse> {
  return unwrap(await addKeywordToPack(packId, request))
}

export async function updatePackKeyword(
  packId: string,
  keywordId: string,
  request: KeywordPackItemUpdateRequest,
): Promise<KeywordPackResponse> {
  return unwrap(await updateKeywordInPack(packId, keywordId, request))
}

export async function removePackKeyword(
  packId: string,
  keywordId: string,
  request: KeywordPackItemRemoveRequest,
): Promise<KeywordPackResponse> {
  return unwrap(await removeKeywordFromPack(packId, keywordId, request))
}

export async function copyPack(
  packId: string,
  request: KeywordPackCopyRequest,
): Promise<KeywordPackResponse> {
  return unwrap(await copyKeywordPack(packId, request))
}

export async function archivePack(packId: string): Promise<void> {
  unwrap(await archiveKeywordPack(packId))
}

export async function fetchArchivedPacks(): Promise<ResourceLifecycleListResponse> {
  return unwrap(await listArchivedKeywordPacks())
}

export async function restorePack(packId: string): Promise<KeywordPackResponse> {
  return unwrap(await restoreKeywordPack(packId))
}

export async function fetchPackDeleteEligibility(
  packId: string,
): Promise<ResourceDeleteEligibilityResponse> {
  return unwrap(await getKeywordPackDeleteEligibility(packId))
}

export async function deletePack(packId: string): Promise<void> {
  unwrap(await deleteKeywordPack(packId))
}

export async function setPackEnabled(
  packId: string,
  enabled: boolean,
): Promise<KeywordPackSummaryResponse> {
  return unwrap(await updateKeywordPackEnabled(packId, { enabled }))
}

export async function fetchGlobalRelevance(): Promise<GlobalRelevanceConfigResponse> {
  return unwrap(await getGlobalRelevanceConfig())
}

export async function setGlobalRelevance(
  keywordPackId: string,
): Promise<GlobalRelevanceConfigResponse> {
  return unwrap(await setGlobalRelevanceConfig({ keyword_pack_id: keywordPackId }))
}

export async function fetchCapabilities(): Promise<CollectionCapabilitiesResponse> {
  return unwrap(await getCollectionCapabilities())
}

export async function fetchPlans(
  params?: ListCollectionPlansParams,
): Promise<CollectionPlanListResponse> {
  return unwrap(await listCollectionPlans(params))
}

export async function createPlan(
  request: CollectionPlanCreateRequest,
): Promise<CollectionPlanResponse> {
  return unwrap(await createCollectionPlan(request))
}

export async function fetchPlan(planId: string): Promise<CollectionPlanResponse> {
  return unwrap(await getCollectionPlan(planId))
}

export async function updatePlan(
  planId: string,
  request: CollectionPlanUpdateRequest,
): Promise<CollectionPlanResponse> {
  return unwrap(await updateCollectionPlan(planId, request))
}

export async function copyPlan(
  planId: string,
  request: CollectionPlanCopyRequest,
): Promise<CollectionPlanResponse> {
  return unwrap(await copyCollectionPlan(planId, request))
}

export async function archivePlan(planId: string): Promise<void> {
  unwrap(await archiveCollectionPlan(planId))
}

export async function fetchArchivedPlans(): Promise<ResourceLifecycleListResponse> {
  return unwrap(await listArchivedCollectionPlans())
}

export async function restorePlan(planId: string): Promise<CollectionPlanResponse> {
  return unwrap(await restoreCollectionPlan(planId))
}

export async function fetchPlanDeleteEligibility(
  planId: string,
): Promise<ResourceDeleteEligibilityResponse> {
  return unwrap(await getCollectionPlanDeleteEligibility(planId))
}

export async function deletePlan(planId: string): Promise<void> {
  unwrap(await deleteCollectionPlan(planId))
}

export async function setPlanEnabled(
  planId: string,
  enabled: boolean,
): Promise<CollectionPlanResponse> {
  return unwrap(await updateCollectionPlanEnabled(planId, { enabled }))
}

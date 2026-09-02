import {
  addKeywordToPack,
  createCollectionPlan,
  createKeywordPack,
  getCollectionCapabilities,
  getCollectionPlan,
  getGlobalRelevanceConfig,
  getKeywordPack,
  listCollectionPlans,
  listKeywordPacks,
  listVehicleModels,
  setGlobalRelevanceConfig,
  updateCollectionPlanEnabled,
  updateKeywordPackEnabled,
  type CollectionCapabilitiesResponse,
  type CollectionPlanCreateRequest,
  type CollectionPlanListResponse,
  type CollectionPlanResponse,
  type GlobalRelevanceConfigResponse,
  type HttpErrorResponse,
  type KeywordPackCreateRequest,
  type KeywordPackKeywordCreateRequest,
  type KeywordPackListResponse,
  type KeywordPackResponse,
  type KeywordPackSummaryResponse,
  type ListCollectionPlansParams,
  type ListKeywordPacksParams,
  type ListVehicleModelsParams,
  type VehicleModelListResponse,
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

export async function addPackKeyword(
  packId: string,
  request: KeywordPackKeywordCreateRequest,
): Promise<KeywordPackResponse> {
  return unwrap(await addKeywordToPack(packId, request))
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

export async function setPlanEnabled(
  planId: string,
  enabled: boolean,
): Promise<CollectionPlanResponse> {
  return unwrap(await updateCollectionPlanEnabled(planId, { enabled }))
}

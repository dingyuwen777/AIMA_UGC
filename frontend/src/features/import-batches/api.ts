import {
  cancelDataImportCampaign,
  createCollectionRun,
  createLocalDataImportCampaign,
  createServerDataImportCampaign,
  createImportBatch,
  finalizeLocalDataImportCampaign,
  getCollectionCampaignSupplementEligibility,
  getCollectionBatchSupplementEligibility,
  getCollectionCapabilities,
  getCollectionRun,
  getCollectionRuntimeSummary,
  getDataImportCampaign,
  getImportBatch,
  getImportBatchSummary,
  listCollectionRuntimeRuns,
  listContents,
  listDataImportCampaignConflicts,
  listDataImportCampaignItems,
  listDataImportCampaigns,
  listDataImportServerDirectories,
  listImportBatches,
  listKeywordPacks,
  retryDataImportCampaignFailedItems,
  startDataImportCampaign,
  uploadLocalDataImportFile,
  type CollectionCapabilitiesResponse,
  type CollectionPlatform,
  type CollectionRunCreateRequest,
  type CollectionRunCreatedResponse,
  type CollectionRunResponse,
  type CollectionRuntimeListResponse,
  type CollectionRuntimeSummaryResponse,
  type HttpErrorResponse,
  type HttpErrorItem,
  type HistoricalCampaignConflictListResponse,
  type HistoricalCampaignCreateRequest,
  type HistoricalCampaignCreatedResponse,
  type HistoricalCampaignItemListResponse,
  type HistoricalCampaignListResponse,
  type HistoricalCampaignResponse,
  type HistoricalDirectoryListResponse,
  type ImportBatchCreatedResponse,
  type ImportBatchListResponse,
  type ImportBatchResponse,
  type ImportBatchSummaryResponse,
  type KeywordPackSummaryResponse,
  type LocalDataImportCampaignCreatedResponse,
  type LocalDataImportCampaignCreateRequest,
  type LocalDataImportFileUploadedResponse,
  type ListImportBatchesParams,
  type ListCollectionRuntimeRunsParams,
} from '../../generated/api/client'
import { httpErrorDetail } from '../../shared/api/http'

export class ImportApiError extends Error {
  readonly status: number
  readonly requestId: string
  readonly errors: readonly HttpErrorItem[]

  constructor(response: HttpErrorResponse) {
    super(httpErrorDetail(response))
    this.name = 'ImportApiError'
    this.status = response.status
    this.requestId = response.request_id
    this.errors = response.errors ?? []
  }
}

function isHttpErrorResponse(value: unknown): value is HttpErrorResponse {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.status === 'number' &&
    typeof candidate.detail === 'string' &&
    typeof candidate.request_id === 'string'
  )
}

function unwrap<T>(value: T): T {
  if (isHttpErrorResponse(value)) throw new ImportApiError(value)
  return value
}

export async function fetchImportBatchList(
  params: ListImportBatchesParams,
): Promise<ImportBatchListResponse> {
  return unwrap(await listImportBatches(params))
}

export async function fetchImportBatchSummary(): Promise<ImportBatchSummaryResponse> {
  return unwrap(await getImportBatchSummary())
}

export async function fetchImportBatchDetail(batchId: string): Promise<ImportBatchResponse> {
  return unwrap(await getImportBatch(batchId))
}

export async function uploadImportBatch(
  file: File,
  keywordPackIds: string[],
  vehicleModelIds: string[] = [],
): Promise<ImportBatchCreatedResponse> {
  return unwrap(await createImportBatch({
    file,
    keyword_pack_ids: keywordPackIds,
    vehicle_model_ids: vehicleModelIds,
  }))
}

/** 分页读取全部已启用词包，供导入与补采流程选择。 */
export async function fetchEnabledKeywordPacks(): Promise<KeywordPackSummaryResponse[]> {
  const first = unwrap(await listKeywordPacks({ enabled: true, offset: 0, limit: 100 }))
  const items = [...first.items]
  let offset = items.length
  while (offset < first.total) {
    const page = unwrap(await listKeywordPacks({ enabled: true, offset, limit: 100 }))
    if (page.items.length === 0) break
    items.push(...page.items)
    offset += page.items.length
  }
  return items
}

export async function fetchCollectionRuntimeList(
  params: ListCollectionRuntimeRunsParams,
): Promise<CollectionRuntimeListResponse> {
  return unwrap(await listCollectionRuntimeRuns(params))
}

export async function fetchCollectionRuntimeSummary(): Promise<CollectionRuntimeSummaryResponse> {
  return unwrap(await getCollectionRuntimeSummary())
}

export async function fetchCollectionCapabilities(): Promise<CollectionCapabilitiesResponse> {
  return unwrap(await getCollectionCapabilities())
}

export async function createTikHubCollectionRun(
  request: CollectionRunCreateRequest,
): Promise<CollectionRunCreatedResponse> {
  return unwrap(await createCollectionRun(request))
}

export async function fetchCollectionRunDetail(runId: string): Promise<CollectionRunResponse> {
  return unwrap(await getCollectionRun(runId))
}

export async function fetchBatchContentPlatforms(
  batchId: string,
  platforms: readonly CollectionPlatform[],
): Promise<CollectionPlatform[]> {
  const eligibility = unwrap(await getCollectionBatchSupplementEligibility(batchId))
  const eligible = new Set(eligibility.targets.map((item) => item.platform))
  return platforms.filter((platform) => eligible.has(platform))
}

export async function fetchCampaignContentPlatforms(
  campaignId: string,
  platforms: readonly CollectionPlatform[],
): Promise<CollectionPlatform[]> {
  const eligibility = unwrap(await getCollectionCampaignSupplementEligibility(campaignId))
  const eligible = new Set(eligibility.targets.map((item) => item.platform))
  return platforms.filter((platform) => eligible.has(platform))
}

export async function fetchHistoricalDirectory(
  relativePath = '',
  cursor?: string,
): Promise<HistoricalDirectoryListResponse> {
  return unwrap(await listDataImportServerDirectories({
    relative_path: relativePath,
    cursor,
    limit: 500,
  }))
}

export async function fetchHistoricalCampaigns(): Promise<HistoricalCampaignListResponse> {
  return unwrap(await listDataImportCampaigns())
}

export async function fetchHistoricalCampaign(
  campaignId: string,
): Promise<HistoricalCampaignResponse> {
  return unwrap(await getDataImportCampaign(campaignId))
}

export async function fetchHistoricalCampaignItems(
  campaignId: string,
): Promise<HistoricalCampaignItemListResponse> {
  return unwrap(await listDataImportCampaignItems(campaignId))
}

export async function fetchHistoricalCampaignConflicts(
  campaignId: string,
): Promise<HistoricalCampaignConflictListResponse> {
  return unwrap(await listDataImportCampaignConflicts(campaignId))
}

export async function createHistoricalCampaign(
  request: HistoricalCampaignCreateRequest,
): Promise<HistoricalCampaignCreatedResponse> {
  return unwrap(await createServerDataImportCampaign(request))
}

export async function createLocalCampaign(
  request: LocalDataImportCampaignCreateRequest,
): Promise<LocalDataImportCampaignCreatedResponse> {
  return unwrap(await createLocalDataImportCampaign(request))
}

export async function uploadLocalCampaignFile(
  campaignId: string,
  itemId: string,
  file: File,
): Promise<LocalDataImportFileUploadedResponse> {
  return unwrap(await uploadLocalDataImportFile(campaignId, itemId, { file }))
}

export async function finalizeLocalCampaign(
  campaignId: string,
): Promise<HistoricalCampaignResponse> {
  return unwrap(await finalizeLocalDataImportCampaign(campaignId))
}

export async function startHistoricalCampaign(
  campaignId: string,
): Promise<HistoricalCampaignResponse> {
  return unwrap(await startDataImportCampaign(campaignId))
}

export async function cancelHistoricalCampaign(
  campaignId: string,
): Promise<HistoricalCampaignResponse> {
  return unwrap(await cancelDataImportCampaign(campaignId))
}

export async function retryHistoricalCampaign(
  campaignId: string,
): Promise<HistoricalCampaignResponse> {
  return unwrap(await retryDataImportCampaignFailedItems(campaignId))
}

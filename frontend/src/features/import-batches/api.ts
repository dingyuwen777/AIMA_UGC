import {
  createCollectionRun,
  createImportBatch,
  getCollectionCapabilities,
  getCollectionRun,
  getCollectionRuntimeSummary,
  getImportBatch,
  getImportBatchSummary,
  listCollectionRuntimeRuns,
  listContents,
  listImportBatches,
  type CollectionCapabilitiesResponse,
  type CollectionPlatform,
  type CollectionRunCreateRequest,
  type CollectionRunCreatedResponse,
  type CollectionRunResponse,
  type CollectionRuntimeListResponse,
  type CollectionRuntimeSummaryResponse,
  type HttpErrorResponse,
  type ImportBatchCreatedResponse,
  type ImportBatchListResponse,
  type ImportBatchResponse,
  type ImportBatchSummaryResponse,
  type ListImportBatchesParams,
  type ListCollectionRuntimeRunsParams,
} from '../../generated/api/client'

export class ImportApiError extends Error {
  readonly status: number
  readonly requestId: string

  constructor(response: HttpErrorResponse) {
    super(response.detail)
    this.name = 'ImportApiError'
    this.status = response.status
    this.requestId = response.request_id
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

export async function uploadImportBatch(file: File): Promise<ImportBatchCreatedResponse> {
  return unwrap(await createImportBatch({ file }))
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


async function batchHasPlatformContent(batchId: string, platform: CollectionPlatform): Promise<boolean> {
  const params = {
    source_identifier: batchId,
    platforms: [platform],
    limit: 1,
  }
  const visible = unwrap(await listContents(params))
  if (visible.items.length > 0) return true

  // Voice Plaza 默认隐藏当前 Analysis 明确为 irrelevant 的 Content，
  // 而 Batch Supplement target reader 按来源账本读取，不应用该展示过滤。
  // 只有默认探测为空时再补一次 irrelevant 查询，使资格判断与后端补采语义一致。
  const irrelevant = unwrap(await listContents({ ...params, relevance: 'irrelevant' }))
  return irrelevant.items.length > 0
}

export async function fetchBatchContentPlatforms(
  batchId: string,
  platforms: readonly CollectionPlatform[],
): Promise<CollectionPlatform[]> {
  const matches = await Promise.all(
    platforms.map(async (platform) =>
      (await batchHasPlatformContent(batchId, platform)) ? platform : null,
    ),
  )
  return matches.filter((platform): platform is CollectionPlatform => platform !== null)
}

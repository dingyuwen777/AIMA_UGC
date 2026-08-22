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
  const visible = unwrap(
    await listContents({
      source_identifier: batchId,
      platforms: [platform],
      limit: 1,
    }),
  )
  return visible.items.length > 0
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

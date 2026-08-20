import {
  createImportBatch,
  getImportBatch,
  getImportBatchSummary,
  listImportBatches,
  type HttpErrorResponse,
  type ImportBatchCreatedResponse,
  type ImportBatchListResponse,
  type ImportBatchResponse,
  type ImportBatchSummaryResponse,
  type ListImportBatchesParams,
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

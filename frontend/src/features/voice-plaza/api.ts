import {
  createContentAnalysis,
  createDataExport,
  downloadDataExport,
  getContent,
  getContentAnalysisCapabilities,
  getContentAnalysisJob,
  getDataExport,
  listContents,
  listDataExports,
  type ContentAnalysisCapabilitiesResponse,
  type ContentAnalysisCreatedResponse,
  type ContentAnalysisSubmitRequest,
  type ContentDetailResponse,
  type ContentListResponse,
  type DataExportCreatedResponse,
  type DataExportListResponse,
  type DataExportResponse,
  type DataExportSubmitRequest,
  type HttpErrorResponse,
  type JobStatusResponse,
  type ListContentsParams,
} from '../../generated/api/client'

export class VoicePlazaApiError extends Error {
  readonly status: number
  readonly requestId: string

  constructor(response: HttpErrorResponse) {
    super(response.detail)
    this.name = 'VoicePlazaApiError'
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
  if (isHttpErrorResponse(value)) throw new VoicePlazaApiError(value)
  return value
}

export async function fetchContents(params: ListContentsParams): Promise<ContentListResponse> {
  return unwrap(await listContents(params))
}

export async function fetchContentDetail(contentId: string): Promise<ContentDetailResponse> {
  return unwrap(await getContent(contentId))
}

export async function fetchContentAnalysisCapabilities(): Promise<ContentAnalysisCapabilitiesResponse> {
  return unwrap(await getContentAnalysisCapabilities())
}

export async function submitContentAnalysis(
  request: ContentAnalysisSubmitRequest,
): Promise<ContentAnalysisCreatedResponse> {
  return unwrap(await createContentAnalysis(request))
}

export async function fetchContentAnalysisJob(jobId: string): Promise<JobStatusResponse> {
  return unwrap(await getContentAnalysisJob(jobId))
}

export async function submitDataExport(
  request: DataExportSubmitRequest,
): Promise<DataExportCreatedResponse> {
  return unwrap(await createDataExport(request))
}

export async function fetchDataExports(): Promise<DataExportListResponse> {
  return unwrap(await listDataExports())
}

export async function fetchDataExport(exportId: string): Promise<DataExportResponse> {
  return unwrap(await getDataExport(exportId))
}

export async function fetchDataExportFile(exportId: string): Promise<Blob> {
  const result = unwrap(await downloadDataExport(exportId))
  if (!(result instanceof Blob)) throw new Error('导出文件响应格式无效。')
  if (result.type.includes('json')) {
    let parsed: unknown
    try {
      parsed = JSON.parse(await result.text())
    } catch {
      throw new Error('导出错误响应格式无效。')
    }
    if (isHttpErrorResponse(parsed)) throw new VoicePlazaApiError(parsed)
    throw new Error('导出错误响应不符合统一 HTTP Error Contract。')
  }
  return result
}

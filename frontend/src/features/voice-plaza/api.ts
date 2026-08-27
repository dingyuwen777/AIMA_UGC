import {
  cancelContentAnalysisRun,
  createContentAnalysisRun,
  createContentAnalysis,
  createContentRelevanceReview,
  createDataExport,
  downloadDataExport,
  getContent,
  getContentAnalysisRun,
  getContentAnalysisCapabilities,
  getContentAnalysisJob,
  getDataExport,
  listContents,
  listContentAnalysisRuns,
  listDataExports,
  previewContentAnalysisRun,
  type AnalysisContentRunCreateRequest,
  type AnalysisContentRunCreatedResponse,
  type AnalysisContentRunListResponse,
  type AnalysisContentRunPreviewRequest,
  type AnalysisContentRunPreviewResponse,
  type AnalysisContentRunResponse,
  type ContentAnalysisCapabilitiesResponse,
  type ContentAnalysisCreatedResponse,
  type ContentAnalysisSubmitRequest,
  type ContentDetailResponse,
  type ContentListResponse,
  type ContentRelevanceReviewRequest,
  type ContentRelevanceReviewResponse,
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

export async function previewAnalysisRun(
  request: AnalysisContentRunPreviewRequest,
): Promise<AnalysisContentRunPreviewResponse> {
  return unwrap(await previewContentAnalysisRun(request))
}

export async function submitAnalysisRun(
  request: AnalysisContentRunCreateRequest,
): Promise<AnalysisContentRunCreatedResponse> {
  return unwrap(await createContentAnalysisRun(request))
}

export async function fetchAnalysisRuns(): Promise<AnalysisContentRunListResponse> {
  const response = unwrap(await listContentAnalysisRuns())
  if (!response || !Array.isArray(response.items)) {
    throw new Error('AI Analysis Run 历史响应格式无效。')
  }
  return response
}

export async function fetchAnalysisRun(runId: string): Promise<AnalysisContentRunResponse> {
  return unwrap(await getContentAnalysisRun(runId))
}

export async function cancelAnalysisRun(runId: string): Promise<AnalysisContentRunResponse> {
  return unwrap(await cancelContentAnalysisRun(runId))
}

export async function submitContentRelevanceReview(
  request: ContentRelevanceReviewRequest,
): Promise<ContentRelevanceReviewResponse> {
  return unwrap(await createContentRelevanceReview(request))
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

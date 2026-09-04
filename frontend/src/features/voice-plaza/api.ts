import {
  countContents,
  createContentAnalysisRun,
  createContentAnalysis,
  createContentRelevanceReview,
  createDataExport,
  downloadDataExport,
  getContent,
  getContentAnalysisCapabilities,
  getContentAnalysisTaxonomy,
  getContentAnalysisJob,
  getExportColumnCatalog,
  getDataExport,
  listContents,
  listDataExports,
  previewContentAnalysisRun,
  reviewContentAnalysis,
  reviewContentVehicles,
  type AnalysisContentRunCreateRequest,
  type AnalysisContentRunCreatedResponse,
  type AnalysisContentRunPreviewRequest,
  type AnalysisContentRunPreviewResponse,
  type ContentAnalysisCapabilitiesResponse,
  type ContentAnalysisTaxonomyResponse,
  type ContentAnalysisManualReviewRequest,
  type ContentAnalysisManualReviewResponse,
  type ContentCountRequest,
  type ContentCountResponse,
  type ContentAnalysisCreatedResponse,
  type ContentAnalysisSubmitRequest,
  type ContentDetailResponse,
  type ContentListResponse,
  type ContentRelevanceReviewRequest,
  type ContentRelevanceReviewResponse,
  type ContentVehicleReviewRequest,
  type ContentVehicleReviewResponse,
  type DataExportCreatedResponse,
  type DataExportListResponse,
  type DataExportResponse,
  type DataExportSubmitRequest,
  type ExportColumnCatalogResponse,
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

export async function fetchContentCount(request: ContentCountRequest): Promise<ContentCountResponse> {
  return unwrap(await countContents(request))
}

export async function reviewVehicles(
  contentId: string,
  request: ContentVehicleReviewRequest,
): Promise<ContentVehicleReviewResponse> {
  return unwrap(await reviewContentVehicles(contentId, request))
}

export async function reviewAnalysis(
  contentId: string,
  request: ContentAnalysisManualReviewRequest,
): Promise<ContentAnalysisManualReviewResponse> {
  return unwrap(await reviewContentAnalysis(contentId, request))
}

/** 通过生成 Client 读取当前 Prompt Taxonomy 的安全只读投影。 */
export async function fetchContentAnalysisTaxonomy(): Promise<ContentAnalysisTaxonomyResponse> {
  return unwrap(await getContentAnalysisTaxonomy())
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

export async function fetchExportColumnCatalog(): Promise<ExportColumnCatalogResponse> {
  return unwrap(await getExportColumnCatalog())
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

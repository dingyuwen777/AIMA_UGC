import {
  cancelContentAnalysisRun,
  getContentAnalysisRun,
  listCollectionRuntimeRuns,
  listContentAnalysisRuns,
  listDataExports,
  type AnalysisContentRunResponse,
  type CollectionRuntimeItemResponse,
  type DataExportResponse,
  type HttpErrorResponse,
} from '../../generated/api/client'

/** 判断 generated client 返回值是否是统一 HTTP Error Contract。 */
function isHttpErrorResponse(value: unknown): value is HttpErrorResponse {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.status === 'number' &&
    typeof candidate.detail === 'string' &&
    typeof candidate.request_id === 'string'
  )
}

/** 把 generated client 的统一错误投影转换为前端可处理异常。 */
function unwrap<T>(value: T): T {
  if (isHttpErrorResponse(value)) {
    throw new Error(`${value.detail}（request_id: ${value.request_id}）`)
  }
  return value
}

/** 读取 Analysis Run，并对活动 Run 尽量补齐 Shard 级详情；详情失败时保留列表事实。 */
export async function fetchTaskCenterAnalysisRuns(): Promise<AnalysisContentRunResponse[]> {
  const response = unwrap(await listContentAnalysisRuns())
  const activeStatuses = new Set(['queued', 'running', 'cancelling'])
  return Promise.all(response.items.map(async (run) => {
    if (!activeStatuses.has(run.status)) return run
    try {
      return unwrap(await getContentAnalysisRun(run.id))
    } catch {
      return run
    }
  }))
}

/** 读取统一 Collection Runtime 投影；这里只消费既有 read model，不改变其物理任务 Owner。 */
export async function fetchTaskCenterCollectionRuns(): Promise<CollectionRuntimeItemResponse[]> {
  const response = unwrap(await listCollectionRuntimeRuns({ limit: 50 }))
  return response.items
}

/** 读取声音广场既有 Excel 导出任务列表。 */
export async function fetchTaskCenterDataExports(): Promise<DataExportResponse[]> {
  const response = unwrap(await listDataExports())
  return response.items
}

/** 从全局任务中心取消仍允许取消的 Analysis Run。 */
export async function cancelTaskCenterAnalysisRun(runId: string): Promise<AnalysisContentRunResponse> {
  return unwrap(await cancelContentAnalysisRun(runId))
}

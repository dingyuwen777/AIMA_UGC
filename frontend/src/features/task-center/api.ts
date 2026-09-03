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

const COLLECTION_RUNTIME_PAGE_LIMIT = 100
const ACTIVE_COLLECTION_STATUSES = ['queued', 'running'] as const

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

/** 按单一活动状态翻完 Collection Runtime，避免较早但仍活动的任务被历史记录挤出首屏。 */
async function fetchAllActiveCollectionRuns(
  status: typeof ACTIVE_COLLECTION_STATUSES[number],
): Promise<CollectionRuntimeItemResponse[]> {
  const items: CollectionRuntimeItemResponse[] = []
  const seenCursors = new Set<string>()
  let cursor: string | undefined

  while (true) {
    const response = unwrap(await listCollectionRuntimeRuns(
      cursor
        ? { status, cursor, limit: COLLECTION_RUNTIME_PAGE_LIMIT }
        : { status, limit: COLLECTION_RUNTIME_PAGE_LIMIT },
    ))
    items.push(...response.items)
    if (!response.has_more) return items

    const nextCursor = response.next_cursor
    if (!nextCursor || seenCursors.has(nextCursor)) {
      throw new Error('Collection Runtime 分页返回了无效游标')
    }
    seenCursors.add(nextCursor)
    cursor = nextCursor
  }
}

/**
 * 读取统一 Collection Runtime 投影。
 * 首屏覆盖常见场景；只有历史超过单页时才额外按活动状态翻页，保证全局活动数量不会漏算。
 */
export async function fetchTaskCenterCollectionRuns(): Promise<CollectionRuntimeItemResponse[]> {
  const recentResponse = unwrap(await listCollectionRuntimeRuns({ limit: COLLECTION_RUNTIME_PAGE_LIMIT }))
  if (!recentResponse.has_more) return recentResponse.items

  const activeGroups = await Promise.all(
    ACTIVE_COLLECTION_STATUSES.map((status) => fetchAllActiveCollectionRuns(status)),
  )
  const merged = new Map(recentResponse.items.map((item) => [item.record_id, item]))
  for (const group of activeGroups) {
    for (const item of group) merged.set(item.record_id, item)
  }
  return [...merged.values()]
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

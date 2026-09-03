import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  AnalysisContentRunResponse,
  CollectionRuntimeItemResponse,
  DataExportResponse,
} from '../../generated/api/client'
import { platformLabel } from '../../shared/domain/platform'
import {
  cancelTaskCenterAnalysisRun,
  fetchTaskCenterAnalysisRuns,
  fetchTaskCenterCollectionRuns,
  fetchTaskCenterDataExports,
} from './api'

export type TaskCenterKind = 'analysis' | 'collection' | 'export'

export interface TaskCenterItem {
  key: string
  sourceId: string
  kind: TaskCenterKind
  title: string
  subtitle: string
  status: string
  statusLabel: string
  progress: number
  progressDetail: string
  active: boolean
  cancelable: boolean
  createdAt: string
  finishedAt: string | null
  href: '/voice-plaza' | '/collection-runtime'
  errorCode: string | null
}

const ACTIVE_ANALYSIS_STATUSES = new Set(['queued', 'running', 'cancelling'])
const ACTIVE_COLLECTION_STATUSES = new Set(['queued', 'running'])
const ACTIVE_EXPORT_STATUSES = new Set(['queued', 'running'])

const ANALYSIS_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  partial_failed: '部分失败',
  failed: '失败',
  cancelling: '取消中',
  cancelled: '已取消',
}

const COLLECTION_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '处理中',
  partial_success: '部分完成',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const EXPORT_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const COLLECTION_TYPE_LABELS: Record<string, string> = {
  excel_import: 'Excel 导入',
  tikhub_discovery: 'TikHub 采集',
  tikhub_batch_supplement: 'TikHub 补采',
}

/** 把未知异常转换为不会泄露请求正文的任务中心提示。 */
function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}

/** 计算 Analysis Run 的 Shard 加权进度；没有 Shard 时退回终态数量。 */
export function analysisRunProgress(run: AnalysisContentRunResponse): number {
  const shards = run.shards ?? []
  if (run.target_count > 0 && shards.length > 0) {
    const weighted = shards.reduce(
      (total, shard) => total + shard.target_count * shard.progress,
      0,
    )
    return Math.max(0, Math.min(100, Math.round(weighted / run.target_count)))
  }
  if (run.target_count <= 0) return 0
  const stats = run.stats
  const terminal = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) +
    (stats?.cancelled ?? 0) + (stats?.stale ?? 0)
  return Math.max(0, Math.min(100, Math.round(terminal * 100 / run.target_count)))
}

/** 将 Analysis Run 转成全局任务中心只读 ViewModel。 */
function analysisTask(run: AnalysisContentRunResponse): TaskCenterItem {
  const stats = run.stats
  const terminal = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) +
    (stats?.cancelled ?? 0) + (stats?.stale ?? 0)
  return {
    key: `analysis:${run.id}`,
    sourceId: run.id,
    kind: 'analysis',
    title: `AI 打标 · Run #${run.sequence_no}`,
    subtitle: `${run.target_count} 条 · ${run.model_provider} / ${run.model}`,
    status: run.status,
    statusLabel: ANALYSIS_STATUS_LABELS[run.status] ?? run.status,
    progress: analysisRunProgress(run),
    progressDetail: `${terminal} / ${run.target_count} 条已取得终态`,
    active: ACTIVE_ANALYSIS_STATUSES.has(run.status),
    cancelable: run.status === 'queued' || run.status === 'running',
    createdAt: run.created_at,
    finishedAt: run.finished_at ?? null,
    href: '/voice-plaza',
    errorCode: run.error_code ?? null,
  }
}

/** 将 Collection Runtime read model 转成全局任务中心只读 ViewModel。 */
function collectionTask(run: CollectionRuntimeItemResponse): TaskCenterItem {
  const typeLabel = COLLECTION_TYPE_LABELS[run.record_type] ?? run.record_type
  const platformText = run.platforms?.length
    ? run.platforms.map((platform) => platformLabel(platform)).join(' / ')
    : '平台未指定'
  const contentCount = run.collection_stats?.content_count
  const rowsIngested = run.import_stats?.rows_ingested
  const resultText = typeof contentCount === 'number'
    ? `${contentCount} 条内容`
    : typeof rowsIngested === 'number'
      ? `${rowsIngested} 行入库`
      : run.stage
  return {
    key: `collection:${run.record_id}`,
    sourceId: run.record_id,
    kind: 'collection',
    title: run.display_name || typeLabel,
    subtitle: `${typeLabel} · ${platformText}`,
    status: run.status,
    statusLabel: COLLECTION_STATUS_LABELS[run.status] ?? run.status,
    progress: run.progress,
    progressDetail: resultText,
    active: ACTIVE_COLLECTION_STATUSES.has(run.status),
    cancelable: false,
    createdAt: run.created_at,
    finishedAt: run.finished_at ?? null,
    href: '/collection-runtime',
    errorCode: run.error_code ?? null,
  }
}

/** 将 Data Export Job 转成全局任务中心只读 ViewModel。 */
function exportTask(item: DataExportResponse): TaskCenterItem {
  const contentCount = item.stats?.content_count
  return {
    key: `export:${item.id}`,
    sourceId: item.id,
    kind: 'export',
    title: 'Excel 导出',
    subtitle: item.filename || (typeof contentCount === 'number' ? `${contentCount} 条声音记录` : '声音广场导出'),
    status: item.job.status,
    statusLabel: EXPORT_STATUS_LABELS[item.job.status] ?? item.job.status,
    progress: item.job.progress,
    progressDetail: typeof contentCount === 'number' ? `${contentCount} 条内容` : `${item.job.progress}%`,
    active: ACTIVE_EXPORT_STATUSES.has(item.job.status),
    cancelable: false,
    createdAt: item.created_at,
    finishedAt: item.completed_at ?? item.job.finished_at ?? null,
    href: '/voice-plaza',
    errorCode: item.job.error_code ?? null,
  }
}

/** 按任务最新可观察时间倒序，保证活动任务和最近完成稳定排序。 */
function taskTime(item: TaskCenterItem): number {
  return Date.parse(item.finishedAt ?? item.createdAt) || 0
}

export const useTaskCenterStore = defineStore('task-center', () => {
  const open = ref(false)
  const loading = ref(false)
  const analysisRuns = ref<AnalysisContentRunResponse[]>([])
  const collectionRuns = ref<CollectionRuntimeItemResponse[]>([])
  const dataExports = ref<DataExportResponse[]>([])
  const warning = ref<string | null>(null)
  const cancellingAnalysisRunId = ref<string | null>(null)
  let refreshInFlight = false
  let pollHandle: ReturnType<typeof setInterval> | undefined

  const items = computed(() => [
    ...analysisRuns.value.map(analysisTask),
    ...collectionRuns.value.map(collectionTask),
    ...dataExports.value.map(exportTask),
  ])
  const activeItems = computed(() => items.value
    .filter((item) => item.active)
    .sort((left, right) => taskTime(right) - taskTime(left)))
  const recentItems = computed(() => items.value
    .filter((item) => !item.active)
    .sort((left, right) => taskTime(right) - taskTime(left))
    .slice(0, 12))
  const activeCount = computed(() => activeItems.value.length)

  /** 独立刷新三个既有 read model；单一来源失败时保留上次成功快照并明确提示。 */
  async function refresh(silent = false): Promise<void> {
    if (refreshInFlight) return
    refreshInFlight = true
    if (!silent) loading.value = true
    const failures: string[] = []
    try {
      const [analysisResult, collectionResult, exportResult] = await Promise.allSettled([
        fetchTaskCenterAnalysisRuns(),
        fetchTaskCenterCollectionRuns(),
        fetchTaskCenterDataExports(),
      ])
      if (analysisResult.status === 'fulfilled') analysisRuns.value = analysisResult.value
      else failures.push(`AI 打标：${errorMessage(analysisResult.reason)}`)
      if (collectionResult.status === 'fulfilled') collectionRuns.value = collectionResult.value
      else failures.push(`采集运行：${errorMessage(collectionResult.reason)}`)
      if (exportResult.status === 'fulfilled') dataExports.value = exportResult.value
      else failures.push(`数据导出：${errorMessage(exportResult.reason)}`)
      warning.value = failures.length
        ? `部分任务状态暂不可更新，继续显示上次成功结果。${failures.join('；')}`
        : null
    } finally {
      refreshInFlight = false
      if (!silent) loading.value = false
    }
  }

  /** 打开全局任务中心并触发一次静默刷新，避免用户看到过久的旧快照。 */
  function openCenter(): void {
    open.value = true
    void refresh(true)
  }

  /** 关闭全局任务中心。 */
  function closeCenter(): void {
    open.value = false
  }

  /** 取消活动 Analysis Run，并同步全局任务列表。 */
  async function cancelAnalysisRun(runId: string): Promise<boolean> {
    if (cancellingAnalysisRunId.value) return false
    cancellingAnalysisRunId.value = runId
    try {
      const cancelled = await cancelTaskCenterAnalysisRun(runId)
      analysisRuns.value = analysisRuns.value.map((run) => run.id === runId ? cancelled : run)
      await refresh(true)
      return true
    } catch (error) {
      warning.value = `AI 打标取消失败：${errorMessage(error)}`
      return false
    } finally {
      cancellingAnalysisRunId.value = null
    }
  }

  /** 启动全局只读轮询；后台标签页不发请求，避免无意义网络噪声。 */
  function startPolling(intervalMs = 15_000): void {
    stopPolling()
    if (typeof document === 'undefined') return
    pollHandle = setInterval(() => {
      if (document.visibilityState === 'hidden') return
      void refresh(true)
    }, intervalMs)
  }

  /** 停止全局任务轮询。 */
  function stopPolling(): void {
    if (!pollHandle) return
    clearInterval(pollHandle)
    pollHandle = undefined
  }

  return {
    open,
    loading,
    warning,
    analysisRuns,
    collectionRuns,
    dataExports,
    cancellingAnalysisRunId,
    items,
    activeItems,
    recentItems,
    activeCount,
    refresh,
    openCenter,
    closeCenter,
    cancelAnalysisRun,
    startPolling,
    stopPolling,
  }
})

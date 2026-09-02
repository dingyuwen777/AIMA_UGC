import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  AnalysisContentRunPreviewResponse,
  AnalysisContentRunResponse,
  AnalysisRunTargetSelection,
  ContentAnalysisManualReviewRequest,
  ContentAnalysisStatus,
  ContentAnalysisTaxonomyResponse,
  ContentCountResponse,
  ContentDetailResponse,
  ContentFilterSnapshot,
  ContentListItemResponse,
  ContentRelevance,
  ContentRelevanceReviewRequestDecision,
  ContentRelevanceReviewResponse,
  ContentTargetSelection,
  DataExportResponse,
  ExportColumnCatalogResponse,
  ExportColumnKey,
  ListContentsParams,
  PlatformName,
} from '../../generated/api/client'
import { beijingDayBoundary } from '../../shared/domain/beijingTime'
import {
  VoicePlazaApiError,
  cancelAnalysisRun,
  fetchAnalysisRun,
  fetchAnalysisRuns,
  fetchContentAnalysisCapabilities,
  fetchContentAnalysisTaxonomy,
  fetchContentCount,
  fetchContentDetail,
  fetchContents,
  fetchDataExport,
  fetchDataExportFile,
  fetchDataExports,
  fetchExportColumnCatalog,
  previewAnalysisRun,
  reviewAnalysis,
  reviewVehicles,
  submitAnalysisRun,
  submitContentRelevanceReview,
  submitDataExport,
} from './api'

export interface VoicePlazaFilters {
  search: string
  platform: '' | PlatformName
  contentType: string
  analysisStatus: '' | ContentAnalysisStatus
  relevance: '' | ContentRelevance
  voiceType: string
  sentiment: string
  primaryLabel: string
  secondaryLabel: string
  publishedFrom: string
  publishedTo: string
  sourceIdentifier: string
  vehicleModelIds: string[]
}

const EMPTY_FILTERS: VoicePlazaFilters = {
  search: '',
  platform: '',
  contentType: '',
  analysisStatus: '',
  relevance: '',
  voiceType: '',
  sentiment: '',
  primaryLabel: '',
  secondaryLabel: '',
  publishedFrom: '',
  publishedTo: '',
  sourceIdentifier: '',
  vehicleModelIds: [],
}

function errorMessage(error: unknown): string {
  if (error instanceof VoicePlazaApiError) {
    return `${error.message}（request_id: ${error.requestId}）`
  }
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}

function relevanceReviewNotice(
  decision: ContentRelevanceReviewRequestDecision,
  result: ContentRelevanceReviewResponse,
): string {
  const unchanged = result.unchanged_count > 0 ? `，${result.unchanged_count} 条无需变化` : ''
  if (decision === 'relevant') return `已人工标记 ${result.changed_count} 条内容为相关${unchanged}。`
  if (decision === 'irrelevant') return `已人工标记 ${result.changed_count} 条内容为不相关${unchanged}。`
  return `已撤销 ${result.changed_count} 条人工相关性判断${unchanged}。`
}

export const useVoicePlazaStore = defineStore('voice-plaza', () => {
  const filters = reactive<VoicePlazaFilters>({ ...EMPTY_FILTERS })
  const items = ref<ContentListItemResponse[]>([])
  const detail = ref<ContentDetailResponse | null>(null)
  const selectedIds = ref<string[]>([])
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(false)
  const exports = ref<DataExportResponse[]>([])
  const analysisRuns = ref<AnalysisContentRunResponse[]>([])
  const analysisPreview = ref<AnalysisContentRunPreviewResponse | null>(null)
  const analysisConfigured = ref<boolean | null>(null)
  const taxonomy = ref<ContentAnalysisTaxonomyResponse | null>(null)
  const taxonomyLoading = ref(false)
  const taxonomyError = ref<string | null>(null)
  const contentCount = ref<ContentCountResponse | null>(null)
  const exportColumnCatalog = ref<ExportColumnCatalogResponse | null>(null)
  const loading = ref(false)
  const loadingNext = ref(false)
  const loadingDetail = ref(false)
  const submittingAnalysis = ref(false)
  const previewingAnalysis = ref(false)
  const cancellingAnalysisRunId = ref<string | null>(null)
  const submittingExport = ref(false)
  const reviewingRelevance = ref(false)
  const reviewingDetail = ref(false)
  const countLoading = ref(false)
  const error = ref<string | null>(null)
  const listError = ref<string | null>(null)
  const notice = ref<string | null>(null)
  let analysisDraft: {
    targets: AnalysisRunTargetSelection
    clientIdempotencyKey: string
  } | null = null
  let pollHandle: ReturnType<typeof setInterval> | undefined

  const allVisibleSelected = computed(
    () => items.value.length > 0 && items.value.every((item) => selectedIds.value.includes(item.id)),
  )
  const hasActiveAnalysisRuns = computed(() =>
  analysisRuns.value.some((item) =>
    item.status === 'queued' || item.status === 'running' || item.status === 'cancelling'),
)
const hasActiveExportJobs = computed(() =>
  exports.value.some((item) => item.job.status === 'queued' || item.job.status === 'running'),
)
const hasActiveJobs = computed(() => hasActiveAnalysisRuns.value || hasActiveExportJobs.value)

  function filterSnapshot(): ContentFilterSnapshot {
    return {
      search: filters.search.trim() || undefined,
      platforms: filters.platform ? [filters.platform] : undefined,
      content_types: filters.contentType ? [filters.contentType] : undefined,
      analysis_status: filters.analysisStatus || undefined,
      relevance: filters.relevance || undefined,
      voice_type: filters.voiceType.trim() || undefined,
      sentiment: filters.sentiment.trim() || undefined,
      primary_label: filters.primaryLabel.trim() || undefined,
      secondary_label: filters.secondaryLabel.trim() || undefined,
      published_from: beijingDayBoundary(filters.publishedFrom, 'start'),
      published_to: beijingDayBoundary(filters.publishedTo, 'end'),
      source_identifier: filters.sourceIdentifier.trim() || undefined,
      vehicle_model_ids: filters.vehicleModelIds.length ? [...filters.vehicleModelIds] : undefined,
    }
  }

  function listParams(cursor?: string): ListContentsParams {
    return { ...filterSnapshot(), cursor, limit: 20 }
  }

  function targetSelection(scope: 'query' | 'selected'): ContentTargetSelection {
    return scope === 'query'
      ? { scope, filters: filterSnapshot() }
      : { scope, content_ids: [...selectedIds.value] }
  }

  function analysisTargetSelection(): AnalysisRunTargetSelection {
    return { scope: 'selected', content_ids: [...selectedIds.value] }
  }

  async function refresh(silent = false): Promise<void> {
    if (!silent) loading.value = true
    listError.value = null
    error.value = null
    try {
      const page = await fetchContents(listParams())
      items.value = page.items
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
      selectedIds.value = selectedIds.value.filter((id) => page.items.some((item) => item.id === id))
      if (detail.value) detail.value = await fetchContentDetail(detail.value.id)
    } catch (reason) {
      const message = errorMessage(reason)
      listError.value = message
      error.value = message
    } finally {
      if (!silent) loading.value = false
    }
  }

  /** 重新读取当前已加载的 Cursor 窗口，刷新内容状态但不把列表折叠回第一页。 */
async function refreshLoadedWindow(): Promise<void> {
  const targetCount = Math.max(items.value.length, 20)
  listError.value = null
  error.value = null
  try {
    const refreshed: ContentListItemResponse[] = []
    const seenIds = new Set<string>()
    const seenCursors = new Set<string>()
    let cursor: string | undefined
    let pageHasMore = false
    let pageNext: string | null = null
    while (true) {
      const page = await fetchContents(listParams(cursor))
      for (const item of page.items) {
        if (seenIds.has(item.id)) continue
        seenIds.add(item.id)
        refreshed.push(item)
      }
      pageHasMore = page.has_more
      pageNext = page.next_cursor ?? null
      if (!pageHasMore || !pageNext || refreshed.length >= targetCount || seenCursors.has(pageNext)) break
      seenCursors.add(pageNext)
      cursor = pageNext
    }
    items.value = refreshed
    nextCursor.value = pageNext
    hasMore.value = pageHasMore
    selectedIds.value = selectedIds.value.filter((id) => seenIds.has(id))
    if (detail.value) detail.value = await fetchContentDetail(detail.value.id)
  } catch (reason) {
    const message = errorMessage(reason)
    listError.value = message
    error.value = message
  }
}

async function refreshAnalysisCapabilities(): Promise<void> {
    try {
      const capability = await fetchContentAnalysisCapabilities()
      analysisConfigured.value = capability.configured
    } catch (reason) {
      analysisConfigured.value = null
      error.value = errorMessage(reason)
    }
  }

  /** 读取当前 Prompt Taxonomy，并清理部署切换后已经失效的分类筛选。 */
  async function refreshTaxonomy(): Promise<void> {
    taxonomyLoading.value = true
    taxonomyError.value = null
    try {
      const loaded = await fetchContentAnalysisTaxonomy()
      taxonomy.value = loaded
      if (!loaded.sentiments.includes(filters.sentiment)) filters.sentiment = ''
      if (!loaded.voice_types.includes(filters.voiceType)) filters.voiceType = ''
      const labelGroup = loaded.labels.find((item) => item.primary_label === filters.primaryLabel)
      if (!labelGroup) {
        filters.primaryLabel = ''
        filters.secondaryLabel = ''
      } else if (!labelGroup.secondary_labels.includes(filters.secondaryLabel)) {
        filters.secondaryLabel = ''
      }
    } catch (reason) {
      taxonomy.value = null
      filters.sentiment = ''
      filters.voiceType = ''
      filters.primaryLabel = ''
      filters.secondaryLabel = ''
      taxonomyError.value = errorMessage(reason)
    } finally {
      taxonomyLoading.value = false
    }
  }

  async function loadNext(): Promise<void> {
    if (!nextCursor.value || loadingNext.value) return
    loadingNext.value = true
    error.value = null
    try {
      const page = await fetchContents(listParams(nextCursor.value))
      items.value = [...items.value, ...page.items]
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingNext.value = false
    }
  }

  async function refreshCount(mode: 'exact' | 'estimated'): Promise<void> {
    countLoading.value = true
    error.value = null
    try {
      contentCount.value = await fetchContentCount({
        filters: filterSnapshot(),
        count_mode: mode,
        exact_limit: mode === 'exact' ? 100_000 : undefined,
      })
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      countLoading.value = false
    }
  }

  async function openDetail(contentId: string): Promise<void> {
    loadingDetail.value = true
    error.value = null
    try {
      detail.value = await fetchContentDetail(contentId)
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingDetail.value = false
    }
  }

  function closeDetail(): void {
    detail.value = null
  }

  function toggleSelection(contentId: string): void {
    selectedIds.value = selectedIds.value.includes(contentId)
      ? selectedIds.value.filter((id) => id !== contentId)
      : [...selectedIds.value, contentId]
  }

  function toggleVisibleSelection(): void {
    selectedIds.value = allVisibleSelected.value ? [] : items.value.map((item) => item.id)
  }

  function clearSelection(): void {
    selectedIds.value = []
  }

  /** 提交相关性人工复核，并刷新当前已加载窗口而不折叠分页。 */
  async function reviewRelevance(
    contentIds: string[],
    decision: ContentRelevanceReviewRequestDecision,
  ): Promise<ContentRelevanceReviewResponse | null> {
    if (contentIds.length === 0 || reviewingRelevance.value) return null
    reviewingRelevance.value = true
    error.value = null
    notice.value = null
    try {
      const result = await submitContentRelevanceReview({
        content_ids: [...contentIds],
        decision,
      })
      selectedIds.value = selectedIds.value.filter((id) => !contentIds.includes(id))
      notice.value = relevanceReviewNotice(decision, result)
      await refreshLoadedWindow()
      return result
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      reviewingRelevance.value = false
    }
  }

  /** 保存详情页车型人工结论，并保持当前列表分页窗口。 */
  async function reviewDetailVehicles(
    vehicleModelIds: string[],
    unlockExisting: boolean,
  ): Promise<boolean> {
    if (!detail.value || reviewingDetail.value) return false
    reviewingDetail.value = true
    error.value = null
    try {
      await reviewVehicles(detail.value.id, {
        content_version: detail.value.content_version,
        vehicle_model_ids: vehicleModelIds,
        unlock_existing: unlockExisting,
      })
      detail.value = await fetchContentDetail(detail.value.id)
      notice.value = '车型人工结论已保存；后续自动处理不会覆盖人工锁定。'
      await refreshLoadedWindow()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      reviewingDetail.value = false
    }
  }

  /** 保存详情页分析人工纠正，并保持当前列表分页窗口。 */
  async function reviewDetailAnalysis(
    request: Omit<ContentAnalysisManualReviewRequest, 'content_version'>,
  ): Promise<boolean> {
    if (!detail.value || reviewingDetail.value) return false
    reviewingDetail.value = true
    error.value = null
    try {
      await reviewAnalysis(detail.value.id, {
        ...request,
        content_version: detail.value.content_version,
      })
      detail.value = await fetchContentDetail(detail.value.id)
      notice.value = '分析人工纠正已保存；修改已锁定维度前必须显式解锁。'
      await refreshLoadedWindow()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      reviewingDetail.value = false
    }
  }

  async function previewAnalysis(
    _scope: 'selected',
  ): Promise<AnalysisContentRunPreviewResponse | null> {
    if (analysisConfigured.value !== true) {
      error.value = '当前环境尚未配置可用的 AI 模型，请配置 LLM 后重启后端。'
      return null
    }
    if (selectedIds.value.length === 0) return null
    if (selectedIds.value.length > 1000) {
      error.value = '单次 AI Analysis Run 最多选择 1000 条内容。'
      return null
    }
    previewingAnalysis.value = true
    error.value = null
    analysisPreview.value = null
    const targets = analysisTargetSelection()
    try {
      const preview = await previewAnalysisRun({ targets })
      analysisDraft = {
        targets,
        clientIdempotencyKey: crypto.randomUUID(),
      }
      analysisPreview.value = preview
      return preview
    } catch (reason) {
      analysisDraft = null
      error.value = errorMessage(reason)
      return null
    } finally {
      previewingAnalysis.value = false
    }
  }

  async function confirmAnalysis(): Promise<number | null> {
    if (!analysisDraft || !analysisPreview.value || submittingAnalysis.value) return null
    submittingAnalysis.value = true
    error.value = null
    try {
      const created = await submitAnalysisRun({
        client_idempotency_key: analysisDraft.clientIdempotencyKey,
        expected_configuration_hash: analysisPreview.value.configuration_hash,
        expected_target_count: analysisPreview.value.target_count,
        run_intent: 'manual_reanalysis',
        targets: analysisDraft.targets,
      })
      await refreshAnalysisRuns()
      analysisDraft = null
      analysisPreview.value = null
      return created.target_count
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      submittingAnalysis.value = false
    }
  }

  async function refreshAnalysisRuns(): Promise<void> {
    try {
      const listedRuns = (await fetchAnalysisRuns()).items
      analysisRuns.value = await Promise.all(
        listedRuns.map((run) =>
          ['queued', 'running', 'cancelling'].includes(run.status)
            ? fetchAnalysisRun(run.id)
            : run,
        ),
      )
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function cancelRun(runId: string): Promise<boolean> {
    if (cancellingAnalysisRunId.value) return false
    cancellingAnalysisRunId.value = runId
    error.value = null
    try {
      const cancelled = await cancelAnalysisRun(runId)
      analysisRuns.value = analysisRuns.value.map((item) =>
        item.id === cancelled.id ? cancelled : item,
      )
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      cancellingAnalysisRunId.value = null
    }
  }

  async function refreshExports(): Promise<void> {
    try {
      const [response, catalog] = await Promise.all([
        fetchDataExports(),
        exportColumnCatalog.value
          ? Promise.resolve(exportColumnCatalog.value)
          : fetchExportColumnCatalog(),
      ])
      exports.value = response.items
      exportColumnCatalog.value = catalog
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function createExport(
    scope: 'query' | 'selected' | 'page',
    columns?: ExportColumnKey[],
  ): Promise<number | null> {
    if (scope === 'selected' && selectedIds.value.length === 0) return null
    if ((scope === 'page' || scope === 'query') && items.value.length === 0) return null
    submittingExport.value = true
    error.value = null
    try {
      const targets = scope === 'page'
        ? { scope: 'selected' as const, content_ids: items.value.map((item) => item.id) }
        : targetSelection(scope)
      const created = await submitDataExport({ targets, format: 'xlsx', columns })
      const record = await fetchDataExport(created.export_id)
      exports.value = [record, ...exports.value.filter((item) => item.id !== record.id)]
      return created.target_count
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      submittingExport.value = false
    }
  }

  async function downloadExport(exportId: string): Promise<Blob | null> {
    error.value = null
    try {
      return await fetchDataExportFile(exportId)
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    }
  }

  function resetFilters(): void {
    Object.assign(filters, EMPTY_FILTERS)
    clearSelection()
    notice.value = null
  }

  /** 刷新后台 Job 状态；仅分析任务需要同步内容窗口，纯导出任务不重载列表。 */
async function poll(): Promise<void> {
  if (document.visibilityState === 'hidden' || !hasActiveJobs.value) return
  try {
    const tasks: Promise<unknown>[] = [refreshExports(), refreshAnalysisRuns()]
    if (hasActiveAnalysisRuns.value) tasks.push(refreshLoadedWindow())
    await Promise.all(tasks)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

  function startPolling(intervalMilliseconds = 5000): void {
    stopPolling()
    pollHandle = setInterval(() => void poll(), intervalMilliseconds)
  }

  function stopPolling(): void {
    if (pollHandle !== undefined) clearInterval(pollHandle)
    pollHandle = undefined
  }

  return {
    filters,
    items,
    detail,
    selectedIds,
    exports,
    analysisRuns,
    analysisPreview,
    analysisConfigured,
    taxonomy,
    taxonomyLoading,
    taxonomyError,
    contentCount,
    exportColumnCatalog,
    hasMore,
    allVisibleSelected,
    hasActiveJobs,
    loading,
    loadingNext,
    loadingDetail,
    submittingAnalysis,
    previewingAnalysis,
    cancellingAnalysisRunId,
    submittingExport,
    reviewingRelevance,
    reviewingDetail,
    countLoading,
    error,
    listError,
    notice,
    refresh,
    refreshAnalysisCapabilities,
    refreshTaxonomy,
    refreshCount,
    loadNext,
    openDetail,
    closeDetail,
    toggleSelection,
    toggleVisibleSelection,
    clearSelection,
    reviewRelevance,
    reviewDetailVehicles,
    reviewDetailAnalysis,
    previewAnalysis,
    confirmAnalysis,
    refreshAnalysisRuns,
    cancelRun,
    refreshExports,
    createExport,
    downloadExport,
    resetFilters,
    startPolling,
    stopPolling,
  }
})

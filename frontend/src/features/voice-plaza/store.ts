import { computed, reactive, ref } from 'vue'
import { defineStore, storeToRefs } from 'pinia'

import type {
  AnalysisContentRunPreviewResponse,
  AnalysisRunTargetSelection,
  ContentAnalysisManualReviewRequest,
  ContentAnalysisStatus,
  ContentAnalysisTaxonomyResponse,
  ContentCountResponse,
  ContentDetailResponse,
  ContentFilterOptionsResponse,
  ContentFilterSnapshot,
  ContentFilterSnapshotCompetitionScopesItem,
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
import { createClientIdempotencyKey } from '../../shared/idempotency'
import { useTaskCenterStore } from '../task-center/store'
import {
  VoicePlazaApiError,
  fetchContentAnalysisCapabilities,
  fetchContentAnalysisTaxonomy,
  fetchContentCount,
  fetchContentDetail,
  fetchContentFilterOptions,
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
  brandIds: string[]
  vehicleModelIds: string[]
  competitionScopes: ContentFilterSnapshotCompetitionScopesItem[]
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
  brandIds: [],
  vehicleModelIds: [],
  competitionScopes: [],
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
  const taskCenter = useTaskCenterStore()
  const { analysisRuns, hasActiveAnalysisRuns, cancellingAnalysisRunId } = storeToRefs(taskCenter)
  const filters = reactive<VoicePlazaFilters>({ ...EMPTY_FILTERS })
  const sortBy = ref<'published_at' | 'follower_count'>('published_at')
  const sortDirection = ref<'asc' | 'desc'>('desc')
  const items = ref<ContentListItemResponse[]>([])
  const detail = ref<ContentDetailResponse | null>(null)
  const detailId = ref<string | null>(null)
  const detailError = ref<string | null>(null)
  let detailRevision = 0
  let listRevision = 0
  let analysisPreviewRevision = 0
  const selectedIds = ref<string[]>([])
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(false)
  const exports = ref<DataExportResponse[]>([])
  const analysisPreview = ref<AnalysisContentRunPreviewResponse | null>(null)
  const analysisConfigured = ref<boolean | null>(null)
  const taxonomy = ref<ContentAnalysisTaxonomyResponse | null>(null)
  const taxonomyLoading = ref(false)
  const taxonomyError = ref<string | null>(null)
  const filterOptions = ref<ContentFilterOptionsResponse | null>(null)
  const filterOptionsLoading = ref(false)
  const filterOptionsError = ref<string | null>(null)
  let filterOptionsRevision = 0
  const contentCount = ref<ContentCountResponse | null>(null)
  const exportColumnCatalog = ref<ExportColumnCatalogResponse | null>(null)
  const loading = ref(false)
  const loadingNext = ref(false)
  const loadingDetail = ref(false)
  const submittingAnalysis = ref(false)
  const previewingAnalysis = ref(false)
  const submittingExport = ref(false)
  const reviewingRelevance = ref(false)
  const reviewingDetail = ref(false)
  const countLoading = ref(false)
  const countError = ref<string | null>(null)
  let countRevision = 0
  const error = ref<string | null>(null)
  const listError = ref<string | null>(null)
  const notice = ref<string | null>(null)
  let analysisDraft: {
    targets: AnalysisRunTargetSelection
    clientIdempotencyKey: string
  } | null = null
  let windowRefreshInFlight = false
  let exportsRefreshInFlight = false
  let pollHandle: ReturnType<typeof setInterval> | undefined
  let pollRevision = 0
  let lastExportPollAt = 0
  let displayedAnalysisSignature = '[]'
  const analysisSignature = computed(() => JSON.stringify(analysisRuns.value.map((run) => [
    run.id, run.status, run.stats?.succeeded, run.stats?.failed, run.stats?.stale,
    run.stats?.cancelled,
  ]).sort(([left], [right]) => String(left).localeCompare(String(right)))))

  const allVisibleSelected = computed(
    () => items.value.length > 0 && items.value.every((item) => selectedIds.value.includes(item.id)),
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
      brand_ids: filters.brandIds.length ? [...filters.brandIds] : undefined,
      vehicle_model_ids: filters.vehicleModelIds.length ? [...filters.vehicleModelIds] : undefined,
      competition_scopes: filters.competitionScopes.length ? [...filters.competitionScopes] : undefined,
    }
  }

  function listParams(cursor?: string): ListContentsParams {
    // 排序参数仅用于列表，分析与导出继续使用既有筛选快照。
    return { ...filterSnapshot(), sort_by: sortBy.value, sort_direction: sortDirection.value, cursor, limit: 20 }
  }

  /** 新字段首次按降序浏览，再次点击切换方向，并重置旧排序的分页边界。 */
  async function changeSort(field: 'published_at' | 'follower_count'): Promise<void> {
    sortDirection.value = sortBy.value === field && sortDirection.value === 'desc' ? 'asc' : 'desc'
    sortBy.value = field
    selectedIds.value = []
    items.value = []
    nextCursor.value = null
    hasMore.value = false
    await refresh()
  }

  function targetSelection(scope: 'query' | 'selected'): ContentTargetSelection {
    return scope === 'query'
      ? { scope, filters: filterSnapshot() }
      : { scope, content_ids: [...selectedIds.value] }
  }

  function analysisTargetSelection(scope: 'selected' | 'all'): AnalysisRunTargetSelection {
    return scope === 'all'
      ? { scope: 'all' }
      : { scope: 'selected', content_ids: [...selectedIds.value] }
  }

  async function refresh(silent = false): Promise<void> {
    // 新查询拥有列表提交权，迟到的旧筛选或排序请求不得覆盖当前画面。
    const revision = ++listRevision
    if (!silent) loading.value = true
    listError.value = null
    error.value = null
    try {
      const page = await fetchContents(listParams())
      if (revision !== listRevision) return
      items.value = page.items
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
      selectedIds.value = selectedIds.value.filter((id) => page.items.some((item) => item.id === id))
      if (detailId.value) await openDetail(detailId.value)
    } catch (reason) {
      if (revision !== listRevision) return
      const message = errorMessage(reason)
      listError.value = message
      error.value = message
    } finally {
      if (!silent && revision === listRevision) loading.value = false
    }
  }

  /** 重新读取当前已加载的 Cursor 窗口，刷新内容状态但不把列表折叠回第一页。 */
async function refreshLoadedWindow(): Promise<boolean> {
  if (windowRefreshInFlight) return false
  windowRefreshInFlight = true
  const filtersAtStart = JSON.stringify(listParams())
  const revision = listRevision
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
    if (revision !== listRevision || filtersAtStart !== JSON.stringify(listParams())) return false
    items.value = refreshed
    nextCursor.value = pageNext
    hasMore.value = pageHasMore
    selectedIds.value = selectedIds.value.filter((id) => seenIds.has(id))
    if (detailId.value) await openDetail(detailId.value)
    return true
  } catch (reason) {
    if (revision !== listRevision || filtersAtStart !== JSON.stringify(listParams())) return false
    const message = errorMessage(reason)
    listError.value = message
    error.value = message
    return false
  } finally {
    windowRefreshInFlight = false
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

  /** 读取当前 Prompt Taxonomy；该目录只供人工纠正，不决定历史结果筛选。 */
  async function refreshTaxonomy(): Promise<void> {
    taxonomyLoading.value = true
    taxonomyError.value = null
    try {
      const loaded = await fetchContentAnalysisTaxonomy()
      taxonomy.value = loaded
    } catch (reason) {
      taxonomy.value = null
      taxonomyError.value = errorMessage(reason)
    } finally {
      taxonomyLoading.value = false
    }
  }

  /** 读取后端筛选目录，并清理已不再能命中当前可见内容的选择。 */
  async function refreshFilterOptions(): Promise<void> {
    const revision = ++filterOptionsRevision
    filterOptionsLoading.value = true
    filterOptionsError.value = null
    try {
      const loaded = await fetchContentFilterOptions()
      if (revision !== filterOptionsRevision) return
      filterOptions.value = loaded
      if (!loaded.platforms.includes(filters.platform as PlatformName)) filters.platform = ''
      if (!loaded.content_types.includes(filters.contentType)) filters.contentType = ''
      if (!loaded.analysis_statuses.includes(filters.analysisStatus as ContentAnalysisStatus)) {
        filters.analysisStatus = ''
      }
      if (!loaded.relevances.includes(filters.relevance as ContentRelevance)) filters.relevance = ''
      if (!loaded.sentiments.some((item) => item.value === filters.sentiment)) filters.sentiment = ''
      if (!loaded.voice_types.some((item) => item.value === filters.voiceType)) filters.voiceType = ''
      const labelGroup = loaded.labels.find((item) => item.primary_label === filters.primaryLabel)
      if (!labelGroup) {
        filters.primaryLabel = ''
        filters.secondaryLabel = ''
      } else if (!labelGroup.secondary_labels.some((item) => item.value === filters.secondaryLabel)) {
        filters.secondaryLabel = ''
      }
    } catch (reason) {
      if (revision !== filterOptionsRevision) return
      filterOptions.value = null
      filterOptionsError.value = errorMessage(reason)
    } finally {
      if (revision === filterOptionsRevision) filterOptionsLoading.value = false
    }
  }

  async function loadNext(): Promise<void> {
    // 换序或重新查询期间不复用旧 Cursor；丢弃换序之前在途的下一页。
    if (!nextCursor.value || loadingNext.value || loading.value) return
    const revision = listRevision
    loadingNext.value = true
    error.value = null
    try {
      const page = await fetchContents(listParams(nextCursor.value))
      if (revision !== listRevision) return
      items.value = [...items.value, ...page.items]
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
    } catch (reason) {
      if (revision !== listRevision) return
      error.value = errorMessage(reason)
    } finally {
      loadingNext.value = false
    }
  }

  async function refreshCount(mode: 'exact' | 'estimated'): Promise<void> {
    // 数量读取失败独立反馈，不覆盖正常内容；筛选变化后旧计数不能回写。
    const revision = ++countRevision
    const snapshot = filterSnapshot()
    countLoading.value = true
    countError.value = null
    contentCount.value = null
    try {
      const result = await fetchContentCount({
        filters: snapshot,
        count_mode: mode,
        exact_limit: mode === 'exact' ? 100_000 : undefined,
      })
      if (revision === countRevision && JSON.stringify(snapshot) === JSON.stringify(filterSnapshot())) contentCount.value = result
    } catch (reason) {
      if (revision === countRevision) countError.value = errorMessage(reason)
    } finally {
      if (revision === countRevision) countLoading.value = false
    }
  }

  async function openDetail(contentId: string): Promise<void> {
    // 抽屉开关独立于成功结果；请求失败保留原入口，关闭后忽略迟到响应。
    const revision = ++detailRevision
    if (detailId.value !== contentId) detail.value = null
    detailId.value = contentId
    detailError.value = null
    loadingDetail.value = true
    error.value = null
    try {
      const result = await fetchContentDetail(contentId)
      if (revision === detailRevision) detail.value = result
    } catch (reason) {
      if (revision === detailRevision) detailError.value = errorMessage(reason)
    } finally {
      if (revision === detailRevision) loadingDetail.value = false
    }
  }

  function closeDetail(): void {
    // 使当前请求失效，避免用户关闭后抽屉被网络回包重新打开。
    detailRevision++
    detailId.value = null
    detailError.value = null
    loadingDetail.value = false
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
      await refreshFilterOptions()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      reviewingDetail.value = false
    }
  }

  async function previewAnalysis(
    scope: 'selected' | 'all',
  ): Promise<AnalysisContentRunPreviewResponse | null> {
    const revision = ++analysisPreviewRevision
    analysisDraft = null
    analysisPreview.value = null
    previewingAnalysis.value = false
    if (analysisConfigured.value !== true) {
      error.value = 'AI 模型未配置，请先在管理台配置可用模型。'
      return null
    }
    if (scope === 'selected' && selectedIds.value.length === 0) return null
    if (scope === 'selected' && selectedIds.value.length > 1000) {
      error.value = '单次 AI 打标任务最多选择 1000 条内容。'
      return null
    }
    previewingAnalysis.value = true
    error.value = null
    analysisPreview.value = null
    const targets = analysisTargetSelection(scope)
    try {
      const preview = await previewAnalysisRun({ targets })
      if (revision !== analysisPreviewRevision) return null
      analysisDraft = {
        targets,
        clientIdempotencyKey: createClientIdempotencyKey(),
      }
      analysisPreview.value = preview
      return preview
    } catch (reason) {
      if (revision !== analysisPreviewRevision) return null
      analysisDraft = null
      error.value = errorMessage(reason)
      return null
    } finally {
      if (revision === analysisPreviewRevision) previewingAnalysis.value = false
    }
  }

  async function confirmAnalysis(): Promise<number | null> {
    if (!analysisDraft || !analysisPreview.value || previewingAnalysis.value || submittingAnalysis.value) return null
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
      await refreshAnalysisRuns(true)
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

  async function refreshAnalysisRuns(afterCreation = false): Promise<void> {
    await taskCenter.refreshAnalysisRuns(afterCreation)
    if (taskCenter.analysisError) error.value = taskCenter.analysisError
  }

  async function cancelRun(runId: string): Promise<boolean> {
    error.value = null
    const cancelled = await taskCenter.cancelAnalysisRun(runId)
    if (!cancelled && taskCenter.warning) error.value = taskCenter.warning
    return cancelled
  }

  async function refreshExports(): Promise<void> {
    if (exportsRefreshInFlight) return
    exportsRefreshInFlight = true
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
    } finally {
      exportsRefreshInFlight = false
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

  /** 先读落库进度再刷新内容；慢窗口未包含的新进度留到下一次，终态也不丢刷新。 */
  async function poll(): Promise<void> {
    if (pageIsHidden()) return
    const revision = pollRevision
    if (hasActiveExportJobs.value && Date.now() - lastExportPollAt >= 5000) {
      lastExportPollAt = Date.now()
      void refreshExports()
    }
    await taskCenter.pollAnalysisRuns()
    if (revision !== pollRevision || pageIsHidden()) return
    const signature = analysisSignature.value
    if (signature !== displayedAnalysisSignature && !loading.value && !loadingNext.value &&
      !filterOptionsLoading.value && await refreshLoadedWindow()) {
      await refreshFilterOptions()
      displayedAnalysisSignature = signature
    }
    if (taskCenter.analysisError) error.value = taskCenter.analysisError
  }

  function pageIsHidden(): boolean {
    return document.visibilityState === 'hidden'
  }

  function startPolling(intervalMilliseconds = 1000): void {
    stopPolling()
    lastExportPollAt = Date.now()
    pollHandle = setInterval(() => void poll(), intervalMilliseconds)
  }

  function stopPolling(): void {
    pollRevision += 1
    if (pollHandle !== undefined) clearInterval(pollHandle)
    pollHandle = undefined
  }

  return {
    filters,
    sortBy,
    sortDirection,
    changeSort,
    detailId,
    detailError,
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
    filterOptions,
    filterOptionsLoading,
    filterOptionsError,
    contentCount,
    countError,
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
    refreshFilterOptions,
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

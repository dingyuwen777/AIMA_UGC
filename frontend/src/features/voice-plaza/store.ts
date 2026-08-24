import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  ContentAnalysisStatus,
  ContentDetailResponse,
  ContentFilterSnapshot,
  ContentListItemResponse,
  ContentRelevance,
  ContentRelevanceReviewRequestDecision,
  ContentRelevanceReviewResponse,
  ContentTargetSelection,
  DataExportResponse,
  JobStatusResponse,
  ListContentsParams,
  PlatformName,
} from '../../generated/api/client'
import {
  VoicePlazaApiError,
  fetchContentAnalysisCapabilities,
  fetchContentAnalysisJob,
  fetchContentDetail,
  fetchContents,
  fetchDataExport,
  fetchDataExportFile,
  fetchDataExports,
  submitContentAnalysis,
  submitContentRelevanceReview,
  submitDataExport,
} from './api'

export interface VoicePlazaFilters {
  search: string
  platform: '' | PlatformName
  contentType: string
  analysisStatus: '' | ContentAnalysisStatus
  relevance: '' | ContentRelevance
  sentiment: string
  primaryLabel: string
  secondaryLabel: string
  publishedFrom: string
  publishedTo: string
  sourceIdentifier: string
}

const EMPTY_FILTERS: VoicePlazaFilters = {
  search: '',
  platform: '',
  contentType: '',
  analysisStatus: '',
  relevance: '',
  sentiment: '',
  primaryLabel: '',
  secondaryLabel: '',
  publishedFrom: '',
  publishedTo: '',
  sourceIdentifier: '',
}

function shanghaiBoundary(value: string, end = false): string | undefined {
  if (!value) return undefined
  return new Date(`${value}T${end ? '23:59:59.999' : '00:00:00'}+08:00`).toISOString()
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
  const analysisJob = ref<JobStatusResponse | null>(null)
  const analysisConfigured = ref<boolean | null>(null)
  const loading = ref(false)
  const loadingNext = ref(false)
  const loadingDetail = ref(false)
  const submittingAnalysis = ref(false)
  const submittingExport = ref(false)
  const reviewingRelevance = ref(false)
  const error = ref<string | null>(null)
  const notice = ref<string | null>(null)
  let analysisJobId: string | null = null
  let pollHandle: ReturnType<typeof setInterval> | undefined

  const allVisibleSelected = computed(
    () => items.value.length > 0 && items.value.every((item) => selectedIds.value.includes(item.id)),
  )
  const hasActiveJobs = computed(
    () =>
      analysisJob.value?.status === 'queued' ||
      analysisJob.value?.status === 'running' ||
      exports.value.some((item) => item.job.status === 'queued' || item.job.status === 'running'),
  )

  function filterSnapshot(): ContentFilterSnapshot {
    return {
      search: filters.search.trim() || undefined,
      platforms: filters.platform ? [filters.platform] : undefined,
      content_types: filters.contentType ? [filters.contentType] : undefined,
      analysis_status: filters.analysisStatus || undefined,
      relevance: filters.relevance || undefined,
      sentiment: filters.sentiment.trim() || undefined,
      primary_label: filters.primaryLabel.trim() || undefined,
      secondary_label: filters.secondaryLabel.trim() || undefined,
      published_from: shanghaiBoundary(filters.publishedFrom),
      published_to: shanghaiBoundary(filters.publishedTo, true),
      source_identifier: filters.sourceIdentifier.trim() || undefined,
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

  async function refresh(silent = false): Promise<void> {
    if (!silent) loading.value = true
    error.value = null
    try {
      const page = await fetchContents(listParams())
      items.value = page.items
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
      selectedIds.value = selectedIds.value.filter((id) => page.items.some((item) => item.id === id))
      if (detail.value) detail.value = await fetchContentDetail(detail.value.id)
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      if (!silent) loading.value = false
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
      await refresh(true)
      return result
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      reviewingRelevance.value = false
    }
  }

  async function createAnalysis(scope: 'query' | 'selected'): Promise<number | null> {
    if (analysisConfigured.value !== true) {
      error.value = '当前环境尚未配置可用的 AI 模型，请配置 LLM 后重启后端。'
      return null
    }
    if (scope === 'selected' && selectedIds.value.length === 0) return null
    submittingAnalysis.value = true
    error.value = null
    try {
      const created = await submitContentAnalysis({ targets: targetSelection(scope) })
      analysisJobId = created.job_id
      analysisJob.value = await fetchContentAnalysisJob(created.job_id)
      return created.target_count
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      submittingAnalysis.value = false
    }
  }

  async function refreshExports(): Promise<void> {
    try {
      const response = await fetchDataExports()
      exports.value = response.items
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function createExport(scope: 'query' | 'selected' | 'page'): Promise<number | null> {
    if (scope === 'selected' && selectedIds.value.length === 0) return null
    if ((scope === 'page' || scope === 'query') && items.value.length === 0) return null
    submittingExport.value = true
    error.value = null
    try {
      const targets = scope === 'page'
        ? { scope: 'selected' as const, content_ids: items.value.map((item) => item.id) }
        : targetSelection(scope)
      const created = await submitDataExport({ targets, format: 'xlsx' })
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

  async function poll(): Promise<void> {
    if (document.visibilityState === 'hidden' || !hasActiveJobs.value) return
    try {
      if (analysisJobId) analysisJob.value = await fetchContentAnalysisJob(analysisJobId)
      await Promise.all([refresh(true), refreshExports()])
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
    analysisJob,
    analysisConfigured,
    hasMore,
    allVisibleSelected,
    hasActiveJobs,
    loading,
    loadingNext,
    loadingDetail,
    submittingAnalysis,
    submittingExport,
    reviewingRelevance,
    error,
    notice,
    refresh,
    refreshAnalysisCapabilities,
    loadNext,
    openDetail,
    closeDetail,
    toggleSelection,
    toggleVisibleSelection,
    clearSelection,
    reviewRelevance,
    createAnalysis,
    refreshExports,
    createExport,
    downloadExport,
    resetFilters,
    startPolling,
    stopPolling,
  }
})

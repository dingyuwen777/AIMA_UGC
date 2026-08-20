import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  ImportBatchCreatedResponse,
  ImportBatchListResponse,
  ImportBatchResponse,
  ImportBatchStatus,
  ImportBatchSummaryResponse,
  ImportStage,
  ListImportBatchesParams,
} from '../../generated/api/client'
import {
  ImportApiError,
  fetchImportBatchDetail,
  fetchImportBatchList,
  fetchImportBatchSummary,
  uploadImportBatch,
} from './api'

export interface ImportBatchFilters {
  identifier: string
  status: '' | ImportBatchStatus
  stage: '' | ImportStage
  createdFrom: string
  createdTo: string
}

const EMPTY_FILTERS: ImportBatchFilters = {
  identifier: '',
  status: '',
  stage: '',
  createdFrom: '',
  createdTo: '',
}

function shanghaiDateStart(value: string): string | undefined {
  return value ? new Date(`${value}T00:00:00+08:00`).toISOString() : undefined
}

function shanghaiDateEnd(value: string): string | undefined {
  return value ? new Date(`${value}T23:59:59.999+08:00`).toISOString() : undefined
}

function errorMessage(error: unknown): string {
  if (error instanceof ImportApiError) {
    return `${error.message}（request_id: ${error.requestId}）`
  }
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}

export const useImportBatchesStore = defineStore('import-batches', () => {
  const filters = reactive<ImportBatchFilters>({ ...EMPTY_FILTERS })
  const items = ref<ImportBatchResponse[]>([])
  const summary = ref<ImportBatchSummaryResponse | null>(null)
  const selected = ref<ImportBatchResponse | null>(null)
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(false)
  const loading = ref(false)
  const loadingNext = ref(false)
  const uploading = ref(false)
  const error = ref<string | null>(null)
  let pollHandle: ReturnType<typeof setInterval> | undefined
  let pollDocument: Document | undefined
  let refreshVersion = 0

  const hasActiveJobs = computed(
    () =>
      items.value.some((item) => item.status === 'queued' || item.status === 'running') ||
      selected.value?.status === 'queued' ||
      selected.value?.status === 'running',
  )

  function listParams(cursor?: string): ListImportBatchesParams {
    return {
      identifier: filters.identifier.trim() || undefined,
      status: filters.status || undefined,
      stage: filters.stage || undefined,
      created_from: shanghaiDateStart(filters.createdFrom),
      created_to: shanghaiDateEnd(filters.createdTo),
      cursor,
      limit: 20,
    }
  }

  function applyPage(page: ImportBatchListResponse): void {
    items.value = page.items
    nextCursor.value = page.next_cursor ?? null
    hasMore.value = page.has_more
  }

  async function refresh(silent = false): Promise<void> {
    const version = ++refreshVersion
    if (!silent) loading.value = true
    error.value = null
    try {
      const [page, kpis, detail] = await Promise.all([
        fetchImportBatchList(listParams()),
        fetchImportBatchSummary(),
        selected.value ? fetchImportBatchDetail(selected.value.id) : Promise.resolve(null),
      ])
      if (version !== refreshVersion) return
      applyPage(page)
      summary.value = kpis
      if (detail !== null) selected.value = detail
    } catch (reason) {
      if (version === refreshVersion) error.value = errorMessage(reason)
    } finally {
      if (version === refreshVersion) loading.value = false
    }
  }

  async function loadNext(): Promise<void> {
    if (!nextCursor.value || loadingNext.value) return
    loadingNext.value = true
    error.value = null
    try {
      const page = await fetchImportBatchList(listParams(nextCursor.value))
      items.value = [...items.value, ...page.items]
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingNext.value = false
    }
  }

  async function openDetail(batchId: string): Promise<void> {
    error.value = null
    try {
      selected.value = await fetchImportBatchDetail(batchId)
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  function closeDetail(): void {
    selected.value = null
  }

  async function upload(file: File): Promise<ImportBatchCreatedResponse | null> {
    uploading.value = true
    error.value = null
    try {
      const created = await uploadImportBatch(file)
      await refresh(true)
      return created
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      uploading.value = false
    }
  }

  function resetFilters(): void {
    Object.assign(filters, EMPTY_FILTERS)
  }

  function startPolling(intervalMilliseconds = 5000): void {
    stopPolling()
    pollDocument = typeof document === 'undefined' ? undefined : document
    pollDocument?.addEventListener('visibilitychange', refreshWhenVisible)
    pollHandle = setInterval(() => {
      if (hasActiveJobs.value && pollDocument?.visibilityState !== 'hidden') void refresh(true)
    }, intervalMilliseconds)
  }

  function refreshWhenVisible(): void {
    if (
      pollHandle !== undefined &&
      pollDocument?.visibilityState === 'visible' &&
      hasActiveJobs.value
    ) {
      void refresh(true)
    }
  }

  function stopPolling(): void {
    if (pollHandle !== undefined) clearInterval(pollHandle)
    pollHandle = undefined
    pollDocument?.removeEventListener('visibilitychange', refreshWhenVisible)
    pollDocument = undefined
  }

  return {
    filters,
    items,
    summary,
    selected,
    hasMore,
    loading,
    loadingNext,
    uploading,
    error,
    hasActiveJobs,
    refresh,
    loadNext,
    openDetail,
    closeDetail,
    upload,
    resetFilters,
    startPolling,
    stopPolling,
  }
})

import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  CollectionCapabilitiesResponse,
  CollectionRunCreateRequest,
  CollectionRunCreatedResponse,
  CollectionRunResponse,
  CollectionRuntimeItemResponse,
  CollectionRuntimeRecordType,
  CollectionRuntimeStatus,
  CollectionRuntimeSummaryResponse,
  ImportBatchCreatedResponse,
  ImportBatchResponse,
  ListCollectionRuntimeRunsParams,
} from '../../generated/api/client'
import {
  createTikHubCollectionRun,
  fetchCollectionCapabilities,
  fetchCollectionRunDetail,
  fetchCollectionRuntimeList,
  fetchCollectionRuntimeSummary,
  fetchImportBatchDetail,
  fetchImportBatchList,
  ImportApiError,
  uploadImportBatch,
} from './api'

export type CollectionRuntimeTab = 'all' | 'excel' | 'tikhub'

export interface CollectionRuntimeFilters {
  search: string
  status: '' | CollectionRuntimeStatus
  recordType: '' | CollectionRuntimeRecordType
  stage: string
  createdFrom: string
  createdTo: string
}

const EMPTY_FILTERS: CollectionRuntimeFilters = {
  search: '',
  status: '',
  recordType: '',
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

export const useImportBatchesStore = defineStore('collection-runtime', () => {
  const filters = reactive<CollectionRuntimeFilters>({ ...EMPTY_FILTERS })
  const activeTab = ref<CollectionRuntimeTab>('all')
  const items = ref<CollectionRuntimeItemResponse[]>([])
  const summary = ref<CollectionRuntimeSummaryResponse | null>(null)
  const selectedBatch = ref<ImportBatchResponse | null>(null)
  const selectedRun = ref<CollectionRunResponse | null>(null)
  const capabilities = ref<CollectionCapabilitiesResponse | null>(null)
  const batchOptions = ref<ImportBatchResponse[]>([])
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(false)
  const loading = ref(false)
  const loadingNext = ref(false)
  const uploading = ref(false)
  const creating = ref(false)
  const error = ref<string | null>(null)
  let pollHandle: ReturnType<typeof setInterval> | undefined
  let pollDocument: Document | undefined
  let refreshVersion = 0

  const hasActiveJobs = computed(
    () =>
      items.value.some((item) => item.status === 'queued' || item.status === 'running') ||
      selectedBatch.value?.status === 'queued' ||
      selectedBatch.value?.status === 'running' ||
      selectedRun.value?.status === 'queued' ||
      selectedRun.value?.status === 'running',
  )

  function selectedRecordTypes(): CollectionRuntimeRecordType[] | undefined {
    if (activeTab.value === 'excel') return ['excel_import']
    if (activeTab.value === 'tikhub') {
      if (
        filters.recordType === 'tikhub_discovery' ||
        filters.recordType === 'tikhub_batch_supplement'
      ) {
        return [filters.recordType]
      }
      return ['tikhub_discovery', 'tikhub_batch_supplement']
    }
    return filters.recordType ? [filters.recordType] : undefined
  }

  function listParams(cursor?: string): ListCollectionRuntimeRunsParams {
    return {
      search: filters.search.trim() || undefined,
      record_types: selectedRecordTypes(),
      status: filters.status || undefined,
      stage: filters.stage.trim() || undefined,
      created_from: shanghaiDateStart(filters.createdFrom),
      created_to: shanghaiDateEnd(filters.createdTo),
      cursor,
      limit: 20,
    }
  }

  async function refresh(silent = false): Promise<void> {
    const version = ++refreshVersion
    if (!silent) loading.value = true
    error.value = null
    try {
      const [page, kpis, batchDetail, runDetail] = await Promise.all([
        fetchCollectionRuntimeList(listParams()),
        fetchCollectionRuntimeSummary(),
        selectedBatch.value
          ? fetchImportBatchDetail(selectedBatch.value.id)
          : Promise.resolve(null),
        selectedRun.value
          ? fetchCollectionRunDetail(selectedRun.value.run_id)
          : Promise.resolve(null),
      ])
      if (version !== refreshVersion) return
      items.value = page.items
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
      summary.value = kpis
      if (batchDetail !== null) selectedBatch.value = batchDetail
      if (runDetail !== null) selectedRun.value = runDetail
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
      const page = await fetchCollectionRuntimeList(listParams(nextCursor.value))
      items.value = [...items.value, ...page.items]
      nextCursor.value = page.next_cursor ?? null
      hasMore.value = page.has_more
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingNext.value = false
    }
  }

  async function setTab(tab: CollectionRuntimeTab): Promise<void> {
    activeTab.value = tab
    if (tab === 'excel' && filters.recordType !== 'excel_import') filters.recordType = ''
    if (tab === 'tikhub' && filters.recordType === 'excel_import') filters.recordType = ''
    await refresh()
  }

  async function openBatchDetail(batchId: string): Promise<void> {
    error.value = null
    selectedRun.value = null
    try {
      selectedBatch.value = await fetchImportBatchDetail(batchId)
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function openRunDetail(runId: string): Promise<void> {
    error.value = null
    selectedBatch.value = null
    try {
      selectedRun.value = await fetchCollectionRunDetail(runId)
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  function closeDetail(): void {
    selectedBatch.value = null
    selectedRun.value = null
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

  async function loadCreationOptions(selectedBatchId?: string | null): Promise<void> {
    error.value = null
    try {
      const [providerCapabilities, batches] = await Promise.all([
        fetchCollectionCapabilities(),
        fetchImportBatchList({ limit: 100 }),
      ])
      capabilities.value = providerCapabilities
      batchOptions.value = batches.items
      if (
        selectedBatchId &&
        !batchOptions.value.some((batch) => batch.id === selectedBatchId)
      ) {
        const selected = await fetchImportBatchDetail(selectedBatchId)
        batchOptions.value = [selected, ...batchOptions.value]
      }
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function createRun(
    request: CollectionRunCreateRequest,
  ): Promise<CollectionRunCreatedResponse | null> {
    creating.value = true
    error.value = null
    try {
      const created = await createTikHubCollectionRun(request)
      await refresh(true)
      await openRunDetail(created.run_id)
      return created
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      creating.value = false
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
    activeTab,
    items,
    summary,
    selectedBatch,
    selectedRun,
    capabilities,
    batchOptions,
    hasMore,
    loading,
    loadingNext,
    uploading,
    creating,
    error,
    hasActiveJobs,
    refresh,
    loadNext,
    setTab,
    openBatchDetail,
    openRunDetail,
    closeDetail,
    upload,
    loadCreationOptions,
    createRun,
    resetFilters,
    startPolling,
    stopPolling,
  }
})

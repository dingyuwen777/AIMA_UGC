import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  CollectionCapabilitiesResponse,
  DataImportIngestionPolicy,
  CollectionPlatform,
  CollectionRunCreateRequest,
  CollectionRunCreatedResponse,
  CollectionRunResponse,
  CollectionRuntimeItemResponse,
  CollectionRuntimeRecordType,
  CollectionRuntimeStatus,
  CollectionRuntimeSummaryResponse,
  HistoricalCampaignConflictResponse,
  HistoricalCampaignCreateRequest,
  HistoricalCampaignCreatedResponse,
  HistoricalCampaignItemResponse,
  HistoricalCampaignResponse,
  HistoricalDirectoryEntryResponse,
  ImportBatchCreatedResponse,
  ImportBatchResponse,
  KeywordPackSummaryResponse,
  ListCollectionRuntimeRunsParams,
  LocalDataImportCampaignCreateRequest,
} from '../../generated/api/client'
import { beijingDayBoundary } from '../../shared/domain/beijingTime'
import {
  createTikHubCollectionRun,
  cancelHistoricalCampaign,
  createLocalCampaign,
  createHistoricalCampaign,
  fetchBatchContentPlatforms,
  fetchCollectionCapabilities,
  fetchCollectionRunDetail,
  fetchCollectionRuntimeList,
  fetchCollectionRuntimeSummary,
  fetchImportBatchDetail,
  fetchImportBatchList,
  fetchEnabledKeywordPacks,
  fetchHistoricalCampaign,
  fetchHistoricalCampaignConflicts,
  fetchHistoricalCampaignItems,
  fetchHistoricalCampaigns,
  fetchHistoricalDirectory,
  finalizeLocalCampaign,
  ImportApiError,
  retryHistoricalCampaign,
  startHistoricalCampaign,
  uploadLocalCampaignFile,
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

export interface DataImportLocalFileSelection {
  file: File
  relativePath: string
}

const EMPTY_FILTERS: CollectionRuntimeFilters = {
  search: '',
  status: '',
  recordType: '',
  stage: '',
  createdFrom: '',
  createdTo: '',
}

const SUPPORTED_PLATFORMS: CollectionPlatform[] = [
  'xiaohongshu',
  'douyin',
  'weibo',
  'bilibili',
  'kuaishou',
]

function errorMessage(error: unknown): string {
  if (error instanceof ImportApiError) {
    return `${error.message}（request_id: ${error.requestId}）`
  }
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}

function isSupplementBatch(batch: ImportBatchResponse): boolean {
  return batch.status === 'succeeded' && (batch.stats.rows_ingested ?? 0) > 0
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
  const keywordPackOptions = ref<KeywordPackSummaryResponse[]>([])
  const batchContentPlatforms = ref<CollectionPlatform[]>([])
  const historicalDirectoryPath = ref('')
  const historicalDirectoryEntries = ref<HistoricalDirectoryEntryResponse[]>([])
  const historicalDirectoryNextCursor = ref<string | null>(null)
  const historicalDirectoryHasMore = ref(false)
  const historicalCampaigns = ref<HistoricalCampaignResponse[]>([])
  const selectedHistoricalCampaign = ref<HistoricalCampaignResponse | null>(null)
  const historicalCampaignItems = ref<HistoricalCampaignItemResponse[]>([])
  const historicalCampaignConflicts = ref<HistoricalCampaignConflictResponse[]>([])
  const historicalCampaignItemsHasMore = ref(false)
  const historicalCampaignConflictsHasMore = ref(false)
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(false)
  const loading = ref(false)
  const loadingNext = ref(false)
  const uploading = ref(false)
  const creating = ref(false)
  const loadingBatchPlatforms = ref(false)
  const loadingKeywordPacks = ref(false)
  const loadingHistorical = ref(false)
  const creatingHistorical = ref(false)
  const actingHistorical = ref(false)
  const localUploadCompleted = ref(0)
  const localUploadTotal = ref(0)
  const error = ref<string | null>(null)
  let pollHandle: ReturnType<typeof setInterval> | undefined
  let pollDocument: Document | undefined
  let refreshVersion = 0
  let batchPlatformVersion = 0

  const hasActiveJobs = computed(
    () =>
      items.value.some((item) => item.status === 'queued' || item.status === 'running') ||
      selectedBatch.value?.status === 'queued' ||
      selectedBatch.value?.status === 'running' ||
      selectedRun.value?.status === 'queued' ||
      selectedRun.value?.status === 'running' ||
      historicalCampaigns.value.some((campaign) =>
        ['uploading', 'discovering', 'snapshotting', 'queued', 'running', 'cancelling'].includes(
          campaign.status,
        ),
      ),
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
      created_from: beijingDayBoundary(filters.createdFrom, 'start'),
      created_to: beijingDayBoundary(filters.createdTo, 'end'),
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

  async function upload(
    file: File,
    keywordPackIds: string[],
    vehicleModelIds: string[] = [],
  ): Promise<ImportBatchCreatedResponse | null> {
    uploading.value = true
    error.value = null
    try {
      const created = await uploadImportBatch(file, keywordPackIds, vehicleModelIds)
      await refresh(true)
      return created
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      uploading.value = false
    }
  }

  async function loadKeywordPacks(): Promise<void> {
    loadingKeywordPacks.value = true
    error.value = null
    try {
      keywordPackOptions.value = await fetchEnabledKeywordPacks()
    } catch (reason) {
      error.value = errorMessage(reason)
      keywordPackOptions.value = []
    } finally {
      loadingKeywordPacks.value = false
    }
  }

  async function loadBatchPlatforms(batchId: string): Promise<void> {
    const version = ++batchPlatformVersion
    batchContentPlatforms.value = []
    if (!batchId) return
    loadingBatchPlatforms.value = true
    error.value = null
    try {
      const platforms = await fetchBatchContentPlatforms(batchId, SUPPORTED_PLATFORMS)
      if (version === batchPlatformVersion) batchContentPlatforms.value = platforms
    } catch (reason) {
      if (version === batchPlatformVersion) error.value = errorMessage(reason)
    } finally {
      if (version === batchPlatformVersion) loadingBatchPlatforms.value = false
    }
  }

  /** 读取全部可用于辅助补采的历史导入批次，避免固定首屏截断。 */
async function fetchAllSupplementBatches(): Promise<ImportBatchResponse[]> {
  const batches: ImportBatchResponse[] = []
  const seenCursors = new Set<string>()
  let cursor: string | undefined
  while (true) {
    const page = await fetchImportBatchList(cursor ? { limit: 100, cursor } : { limit: 100 })
    batches.push(...page.items)
    const next = page.next_cursor ?? undefined
    if (!page.has_more || !next || seenCursors.has(next)) break
    seenCursors.add(next)
    cursor = next
  }
  return batches.filter(isSupplementBatch)
}

  async function loadCreationOptions(selectedBatchId?: string | null): Promise<void> {
    error.value = null
    batchContentPlatforms.value = []
    try {
      const [providerCapabilities, batches, packs] = await Promise.all([
        fetchCollectionCapabilities(),
        fetchAllSupplementBatches(),
        fetchEnabledKeywordPacks(),
      ])
      capabilities.value = providerCapabilities
      keywordPackOptions.value = packs
      batchOptions.value = batches
      if (
        selectedBatchId &&
        !batchOptions.value.some((batch) => batch.id === selectedBatchId)
      ) {
        const selected = await fetchImportBatchDetail(selectedBatchId)
        if (isSupplementBatch(selected)) batchOptions.value = [selected, ...batchOptions.value]
      }
      if (selectedBatchId && batchOptions.value.some((batch) => batch.id === selectedBatchId)) {
        await loadBatchPlatforms(selectedBatchId)
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

  async function openHistoricalWorkspace(): Promise<void> {
    loadingHistorical.value = true
    error.value = null
    try {
      const [campaigns, packs] = await Promise.all([
        fetchHistoricalCampaigns(),
        fetchEnabledKeywordPacks(),
      ])
      historicalCampaigns.value = campaigns.items
      keywordPackOptions.value = packs
      if (selectedHistoricalCampaign.value) {
        await refreshHistoricalCampaign(selectedHistoricalCampaign.value.id)
      }
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingHistorical.value = false
    }
  }

  async function openServerImportSource(): Promise<void> {
    await browseHistoricalDirectory('')
  }

  async function browseHistoricalDirectory(relativePath: string): Promise<void> {
    loadingHistorical.value = true
    error.value = null
    try {
      const directory = await fetchHistoricalDirectory(relativePath)
      if (!directory.available) {
        throw new Error(directory.unavailable_reason || '服务器历史目录当前不可用。')
      }
      historicalDirectoryPath.value = relativePath
      historicalDirectoryEntries.value = directory.items ?? []
      historicalDirectoryNextCursor.value = directory.next_cursor ?? null
      historicalDirectoryHasMore.value = Boolean(directory.has_more)
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingHistorical.value = false
    }
  }

  async function loadMoreHistoricalDirectory(): Promise<void> {
    const cursor = historicalDirectoryNextCursor.value
    if (!cursor || loadingHistorical.value) return
    loadingHistorical.value = true
    error.value = null
    try {
      const directory = await fetchHistoricalDirectory(historicalDirectoryPath.value, cursor)
      if (!directory.available) {
        throw new Error(directory.unavailable_reason || '服务器历史目录当前不可用。')
      }
      const existing = new Set(historicalDirectoryEntries.value.map((item) => item.relative_path))
      historicalDirectoryEntries.value = [
        ...historicalDirectoryEntries.value,
        ...(directory.items ?? []).filter((item) => !existing.has(item.relative_path)),
      ]
      historicalDirectoryNextCursor.value = directory.next_cursor ?? null
      historicalDirectoryHasMore.value = Boolean(directory.has_more)
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingHistorical.value = false
    }
  }

  async function refreshHistoricalCampaign(campaignId: string): Promise<void> {
    const [campaign, campaignItems, conflicts] = await Promise.all([
      fetchHistoricalCampaign(campaignId),
      fetchHistoricalCampaignItems(campaignId),
      fetchHistoricalCampaignConflicts(campaignId),
    ])
    selectedHistoricalCampaign.value = campaign
    historicalCampaignItems.value = campaignItems.items
    historicalCampaignConflicts.value = conflicts.items
    historicalCampaignItemsHasMore.value = Boolean(campaignItems.has_more)
    historicalCampaignConflictsHasMore.value = Boolean(conflicts.has_more)
    historicalCampaigns.value = [
      campaign,
      ...historicalCampaigns.value.filter((item) => item.id !== campaign.id),
    ]
  }

  async function refreshHistoricalCampaignSummary(campaignId: string): Promise<void> {
    const campaign = await fetchHistoricalCampaign(campaignId)
    selectedHistoricalCampaign.value = campaign
    historicalCampaigns.value = [
      campaign,
      ...historicalCampaigns.value.filter((item) => item.id !== campaign.id),
    ]
  }

  async function submitHistoricalCampaign(
    request: HistoricalCampaignCreateRequest,
  ): Promise<HistoricalCampaignCreatedResponse | null> {
    creatingHistorical.value = true
    error.value = null
    try {
      const created = await createHistoricalCampaign(request)
      await refreshHistoricalCampaign(created.campaign_id)
      return created
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      creatingHistorical.value = false
    }
  }

  async function submitLocalCampaign(
    files: DataImportLocalFileSelection[],
    keywordPackIds: string[],
    vehicleModelIds: string[],
    ingestionPolicy: DataImportIngestionPolicy,
  ): Promise<HistoricalCampaignResponse | null> {
    creatingHistorical.value = true
    localUploadCompleted.value = 0
    localUploadTotal.value = files.length
    error.value = null
    let campaignId: string | null = null
    try {
      const request: LocalDataImportCampaignCreateRequest = {
        client_idempotency_key: crypto.randomUUID(),
        files: files.map((item) => ({
          relative_path: item.relativePath,
          byte_size: item.file.size,
        })),
        keyword_pack_ids: keywordPackIds,
        vehicle_model_ids: vehicleModelIds,
        ingestion_policy: ingestionPolicy,
        profile: 'aima-monitoring-excel.v1',
      }
      const created = await createLocalCampaign(request)
      campaignId = created.campaign_id
      await refreshHistoricalCampaign(campaignId)
      const selectedByPath = new Map(files.map((item) => [item.relativePath, item.file]))
      for (const uploadItem of created.upload_items) {
        const file = selectedByPath.get(uploadItem.relative_path)
        if (!file) throw new Error(`服务器返回了未知上传项：${uploadItem.relative_path}`)
        await uploadLocalCampaignFile(campaignId, uploadItem.item_id, file)
        localUploadCompleted.value += 1
      }
      const campaign = await finalizeLocalCampaign(campaignId)
      selectedHistoricalCampaign.value = campaign
      historicalCampaigns.value = [
        campaign,
        ...historicalCampaigns.value.filter((item) => item.id !== campaign.id),
      ]
      return campaign
    } catch (reason) {
      error.value = errorMessage(reason)
      if (campaignId) {
        try {
          await refreshHistoricalCampaign(campaignId)
        } catch {
          // 保留原始上传错误；Campaign ID 已在服务端审计，可从历史记录继续排查。
        }
      }
      return null
    } finally {
      creatingHistorical.value = false
    }
  }

  async function actOnHistoricalCampaign(
    action: 'start' | 'cancel' | 'retry',
  ): Promise<HistoricalCampaignResponse | null> {
    const campaignId = selectedHistoricalCampaign.value?.id
    if (!campaignId) return null
    actingHistorical.value = true
    error.value = null
    try {
      const campaign = action === 'start'
        ? await startHistoricalCampaign(campaignId)
        : action === 'cancel'
          ? await cancelHistoricalCampaign(campaignId)
          : await retryHistoricalCampaign(campaignId)
      selectedHistoricalCampaign.value = campaign
      historicalCampaigns.value = [
        campaign,
        ...historicalCampaigns.value.filter((item) => item.id !== campaign.id),
      ]
      return campaign
    } catch (reason) {
      error.value = errorMessage(reason)
      return null
    } finally {
      actingHistorical.value = false
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
    keywordPackOptions,
    batchContentPlatforms,
    historicalDirectoryPath,
    historicalDirectoryEntries,
    historicalDirectoryNextCursor,
    historicalDirectoryHasMore,
    historicalCampaigns,
    selectedHistoricalCampaign,
    historicalCampaignItems,
    historicalCampaignConflicts,
    historicalCampaignItemsHasMore,
    historicalCampaignConflictsHasMore,
    hasMore,
    loading,
    loadingNext,
    uploading,
    creating,
    loadingBatchPlatforms,
    loadingKeywordPacks,
    loadingHistorical,
    creatingHistorical,
    actingHistorical,
    localUploadCompleted,
    localUploadTotal,
    error,
    hasActiveJobs,
    refresh,
    loadNext,
    setTab,
    openBatchDetail,
    openRunDetail,
    closeDetail,
    upload,
    loadKeywordPacks,
    loadBatchPlatforms,
    loadCreationOptions,
    createRun,
    openHistoricalWorkspace,
    openServerImportSource,
    browseHistoricalDirectory,
    loadMoreHistoricalDirectory,
    refreshHistoricalCampaign,
    refreshHistoricalCampaignSummary,
    submitHistoricalCampaign,
    submitLocalCampaign,
    actOnHistoricalCampaign,
    resetFilters,
    startPolling,
    stopPolling,
  }
})

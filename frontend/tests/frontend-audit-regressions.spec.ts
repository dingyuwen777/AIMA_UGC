import { readFile } from 'node:fs/promises'

import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  addKeywordToPack: vi.fn(),
  cancelContentAnalysisRun: vi.fn(),
  cancelDataImportCampaign: vi.fn(),
  countContents: vi.fn(),
  createAnalysisSchemeDraft: vi.fn(),
  createCollectionPlan: vi.fn(),
  createCollectionRun: vi.fn(),
  createContentAnalysis: vi.fn(),
  createContentAnalysisRun: vi.fn(),
  createContentRelevanceReview: vi.fn(),
  createDataExport: vi.fn(),
  createDataImportCampaign: vi.fn(),
  createImportBatch: vi.fn(),
  createKeywordPack: vi.fn(),
  createLocalDataImportCampaign: vi.fn(),
  createServerDataImportCampaign: vi.fn(),
  createVehicleModel: vi.fn(),
  deleteVehicleModel: vi.fn(),
  downloadDataExport: vi.fn(),
  finalizeLocalDataImportCampaign: vi.fn(),
  getCollectionBatchSupplementEligibility: vi.fn(),
  getCollectionCapabilities: vi.fn(),
  getCollectionPlan: vi.fn(),
  getCollectionRun: vi.fn(),
  getCollectionRuntimeSummary: vi.fn(),
  getContent: vi.fn(),
  getContentAnalysisCapabilities: vi.fn(),
  getContentAnalysisJob: vi.fn(),
  getContentAnalysisRun: vi.fn(),
  getContentAnalysisTaxonomy: vi.fn(),
  getCurrentPrincipal: vi.fn(),
  getDataExport: vi.fn(),
  getDataImportCampaign: vi.fn(),
  getExportColumnCatalog: vi.fn(),
  getGlobalRelevanceConfig: vi.fn(),
  getImportBatch: vi.fn(),
  getImportBatchSummary: vi.fn(),
  getKeywordPack: vi.fn(),
  listAnalysisSchemes: vi.fn(),
  listAuditEvents: vi.fn(),
  listCollectionPlans: vi.fn(),
  listCollectionRuntimeRuns: vi.fn(),
  listContentAnalysisRuns: vi.fn(),
  listContents: vi.fn(),
  listDataExports: vi.fn(),
  listDataImportCampaignConflicts: vi.fn(),
  listDataImportCampaignItems: vi.fn(),
  listDataImportCampaigns: vi.fn(),
  listDataImportServerDirectories: vi.fn(),
  listImportBatches: vi.fn(),
  listKeywordPacks: vi.fn(),
  listNotifications: vi.fn(),
  listVehicleModels: vi.fn(),
  markNotificationsRead: vi.fn(),
  mergeVehicleModel: vi.fn(),
  previewContentAnalysisRun: vi.fn(),
  publishAnalysisScheme: vi.fn(),
  replaceKeywordPackVehicleModels: vi.fn(),
  retryDataImportCampaignFailedItems: vi.fn(),
  reviewContentAnalysis: vi.fn(),
  reviewContentVehicles: vi.fn(),
  rollbackAnalysisScheme: vi.fn(),
  setGlobalRelevanceConfig: vi.fn(),
  startDataImportCampaign: vi.fn(),
  updateAnalysisSchemeDraft: vi.fn(),
  updateCollectionPlanEnabled: vi.fn(),
  updateKeywordPackEnabled: vi.fn(),
  updateVehicleModel: vi.fn(),
  uploadLocalDataImportFile: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import {
  fetchAuditEvents,
  fetchKeywordPacksForAdmin,
  fetchVehicles,
} from '../src/features/admin-configuration/api'
import { useCollectionStrategyStore } from '../src/features/collection-strategy/store'
import { fetchEnabledKeywordPacks } from '../src/features/import-batches/api'
import { useImportBatchesStore } from '../src/features/import-batches/store'
import { useIdentityStore } from '../src/features/identity/store'
import { useVoicePlazaStore } from '../src/features/voice-plaza/store'

describe('frontend full-stack audit regressions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('loads every vehicle and keyword pack page before admin replacement operations', async () => {
    const vehicles = Array.from({ length: 200 }, (_, index) => ({ id: `vehicle-${index}` }))
    generated.listVehicleModels
      .mockResolvedValueOnce({ items: vehicles, total: 201, catalog_version: 9, offset: 0, limit: 200 })
      .mockResolvedValueOnce({ items: [{ id: 'vehicle-200' }], total: 201, catalog_version: 9, offset: 200, limit: 200 })

    const vehicleResponse = await fetchVehicles()

    expect(vehicleResponse.items).toHaveLength(201)
    expect(vehicleResponse.items.at(-1)?.id).toBe('vehicle-200')
    expect(generated.listVehicleModels).toHaveBeenNthCalledWith(1, { offset: 0, limit: 200 })
    expect(generated.listVehicleModels).toHaveBeenNthCalledWith(2, { offset: 200, limit: 200 })

    const packs = Array.from({ length: 100 }, (_, index) => ({ id: `pack-${index}` }))
    generated.listKeywordPacks
      .mockResolvedValueOnce({ items: packs, total: 101, offset: 0, limit: 100 })
      .mockResolvedValueOnce({ items: [{ id: 'pack-100' }], total: 101, offset: 100, limit: 100 })

    const packResponse = await fetchKeywordPacksForAdmin()

    expect(packResponse.items).toHaveLength(101)
    expect(packResponse.items.at(-1)?.id).toBe('pack-100')
    expect(generated.listKeywordPacks).toHaveBeenNthCalledWith(1, { offset: 0, limit: 100 })
    expect(generated.listKeywordPacks).toHaveBeenNthCalledWith(2, { offset: 100, limit: 100 })
  })

  it('loads every enabled keyword pack page for import and supplement selectors', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: `pack-${index}` }))
    generated.listKeywordPacks
      .mockResolvedValueOnce({ items: firstPage, total: 101, offset: 0, limit: 100 })
      .mockResolvedValueOnce({ items: [{ id: 'pack-100' }], total: 101, offset: 100, limit: 100 })

    const packs = await fetchEnabledKeywordPacks()

    expect(packs).toHaveLength(101)
    expect(packs.at(-1)?.id).toBe('pack-100')
    expect(generated.listKeywordPacks).toHaveBeenNthCalledWith(1, { enabled: true, offset: 0, limit: 100 })
    expect(generated.listKeywordPacks).toHaveBeenNthCalledWith(2, { enabled: true, offset: 100, limit: 100 })
  })

  it('loads all cursor pages of successful import batches for supplement creation', async () => {
    generated.getCollectionCapabilities.mockResolvedValue({ capabilities: [], provider_configs: [] })
    generated.listKeywordPacks.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 })
    generated.listImportBatches
      .mockResolvedValueOnce({
        items: [{ id: 'batch-1', status: 'succeeded', stats: { rows_ingested: 1 } }],
        has_more: true,
        next_cursor: 'batch-next',
      })
      .mockResolvedValueOnce({
        items: [{ id: 'batch-2', status: 'succeeded', stats: { rows_ingested: 2 } }],
        has_more: false,
        next_cursor: null,
      })
    const store = useImportBatchesStore()

    await store.loadCreationOptions()

    expect(store.batchOptions.map((batch) => batch.id)).toEqual(['batch-1', 'batch-2'])
    expect(generated.listImportBatches).toHaveBeenNthCalledWith(1, { limit: 100 })
    expect(generated.listImportBatches).toHaveBeenNthCalledWith(2, { limit: 100, cursor: 'batch-next' })
  })

  it('keeps the principal-wide unread count authoritative after marking a visible notification read', async () => {
    const notification = {
      id: '01991f80-6d5d-7dc8-95cb-c67c12345678',
      event_type: 'data_export_succeeded',
      title: '导出完成',
      message: '导出文件已就绪。',
      is_read: false,
      created_at: '2026-09-03T00:00:00+08:00',
    }
    generated.listNotifications
      .mockResolvedValueOnce({ items: [notification], unread_count: 80 })
      .mockResolvedValueOnce({ items: [{ ...notification, is_read: true }], unread_count: 79 })
    generated.markNotificationsRead.mockResolvedValue({ requested_count: 1, changed_count: 1 })
    const store = useIdentityStore()

    await store.refreshNotifications()
    await store.markRead([notification.id])

    expect(store.unreadCount).toBe(79)
    expect(generated.listNotifications).toHaveBeenCalledTimes(2)
    expect(generated.listNotifications).toHaveBeenLastCalledWith({ limit: 50 })
  })

  it('creates a keyword pack and its initial keywords through one atomic request', async () => {
    const created = {
      id: 'pack-1',
      name: '原子词包',
      description: '一次保存',
      enabled: true,
      version: 3,
      keywords: [
        { id: 'kw-1', text: '爱玛', enabled: true, priority: 100, note: '' },
        { id: 'kw-2', text: '电动车', enabled: true, priority: 100, note: '' },
      ],
    }
    generated.createKeywordPack.mockResolvedValue(created)
    generated.addKeywordToPack.mockResolvedValue(created)
    const store = useCollectionStrategyStore()

    const saved = await store.savePack('原子词包', '一次保存', ['爱玛', '电动车'])

    expect(saved).toBe(true)
    expect(generated.createKeywordPack).toHaveBeenCalledTimes(1)
    expect(generated.createKeywordPack).toHaveBeenCalledWith({
      name: '原子词包',
      description: '一次保存',
      keywords: [
        { text: '爱玛', priority: 100, enabled: true },
        { text: '电动车', priority: 100, enabled: true },
      ],
    })
    expect(generated.addKeywordToPack).not.toHaveBeenCalled()
  })

  it('requests audit history by explicit offset and limit instead of a fixed recent slice', async () => {
    generated.listAuditEvents.mockResolvedValue({ items: [], total: 250, offset: 100, limit: 100 })
    const fetchPage = fetchAuditEvents as unknown as (offset: number, limit: number) => Promise<unknown>

    await fetchPage(100, 100)

    expect(generated.listAuditEvents).toHaveBeenCalledWith({ offset: 100, limit: 100 })
  })

  it('preserves loaded cursor pages and later-page selection while active jobs poll', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('document', { visibilityState: 'visible' })
    const first = { id: 'content-1' }
    const second = { id: 'content-2' }
    generated.listContents
      .mockResolvedValueOnce({ items: [first], has_more: true, next_cursor: 'content-next' })
      .mockResolvedValueOnce({ items: [second], has_more: false, next_cursor: null })
      .mockResolvedValueOnce({ items: [{ ...first, refreshed: true }], has_more: true, next_cursor: 'content-next' })
      .mockResolvedValueOnce({ items: [second], has_more: false, next_cursor: null })
    const activeRun = { id: 'run-1', status: 'queued', target_count: 2, shards: [] }
    generated.listContentAnalysisRuns.mockResolvedValue({ items: [activeRun] })
    generated.getContentAnalysisRun.mockResolvedValue(activeRun)
    generated.listDataExports.mockResolvedValue({ items: [] })
    generated.getExportColumnCatalog.mockResolvedValue({ version: 1, columns: [{ key: 'id', label: 'ID', default_selected: true }] })
    const store = useVoicePlazaStore()

    await store.refresh()
    await store.loadNext()
    store.toggleSelection(second.id)
    await store.refreshAnalysisRuns()
    store.startPolling(1000)
    await vi.advanceTimersByTimeAsync(1000)

    expect(store.items.map((content) => content.id)).toEqual(['content-1', 'content-2'])
    expect(store.selectedIds).toEqual(['content-2'])
    expect(generated.listContents).toHaveBeenNthCalledWith(3, { limit: 20 })
    expect(generated.listContents).toHaveBeenNthCalledWith(4, { cursor: 'content-next', limit: 20 })
    store.stopPolling()
  })

  it('makes an existing Analysis Scheme draft name visibly read-only', async () => {
    const source = await readFile(
      new URL('../src/features/admin-configuration/pages/AdminConfigurationPage.vue', import.meta.url),
      'utf8',
    )

    expect(source).toContain(':readonly="selectedSchemeVersion?.version.status === \'draft\'"')
    expect(source).toContain('已有草稿保存时不会修改 Scheme 名称')
  })

  it('derives historical retry action from campaign-level failed chunk facts', async () => {
    const source = await readFile(
      new URL('../src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue', import.meta.url),
      'utf8',
    )

    expect(source).toContain('failed_chunk_count')
    expect(source).not.toContain("item.item_kind === 'chunk' && item.status === 'failed'")
  })

  it('offers a retry control when the shared vehicle catalog fails to load', async () => {
    const source = await readFile(new URL('../src/shared/VehicleMultiSelect.vue', import.meta.url), 'utf8')

    expect(source).toContain('重试')
    expect(source).toContain('@click="load"')
  })

  it('prevents an empty vehicle form from becoming a silent save click', async () => {
    const source = await readFile(
      new URL('../src/features/admin-configuration/pages/AdminConfigurationPage.vue', import.meta.url),
      'utf8',
    )

    expect(source).toContain('vehicleFormValid')
    expect(source).toContain(':disabled="saving || !vehicleFormValid"')
  })
})

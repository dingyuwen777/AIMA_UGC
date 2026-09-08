import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const featureApi = vi.hoisted(() => ({
  fetchCollectionRuntimeList: vi.fn(),
  fetchCollectionRuntimeSummary: vi.fn(),
  fetchCollectionRunDetail: vi.fn(),
  fetchCollectionCapabilities: vi.fn(),
  createTikHubCollectionRun: vi.fn(),
  fetchImportBatchList: vi.fn(),
  fetchImportBatchDetail: vi.fn(),
  uploadImportBatch: vi.fn(),
}))

vi.mock('../src/features/import-batches/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/features/import-batches/api')>()
  return { ...actual, ...featureApi }
})

import { useImportBatchesStore } from '../src/features/import-batches/store'

describe('import batches store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    featureApi.fetchCollectionRuntimeList.mockResolvedValue({
      items: [],
      has_more: false,
      next_cursor: null,
    })
    featureApi.fetchCollectionRuntimeSummary.mockResolvedValue({
      processing_count: 0,
      completed_today_count: 0,
      contents_ingested_today: 0,
      as_of: '2026-08-21T00:00:00Z',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('loads list and KPI facts together', async () => {
    const store = useImportBatchesStore()

    await store.refresh()

    expect(featureApi.fetchCollectionRuntimeList).toHaveBeenCalledOnce()
    expect(featureApi.fetchCollectionRuntimeSummary).toHaveBeenCalledOnce()
    expect(store.summary?.processing_count).toBe(0)
    expect(store.loading).toBe(false)
  })

  it('appends the next cursor page without replacing existing rows', async () => {
    featureApi.fetchCollectionRuntimeList
      .mockResolvedValueOnce({
        items: [{ record_id: 'batch-1' }],
        has_more: true,
        next_cursor: 'next-page',
      })
      .mockResolvedValueOnce({
        items: [{ record_id: 'batch-2' }],
        has_more: false,
        next_cursor: null,
      })
    const store = useImportBatchesStore()
    await store.refresh()

    await store.loadNext()

    expect(store.items.map((item) => item.record_id)).toEqual(['batch-1', 'batch-2'])
    expect(featureApi.fetchCollectionRuntimeList).toHaveBeenLastCalledWith(
      expect.objectContaining({ cursor: 'next-page' }),
    )
  })

  it('always clears uploading after import creation fails', async () => {
    let rejectUpload!: (reason?: unknown) => void
    featureApi.uploadImportBatch.mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectUpload = reject
        }),
    )
    const store = useImportBatchesStore()
    const pendingUpload = store.upload({ name: 'aima.xlsx' } as File, ['keyword-pack-1'])

    expect(store.uploading).toBe(true)
    rejectUpload(new Error('Excel 导入创建失败'))

    await expect(pendingUpload).resolves.toBeNull()
    expect(store.uploading).toBe(false)
    expect(store.error).toBe('Excel 导入创建失败')
  })

  it('refreshes the loaded window without applying unfinished filter edits', async () => {
    const first = { items: [{ record_id: 'batch-1', status: 'running' }], has_more: true, next_cursor: 'next-page' }
    const second = { items: [{ record_id: 'batch-2' }], has_more: false, next_cursor: null }
    featureApi.fetchCollectionRuntimeList
      .mockResolvedValueOnce(first).mockResolvedValueOnce(second)
      .mockResolvedValueOnce(first).mockResolvedValueOnce(second)
    const store = useImportBatchesStore()
    store.filters.search = '已查询'
    await store.refresh()
    await store.loadNext()
    store.filters.search = '尚未查询'

    await store.refresh(true)

    expect(store.items.map((item) => item.record_id)).toEqual(['batch-1', 'batch-2'])
    expect(featureApi.fetchCollectionRuntimeList).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: '已查询', cursor: 'next-page' }),
    )
  })

  it('honors the selected import record type inside the data import tab', async () => {
    const store = useImportBatchesStore()
    await store.setTab('excel')
    store.filters.recordType = 'data_import_campaign'
    await store.refresh()
    expect(featureApi.fetchCollectionRuntimeList).toHaveBeenLastCalledWith(
      expect.objectContaining({ record_types: ['data_import_campaign'] }),
    )
  })

  it.each(['list', 'summary'] as const)('keeps the displayed cursor bound to its query when %s refresh fails', async (failedRequest) => {
    const store = useImportBatchesStore()
    featureApi.fetchCollectionRuntimeList.mockResolvedValueOnce({
      items: [{ record_id: 'a-1' }], has_more: true, next_cursor: 'a-next',
    })
    store.filters.search = '查询 A'
    await store.refresh()
    store.filters.search = '查询 B'
    if (failedRequest === 'list') featureApi.fetchCollectionRuntimeList.mockRejectedValueOnce(new Error('暂时失败'))
    else featureApi.fetchCollectionRuntimeSummary.mockRejectedValueOnce(new Error('暂时失败'))
    await store.refresh()
    expect(store.error).toBe('暂时失败')
    expect(store.items.map((item) => item.record_id)).toEqual(['a-1'])
    featureApi.fetchCollectionRuntimeList.mockResolvedValueOnce({
      items: [{ record_id: 'a-2' }], has_more: false, next_cursor: null,
    })
    await store.loadNext()
    expect(featureApi.fetchCollectionRuntimeList).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: '查询 A', cursor: 'a-next' }),
    )
    expect(store.items.map((item) => item.record_id)).toEqual(['a-1', 'a-2'])
  })

  it('discards an old next page after the user submits a different query', async () => {
    let resolveNext!: (value: unknown) => void
    featureApi.fetchCollectionRuntimeList
      .mockResolvedValueOnce({ items: [{ record_id: 'old-1' }], has_more: true, next_cursor: 'next-page' })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve }))
      .mockResolvedValueOnce({ items: [{ record_id: 'new-1' }], has_more: false, next_cursor: null })
    const store = useImportBatchesStore()
    await store.refresh()
    const pending = store.loadNext()
    store.filters.search = '新查询'
    await store.refresh()
    resolveNext({ items: [{ record_id: 'old-2' }], has_more: false, next_cursor: null })
    await pending
    expect(store.items.map((item) => item.record_id)).toEqual(['new-1'])
  })

  it('pauses polling while hidden and refreshes immediately when visible again', async () => {
    vi.useFakeTimers()
    const documentStub = Object.assign(new EventTarget(), {
      visibilityState: 'hidden' as DocumentVisibilityState,
    })
    vi.stubGlobal('document', documentStub)
    featureApi.fetchCollectionRuntimeList.mockResolvedValue({
      items: [{ record_id: 'batch-1', status: 'running' }],
      has_more: false,
      next_cursor: null,
    })
    const store = useImportBatchesStore()
    await store.refresh()
    store.startPolling(5000)
    vi.clearAllMocks()

    await vi.advanceTimersByTimeAsync(5000)
    expect(featureApi.fetchCollectionRuntimeList).not.toHaveBeenCalled()

    documentStub.visibilityState = 'visible'
    documentStub.dispatchEvent(new Event('visibilitychange'))
    await vi.runAllTicks()

    expect(featureApi.fetchCollectionRuntimeList).toHaveBeenCalledOnce()
    store.stopPolling()
  })
})

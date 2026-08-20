import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const featureApi = vi.hoisted(() => ({
  fetchImportBatchList: vi.fn(),
  fetchImportBatchSummary: vi.fn(),
  fetchImportBatchDetail: vi.fn(),
  uploadImportBatch: vi.fn(),
}))

vi.mock('../src/features/import-batches/api', () => featureApi)

import { useImportBatchesStore } from '../src/features/import-batches/store'

describe('import batches store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    featureApi.fetchImportBatchList.mockResolvedValue({
      items: [],
      has_more: false,
      next_cursor: null,
    })
    featureApi.fetchImportBatchSummary.mockResolvedValue({
      processing_count: 0,
      completed_today_count: 0,
      rows_ingested_today: 0,
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

    expect(featureApi.fetchImportBatchList).toHaveBeenCalledOnce()
    expect(featureApi.fetchImportBatchSummary).toHaveBeenCalledOnce()
    expect(store.summary?.processing_count).toBe(0)
    expect(store.loading).toBe(false)
  })

  it('appends the next cursor page without replacing existing rows', async () => {
    featureApi.fetchImportBatchList
      .mockResolvedValueOnce({
        items: [{ id: 'batch-1' }],
        has_more: true,
        next_cursor: 'next-page',
      })
      .mockResolvedValueOnce({
        items: [{ id: 'batch-2' }],
        has_more: false,
        next_cursor: null,
      })
    const store = useImportBatchesStore()
    await store.refresh()

    await store.loadNext()

    expect(store.items.map((item) => item.id)).toEqual(['batch-1', 'batch-2'])
    expect(featureApi.fetchImportBatchList).toHaveBeenLastCalledWith(
      expect.objectContaining({ cursor: 'next-page' }),
    )
  })

  it('pauses polling while hidden and refreshes immediately when visible again', async () => {
    vi.useFakeTimers()
    const documentStub = Object.assign(new EventTarget(), {
      visibilityState: 'hidden' as DocumentVisibilityState,
    })
    vi.stubGlobal('document', documentStub)
    featureApi.fetchImportBatchList.mockResolvedValue({
      items: [{ id: 'batch-1', status: 'running' }],
      has_more: false,
      next_cursor: null,
    })
    const store = useImportBatchesStore()
    await store.refresh()
    store.startPolling(5000)
    vi.clearAllMocks()

    await vi.advanceTimersByTimeAsync(5000)
    expect(featureApi.fetchImportBatchList).not.toHaveBeenCalled()

    documentStub.visibilityState = 'visible'
    documentStub.dispatchEvent(new Event('visibilitychange'))
    await vi.runAllTicks()

    expect(featureApi.fetchImportBatchList).toHaveBeenCalledOnce()
    store.stopPolling()
  })
})

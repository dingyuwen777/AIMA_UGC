import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listCollectionRuntimeRuns: vi.fn(),
  getCollectionRuntimeSummary: vi.fn(),
  getCollectionCapabilities: vi.fn(),
  getCollectionDateSupplementEligibility: vi.fn(),
  getCollectionBatchSupplementEligibility: vi.fn(),
  getCollectionCampaignSupplementEligibility: vi.fn(),
  createCollectionRun: vi.fn(),
  getCollectionRun: vi.fn(),
  listImportBatches: vi.fn(),
  listKeywordPacks: vi.fn(),
  listDataImportCampaigns: vi.fn(),
  getDataImportCampaign: vi.fn(),
  listDataImportCampaignItems: vi.fn(),
  getImportBatch: vi.fn(),
  createImportBatch: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import {
  createTikHubCollectionRun,
  fetchBatchContentPlatforms,
  fetchCampaignContentPlatforms,
  fetchCollectionRuntimeList,
} from '../src/features/import-batches/api'
import { useImportBatchesStore } from '../src/features/import-batches/store'
import { runtimeStageLabel } from '../src/features/import-batches/format'

describe('collection runtime feature', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    generated.listCollectionRuntimeRuns.mockResolvedValue({ items: [], has_more: false, next_cursor: null })
    generated.getCollectionRuntimeSummary.mockResolvedValue({
      processing_count: 0,
      completed_today_count: 0,
      contents_ingested_today: 0,
      as_of: '2026-08-21T00:00:00Z',
    })
    generated.getCollectionBatchSupplementEligibility.mockImplementation(async (batchId: string) => ({
      batch_id: batchId,
      targets: [],
    }))
    generated.getCollectionCampaignSupplementEligibility.mockImplementation(async (campaignId: string) => ({
      campaign_id: campaignId,
      targets: [],
    }))
    generated.listDataImportCampaigns.mockResolvedValue({ items: [] })
    generated.listKeywordPacks.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })
  })

  it('shows distinct import revocation stages', () => {
    expect(runtimeStageLabel('revoking')).toBe('正在撤销导入')
    expect(runtimeStageLabel('revoked')).toBe('已撤销导入')
  })

  it('delegates the unified list query to the Orval client', async () => {
    await fetchCollectionRuntimeList({ record_types: ['tikhub_discovery', 'tikhub_batch_supplement'], status: 'running', limit: 20 })
    expect(generated.listCollectionRuntimeRuns).toHaveBeenCalledWith({ record_types: ['tikhub_discovery', 'tikhub_batch_supplement'], status: 'running', limit: 20 })
  })

  it('creates a discovery Run through the generated Contract', async () => {
    generated.createCollectionRun.mockResolvedValue({ run_id: 'run-1', job_id: 'job-1', mode: 'discovery', status: 'queued' })
    await createTikHubCollectionRun({
      mode: 'discovery', keyword_pack_ids: ['pack-1', 'pack-2'],
      platforms: [{
        platform: 'xiaohongshu', provider_config_id: 'provider-1',
        search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
      }],
      include_comments: true, include_sub_comments: false,
    })
    expect(generated.createCollectionRun).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'discovery', keyword_pack_ids: ['pack-1', 'pack-2'],
        platforms: [expect.objectContaining({ search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' } })],
      }),
    )
  })

  it('loads the centralized Excel and TikHub runtime facts together', async () => {
    generated.listCollectionRuntimeRuns.mockResolvedValue({
      items: [{ record_id: 'run-1', record_type: 'tikhub_discovery', display_name: '爱玛 / Q7 主动发现', job_id: 'job-1', status: 'running', stage: 'content_discovery', progress: 50, created_at: '2026-08-21T00:00:00Z' }],
      has_more: false, next_cursor: null,
    })
    const store = useImportBatchesStore()
    await store.refresh()
    expect(generated.listCollectionRuntimeRuns).toHaveBeenCalledOnce()
    expect(generated.getCollectionRuntimeSummary).toHaveBeenCalledOnce()
    expect(store.items[0]?.record_type).toBe('tikhub_discovery')
  })

  it('updates running campaign statistics and settled source results on the same refresh', async () => {
    const store = useImportBatchesStore()
    store.selectedHistoricalCampaign = { id: 'campaign-1', status: 'running', stats: { created: 0 } } as typeof store.selectedHistoricalCampaign & object
    generated.getDataImportCampaign.mockResolvedValue({
      id: 'campaign-1', status: 'running', stats: { created: 12 },
    })
    generated.listDataImportCampaignItems.mockResolvedValue({
      items: [{ id: 'item-1', status: 'succeeded', relative_path: 'part-1.xlsx' }],
      has_more: false,
    })

    await store.refreshHistoricalCampaignLive('campaign-1')

    expect(store.selectedHistoricalCampaign?.stats?.created).toBe(12)
    expect(store.historicalCampaignItems.map((item) => item.id)).toEqual(['item-1'])
    expect(generated.getDataImportCampaign).toHaveBeenCalledWith('campaign-1')
    expect(generated.listDataImportCampaignItems).toHaveBeenCalledWith('campaign-1')
  })

  it('loads creation capabilities and packs without importing source catalogs', async () => {
    generated.getCollectionCapabilities.mockResolvedValue({ provider_configs: [], capabilities: [] })
    const store = useImportBatchesStore()
    await store.loadCreationOptions()
    expect(generated.getCollectionCapabilities).toHaveBeenCalledOnce()
    expect(generated.listImportBatches).not.toHaveBeenCalled()
    expect(generated.listDataImportCampaigns).not.toHaveBeenCalled()
    expect(generated.getImportBatch).not.toHaveBeenCalled()
  })

  it('loads date target counts and diagnostics from the generated client', async () => {
    const range = { published_from: '2026-09-01T00:00:00+08:00', published_to: '2026-09-01T23:59:59.999+08:00' }
    generated.getCollectionDateSupplementEligibility.mockResolvedValue({
      ...range, targets: [{ platform: 'douyin', target_count: 2 }], diagnostics: [],
    })
    const store = useImportBatchesStore()
    await store.loadSupplementPlatforms(range)
    expect(generated.getCollectionDateSupplementEligibility).toHaveBeenCalledWith(range)
    expect(store.supplementContentPlatforms).toEqual(['douyin'])
    expect(store.supplementTargets).toEqual([{ platform: 'douyin', target_count: 2 }])
    expect(store.supplementEligibilityReady).toBe(true)
  })

  it('uses backend supplement eligibility instead of probing Voice Plaza content', async () => {
    generated.getCollectionBatchSupplementEligibility.mockResolvedValue({
      batch_id: 'batch-1',
      targets: [{ platform: 'xiaohongshu', target_count: 2 }],
      diagnostics: [{ platform: 'weibo', direct_target_count: 0, resolution_candidate_count: 1, blocked_count: 0, block_reasons: { exact_resolution_unavailable: 1 } }],
    })

    await expect(fetchBatchContentPlatforms('batch-1', ['xiaohongshu', 'douyin'])).resolves.toEqual({
      platforms: ['xiaohongshu'],
      diagnostics: [{ platform: 'weibo', direct_target_count: 0, resolution_candidate_count: 1, blocked_count: 0, block_reasons: { exact_resolution_unavailable: 1 } }],
    })
    expect(generated.getCollectionBatchSupplementEligibility).toHaveBeenCalledWith('batch-1')
  })

  it('retains legacy Campaign eligibility API compatibility', async () => {
    generated.getCollectionCampaignSupplementEligibility.mockResolvedValue({
      campaign_id: 'campaign-1', targets: [{ platform: 'douyin', target_count: 2 }],
    })
    await expect(fetchCampaignContentPlatforms('campaign-1', ['xiaohongshu', 'douyin']))
      .resolves.toEqual({ platforms: ['douyin'], diagnostics: [] })
  })

  it('ignores stale A to B to A responses and close/reopen responses', async () => {
    const deferred: ((value: unknown) => void)[] = []
    generated.getCollectionDateSupplementEligibility.mockImplementation(() => new Promise((resolve) => deferred.push(resolve)))
    const store = useImportBatchesStore()
    const a = { published_from: '2026-09-01T00:00:00+08:00', published_to: '2026-09-01T23:59:59+08:00' }
    const b = { ...a, published_to: '2026-09-02T23:59:59+08:00' }
    const oldA = store.loadSupplementPlatforms(a)
    const oldB = store.loadSupplementPlatforms(b)
    const newA = store.loadSupplementPlatforms(a)
    deferred[2]!({ ...a, targets: [{ platform: 'douyin', target_count: 2 }], diagnostics: [] })
    await newA
    deferred[0]!({ ...a, targets: [{ platform: 'weibo', target_count: 1 }], diagnostics: [] })
    deferred[1]!({ ...b, targets: [{ platform: 'bilibili', target_count: 1 }], diagnostics: [] })
    await Promise.all([oldA, oldB])
    expect(store.supplementContentPlatforms).toEqual(['douyin'])
    const closing = store.loadSupplementPlatforms(b)
    store.resetSupplementEligibility()
    deferred[3]!({ ...b, targets: [{ platform: 'weibo', target_count: 1 }], diagnostics: [] })
    await closing
    expect(store.supplementContentPlatforms).toEqual([])
    expect(store.supplementEligibilityReady).toBe(false)
    expect(store.loadingSupplementPlatforms).toBe(false)
  })

  it('distinguishes failed and empty date eligibility and can recover', async () => {
    const range = { published_from: '2026-09-01T00:00:00+08:00', published_to: '2026-09-01T23:59:59+08:00' }
    const store = useImportBatchesStore()
    generated.getCollectionDateSupplementEligibility.mockRejectedValueOnce(new Error('资格查询失败'))
    await store.loadSupplementPlatforms(range)
    expect(store.supplementEligibilityError).toBe('资格查询失败')
    expect(store.supplementEligibilityReady).toBe(false)
    generated.getCollectionDateSupplementEligibility.mockResolvedValueOnce({ ...range, targets: [], diagnostics: [] })
    await store.loadSupplementPlatforms(range)
    expect(store.supplementEligibilityError).toBeNull()
    expect(store.supplementEligibilityReady).toBe(true)
    expect(store.supplementContentPlatforms).toEqual([])
  })

  it('does not offer a platform when backend eligibility excludes its current irrelevant content', async () => {
    generated.getCollectionBatchSupplementEligibility.mockResolvedValue({
      batch_id: 'batch-irrelevant',
      targets: [],
    })

    await expect(fetchBatchContentPlatforms('batch-irrelevant', ['xiaohongshu'])).resolves.toEqual({
      platforms: [], diagnostics: [],
    })
    expect(generated.getCollectionBatchSupplementEligibility).toHaveBeenCalledWith('batch-irrelevant')
  })
})

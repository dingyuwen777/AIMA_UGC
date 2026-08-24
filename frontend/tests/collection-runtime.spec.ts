import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listCollectionRuntimeRuns: vi.fn(),
  getCollectionRuntimeSummary: vi.fn(),
  getCollectionCapabilities: vi.fn(),
  getCollectionBatchSupplementEligibility: vi.fn(),
  createCollectionRun: vi.fn(),
  getCollectionRun: vi.fn(),
  listImportBatches: vi.fn(),
  listKeywordPacks: vi.fn(),
  getImportBatch: vi.fn(),
  createImportBatch: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import {
  createTikHubCollectionRun,
  fetchBatchContentPlatforms,
  fetchCollectionRuntimeList,
} from '../src/features/import-batches/api'
import { useImportBatchesStore } from '../src/features/import-batches/store'

function batch(id: string, status: 'succeeded' | 'failed', rowsIngested: number) {
  return {
    id,
    input_artifact_id: `artifact-${id}`,
    source_filename: `${id}.xlsx`,
    status,
    stage: status,
    stats: {
      rows_seen: 1,
      rows_matched: 1,
      rows_filtered_out: 0,
      duplicates_removed: 0,
      rows_ingested: rowsIngested,
      rows_rejected: status === 'failed' ? 1 : 0,
    },
    created_at: '2026-08-21T00:00:00Z',
    job: {
      id: `job-${id}`,
      job_type: 'ingestion.import-excel.v1',
      status,
      attempt: 1,
      max_attempts: 10,
      progress: status === 'succeeded' ? 100 : 40,
      created_at: '2026-08-21T00:00:00Z',
    },
  }
}

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
    generated.listKeywordPacks.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })
  })

  it('delegates the unified list query to the Orval client', async () => {
    await fetchCollectionRuntimeList({ record_types: ['tikhub_discovery', 'tikhub_batch_supplement'], status: 'running', limit: 20 })
    expect(generated.listCollectionRuntimeRuns).toHaveBeenCalledWith({ record_types: ['tikhub_discovery', 'tikhub_batch_supplement'], status: 'running', limit: 20 })
  })

  it('creates a discovery Run through the generated Contract', async () => {
    generated.createCollectionRun.mockResolvedValue({ run_id: 'run-1', job_id: 'job-1', mode: 'discovery', status: 'queued' })
    await createTikHubCollectionRun({
      mode: 'discovery', keyword_pack_ids: ['pack-1', 'pack-2'],
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
      include_comments: true, include_sub_comments: false,
    })
    expect(generated.createCollectionRun).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'discovery', keyword_pack_ids: ['pack-1', 'pack-2'] }),
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

  it('keeps an older selected usable Import Batch available in the supplement drawer', async () => {
    generated.getCollectionCapabilities.mockResolvedValue({ provider_configs: [], capabilities: [] })
    generated.listImportBatches.mockResolvedValue({ items: [], next_cursor: null, has_more: false })
    generated.getImportBatch.mockResolvedValue(batch('older-batch', 'succeeded', 1))
    const store = useImportBatchesStore()
    await store.loadCreationOptions('older-batch')
    expect(generated.getImportBatch).toHaveBeenCalledWith('older-batch')
    expect(store.batchOptions.map((item) => item.id)).toEqual(['older-batch'])
  })

  it('offers only succeeded Import Batches that actually ingested content for supplement', async () => {
    generated.getCollectionCapabilities.mockResolvedValue({ provider_configs: [], capabilities: [] })
    generated.listImportBatches.mockResolvedValue({
      items: [batch('usable-batch', 'succeeded', 2), batch('empty-batch', 'succeeded', 0), batch('failed-batch', 'failed', 0)],
      next_cursor: null, has_more: false,
    })
    const store = useImportBatchesStore()
    await store.loadCreationOptions()
    expect(store.batchOptions.map((item) => item.id)).toEqual(['usable-batch'])
  })

  it('uses backend supplement eligibility instead of probing Voice Plaza content', async () => {
    generated.getCollectionBatchSupplementEligibility.mockResolvedValue({
      batch_id: 'batch-1',
      targets: [{ platform: 'xiaohongshu', target_count: 2 }],
    })

    await expect(fetchBatchContentPlatforms('batch-1', ['xiaohongshu', 'douyin'])).resolves.toEqual(['xiaohongshu'])
    expect(generated.getCollectionBatchSupplementEligibility).toHaveBeenCalledWith('batch-1')
  })

  it('does not offer a platform when backend eligibility excludes its current irrelevant content', async () => {
    generated.getCollectionBatchSupplementEligibility.mockResolvedValue({
      batch_id: 'batch-irrelevant',
      targets: [],
    })

    await expect(fetchBatchContentPlatforms('batch-irrelevant', ['xiaohongshu'])).resolves.toEqual([])
    expect(generated.getCollectionBatchSupplementEligibility).toHaveBeenCalledWith('batch-irrelevant')
  })
})

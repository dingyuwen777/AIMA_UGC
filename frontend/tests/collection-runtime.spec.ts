import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listCollectionRuntimeRuns: vi.fn(),
  getCollectionRuntimeSummary: vi.fn(),
  getCollectionCapabilities: vi.fn(),
  createCollectionRun: vi.fn(),
  getCollectionRun: vi.fn(),
  listImportBatches: vi.fn(),
  getImportBatch: vi.fn(),
  createImportBatch: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import {
  createTikHubCollectionRun,
  fetchCollectionRuntimeList,
} from '../src/features/import-batches/api'
import { useImportBatchesStore } from '../src/features/import-batches/store'

describe('collection runtime feature', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    generated.listCollectionRuntimeRuns.mockResolvedValue({
      items: [],
      has_more: false,
      next_cursor: null,
    })
    generated.getCollectionRuntimeSummary.mockResolvedValue({
      processing_count: 0,
      completed_today_count: 0,
      contents_ingested_today: 0,
      as_of: '2026-08-21T00:00:00Z',
    })
  })

  it('delegates the unified list query to the Orval client', async () => {
    await fetchCollectionRuntimeList({
      record_types: ['tikhub_discovery', 'tikhub_batch_supplement'],
      status: 'running',
      limit: 20,
    })

    expect(generated.listCollectionRuntimeRuns).toHaveBeenCalledWith({
      record_types: ['tikhub_discovery', 'tikhub_batch_supplement'],
      status: 'running',
      limit: 20,
    })
  })

  it('creates a discovery Run through the generated Contract', async () => {
    generated.createCollectionRun.mockResolvedValue({
      run_id: 'run-1',
      job_id: 'job-1',
      mode: 'discovery',
      status: 'queued',
    })

    await createTikHubCollectionRun({
      mode: 'discovery',
      keywords: ['爱玛', 'Q7'],
      platforms: [{ platform: 'xhs', provider_config_id: 'provider-1' }],
      include_comments: true,
      include_sub_comments: false,
    })

    expect(generated.createCollectionRun).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'discovery', keywords: ['爱玛', 'Q7'] }),
    )
  })

  it('loads the centralized Excel and TikHub runtime facts together', async () => {
    generated.listCollectionRuntimeRuns.mockResolvedValue({
      items: [
        {
          record_id: 'run-1',
          record_type: 'tikhub_discovery',
          display_name: '爱玛 / Q7 主动发现',
          job_id: 'job-1',
          status: 'running',
          stage: 'content_discovery',
          progress: 50,
          created_at: '2026-08-21T00:00:00Z',
        },
      ],
      has_more: false,
      next_cursor: null,
    })
    const store = useImportBatchesStore()

    await store.refresh()

    expect(generated.listCollectionRuntimeRuns).toHaveBeenCalledOnce()
    expect(generated.getCollectionRuntimeSummary).toHaveBeenCalledOnce()
    expect(store.items[0]?.record_type).toBe('tikhub_discovery')
    expect(store.summary?.contents_ingested_today).toBe(0)
  })

  it('keeps an older selected Import Batch available in the supplement drawer', async () => {
    generated.getCollectionCapabilities.mockResolvedValue({
      provider_configs: [],
      capabilities: [],
    })
    generated.listImportBatches.mockResolvedValue({
      items: [],
      next_cursor: null,
      has_more: false,
    })
    generated.getImportBatch.mockResolvedValue({
      id: 'older-batch',
      input_artifact_id: 'artifact-1',
      status: 'succeeded',
      stage: 'succeeded',
      stats: {
        rows_seen: 1,
        rows_matched: 1,
        rows_filtered_out: 0,
        duplicates_removed: 0,
        rows_ingested: 1,
        rows_rejected: 0,
      },
      created_at: '2026-08-01T00:00:00Z',
      job: {
        id: 'job-1',
        job_type: 'ingestion.import-excel.v1',
        status: 'succeeded',
        attempt: 1,
        max_attempts: 10,
        progress: 100,
        created_at: '2026-08-01T00:00:00Z',
      },
    })
    const store = useImportBatchesStore()

    await store.loadCreationOptions('older-batch')

    expect(generated.getImportBatch).toHaveBeenCalledWith('older-batch')
    expect(store.batchOptions.map((item) => item.id)).toEqual(['older-batch'])
  })
})

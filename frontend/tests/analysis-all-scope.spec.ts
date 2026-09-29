import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  VoicePlazaApiError: class VoicePlazaApiError extends Error {
    requestId = 'test-request'
  },
  cancelAnalysisRun: vi.fn(),
  fetchAnalysisRun: vi.fn(),
  fetchAnalysisRuns: vi.fn(),
  fetchContentAnalysisCapabilities: vi.fn(),
  fetchContentAnalysisTaxonomy: vi.fn(),
  fetchContentCount: vi.fn(),
  fetchContentDetail: vi.fn(),
  fetchContents: vi.fn(),
  fetchDataExport: vi.fn(),
  fetchDataExportFile: vi.fn(),
  fetchDataExports: vi.fn(),
  fetchExportColumnCatalog: vi.fn(),
  previewAnalysisRun: vi.fn(),
  reviewAnalysis: vi.fn(),
  reviewVehicles: vi.fn(),
  submitAnalysisRun: vi.fn(),
  submitContentRelevanceReview: vi.fn(),
  submitDataExport: vi.fn(),
}))

vi.mock('../src/features/voice-plaza/api', () => api)

import { useVoicePlazaStore } from '../src/features/voice-plaza/store'

describe('AI Analysis Run all scope', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    api.fetchContentAnalysisCapabilities.mockResolvedValue({ configured: true })
    api.previewAnalysisRun.mockResolvedValue({
      target_count: 4200,
      shard_count: 42,
      shard_size: 100,
      analysis_scheme_version_id: null,
      prompt_version: 'v3',
      prompt_sha256: 'a'.repeat(64),
      taxonomy_sha256: 'b'.repeat(64),
      model_provider: 'local',
      model: 'deepseek',
      generation_config: {},
      generation_config_hash: 'c'.repeat(64),
      configuration_hash: 'd'.repeat(64),
      cost_estimate_available: false,
      cost_estimate_note: '不做预算门禁',
    })
  })

  it('previews all current data without a browser-side id list', async () => {
    const store = useVoicePlazaStore()
    await store.refreshAnalysisCapabilities()

    const preview = await store.previewAnalysis('all')

    expect(preview?.target_count).toBe(4200)
    expect(api.previewAnalysisRun).toHaveBeenCalledWith({
      targets: { scope: 'all' },
    })
  })

  it('submits the current applied query snapshot without page or sort state', async () => {
    const store = useVoicePlazaStore()
    await store.refreshAnalysisCapabilities()
    store.filters.platform = 'xiaohongshu'
    store.filters.sentiment = '负面'
    store.applyFilters()

    const preview = await store.previewAnalysis('query')

    expect(preview?.target_count).toBe(4200)
    expect(api.previewAnalysisRun).toHaveBeenCalledWith(expect.objectContaining({
      targets: expect.objectContaining({
        scope: 'query',
        filters: expect.objectContaining({
          platforms: ['xiaohongshu'],
          sentiment: '负面',
        }),
      }),
    }))
    const request = api.previewAnalysisRun.mock.calls.at(-1)?.[0]
    expect(request?.targets).not.toHaveProperty('content_ids')
    expect(request?.targets.filters).not.toHaveProperty('sort_by')
    expect(request?.targets.filters).not.toHaveProperty('cursor')
  })

  it('keeps selected mode validation independent from all mode', async () => {
    const store = useVoicePlazaStore()
    await store.refreshAnalysisCapabilities()

    expect(await store.previewAnalysis('selected')).toBeNull()
    expect(api.previewAnalysisRun).not.toHaveBeenCalled()
  })
})

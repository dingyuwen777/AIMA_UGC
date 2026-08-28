import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listContents: vi.fn(),
  getContent: vi.fn(),
  getContentAnalysisCapabilities: vi.fn(),
  previewContentAnalysisRun: vi.fn(),
  createContentAnalysisRun: vi.fn(),
  listContentAnalysisRuns: vi.fn(),
  getContentAnalysisRun: vi.fn(),
  cancelContentAnalysisRun: vi.fn(),
  createContentRelevanceReview: vi.fn(),
  getContentAnalysisJob: vi.fn(),
  createDataExport: vi.fn(),
  listDataExports: vi.fn(),
  getDataExport: vi.fn(),
  downloadDataExport: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import VoicePlazaFilters from '../src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaFilters.vue'
import VoicePlazaTable from '../src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaTable.vue'
import { VoicePlazaApiError, fetchContents, fetchDataExportFile } from '../src/features/voice-plaza/api'
import { useVoicePlazaStore } from '../src/features/voice-plaza/store'

const item = {
  id: '01991f80-6d5d-7dc8-95cb-c67c12345678',
  platform: 'xiaohongshu' as const,
  external_content_id: 'note-1',
  content_type: 'note',
  title: '续航体验',
  text: '真实用户内容',
  published_at: '2026-08-21T01:00:00Z',
  last_seen_at: '2026-08-21T02:00:00Z',
  metrics: { like_count: 12, comment_count: 3 },
  analysis: {
    status: 'completed' as const,
    relevance: 'relevant' as const,
    voice_type: '真实用户发声' as const,
    sentiment: '负面',
    labels: [
      { primary_label: '产品体验', secondary_label: '续航表现' },
      { primary_label: '服务体验', secondary_label: '门店服务' },
      { primary_label: '购买体验', secondary_label: '价格感知' },
    ],
    analyzed_at: '2026-08-21T03:00:00Z',
  },
  effective_relevance: 'relevant' as const,
  relevance_source: 'ai' as const,
  source: { provider_name: 'file-import' },
}

describe('voice plaza', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    generated.getContentAnalysisCapabilities.mockResolvedValue({ configured: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('queries contents only through the generated Orval client', async () => {
    generated.listContents.mockResolvedValue({ items: [item], has_more: false })

    await expect(fetchContents({ sentiment: '负面', limit: 20 })).resolves.toMatchObject({
      items: [item],
    })
    expect(generated.listContents).toHaveBeenCalledWith({ sentiment: '负面', limit: 20 })
  })

  it('offers exactly the five supported content platforms in the platform filter', async () => {
    const html = await renderToString(
      createSSRApp({
        render: () => h(VoicePlazaFilters, {
          search: '',
          platform: '',
          contentType: '',
          analysisStatus: '',
          relevance: '',
          sentiment: '',
          primaryLabel: '',
          secondaryLabel: '',
          publishedFrom: '',
          publishedTo: '',
          sourceIdentifier: '',
        }),
      }),
    )

    for (const [value, label] of [
      ['xiaohongshu', '小红书'],
      ['douyin', '抖音'],
      ['weibo', '微博'],
      ['bilibili', 'B站'],
      ['kuaishou', '快手'],
    ]) {
      expect(html).toContain(`value="${value}"`)
      expect(html).toContain(label)
    }
    expect(html).not.toContain('value="file"')
  })

  it('renders every ordered primary and secondary AI label pair in the label column', async () => {
    const labels = await renderToString(
      createSSRApp({
        render: () => h(VoicePlazaTable, {
          items: [item],
          loading: false,
          selectedIds: [],
          reviewing: false,
        }),
      }),
    )
    expect(labels).toContain('产品体验')
    expect(labels).toContain('续航表现')
    expect(labels).toContain('服务体验')
    expect(labels).toContain('门店服务')
    expect(labels).toContain('购买体验')
    expect(labels).toContain('价格感知')
  })

  it('keeps a manual relevance override visible and undoable when AI is stale', async () => {
    const staleManualItem = {
      ...item,
      analysis: {
        status: 'stale' as const,
        relevance: null,
        voice_type: null,
        sentiment: null,
        labels: [],
        analyzed_at: null,
      },
      effective_relevance: 'relevant' as const,
      relevance_source: 'manual_review' as const,
    }
    const html = await renderToString(
      createSSRApp({
        render: () => h(VoicePlazaTable, {
          items: [staleManualItem],
          loading: false,
          selectedIds: [],
          reviewing: false,
        }),
      }),
    )

    expect(html).toContain('人工复核相关')
    expect(html).toContain('撤销人工判断')
  })

  it('preserves the shared HTTP error contract for binary export responses', async () => {
    generated.downloadDataExport.mockResolvedValue(
      new Blob(
        [JSON.stringify({ status: 409, detail: '导出尚未完成', request_id: 'request-export' })],
        { type: 'application/json' },
      ),
    )

    const error = await fetchDataExportFile('export-1').catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(VoicePlazaApiError)
    expect(error).toMatchObject({ status: 409, requestId: 'request-export' })
  })

  it('blocks analysis creation when the backend reports no configured runtime', async () => {
    generated.getContentAnalysisCapabilities.mockResolvedValue({ configured: false })
    const store = useVoicePlazaStore()

    await store.refreshAnalysisCapabilities()
    const preview = await store.previewAnalysis('selected')

    expect(store.analysisConfigured).toBe(false)
    expect(preview).toBeNull()
    expect(store.error).toContain('当前环境尚未配置可用的 AI 模型')
    expect(generated.previewContentAnalysisRun).not.toHaveBeenCalled()
  })

  it('previews and confirms an analysis run with the exact frozen target selection', async () => {
    generated.previewContentAnalysisRun.mockResolvedValue({
      target_count: 1,
      shard_count: 1,
      shard_size: 1,
      prompt_version: 'content_labeling_v3',
      prompt_sha256: 'a'.repeat(64),
      taxonomy_sha256: 'b'.repeat(64),
      model_provider: 'openai-compatible',
      model: 'fixture-model',
      generation_config: { temperature: 0 },
      generation_config_hash: 'c'.repeat(64),
      configuration_hash: 'd'.repeat(64),
      cost_estimate_available: false,
      cost_estimate_note: '不能伪造费用估算。',
    })
    generated.createContentAnalysisRun.mockResolvedValue({
      run_id: 'run-1',
      planner_job_id: 'job-1',
      target_count: 1,
      shard_count: 1,
      status: 'queued',
    })
    generated.listContentAnalysisRuns.mockResolvedValue({ items: [] })
    const store = useVoicePlazaStore()
    store.selectedIds = [item.id]

    await store.refreshAnalysisCapabilities()
    const preview = await store.previewAnalysis('selected')
    store.selectedIds = []
    const created = await store.confirmAnalysis()

    expect(preview?.configuration_hash).toBe('d'.repeat(64))
    expect(created).toBe(1)
    expect(generated.previewContentAnalysisRun).toHaveBeenCalledWith({
      targets: { scope: 'selected', content_ids: [item.id] },
    })
    expect(generated.createContentAnalysisRun).toHaveBeenCalledWith(expect.objectContaining({
      targets: { scope: 'selected', content_ids: [item.id] },
      expected_target_count: 1,
      expected_configuration_hash: 'd'.repeat(64),
      run_intent: 'manual_reanalysis',
    }))
  })

  it('surfaces an analysis run polling failure instead of leaving an unhandled rejection', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('document', { visibilityState: 'visible' })
    generated.listContentAnalysisRuns
      .mockResolvedValueOnce({
        items: [{ id: 'run-1', status: 'queued', stats: { pending: 1 } }],
      })
      .mockRejectedValueOnce(new Error('analysis polling failed'))
    generated.getContentAnalysisRun.mockResolvedValue({
      id: 'run-1',
      status: 'queued',
      stats: { pending: 1 },
      shards: [],
    })
    generated.listContents.mockResolvedValue({ items: [], has_more: false })
    generated.listDataExports.mockResolvedValue({ items: [], has_more: false })
    const store = useVoicePlazaStore()

    await store.refreshAnalysisRuns()
    store.startPolling(1000)
    await vi.advanceTimersByTimeAsync(1000)

    expect(store.error).toBe('analysis polling failed')
    store.stopPolling()
  })

  it('loads shard progress for active runs omitted by the list response', async () => {
    const listedRun = {
      id: 'run-1',
      status: 'running',
      target_count: 20,
      shards: [],
    }
    generated.listContentAnalysisRuns.mockResolvedValue({ items: [listedRun] })
    generated.getContentAnalysisRun.mockResolvedValue({
      ...listedRun,
      shards: [{ request_id: 'request-1', job_id: 'job-1', shard_no: 0, target_count: 10, status: 'running', progress: 50 }],
    })
    const store = useVoicePlazaStore()

    await store.refreshAnalysisRuns()

    expect(generated.getContentAnalysisRun).toHaveBeenCalledWith('run-1')
    expect(store.analysisRuns[0]?.shards).toHaveLength(1)
  })

  it('keeps an empty run list when the server response is malformed', async () => {
    generated.listContentAnalysisRuns.mockResolvedValue(undefined)
    const store = useVoicePlazaStore()

    await store.refreshAnalysisRuns()

    expect(store.analysisRuns).toEqual([])
    expect(store.error).toBe('AI Analysis Run 历史响应格式无效。')
  })

  it('does not create a query export when the current query has no content', async () => {
    generated.createDataExport.mockResolvedValue({
      export_id: 'export-empty',
      job_id: 'job-empty',
      target_count: 0,
    })
    const store = useVoicePlazaStore()

    const created = await store.createExport('query')

    expect(created).toBeNull()
    expect(generated.createDataExport).not.toHaveBeenCalled()
  })
})

import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listContents: vi.fn(),
  getContent: vi.fn(),
  getContentAnalysisCapabilities: vi.fn(),
  createContentAnalysis: vi.fn(),
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
    voice_type: 'user_voice' as const,
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
    vi.clearAllMocks()
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
    const created = await store.createAnalysis('query')

    expect(store.analysisConfigured).toBe(false)
    expect(created).toBeNull()
    expect(store.error).toContain('当前环境尚未配置可用的 AI 模型')
    expect(generated.createContentAnalysis).not.toHaveBeenCalled()
  })

  it('surfaces an analysis job polling failure instead of leaving an unhandled rejection', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('document', { visibilityState: 'visible' })
    generated.createContentAnalysis.mockResolvedValue({ job_id: 'job-1', target_count: 1 })
    generated.getContentAnalysisJob
      .mockResolvedValueOnce({ id: 'job-1', status: 'queued' })
      .mockRejectedValueOnce(new Error('analysis polling failed'))
    generated.listContents.mockResolvedValue({ items: [], has_more: false })
    generated.listDataExports.mockResolvedValue({ items: [], has_more: false })
    const store = useVoicePlazaStore()

    await store.refreshAnalysisCapabilities()
    await store.createAnalysis('query')
    store.startPolling(1000)
    await vi.advanceTimersByTimeAsync(1000)

    expect(store.error).toBe('analysis polling failed')
    store.stopPolling()
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

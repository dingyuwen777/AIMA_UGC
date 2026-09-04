import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listContents: vi.fn(),
  getContent: vi.fn(),
  getContentAnalysisCapabilities: vi.fn(),
  getContentAnalysisTaxonomy: vi.fn(),
  previewContentAnalysisRun: vi.fn(),
  createContentAnalysisRun: vi.fn(),
  listContentAnalysisRuns: vi.fn(),
  listCollectionRuntimeRuns: vi.fn(),
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
import { useTaskCenterStore } from '../src/features/task-center/store'

const item = {
  id: '01991f80-6d5d-7dc8-95cb-c67c12345678',
  content_version: 1,
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

const taxonomy = {
  prompt_version: 'content-labeling.v3',
  prompt_sha256: 'a'.repeat(64),
  schema_version: 'aima-content-taxonomy.v2',
  taxonomy_sha256: 'b'.repeat(64),
  sentiments: ['正面', '中性', '负面'],
  voice_types: ['真实用户发声', '媒体机构发声', '无法判断'],
  labels: [
    { primary_label: '产品体验', secondary_labels: ['续航表现', '骑行舒适'] },
    { primary_label: '服务体验', secondary_labels: ['门店服务'] },
  ],
}

describe('voice plaza', () => {
  it('慢 AI 查询不叠加，停止轮询后旧响应不会再触发内容请求', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('document', { visibilityState: 'visible' })
    const run = { id: 'run-1', status: 'running', stats: { pending: 2 } }
    generated.listContentAnalysisRuns.mockResolvedValueOnce({ items: [run] })
    const plaza = useVoicePlazaStore()
    const center = useTaskCenterStore()
    await plaza.refreshAnalysisRuns()
    let finishAnalysis!: (value: unknown) => void
    generated.listContentAnalysisRuns.mockReturnValue(new Promise((resolve) => { finishAnalysis = resolve }))
    plaza.startPolling()
    center.startPolling()
    await vi.advanceTimersByTimeAsync(4000)
    expect(generated.listContentAnalysisRuns).toHaveBeenCalledTimes(2)
    plaza.stopPolling()
    center.stopPolling()
    const beforeStop = generated.listContents.mock.calls.length
    finishAnalysis({ items: [{ ...run, status: 'succeeded', stats: { pending: 0, succeeded: 2 } }] })
    await vi.advanceTimersByTimeAsync(2000)
    expect(generated.listContents).toHaveBeenCalledTimes(beforeStop)
  })

  it('任务结束后的内容刷新失败仍会重试，不再轮询已完成任务', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('document', { visibilityState: 'visible' })
    generated.listContentAnalysisRuns
      .mockResolvedValueOnce({ items: [{ id: 'run-1', status: 'running', stats: { pending: 1 } }] })
      .mockResolvedValue({ items: [{ id: 'run-1', status: 'succeeded', stats: { succeeded: 1 } }] })
    generated.listContents
      .mockRejectedValueOnce(new Error('内容读取暂时失败'))
      .mockResolvedValue({ items: [{ ...item, title: '最终内容' }], has_more: false })
    const plaza = useVoicePlazaStore()
    await plaza.refreshAnalysisRuns()
    plaza.startPolling()
    try {
      await vi.advanceTimersByTimeAsync(1000)
      expect(plaza.listError).toBe('内容读取暂时失败')
      expect(plaza.analysisRuns[0]?.status).toBe('succeeded')
      await vi.advanceTimersByTimeAsync(1000)
      expect(plaza.items[0]?.title).toBe('最终内容')
      expect(plaza.listError).toBeNull()
      expect(generated.listContentAnalysisRuns).toHaveBeenCalledTimes(2)
      expect(generated.listContents).toHaveBeenCalledTimes(2)
    } finally {
      plaza.stopPolling()
    }
  })

  it('两个页面共享 AI 查询，进度未变不重读内容，终态后也补齐慢查询遗漏的最后结果', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('document', { visibilityState: 'visible' })
    const run = { id: 'run-1', status: 'running', target_count: 2,
      stats: { pending: 2, succeeded: 0, failed: 0, stale: 0, cancelled: 0 }, shards: [] }
    generated.listContentAnalysisRuns.mockResolvedValue({ items: [run] })
    generated.listCollectionRuntimeRuns.mockResolvedValue({ items: [], has_more: false })
    generated.listDataExports.mockResolvedValue({ items: [], has_more: false })
    generated.listContents.mockResolvedValue({ items: [item], has_more: false })
    const plaza = useVoicePlazaStore()
    const center = useTaskCenterStore()
    await Promise.all([plaza.refreshAnalysisRuns(), center.refresh()])
    expect(generated.listContentAnalysisRuns).toHaveBeenCalledTimes(1)
    plaza.startPolling()
    center.startPolling()
    try {
      await vi.advanceTimersByTimeAsync(1000)
      const initialContentReads = generated.listContents.mock.calls.length
      await vi.advanceTimersByTimeAsync(2000)
      expect(generated.listContents).toHaveBeenCalledTimes(initialContentReads)
      expect(generated.listContentAnalysisRuns).toHaveBeenCalledTimes(4)
      let finishOldWindow!: (value: unknown) => void
      generated.listContents.mockReturnValueOnce(new Promise((resolve) => { finishOldWindow = resolve }))
      generated.listContentAnalysisRuns.mockResolvedValue({ items: [{ ...run,
        stats: { ...run.stats, pending: 1, succeeded: 1 } }] })
      await vi.advanceTimersByTimeAsync(1000)
      expect(generated.listContents).toHaveBeenCalledTimes(initialContentReads + 1)
      generated.listContentAnalysisRuns.mockResolvedValue({ items: [{ ...run, status: 'succeeded',
        stats: { ...run.stats, pending: 0, succeeded: 2 } }] })
      await vi.advanceTimersByTimeAsync(1000)
      expect(plaza.analysisRuns[0]?.status).toBe('succeeded')
      expect(center.analysisRuns[0]?.status).toBe('succeeded')
      finishOldWindow({ items: [{ ...item, title: '旧内容' }], has_more: false })
      generated.listContents.mockResolvedValue({ items: [{ ...item, title: '最后完成的内容' }], has_more: false })
      await vi.advanceTimersByTimeAsync(1000)
      expect(plaza.items[0]?.title).toBe('最后完成的内容')
      const finalReads = generated.listContents.mock.calls.length
      await vi.advanceTimersByTimeAsync(2000)
      expect(generated.listContents).toHaveBeenCalledTimes(finalReads)
      expect(generated.listDataExports).toHaveBeenCalledTimes(1)
    } finally {
      plaza.stopPolling()
      center.stopPolling()
    }
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    generated.getContentAnalysisCapabilities.mockResolvedValue({ configured: true })
    generated.getContentAnalysisTaxonomy.mockResolvedValue(taxonomy)
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
          voiceType: '',
          sentiment: '',
          primaryLabel: '',
          secondaryLabel: '',
          publishedFrom: '',
          publishedTo: '',
          sourceIdentifier: '',
          taxonomy,
          taxonomyLoading: false,
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

  it('renders sentiments, voice types and dependent labels from the backend taxonomy', async () => {
    const futureTaxonomy = {
      ...taxonomy,
      sentiments: ['混合情感'],
      voice_types: ['社区活动发声'],
      labels: [{ primary_label: '社区反馈', secondary_labels: ['活动体验'] }],
    }
    const html = await renderToString(
      createSSRApp({
        render: () => h(VoicePlazaFilters, {
          search: '',
          platform: '',
          contentType: '',
          analysisStatus: '',
          relevance: '',
          voiceType: '',
          sentiment: '',
          primaryLabel: '社区反馈',
          secondaryLabel: '',
          publishedFrom: '',
          publishedTo: '',
          sourceIdentifier: '',
          taxonomy: futureTaxonomy,
          taxonomyLoading: false,
        }),
      }),
    )

    expect(html).toContain('混合情感')
    expect(html).toContain('社区活动发声')
    expect(html).toContain('社区反馈')
    expect(html).toContain('活动体验')
    expect(html).not.toContain('value="正面"')
  })

  it('disables taxonomy-dependent controls while a newer taxonomy is loading', async () => {
    const html = await renderToString(
      createSSRApp({
        render: () => h(VoicePlazaFilters, {
          search: '',
          platform: '',
          contentType: '',
          analysisStatus: '',
          relevance: '',
          voiceType: '',
          sentiment: '',
          primaryLabel: '',
          secondaryLabel: '',
          publishedFrom: '',
          publishedTo: '',
          sourceIdentifier: '',
          taxonomy,
          taxonomyLoading: true,
        }),
      }),
    )

    expect(html.match(/<select[^>]*disabled/g)?.length ?? 0).toBeGreaterThanOrEqual(4)
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
    expect(labels).toContain('真实用户发声')
  })

  it('loads taxonomy and sends voice type with the existing query filters', async () => {
    generated.listContents.mockResolvedValue({ items: [item], has_more: false })
    const store = useVoicePlazaStore()

    await store.refreshTaxonomy()
    store.filters.voiceType = '真实用户发声'
    store.filters.sentiment = '负面'
    store.filters.primaryLabel = '产品体验'
    store.filters.secondaryLabel = '续航表现'
    await store.refresh()

    expect(store.taxonomy?.taxonomy_sha256).toBe('b'.repeat(64))
    expect(generated.listContents).toHaveBeenCalledWith(expect.objectContaining({
      voice_type: '真实用户发声',
      sentiment: '负面',
      primary_label: '产品体验',
      secondary_label: '续航表现',
    }))
  })

  it('fails taxonomy closed without blocking the independent content list', async () => {
    generated.getContentAnalysisTaxonomy.mockRejectedValue(
      new VoicePlazaApiError({
        type: 'about:blank',
        title: 'AI 分类配置暂不可用',
        status: 503,
        detail: '当前 Prompt Taxonomy 无法安全读取或校验。',
        request_id: 'request-taxonomy',
        errors: [],
      }),
    )
    generated.listContents.mockResolvedValue({ items: [item], has_more: false })
    const store = useVoicePlazaStore()

    await Promise.all([store.refreshTaxonomy(), store.refresh()])

    expect(store.taxonomy).toBeNull()
    expect(store.taxonomyError).toContain('request-taxonomy')
    expect(store.items).toEqual([item])
    expect(store.listError).toBeNull()
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
    let finishOldPoll!: (value: unknown) => void
    generated.listContentAnalysisRuns
      .mockReturnValueOnce(new Promise((resolve) => { finishOldPoll = resolve }))
      .mockResolvedValue({ items: [{ id: 'run-1', status: 'queued', stats: { pending: 1 } }] })
    const store = useVoicePlazaStore()
    store.selectedIds = [item.id]
    const oldPoll = store.refreshAnalysisRuns()

    await store.refreshAnalysisCapabilities()
    const preview = await store.previewAnalysis('selected')
    store.selectedIds = []
    const created = await store.confirmAnalysis()
    expect(store.analysisRuns[0]?.id).toBe('run-1')
    finishOldPoll({ items: [] })
    await oldPoll
    expect(store.analysisRuns[0]?.id).toBe('run-1')

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

  it('uses persisted list statistics without issuing another request per active run', async () => {
    const listedRun = {
      id: 'run-1',
      status: 'running',
      target_count: 20,
      shards: [],
      stats: { pending: 15, succeeded: 5, failed: 0, stale: 0, cancelled: 0 },
    }
    generated.listContentAnalysisRuns.mockResolvedValue({ items: [listedRun] })
    generated.getContentAnalysisRun.mockResolvedValue({
      ...listedRun,
      shards: [{ request_id: 'request-1', job_id: 'job-1', shard_no: 0, target_count: 10, status: 'running', progress: 50 }],
    })
    const store = useVoicePlazaStore()

    await store.refreshAnalysisRuns()

    expect(generated.getContentAnalysisRun).not.toHaveBeenCalled()
    expect(store.analysisRuns[0]?.stats?.succeeded).toBe(5)
  })

  it('deduplicates polling and rejects a stale response after cancellation', async () => {
    const run = { id: 'run-1', status: 'running', stats: { pending: 1 } }
    generated.listContentAnalysisRuns.mockResolvedValueOnce({ items: [run] })
    const store = useVoicePlazaStore()
    await store.refreshAnalysisRuns()
    let resolve!: (value: unknown) => void
    generated.listContentAnalysisRuns.mockReturnValueOnce(new Promise((done) => { resolve = done }))
    const pending = store.refreshAnalysisRuns()
    await store.refreshAnalysisRuns()
    expect(generated.listContentAnalysisRuns).toHaveBeenCalledTimes(2)
    generated.cancelContentAnalysisRun.mockResolvedValue({ ...run, status: 'cancelling' })
    expect(await store.cancelRun(run.id)).toBe(true)
    resolve({ items: [run] })
    await pending
    expect(store.analysisRuns[0]?.status).toBe('cancelling')
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

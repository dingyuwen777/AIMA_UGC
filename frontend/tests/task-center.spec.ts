import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  fetchTaskCenterAnalysisRuns: vi.fn(),
  fetchTaskCenterCollectionRuns: vi.fn(),
  fetchTaskCenterDataExports: vi.fn(),
  cancelTaskCenterAnalysisRun: vi.fn(),
}))
vi.mock('../src/features/task-center/api', () => api)

import type {
  AnalysisContentRunResponse,
  CollectionRuntimeItemResponse,
  DataExportResponse,
} from '../src/generated/api/client'
import { analysisRunProgress, useTaskCenterStore } from '../src/features/task-center/store'

const analysisBase: AnalysisContentRunResponse = {
  id: 'analysis-1',
  planner_job_id: 'planner-1',
  sequence_no: 12,
  status: 'running',
  run_intent: 'manual_reanalysis',
  scope: 'selected',
  target_count: 100,
  shard_count: 2,
  shard_size: 50,
  prompt_version: 'content_labeling_v3',
  prompt_sha256: 'a'.repeat(64),
  taxonomy_sha256: 'b'.repeat(64),
  model_provider: 'openai-compatible',
  model: 'fixture-model',
  generation_config: {},
  generation_config_hash: 'c'.repeat(64),
  stats: { pending: 50, succeeded: 48, failed: 2, cancelled: 0, stale: 0 },
  shards: [
    { request_id: 'request-1', job_id: 'job-1', shard_no: 0, target_count: 50, status: 'succeeded', progress: 100, error_code: null },
    { request_id: 'request-2', job_id: 'job-2', shard_no: 1, target_count: 50, status: 'running', progress: 0, error_code: null },
  ],
  created_at: '2026-09-03T18:00:00+08:00',
  started_at: '2026-09-03T18:00:05+08:00',
  finished_at: null,
}

const collectionRun: CollectionRuntimeItemResponse = {
  record_id: 'collection-1',
  record_type: 'tikhub_discovery',
  display_name: '爱玛关键词采集',
  job_id: 'collection-job-1',
  collection_run_id: 'collection-run-1',
  import_batch_id: null,
  status: 'running',
  stage: 'discovering',
  progress: 36,
  created_at: '2026-09-03T17:50:00+08:00',
  started_at: '2026-09-03T17:50:03+08:00',
  finished_at: null,
  platforms: ['xiaohongshu'],
  keywords: ['爱玛'],
  collection_stats: {
    content_count: 120,
    comment_count: 36,
    requested_count: 160,
    succeeded_count: 120,
    failed_count: 4,
    filtered_count: 36,
  },
}

const exportRun: DataExportResponse = {
  id: 'export-1',
  job: {
    id: 'export-job-1',
    job_type: 'reporting.content-export-excel.v1',
    status: 'running',
    attempt: 1,
    max_attempts: 3,
    progress: 64,
    error_code: null,
    result: null,
    created_at: '2026-09-03T17:40:00+08:00',
    started_at: '2026-09-03T17:40:02+08:00',
    finished_at: null,
  },
  artifact_id: null,
  filename: null,
  stats: null,
  created_at: '2026-09-03T17:40:00+08:00',
  completed_at: null,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  api.fetchTaskCenterAnalysisRuns.mockResolvedValue([])
  api.fetchTaskCenterCollectionRuns.mockResolvedValue([])
  api.fetchTaskCenterDataExports.mockResolvedValue([])
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('全局任务中心聚合', () => {
  it('活动 AI 每秒刷新，慢采集不阻塞，其他来源保持原频率，结束后停止快速查询', async () => {
    vi.useFakeTimers()
    const documentState = { visibilityState: 'visible' }
    vi.stubGlobal('document', documentState)
    api.fetchTaskCenterAnalysisRuns.mockResolvedValue([analysisBase])
    api.fetchTaskCenterCollectionRuns.mockReturnValue(new Promise(() => {}))
    const store = useTaskCenterStore()
    void store.refresh()
    store.startPolling()
    try {
      await vi.advanceTimersByTimeAsync(2100)
      expect(api.fetchTaskCenterAnalysisRuns).toHaveBeenCalledTimes(3)
      expect(api.fetchTaskCenterCollectionRuns).toHaveBeenCalledTimes(1)
      expect(api.fetchTaskCenterDataExports).toHaveBeenCalledTimes(1)
      api.fetchTaskCenterAnalysisRuns.mockResolvedValue([{ ...analysisBase, status: 'succeeded' }])
      await vi.advanceTimersByTimeAsync(1000)
      expect(store.activeCount).toBe(0)
      const completedCalls = api.fetchTaskCenterAnalysisRuns.mock.calls.length
      await vi.advanceTimersByTimeAsync(3000)
      expect(api.fetchTaskCenterAnalysisRuns).toHaveBeenCalledTimes(completedCalls)
      store.analysisRuns = [{ ...analysisBase, status: 'cancelling' }]
      documentState.visibilityState = 'hidden'
      await vi.advanceTimersByTimeAsync(1000)
      expect(api.fetchTaskCenterAnalysisRuns).toHaveBeenCalledTimes(completedCalls)
      documentState.visibilityState = 'visible'
      await vi.advanceTimersByTimeAsync(1000)
      expect(api.fetchTaskCenterAnalysisRuns).toHaveBeenCalledTimes(completedCalls + 1)
    } finally {
      store.stopPolling()
    }
    await vi.advanceTimersByTimeAsync(20_000)
    expect(api.fetchTaskCenterDataExports).toHaveBeenCalledTimes(1)
  })

  it('采集响应阻塞时仍更新并继续轮询 AI 任务，且不叠加同来源请求', async () => {
    let finishCollection!: (value: CollectionRuntimeItemResponse[]) => void
    api.fetchTaskCenterCollectionRuns.mockReturnValue(new Promise((resolve) => {
      finishCollection = resolve
    }))
    api.fetchTaskCenterAnalysisRuns.mockResolvedValue([analysisBase])
    const store = useTaskCenterStore()
    const first = store.refresh()
    await vi.waitFor(() => expect(store.analysisRuns).toHaveLength(1))
    api.fetchTaskCenterAnalysisRuns.mockResolvedValue([{ ...analysisBase, status: 'succeeded' }])
    await store.refresh(true)
    expect(store.analysisRuns[0]?.status).toBe('succeeded')
    expect(api.fetchTaskCenterAnalysisRuns).toHaveBeenCalledTimes(2)
    expect(api.fetchTaskCenterCollectionRuns).toHaveBeenCalledTimes(1)
    finishCollection([collectionRun])
    await first
    expect(store.collectionRuns).toHaveLength(1)
  })

  it('取消后到达的旧查询不能覆盖取消结果', async () => {
    let finishAnalysis!: (value: AnalysisContentRunResponse[]) => void
    api.fetchTaskCenterAnalysisRuns.mockReturnValue(new Promise((resolve) => {
      finishAnalysis = resolve
    }))
    api.cancelTaskCenterAnalysisRun.mockResolvedValue({ ...analysisBase, status: 'cancelling' })
    const store = useTaskCenterStore()
    store.analysisRuns = [analysisBase]
    const pending = store.refresh()
    expect(await store.cancelAnalysisRun(analysisBase.id)).toBe(true)
    finishAnalysis([analysisBase])
    await pending
    expect(store.analysisRuns[0]?.status).toBe('cancelling')
  })

  it('按持久化终态计数显示进度，即使 Shard 心跳进度落后', () => {
    expect(analysisRunProgress(analysisBase)).toBe(50)
    expect(analysisRunProgress({ ...analysisBase, shards: [] })).toBe(50)
    expect(analysisRunProgress({
      ...analysisBase,
      stats: { pending: 40, succeeded: 58, failed: 2, cancelled: 0, stale: 0 },
    })).toBe(60)
  })

  it('把 Analysis、Collection 与 Export 活动任务统一成只读 ViewModel', () => {
    const store = useTaskCenterStore()
    store.analysisRuns = [analysisBase]
    store.collectionRuns = [collectionRun]
    store.dataExports = [exportRun]

    expect(store.activeCount).toBe(3)
    expect(store.activeItems.map((item) => item.kind)).toEqual(['analysis', 'collection', 'export'])
    expect(store.activeItems[0]).toMatchObject({
      title: 'AI 打标 · Run #12',
      statusLabel: '处理中',
      progress: 50,
      href: '/voice-plaza',
    })
    expect(store.activeItems[1]).toMatchObject({
      title: '爱玛关键词采集',
      subtitle: 'TikHub 采集 · 小红书',
      href: '/collection-runtime',
    })
  })

  it('把最新主线的 Data Import Campaign 映射为用户可读任务类型', () => {
    const store = useTaskCenterStore()
    store.collectionRuns = [{
      ...collectionRun,
      record_id: 'campaign-1',
      record_type: 'data_import_campaign',
      display_name: '8 月历史数据导入',
      data_import_campaign_id: 'campaign-1',
      collection_run_id: null,
      platforms: [],
      collection_stats: null,
      import_stats: { rows_ingested: 320 },
      stage: 'ingesting',
    }]

    expect(store.activeItems[0]).toMatchObject({
      title: '8 月历史数据导入',
      subtitle: '数据导入 · 平台未指定',
      progressDetail: '320 行入库',
      href: '/collection-runtime',
    })
  })

  it('终态任务不计入活动数量，并只保留最近 12 条作为界面历史', () => {
    const store = useTaskCenterStore()
    store.analysisRuns = Array.from({ length: 14 }, (_, index) => ({
      ...analysisBase,
      id: `analysis-${index}`,
      sequence_no: index + 1,
      status: 'succeeded' as const,
      created_at: `2026-09-03T${String(index + 1).padStart(2, '0')}:00:00+08:00`,
      finished_at: `2026-09-03T${String(index + 1).padStart(2, '0')}:30:00+08:00`,
      stats: { pending: 0, succeeded: 100, failed: 0, cancelled: 0, stale: 0 },
    }))

    expect(store.activeCount).toBe(0)
    expect(store.recentItems).toHaveLength(12)
    expect(store.recentItems[0].title).toBe('AI 打标 · Run #14')
    expect(store.recentItems.at(-1)?.title).toBe('AI 打标 · Run #3')
  })
})

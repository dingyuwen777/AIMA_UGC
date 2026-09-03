import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

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

beforeEach(() => setActivePinia(createPinia()))

describe('全局任务中心聚合', () => {
  it('按 Shard 目标数计算 Analysis Run 加权进度', () => {
    expect(analysisRunProgress(analysisBase)).toBe(50)
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

import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  CollectionRuntimeItemResponse,
  ListCollectionRuntimeRunsParams,
} from '../src/generated/api/client'

const { listCollectionRuntimeRunsMock } = vi.hoisted(() => ({
  listCollectionRuntimeRunsMock: vi.fn(),
}))

vi.mock('../src/generated/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/generated/api/client')>()
  return {
    ...actual,
    listCollectionRuntimeRuns: listCollectionRuntimeRunsMock,
  }
})

import { fetchTaskCenterCollectionRuns } from '../src/features/task-center/api'

/** 构造最小合法的 Collection Runtime 投影，便于覆盖分页和活动状态。 */
function runtimeItem(
  recordId: string,
  status: CollectionRuntimeItemResponse['status'],
): CollectionRuntimeItemResponse {
  return {
    record_id: recordId,
    record_type: 'tikhub_discovery',
    display_name: recordId,
    job_id: `${recordId}-job`,
    collection_run_id: `${recordId}-run`,
    import_batch_id: null,
    status,
    stage: status,
    progress: status === 'succeeded' ? 100 : 20,
    created_at: '2026-09-03T18:00:00+08:00',
    started_at: '2026-09-03T18:00:01+08:00',
    finished_at: status === 'succeeded' ? '2026-09-03T18:05:00+08:00' : null,
    platforms: ['xiaohongshu'],
    keywords: ['爱玛'],
  }
}

beforeEach(() => {
  listCollectionRuntimeRunsMock.mockReset()
})

describe('任务中心 Collection Runtime 读取', () => {
  it('历史超过单页时继续按活动状态翻页，避免较早活动任务从全局数量中消失', async () => {
    const recent = runtimeItem('recent-terminal', 'succeeded')
    const queued = runtimeItem('deep-queued', 'queued')
    const runningFirst = runtimeItem('deep-running-1', 'running')
    const runningSecond = runtimeItem('deep-running-2', 'running')

    listCollectionRuntimeRunsMock.mockImplementation(async (
      params?: ListCollectionRuntimeRunsParams,
    ) => {
      if (!params?.status) {
        return { items: [recent], has_more: true, next_cursor: 'older-history' }
      }
      if (params.status === 'queued') {
        return { items: [queued], has_more: false, next_cursor: null }
      }
      if (params.status === 'running' && !params.cursor) {
        return { items: [runningFirst], has_more: true, next_cursor: 'running-next' }
      }
      if (params.status === 'running' && params.cursor === 'running-next') {
        return { items: [runningSecond], has_more: false, next_cursor: null }
      }
      throw new Error(`unexpected params: ${JSON.stringify(params)}`)
    })

    const items = await fetchTaskCenterCollectionRuns()

    expect(items.map((item) => item.record_id)).toEqual([
      'recent-terminal',
      'deep-queued',
      'deep-running-1',
      'deep-running-2',
    ])
    expect(listCollectionRuntimeRunsMock).toHaveBeenCalledWith({ limit: 100 })
    expect(listCollectionRuntimeRunsMock).toHaveBeenCalledWith({ status: 'queued', limit: 100 })
    expect(listCollectionRuntimeRunsMock).toHaveBeenCalledWith({ status: 'running', limit: 100 })
    expect(listCollectionRuntimeRunsMock).toHaveBeenCalledWith({
      status: 'running',
      cursor: 'running-next',
      limit: 100,
    })
  })

  it('首屏已经覆盖全部记录时不增加活动状态查询', async () => {
    const running = runtimeItem('running-on-first-page', 'running')
    listCollectionRuntimeRunsMock.mockResolvedValue({
      items: [running],
      has_more: false,
      next_cursor: null,
    })

    await expect(fetchTaskCenterCollectionRuns()).resolves.toEqual([running])
    expect(listCollectionRuntimeRunsMock).toHaveBeenCalledTimes(1)
    expect(listCollectionRuntimeRunsMock).toHaveBeenCalledWith({ limit: 100 })
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listImportBatches: vi.fn(),
  getImportBatchSummary: vi.fn(),
  getImportBatch: vi.fn(),
  createImportBatch: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import {
  ImportApiError,
  fetchImportBatchList,
  fetchImportBatchSummary,
} from '../src/features/import-batches/api'

describe('import batch feature api', () => {
  beforeEach(() => vi.clearAllMocks())

  it('delegates list queries to the generated Orval client', async () => {
    generated.listImportBatches.mockResolvedValue({
      items: [],
      has_more: false,
      next_cursor: null,
    })

    await expect(fetchImportBatchList({ status: 'running', limit: 20 })).resolves.toEqual({
      items: [],
      has_more: false,
      next_cursor: null,
    })
    expect(generated.listImportBatches).toHaveBeenCalledWith({ status: 'running', limit: 20 })
  })

  it('turns the shared HTTP error contract into a feature error', async () => {
    generated.getImportBatchSummary.mockResolvedValue({
      type: 'about:blank',
      title: '服务器内部错误',
      status: 500,
      detail: '请求处理失败，请使用 request_id 定位日志。',
      request_id: 'request-stage8c',
      errors: [{ code: 'internal_error', message: '请求失败' }],
    })

    const error = await fetchImportBatchSummary().catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(ImportApiError)
    expect(error).toMatchObject({ status: 500, requestId: 'request-stage8c' })
  })
})

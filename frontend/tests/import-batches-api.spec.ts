import { beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  listImportBatches: vi.fn(),
  getImportBatchSummary: vi.fn(),
  getImportBatch: vi.fn(),
  createImportBatch: vi.fn(),
  previewDataImportCampaignRevocation: vi.fn(),
  revokeDataImportCampaign: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import {
  ImportApiError,
  fetchImportBatchList,
  fetchImportBatchSummary,
  previewHistoricalCampaignRevocation,
  revokeHistoricalCampaign,
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

  it('uses the generated two-step revocation contract without inventing a parallel HTTP client', async () => {
    const preview = {
      campaign_id: 'campaign-1',
      eligible: true,
      already_revoked: false,
      impact: {
        affected_content_count: 8,
        hidden_content_count: 5,
        retained_shared_content_count: 3,
        unreversible_content_count: 0,
      },
    }
    const revoked = {
      campaign_id: 'campaign-1',
      already_revoked: false,
      impact: preview.impact,
      revoked_at: '2026-09-07T14:00:00+08:00',
    }
    generated.previewDataImportCampaignRevocation.mockResolvedValue(preview)
    generated.revokeDataImportCampaign.mockResolvedValue(revoked)

    await expect(previewHistoricalCampaignRevocation('campaign-1')).resolves.toEqual(preview)
    await expect(revokeHistoricalCampaign('campaign-1', { reason: '误选目录' })).resolves.toEqual(revoked)

    expect(generated.previewDataImportCampaignRevocation).toHaveBeenCalledWith('campaign-1')
    expect(generated.revokeDataImportCampaign).toHaveBeenCalledWith('campaign-1', { reason: '误选目录' })
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
    expect((error as ImportApiError).message).toContain('request: internal_error')
  })

  it('keeps Contract field and code while never echoing rejected values', async () => {
    generated.getImportBatchSummary.mockResolvedValue({
      type: 'about:blank',
      title: '请求参数错误',
      status: 422,
      detail: '请求未通过 Contract 校验。',
      request_id: 'request-contract',
      errors: [{ code: 'extra_forbidden', field: 'query.legacy', message: '不允许额外字段' }],
    })

    const error = await fetchImportBatchSummary().catch((reason: unknown) => reason)

    expect((error as ImportApiError).message).toContain('query.legacy: extra_forbidden')
    expect((error as ImportApiError).message).not.toContain('secret-value')
  })
})
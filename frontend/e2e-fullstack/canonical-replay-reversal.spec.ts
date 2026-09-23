import { expect, test, type APIRequestContext } from '@playwright/test'
import { readFile } from 'node:fs/promises'

import { ensureStage3FilterBrand } from './stage3-brand-support'

async function uploadCanonical(
  request: APIRequestContext,
  fixturePath: string,
  brandId: string,
): Promise<void> {
  const created = await request.post('/api/v1/import-batches', {
    multipart: {
      file: {
        name: 'canonical-replay-reversal.xlsx',
        mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        buffer: await readFile(fixturePath),
      },
      brand_ids: brandId,
    },
  })
  expect(created.status()).toBe(202)
  const { batch_id: batchId } = await created.json() as { batch_id: string }
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/import-batches/${batchId}`)
    return (await response.json() as { status: string }).status
  }, { timeout: 60_000 }).toBe('succeeded')
}

test('历史重筛通过真实 API 和 Worker 入库，并在运行中心 Modal 精确撤回', async ({
  page,
  request,
}) => {
  const fixture = process.env.AIMA_STAGE12_ORDINARY_FIXTURE
  expect(fixture, 'AIMA_STAGE12_ORDINARY_FIXTURE 必须指向普通导入 Fixture').toBeTruthy()
  const brand = await ensureStage3FilterBrand(request)
  await uploadCanonical(request, fixture!, brand.id)

  const createdResponse = await request.post('/api/v1/canonical-replays/all', {
    data: { idempotency_key: `fullstack-replay-${Date.now()}` },
  })
  expect(createdResponse.status()).toBe(202)
  const created = await createdResponse.json() as { request_id: string }
  await expect.poll(async () => {
    const response = await request.get('/api/v1/collection-runtime/runs', {
      params: { record_types: 'canonical_replay' },
    })
    if (response.status() !== 200) return `http-${response.status()}`
    const runtime = await response.json() as {
      items: Array<{
        canonical_replay_request_id: string | null
        status: string
      }>
    }
    return runtime.items.find(
      item => item.canonical_replay_request_id === created.request_id,
    )?.status ?? 'missing'
  }, { timeout: 60_000 }).toBe('succeeded')

  await page.goto('/collection-runtime')
  const row = page.getByRole('region', { name: '采集运行记录', exact: true })
    .locator('.table-row')
    .filter({ hasText: '历史数据重筛' })
    .first()
  await row.getByRole('button', { name: '查看详情', exact: true }).click()
  const modal = page.getByRole('dialog', { name: '重筛详情', exact: true })
  await expect(modal).toBeVisible()
  await modal.getByRole('button', { name: '撤回本次入库', exact: true }).click()

  const revokeResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname
        === `/api/v1/canonical-replays/all/${created.request_id}/revoke`,
  )
  const confirmation = page.getByRole('dialog', { name: '确认撤回历史重筛' })
  await confirmation.getByRole('button', { name: '确认撤回', exact: true }).click()
  expect((await revokeResponsePromise).status()).toBe(202)

  await expect.poll(async () => {
    const response = await request.get('/api/v1/collection-runtime/runs', {
      params: { record_types: 'canonical_replay' },
    })
    if (response.status() !== 200) return `http-${response.status()}`
    const runtime = await response.json() as {
      items: Array<{
        canonical_replay_request_id: string | null
        canonical_replay_stats: { lifecycle_status: string } | null
      }>
    }
    return runtime.items.find(
      item => item.canonical_replay_request_id === created.request_id,
    )?.canonical_replay_stats?.lifecycle_status ?? 'missing'
  }, { timeout: 60_000 }).toBe('reverted')
  await modal.getByRole('button', { name: '刷新详情', exact: true }).click()
  await expect(modal.getByText('撤回统计', { exact: true })).toBeVisible()
  await expect(modal.getByText('撤回本次入库', { exact: true })).toHaveCount(0)
})

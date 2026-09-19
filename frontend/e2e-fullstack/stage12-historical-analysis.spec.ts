import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { promisify } from 'node:util'
import { ensureStage3FilterBrand } from './stage3-brand-support'

const execFileAsync = promisify(execFile)

async function uploadBaseline(
  request: APIRequestContext,
  fixturePath: string,
  brandId: string,
): Promise<void> {
  const created = await request.post('/api/v1/import-batches', {
    multipart: {
      file: {
        name: 'stage12-current.xlsx',
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

async function assertCompletedRunRetained(
  page: Page,
  request: APIRequestContext,
  runId: string,
  sequenceNo: number,
): Promise<void> {
  const listedResponse = await request.get('/api/v1/analysis/content-runs')
  expect(listedResponse.status()).toBe(200)
  const listed = await listedResponse.json() as {
    items: Array<{ id: string; sequence_no: number; status: string }>
  }
  expect(listed.items).toContainEqual(expect.objectContaining({
    id: runId,
    sequence_no: sequenceNo,
    status: 'succeeded',
  }))

  // 声音广场只展示 queued/running/cancelling 活动任务；终态历史统一进入任务中心。
  await expect(page.getByRole('region', { name: 'AI 分析活动任务' })).toHaveCount(0, {
    timeout: 5_000,
  })
}

async function createAnalysisRun(
  page: Page,
  request: APIRequestContext,
): Promise<{ id: string; sequenceNo: number }> {
  await page.getByLabel(/选择 爱玛 Stage12 当前标题/).check()
  await page.getByRole('button', { name: 'AI 分析', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  await expect(dialog.getByText('预计分析 1 条内容', { exact: true })).toBeVisible()
  const createdResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/analysis/content-runs')
  await dialog.getByRole('button', { name: '确认开始分析' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(202)
  const created = await createdResponse.json() as { run_id: string }
  let sequenceNo = 0
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/analysis/content-runs/${created.run_id}`)
    if (response.status() !== 200) return `http-${response.status()}`
    const run = await response.json() as { sequence_no: number; status: string }
    sequenceNo = run.sequence_no
    return run.status
  }, { timeout: 60_000 }).toBe('succeeded')
  await assertCompletedRunRetained(page, request, created.run_id, sequenceNo)
  return { id: created.run_id, sequenceNo }
}

async function createAllDataAnalysisRun(
  page: Page,
  request: APIRequestContext,
): Promise<{ id: string; sequenceNo: number; targetCount: number }> {
  await page.getByRole('button', { name: 'AI 分析', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  const allPreviewPromise = page.waitForResponse((response) => {
    if (
      response.request().method() !== 'POST'
      || new URL(response.url()).pathname !== '/api/v1/analysis/content-runs/preview'
    ) return false
    const payload = response.request().postDataJSON() as { targets?: { scope?: string } }
    return payload.targets?.scope === 'all'
  })
  await dialog.getByRole('radio', { name: /全部系统内容/ }).check()
  const previewResponse = await allPreviewPromise
  expect(previewResponse.status()).toBe(200)
  const previewRequest = previewResponse.request().postDataJSON() as {
    targets: { scope: string; content_ids?: string[] }
  }
  expect(previewRequest).toEqual({ targets: { scope: 'all' } })
  const preview = await previewResponse.json() as { target_count: number }
  expect(preview.target_count).toBeGreaterThan(1)
  await expect(dialog.getByText(`预计分析 ${preview.target_count} 条内容`, { exact: true })).toBeVisible()

  const createdResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname === '/api/v1/analysis/content-runs')
  await dialog.getByRole('button', { name: '确认开始分析' }).click()
  const createdResponse = await createdResponsePromise
  expect(createdResponse.status()).toBe(202)
  const createPayload = createdResponse.request().postDataJSON() as {
    targets: { scope: string; content_ids?: string[] }
    expected_target_count: number
  }
  expect(createPayload.targets).toEqual({ scope: 'all' })
  expect(createPayload.expected_target_count).toBe(preview.target_count)
  const created = await createdResponse.json() as { run_id: string; target_count: number }
  expect(created.target_count).toBe(preview.target_count)

  let sequenceNo = 0
  let succeeded = 0
  let observedTargetCount = 0
  let observedScope = ''
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/analysis/content-runs/${created.run_id}`)
    if (response.status() !== 200) return `http-${response.status()}`
    const run = await response.json() as {
      sequence_no: number
      status: string
      scope: string
      target_count: number
      stats: { succeeded: number }
    }
    sequenceNo = run.sequence_no
    observedScope = run.scope
    observedTargetCount = run.target_count
    succeeded = run.stats.succeeded
    return run.status
  }, { timeout: 60_000 }).toBe('succeeded')
  expect(observedScope).toBe('all')
  expect(observedTargetCount).toBe(preview.target_count)
  expect(succeeded).toBe(preview.target_count)
  await assertCompletedRunRetained(page, request, created.run_id, sequenceNo)
  return { id: created.run_id, sequenceNo, targetCount: preview.target_count }
}

async function injectPrewriteChunkFailure(campaignId: string): Promise<void> {
  await execFileAsync(
    'uv',
    [
      'run',
      'python',
      'tests/fullstack/force_stage12_ready_chunk_failed.py',
      campaignId,
    ],
    {
      cwd: resolve(process.cwd(), '..'),
      env: { ...process.env, AIMA_FULLSTACK_SEED: '1' },
    },
  )
}


async function revokeHistoricalCampaign(
  page: Page,
  request: APIRequestContext,
  campaignId: string,
): Promise<void> {
  await page.goto(`/collection-runtime?data_import_campaign_id=${campaignId}`)
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await expect(dialog).toBeVisible({ timeout: 60_000 })

  const previewResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'GET'
      && new URL(response.url()).pathname
        === `/api/v1/data-import-campaigns/${campaignId}/revocation-preview`,
  )
  await dialog.getByRole('button', { name: '评估撤销', exact: true }).click()
  const previewResponse = await previewResponsePromise
  expect(previewResponse.status()).toBe(200)
  const preview = await previewResponse.json() as {
    eligible: boolean
    already_revoked: boolean
    impact: {
      affected_content_count: number
      hidden_content_count: number
      retained_shared_content_count: number
      unreversible_content_count: number
    }
  }
  expect(preview.eligible).toBe(true)
  expect(preview.already_revoked).toBe(false)
  expect(preview.impact.affected_content_count).toBeGreaterThan(0)
  expect(preview.impact.hidden_content_count).toBeGreaterThan(0)
  expect(preview.impact.retained_shared_content_count).toBeGreaterThan(0)
  expect(preview.impact.unreversible_content_count).toBe(0)
  await expect(dialog.getByText('撤销影响', { exact: true })).toBeVisible()
  await expect(
    dialog.locator('.revocation-facts span').filter({ hasText: '其它来源保留' }),
  ).toContainText(`其它来源保留${preview.impact.retained_shared_content_count}`)

  const revokeResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname === `/api/v1/data-import-campaigns/${campaignId}/revoke`,
  )
  await dialog.getByRole('button', { name: '撤销本次导入', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: '确认撤销这次导入', exact: true })
  await expect(confirmation).toContainText(String(preview.impact.affected_content_count))
  await confirmation.getByRole('button', { name: '确认撤销', exact: true }).click()
  const revokeResponse = await revokeResponsePromise
  expect(revokeResponse.status()).toBe(200)
  const revoked = await revokeResponse.json() as {
    already_revoked: boolean
    impact: {
      affected_content_count: number
      hidden_content_count: number
      retained_shared_content_count: number

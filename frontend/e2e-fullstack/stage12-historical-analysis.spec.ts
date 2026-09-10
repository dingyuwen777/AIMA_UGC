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

  // 声音广场只展示 queued/running/cancelling 活动 Run；终态历史统一进入任务中心。
  await page.locator('.count-options > summary').click()
  await page.locator('.count-options').getByRole('button', { name: '刷新数据', exact: true }).click()
  await page.locator('.count-options > summary').click()
  await expect(page.getByRole('region', { name: 'AI 打标活动任务' })).toHaveCount(0)
}

async function createAnalysisRun(
  page: Page,
  request: APIRequestContext,
): Promise<{ id: string; sequenceNo: number }> {
  await page.getByLabel(/选择 爱玛 Stage12 当前标题/).check()
  await page.getByRole('button', { name: 'AI 分析', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  await expect(dialog.getByText(/预计分析 1 条内容 · 1 个分片 · 每片最多 \d+ 条/)).toBeVisible()
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
  const preview = await previewResponse.json() as { target_count: number; shard_count: number; shard_size: number }
  expect(preview.target_count).toBeGreaterThan(1)
  await expect(
    dialog.getByText(
      `预计分析 ${preview.target_count} 条内容 · ${preview.shard_count} 个分片 · 每片最多 ${preview.shard_size} 条`,
    ),
  ).toBeVisible()

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
    }
  }
  expect(revoked.already_revoked).toBe(false)
  expect(revoked.impact).toMatchObject({
    affected_content_count: preview.impact.affected_content_count,
    hidden_content_count: preview.impact.hidden_content_count,
    retained_shared_content_count: preview.impact.retained_shared_content_count,
  })
  await expect(dialog.getByText(/撤销完成：影响 \d+ 条内容/)).toBeVisible()

  const repeated = await request.post(`/api/v1/data-import-campaigns/${campaignId}/revoke`, {
    data: { reason: 'full-stack idempotency check' },
  })
  expect(repeated.status()).toBe(200)
  expect((await repeated.json() as { already_revoked: boolean }).already_revoked).toBe(true)

  const hiddenResponse = await request.get(
    `/api/v1/contents?search=${encodeURIComponent('爱玛 Stage12 历史新建')}&limit=10`,
  )
  expect(hiddenResponse.status()).toBe(200)
  const hiddenItems = await hiddenResponse.json() as { items: Array<{ title: string | null }> }
  expect(hiddenItems.items.some((item) => item.title === '爱玛 Stage12 历史新建')).toBe(false)

  const retainedResponse = await request.get(
    `/api/v1/contents?search=${encodeURIComponent('爱玛 Stage12 当前标题')}&limit=10`,
  )
  expect(retainedResponse.status()).toBe(200)
  const retainedItems = await retainedResponse.json() as { items: Array<{ title: string | null }> }
  expect(retainedItems.items.some((item) => item.title === '爱玛 Stage12 当前标题')).toBe(true)

  await page.goto('/voice-plaza')
  await expect(page.getByText('爱玛 Stage12 当前标题', { exact: true })).toBeVisible()
  await expect(page.getByText('爱玛 Stage12 历史新建', { exact: true })).toHaveCount(0)
}

test('统一导入的服务器历史补空 Campaign 经真实 API/Worker/DB 入库，并保留 selected/all Analysis Run', async ({ page, request }) => {
  const ordinaryFixture = process.env.AIMA_STAGE12_ORDINARY_FIXTURE
  expect(ordinaryFixture, 'AIMA_STAGE12_ORDINARY_FIXTURE 必须指向普通导入 Fixture').toBeTruthy()
  const brand = await ensureStage3FilterBrand(request)
  await uploadBaseline(request, ordinaryFixture!, brand.id)

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const migration = page.getByRole('dialog', { name: '导入数据' })
  await migration.getByRole('button', { name: '服务器目录', exact: true }).click()
  await migration.getByRole('radio', { name: /历史补空/ }).check()
  await migration.getByLabel('选择 history.xlsx').check()
  await expect(migration).toContainText('当前按创建时全部已启用品牌冻结过滤范围')
  const campaignResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/api/v1/data-import-campaigns/server'
      && response.request().method() === 'POST'
  })
  await migration.getByRole('button', { name: '创建并预检' }).click()
  const campaignResponse = await campaignResponsePromise
  const { campaign_id: campaignId } = await campaignResponse.json() as { campaign_id: string }
  await expect(migration.locator('.campaign-status')).toHaveText('预检完成', { timeout: 60_000 })
  await injectPrewriteChunkFailure(campaignId)
  await migration.getByRole('button', { name: '开始导入' }).click()
  await expect(migration.locator('.campaign-status')).toHaveText('部分导入失败', { timeout: 60_000 })
  await migration.getByRole('button', { name: '重试失败项' }).click()
  await expect(migration.locator('.campaign-status')).toHaveText('导入完成', { timeout: 60_000 })
  await expect(migration.getByText('冲突行数 1', { exact: true })).toBeVisible()
  await expect(migration.getByRole('region', { name: '冲突字段明细' })).toContainText('条冲突字段')

  const runtimeResponse = await request.get('/api/v1/collection-runtime/runs', {
    params: { record_types: 'data_import_campaign' },
  })
  expect(runtimeResponse.status()).toBe(200)
  const runtime = await runtimeResponse.json() as {
    items: Array<{
      record_id: string
      record_type: string
      job_id: string | null
      status: string
      progress: number
    }>
  }
  expect(runtime.items).toContainEqual(expect.objectContaining({
    record_id: campaignId,
    record_type: 'data_import_campaign',
    job_id: null,
    status: 'succeeded',
    progress: 100,
  }))

  const eligibilityResponse = await request.get(
    `/api/v1/data-import-campaigns/${campaignId}/supplement-eligibility`,
  )
  expect(eligibilityResponse.status()).toBe(200)
  const eligibility = await eligibilityResponse.json() as {
    targets: Array<{ platform: string; target_count: number }>
  }
  expect(eligibility.targets).toContainEqual(expect.objectContaining({
    platform: 'xiaohongshu',
    target_count: expect.any(Number),
  }))
  expect(eligibility.targets.find((item) => item.platform === 'xiaohongshu')!.target_count)
    .toBeGreaterThan(0)

  await migration.getByRole('button', { name: '查看导入内容' }).click()

  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && Boolean(url.searchParams.get('source_identifier')),
  )
  await expect(page.getByText('爱玛 Stage12 当前标题', { exact: true })).toBeVisible()
  await expect(page.getByText('爱玛 Stage12 历史新建', { exact: true })).toBeVisible()
  await expect(page.getByText('爱玛 Stage12 历史冲突标题', { exact: true })).toHaveCount(0)
  await page.locator('.content-row').filter({ hasText: '爱玛 Stage12 当前标题' })
    .getByRole('button', { name: '查看详情', exact: true }).click()
  const contentDetail = page.getByRole('dialog', { name: '内容详情' })
  await expect(contentDetail.getByText('历史正文补空成功', { exact: true })).toBeVisible()
  await contentDetail.getByRole('button', { name: '关闭', exact: true }).click()

  const firstRun = await createAnalysisRun(page, request)
  const contentList = page.getByRole('region', { name: '声音广场内容列表' })
  await expect(contentList.getByText('正面', { exact: true })).toBeVisible()
  const secondRun = await createAnalysisRun(page, request)
  await expect(contentList.getByText('负面', { exact: true })).toBeVisible()
  expect(secondRun.id).not.toBe(firstRun.id)
  expect(secondRun.sequenceNo).toBeGreaterThan(firstRun.sequenceNo)

  const allRun = await createAllDataAnalysisRun(page, request)
  expect(allRun.id).not.toBe(firstRun.id)
  expect(allRun.id).not.toBe(secondRun.id)
  expect(allRun.sequenceNo).toBeGreaterThan(secondRun.sequenceNo)
  expect(allRun.targetCount).toBeGreaterThan(1)

  await revokeHistoricalCampaign(page, request, campaignId)
})

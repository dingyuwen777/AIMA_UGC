import { expect, test } from '@playwright/test'

const batchId = '12345678-1234-5678-1234-567812345678'
const secondBatchId = '13345678-1234-5678-1234-567812345678'
const importJobId = '22345678-1234-5678-1234-567812345678'
const runId = '42345678-1234-5678-1234-567812345678'
const collectionJobId = '52345678-1234-5678-1234-567812345678'
const providerConfigId = '62345678-1234-5678-1234-567812345678'
const brandPackId = '82345678-1234-5678-1234-567812345678'
const modelPackId = '92345678-1234-5678-1234-567812345678'

const keywordPacks = {
  items: [
    { id: brandPackId, name: '爱玛品牌词包', description: '', enabled: true, version: 2, keyword_count: 8 },
    { id: modelPackId, name: '产品车型词包', description: '', enabled: true, version: 3, keyword_count: 12 },
  ],
  total: 2,
  offset: 0,
  limit: 100,
}

const importDetail = {
  id: batchId, input_artifact_id: '32345678-1234-5678-1234-567812345678', source_filename: '爱玛8月舆情.xlsx',
  status: 'running', stage: 'filtering',
  stats: { rows_seen: 1284, rows_matched: 1152, rows_filtered_out: 132, duplicates_removed: 0, rows_ingested: 0, rows_rejected: 0 },
  error_summary: null, created_at: '2026-08-21T01:30:42Z', started_at: '2026-08-21T01:30:42Z', finished_at: null,
  job: { id: importJobId, job_type: 'ingestion.import-excel.v1', status: 'running', attempt: 2, max_attempts: 10, progress: 67, error_code: null, result: null, created_at: '2026-08-21T01:30:42Z', started_at: '2026-08-21T01:30:42Z', finished_at: null },
}
const usableImport = {
  ...importDetail,
  status: 'succeeded', stage: 'succeeded', finished_at: '2026-08-21T01:32:00Z',
  stats: { ...importDetail.stats, rows_ingested: 1 },
  job: { ...importDetail.job, status: 'succeeded', progress: 100, finished_at: '2026-08-21T01:32:00Z' },
}
const secondUsableImport = {
  ...usableImport,
  id: secondBatchId,
  source_filename: '爱玛抖音批次.xlsx',
  input_artifact_id: '33345678-1234-5678-1234-567812345678',
  job: { ...usableImport.job, id: '23345678-1234-5678-1234-567812345678' },
}
const failedImport = {
  ...importDetail,
  status: 'failed', stage: 'failed', error_summary: 'invalid_import', finished_at: '2026-08-21T01:31:00Z',
  job: { ...importDetail.job, status: 'failed', progress: 40, error_code: 'invalid_import', finished_at: '2026-08-21T01:31:00Z' },
}
const runtimeItem = {
  record_id: batchId, record_type: 'excel_import', display_name: '爱玛8月舆情.xlsx', source_filename: '爱玛8月舆情.xlsx', import_batch_id: batchId, collection_run_id: null, job_id: importJobId,
  status: 'running', stage: 'filtering', progress: 67, import_stats: importDetail.stats, collection_stats: null, platforms: [], keywords: [], created_at: '2026-08-21T01:30:42Z', started_at: '2026-08-21T01:30:42Z', finished_at: null, error_code: null, error_summary: null,
}
const runDetail = {
  run_id: runId, job_id: collectionJobId, mode: 'discovery', import_batch_id: null, keywords: ['爱玛', 'Q7'], platforms: ['xiaohongshu'], status: 'queued', stage: 'queued', progress: 0, attempt: 0, max_attempts: 2,
  stats: { requested_count: 0, succeeded_count: 0, failed_count: 0, content_count: 0, comment_count: 0, filtered_count: 0 },
  scopes: [{ id: '72345678-1234-5678-1234-567812345678', platform: 'xiaohongshu', source_type: 'keyword_search', operation_group: 'content_discovery', status: 'queued', progress: 0, stats: { requested_count: 0, succeeded_count: 0, failed_count: 0, content_count: 0, comment_count: 0, filtered_count: 0 } }],
  error_code: null, error_summary: null, created_at: '2026-08-21T02:00:00Z', started_at: null, finished_at: null,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/collection-runtime/summary') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ processing_count: 12, completed_today_count: 86, contents_ingested_today: 3284, as_of: '2026-08-21T02:00:00Z' }) })
    if (url.pathname === '/api/v1/collection-runtime/runs') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [runtimeItem], next_cursor: null, has_more: false }) })
    if (url.pathname === '/api/v1/collection-capabilities') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ provider_configs: [{ id: providerConfigId, provider: 'tikhub', display_name: 'TikHub 主配置' }], capabilities: [{ provider: 'tikhub', platform: 'xiaohongshu', operations: ['keyword_search', 'content_detail', 'comments', 'sub_comments'] }, { provider: 'tikhub', platform: 'douyin', operations: ['keyword_search', 'content_detail', 'comments', 'sub_comments'] }] }) })
    if (url.pathname === '/api/v1/keyword-packs' && request.method() === 'GET') return route.fulfill({ contentType: 'application/json', body: JSON.stringify(keywordPacks) })
    if (url.pathname === '/api/v1/collection-runs' && request.method() === 'POST') return route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ run_id: runId, job_id: collectionJobId, mode: 'discovery', status: 'queued' }) })
    if (url.pathname === `/api/v1/collection-runs/${runId}`) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(runDetail) })
    if (url.pathname === '/api/v1/import-batches' && request.method() === 'POST') return route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ batch_id: batchId, job_id: importJobId, status: 'queued' }) })
    if (url.pathname === '/api/v1/import-batches') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [usableImport, secondUsableImport], next_cursor: null, has_more: false }) })
    if (url.pathname === `/api/v1/import-batches/${batchId}/supplement-eligibility`) return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ batch_id: batchId, targets: [{ platform: 'xiaohongshu', target_count: 1 }] }) })
    if (url.pathname === `/api/v1/import-batches/${secondBatchId}/supplement-eligibility`) return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ batch_id: secondBatchId, targets: [{ platform: 'douyin', target_count: 1 }] }) })
    if (url.pathname === `/api/v1/import-batches/${batchId}`) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(importDetail) })
    if (url.pathname === `/api/v1/import-batches/${secondBatchId}`) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(secondUsableImport) })
    await route.fulfill({ status: 404, body: 'not mocked' })
  })
})

test('centralizes runtime facts, opens Batch detail, and creates an Import Job with selected packs', async ({ page }) => {
  await page.goto('/collection-runtime')
  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await expect(page.getByText('3,284')).toBeVisible()
  await page.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByRole('dialog', { name: '批次详情' })).toBeVisible()
  await expect(page.getByText('2 / 10')).toBeVisible()
  await page.getByRole('button', { name: '关闭详情' }).click()
  await page.getByRole('button', { name: /导入 Excel/ }).click()
  const dialog = page.getByRole('dialog', { name: '导入 Excel' })
  await dialog.locator('input[type="file"]').setInputFiles({ name: 'stage8e.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('stage8e') })
  await dialog.getByLabel(/爱玛品牌词包/).check()
  await dialog.getByLabel(/产品车型词包/).check()
  const requestPromise = page.waitForRequest((request) => new URL(request.url()).pathname === '/api/v1/import-batches' && request.method() === 'POST')
  await dialog.getByRole('button', { name: '开始导入' }).click()
  const multipart = (await requestPromise).postData() ?? ''
  expect(multipart).toContain(brandPackId)
  expect(multipart).toContain(modelPackId)
  await expect(page.getByText('Import Job 已创建，文件将在后台继续处理。')).toBeVisible()
})

test('creates a one-time TikHub discovery Run from multiple Keyword Packs', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: /新建 TikHub 补采/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建 TikHub 辅助补采' })
  await drawer.getByLabel(/爱玛品牌词包/).check()
  await drawer.getByLabel(/产品车型词包/).check()
  await drawer.getByRole('button', { name: /小红书/ }).click()
  const requestPromise = page.waitForRequest((request) => new URL(request.url()).pathname === '/api/v1/collection-runs' && request.method() === 'POST')
  await drawer.getByRole('button', { name: '创建补采任务' }).click()
  expect((await requestPromise).postDataJSON()).toMatchObject({
    mode: 'discovery',
    keyword_pack_ids: [brandPackId, modelPackId],
    platforms: [{ platform: 'xiaohongshu', provider_config_id: providerConfigId }],
  })
  await expect(page.getByText('TikHub Collection Run / Job 已创建，将由 Worker 在后台执行。')).toBeVisible()
})

test('creates a TikHub supplement Run only for a platform that exists in the Batch', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: /新建 TikHub 补采/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建 TikHub 辅助补采' })
  await drawer.getByRole('button', { name: '基于已有批次补采' }).click()
  await drawer.getByLabel('Excel Import Batch').selectOption(batchId)
  await expect(drawer.getByRole('button', { name: /小红书/ })).toBeVisible()
  await expect(drawer.getByRole('button', { name: /抖音/ })).toHaveCount(0)
  await drawer.getByRole('button', { name: /小红书/ }).click()
  const requestPromise = page.waitForRequest((request) => new URL(request.url()).pathname === '/api/v1/collection-runs' && request.method() === 'POST')
  await drawer.getByRole('button', { name: '创建补采任务' }).click()
  expect((await requestPromise).postDataJSON()).toMatchObject({
    mode: 'batch_supplement',
    import_batch_id: batchId,
    keyword_pack_ids: [],
    platforms: [{ platform: 'xiaohongshu', provider_config_id: providerConfigId }],
  })
})

test('re-probes Batch platform eligibility when switching A to B and back to A', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: /新建 TikHub 补采/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建 TikHub 辅助补采' })
  await drawer.getByRole('button', { name: '基于已有批次补采' }).click()

  await drawer.getByLabel('Excel Import Batch').selectOption(batchId)
  await expect(drawer.getByRole('button', { name: /小红书/ })).toBeVisible()
  await expect(drawer.getByRole('button', { name: /抖音/ })).toHaveCount(0)

  await drawer.getByLabel('Excel Import Batch').selectOption(secondBatchId)
  await expect(drawer.getByRole('button', { name: /抖音/ })).toBeVisible()
  await expect(drawer.getByRole('button', { name: /小红书/ })).toHaveCount(0)

  await drawer.getByLabel('Excel Import Batch').selectOption(batchId)
  await expect(drawer.getByRole('button', { name: /小红书/ })).toBeVisible()
  await expect(drawer.getByRole('button', { name: /抖音/ })).toHaveCount(0)
})

test('explains failed Import terminal state without inventing pending stages', async ({ page }) => {
  await page.route(`**/api/v1/import-batches/${batchId}`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(failedImport) }))
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '批次详情' })
  await detail.getByRole('button', { name: '处理阶段' }).click()
  await expect(detail.getByText('任务已失败。')).toBeVisible()
  await expect(detail.getByText('失败前最后完成阶段', { exact: false })).toBeVisible()
  await expect(detail.locator('.stage-row')).toHaveCount(0)
})

test('shows the stable unified Error Contract request_id', async ({ page }) => {
  await page.unroute('**/api/v1/**')
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/collection-runtime/summary') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ processing_count: 0, completed_today_count: 0, contents_ingested_today: 0, as_of: '2026-08-21T02:00:00Z' }) })
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ title: '分页服务暂不可用', status: 503, detail: '分页服务配置不可用，请使用 request_id 联系管理员。', request_id: 'req_stage8e_error', errors: [] }) })
  })
  await page.goto('/collection-runtime')
  await expect(page.getByRole('alert')).toContainText('req_stage8e_error')
})

import { expect, test } from '@playwright/test'

const batchId = '12345678-1234-5678-1234-567812345678'
const importJobId = '22345678-1234-5678-1234-567812345678'
const runId = '42345678-1234-5678-1234-567812345678'
const collectionJobId = '52345678-1234-5678-1234-567812345678'
const providerConfigId = '62345678-1234-5678-1234-567812345678'

const importDetail = {
  id: batchId,
  input_artifact_id: '32345678-1234-5678-1234-567812345678',
  source_filename: '爱玛8月舆情.xlsx',
  status: 'running',
  stage: 'filtering',
  stats: {
    rows_seen: 1284,
    rows_matched: 1152,
    rows_filtered_out: 132,
    duplicates_removed: 0,
    rows_ingested: 0,
    rows_rejected: 0,
  },
  error_summary: null,
  created_at: '2026-08-21T01:30:42Z',
  started_at: '2026-08-21T01:30:42Z',
  finished_at: null,
  job: {
    id: importJobId,
    job_type: 'ingestion.import-excel.v1',
    status: 'running',
    attempt: 2,
    max_attempts: 10,
    progress: 67,
    error_code: null,
    result: null,
    created_at: '2026-08-21T01:30:42Z',
    started_at: '2026-08-21T01:30:42Z',
    finished_at: null,
  },
}

const runtimeItem = {
  record_id: batchId,
  record_type: 'excel_import',
  display_name: '爱玛8月舆情.xlsx',
  source_filename: '爱玛8月舆情.xlsx',
  import_batch_id: batchId,
  collection_run_id: null,
  job_id: importJobId,
  status: 'running',
  stage: 'filtering',
  progress: 67,
  import_stats: importDetail.stats,
  collection_stats: null,
  platforms: [],
  keywords: [],
  created_at: '2026-08-21T01:30:42Z',
  started_at: '2026-08-21T01:30:42Z',
  finished_at: null,
  error_code: null,
  error_summary: null,
}

const runDetail = {
  run_id: runId,
  job_id: collectionJobId,
  mode: 'discovery',
  import_batch_id: null,
  keywords: ['爱玛', 'Q7'],
  platforms: ['xhs'],
  status: 'queued',
  stage: 'queued',
  progress: 0,
  attempt: 0,
  max_attempts: 2,
  stats: {
    requested_count: 0,
    succeeded_count: 0,
    failed_count: 0,
    content_count: 0,
    comment_count: 0,
    filtered_count: 0,
  },
  scopes: [
    {
      id: '72345678-1234-5678-1234-567812345678',
      platform: 'xhs',
      source_type: 'keyword_search',
      operation_group: 'content_discovery',
      status: 'queued',
      progress: 0,
      stats: {
        requested_count: 0,
        succeeded_count: 0,
        failed_count: 0,
        content_count: 0,
        comment_count: 0,
        filtered_count: 0,
      },
    },
  ],
  error_code: null,
  error_summary: null,
  created_at: '2026-08-21T02:00:00Z',
  started_at: null,
  finished_at: null,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/collection-runtime/summary') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 12,
          completed_today_count: 86,
          contents_ingested_today: 3284,
          as_of: '2026-08-21T02:00:00Z',
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-runtime/runs') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [runtimeItem], next_cursor: null, has_more: false }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-capabilities') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          provider_configs: [
            { id: providerConfigId, provider: 'tikhub', display_name: 'TikHub 主配置' },
          ],
          capabilities: [
            {
              provider: 'tikhub',
              platform: 'xhs',
              operations: ['keyword_search', 'content_detail', 'comments', 'sub_comments'],
            },
          ],
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-runs' && request.method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: runId,
          job_id: collectionJobId,
          mode: 'discovery',
          status: 'queued',
        }),
      })
      return
    }
    if (url.pathname === `/api/v1/collection-runs/${runId}`) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(runDetail) })
      return
    }
    if (url.pathname === '/api/v1/import-batches' && request.method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ batch_id: batchId, job_id: importJobId, status: 'queued' }),
      })
      return
    }
    if (url.pathname === '/api/v1/import-batches') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [importDetail], next_cursor: null, has_more: false }),
      })
      return
    }
    if (url.pathname === `/api/v1/import-batches/${batchId}`) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(importDetail) })
      return
    }
    await route.fulfill({ status: 404, body: 'not mocked' })
  })
})

test('centralizes runtime facts, opens Batch detail, and creates an Import Job', async ({
  page,
}) => {
  await page.goto('/collection-runtime')

  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await expect(page.getByText('今日入库内容')).toBeVisible()
  await expect(page.getByText('3,284')).toBeVisible()
  await expect(page.getByText('全部运行')).toBeVisible()
  await expect(page.getByText('爱玛8月舆情.xlsx').first()).toBeVisible()
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({
      path: 'test-results/stage8e-centralized-runtime.png',
      fullPage: true,
    })
  }

  await page.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByRole('dialog', { name: '批次详情' })).toBeVisible()
  await expect(page.getByText('2 / 10')).toBeVisible()
  await page.getByRole('button', { name: '关闭详情' }).click()

  await page.getByRole('button', { name: /导入 Excel/ }).click()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'stage8e.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('stage8e'),
  })
  await page.getByRole('button', { name: '开始导入' }).click()
  await expect(page.getByText('Import Job 已创建，文件将在后台继续处理。')).toBeVisible()
})

test('creates a one-time TikHub discovery Run from the drawer', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: /新建 TikHub 补采/ }).click()

  const drawer = page.getByRole('dialog', { name: '新建 TikHub 辅助补采' })
  await expect(drawer).toBeVisible()
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({
      path: 'test-results/stage8e-tikhub-create-drawer.png',
      fullPage: true,
    })
  }
  await drawer.getByPlaceholder('输入关键词后回车').fill('爱玛')
  await drawer.getByPlaceholder('输入关键词后回车').press('Enter')
  await drawer.getByRole('button', { name: /小红书/ }).click()
  await drawer.getByRole('button', { name: '创建补采任务' }).click()

  await expect(page.getByText('TikHub Collection Run / Job 已创建，将由 Worker 在后台执行。')).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'TikHub 运行详情' })).toBeVisible()
  await expect(page.getByText('爱玛 / Q7')).toBeVisible()
})

test('creates a TikHub supplement Run from an existing Import Batch', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: /新建 TikHub 补采/ }).click()

  const drawer = page.getByRole('dialog', { name: '新建 TikHub 辅助补采' })
  await drawer.getByRole('button', { name: '基于已有批次补采' }).click()
  await drawer.getByLabel('Excel Import Batch').selectOption(batchId)
  await drawer.getByRole('button', { name: /小红书/ }).click()
  const requestPromise = page.waitForRequest(
    (request) =>
      new URL(request.url()).pathname === '/api/v1/collection-runs' &&
      request.method() === 'POST',
  )
  await drawer.getByRole('button', { name: '创建补采任务' }).click()

  const request = await requestPromise
  expect(request.postDataJSON()).toEqual({
    mode: 'batch_supplement',
    keywords: [],
    import_batch_id: batchId,
    platforms: [{ platform: 'xhs', provider_config_id: providerConfigId }],
    include_comments: true,
    include_sub_comments: false,
  })
})

test('shows the stable unified Error Contract request_id', async ({ page }) => {
  await page.unroute('**/api/v1/**')
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/collection-runtime/summary') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 0,
          completed_today_count: 0,
          contents_ingested_today: 0,
          as_of: '2026-08-21T02:00:00Z',
        }),
      })
      return
    }
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'https://aima.example/problems/collection_cursor_unavailable',
        title: '分页服务暂不可用',
        status: 503,
        detail: '分页服务配置不可用，请使用 request_id 联系管理员。',
        request_id: 'req_stage8e_error',
        errors: [
          {
            field: null,
            code: 'collection_cursor_unavailable',
            message: '分页服务配置不可用，请使用 request_id 联系管理员。',
          },
        ],
      }),
    })
  })

  await page.goto('/collection-runtime')
  await expect(page.getByRole('alert')).toContainText('req_stage8e_error')
  await expect(page.getByText('暂无采集运行')).toBeVisible()
})

import { expect, test } from '@playwright/test'

const batchId = '12345678-1234-5678-1234-567812345678'
const jobId = '22345678-1234-5678-1234-567812345678'

const item = {
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
    id: jobId,
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

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/import-batches**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ batch_id: batchId, job_id: jobId, status: 'queued' }),
      })
      return
    }
    if (url.pathname === '/api/v1/import-batches/summary') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 12,
          completed_today_count: 86,
          rows_ingested_today: 3284,
          as_of: '2026-08-21T02:00:00Z',
        }),
      })
      return
    }
    if (url.pathname !== '/api/v1/import-batches') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(item) })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [item], next_cursor: null, has_more: false }),
    })
  })
})

test('shows real Batch facts, opens detail, and creates an Import Job', async ({ page }) => {
  await page.goto('/collection-runtime')

  await expect(page.getByRole('heading', { name: '采集运行中心' })).toBeVisible()
  await expect(page.getByText('今日导入内容')).toBeVisible()
  await expect(page.getByText('3,284')).toBeVisible()
  await expect(page.getByText('爱玛8月舆情.xlsx').first()).toBeVisible()
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({
      path: 'test-results/stage8c-collection-runtime.png',
      fullPage: true,
    })
  }

  await page.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByRole('dialog', { name: '批次详情' })).toBeVisible()
  await expect(page.getByText('2 / 10')).toBeVisible()
  await expect(page.getByText('67%').first()).toBeVisible()
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({
      path: 'test-results/stage8c-import-batch-detail.png',
      fullPage: true,
    })
  }
  await page.getByRole('button', { name: '关闭详情' }).click()

  await page.getByRole('button', { name: /导入 Excel/ }).click()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'stage8c.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('stage8c'),
  })
  await page.getByRole('button', { name: '开始导入' }).click()
  await expect(page.getByText('Import Job 已创建，文件将在后台继续处理。')).toBeVisible()
})

test('shows loading and empty states without inventing records', async ({ page }) => {
  await page.unroute('**/api/v1/import-batches**')
  await page.route('**/api/v1/import-batches**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/import-batches/summary') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 0,
          completed_today_count: 0,
          rows_ingested_today: 0,
          as_of: '2026-08-21T02:00:00Z',
        }),
      })
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 800))
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/collection-runtime')
  await expect(page.getByText('正在加载批次…')).toBeVisible()
  await expect(page.getByText('暂无导入批次')).toBeVisible()
})

test('shows the stable Error Contract request_id', async ({ page }) => {
  await page.unroute('**/api/v1/import-batches**')
  await page.route('**/api/v1/import-batches**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/import-batches/summary') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 0,
          completed_today_count: 0,
          rows_ingested_today: 0,
          as_of: '2026-08-21T02:00:00Z',
        }),
      })
      return
    }
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'https://aima.example/problems/import_cursor_unavailable',
        title: '分页服务暂不可用',
        status: 503,
        detail: '分页服务配置不可用，请使用 request_id 联系管理员。',
        request_id: 'req_stage8c_error',
        errors: [
          {
            field: null,
            code: 'import_cursor_unavailable',
            message: '分页服务配置不可用，请使用 request_id 联系管理员。',
          },
        ],
      }),
    })
  })

  await page.goto('/collection-runtime')

  await expect(page.getByRole('alert')).toContainText('req_stage8c_error')
  await expect(page.getByText('暂无导入批次')).toBeVisible()
})

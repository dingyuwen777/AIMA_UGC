import { expect, test, type Page } from './fixture'

const keywordPackId = '82345678-1234-5678-1234-567812345678'
const campaignId = '12345678-1234-4678-9234-567812345678'
const itemId = '22345678-1234-4678-9234-567812345678'

const keywordPacks = {
  items: [{
    id: keywordPackId,
    name: '爱玛品牌词包',
    description: '',
    enabled: true,
    version: 2,
    keyword_count: 8,
  }],
  total: 1,
  offset: 0,
  limit: 100,
}

const campaign = {
  id: campaignId,
  status: 'uploading',
  source_kind: 'local_upload',
  ingestion_policy: 'standard_observation',
  declared_file_count: 1,
  root_relative_path: '',
  recursive: true,
  discovered_file_count: 0,
  ready_item_count: 0,
  total_rows: 0,
  progress: {
    preflight_completed_file_count: 0,
    preflight_percent: 0,
    migration_completed_row_count: 0,
    migration_percent: 0,
  },
  stats: {},
  can_start: false,
  error_summary: null,
  created_at: '2026-08-27T15:00:00+08:00',
  started_at: null,
  finished_at: null,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/collection-runtime/summary') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 0,
          completed_today_count: 0,
          contents_ingested_today: 0,
          as_of: '2026-08-27T15:00:00+08:00',
        }),
      })
    }
    if (url.pathname === '/api/v1/collection-runtime/runs') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
      })
    }
    if (url.pathname === '/api/v1/keyword-packs' && request.method() === 'GET') {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(keywordPacks) })
    }
    if (url.pathname === '/api/v1/data-import-campaigns' && request.method() === 'GET') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [] }),
      })
    }
    if (url.pathname === '/api/v1/data-import-campaigns/local' && request.method() === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          campaign_id: campaignId,
          upload_items: [{ item_id: itemId, relative_path: 'aima.xlsx' }],
        }),
      })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}`) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(campaign) })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/items`) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total_count: 0, has_more: false }),
      })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/conflicts`) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total_count: 0, has_more: false }),
      })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/items/${itemId}/content`) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          campaign_id: campaignId,
          item_id: itemId,
          artifact_id: '32345678-1234-4678-9234-567812345678',
          sha256: 'a'.repeat(64),
          byte_size: 4,
        }),
      })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/finalize`) {
      return route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ ...campaign, status: 'snapshotting', discovered_file_count: 1 }),
      })
    }
    await route.fallback()
  })
})

async function openImportDialog(page: Page) {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  return page.getByRole('dialog', { name: '导入数据' })
}

test('requires a source file but not Provider search or a single-vehicle filter', async ({ page }) => {
  const dialog = await openImportDialog(page)
  const submitButton = dialog.locator('.create-button')

  await expect(submitButton).toBeDisabled()
  await expect(submitButton).toHaveCSS('cursor', 'not-allowed')

  await dialog.locator('input[type="file"]').first().setInputFiles({
    name: 'aima.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('aima'),
  })
  await expect(dialog.getByLabel('搜索条件')).toHaveValue('不适用于 Excel 文件导入')
  await expect(dialog).toContainText('创建任务时冻结品牌与旗下车型目录快照；Excel 导入不会发起 Provider 搜索。')
  await expect(submitButton).toBeEnabled()
  await expect(submitButton).toHaveCSS('cursor', 'pointer')
})

test('creates a local Campaign when randomUUID is unavailable', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(globalThis.crypto, 'randomUUID', {
      configurable: true,
      value: undefined,
    })
  })
  let createRequestBody: Record<string, unknown> | undefined
  await page.route('**/api/v1/data-import-campaigns/local', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    createRequestBody = route.request().postDataJSON() as Record<string, unknown>
    await route.fallback()
  })

  const dialog = await openImportDialog(page)
  await dialog.locator('input[type="file"]').first().setInputFiles({
    name: 'aima.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('aima'),
  })
  await dialog.locator('.create-button').click()

  await expect(dialog.getByText('文件上传完成，服务器正在准备并预检数据。')).toBeVisible()
  expect(createRequestBody?.brand_ids).toEqual([])
  expect(createRequestBody).not.toHaveProperty('keyword_pack_ids')
  expect(createRequestBody).not.toHaveProperty('vehicle_model_ids')
  expect(createRequestBody?.client_idempotency_key).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  )
})

test('stages local files through Campaign upload and restores a visible error', async ({ page }) => {
  let releaseCreate!: () => void
  const createGate = new Promise<void>((resolve) => {
    releaseCreate = resolve
  })
  await page.route('**/api/v1/data-import-campaigns/local', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    await createGate
    return route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        title: '上传服务暂不可用',
        status: 503,
        detail: '数据导入 Campaign 创建失败，请稍后重试。',
        request_id: 'req_data_import_busy_state',
        errors: [],
      }),
    })
  })

  const dialog = await openImportDialog(page)
  await dialog.locator('input[type="file"]').first().setInputFiles({
    name: 'aima.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('aima'),
  })
  const submitButton = dialog.locator('.create-button')

  await submitButton.click()
  await expect(submitButton).toBeDisabled()
  await expect(submitButton).toHaveAttribute('aria-busy', 'true')
  await expect(submitButton).toHaveText('正在创建…')

  releaseCreate()

  await expect(submitButton).toBeEnabled()
  await expect(submitButton).toHaveAttribute('aria-busy', 'false')
  await expect(submitButton).toHaveText('创建并预检')
  await expect(dialog.getByRole('alert')).toContainText('数据导入 Campaign 创建失败')
  await expect(dialog.getByRole('alert')).toContainText('req_data_import_busy_state')
})

test('allows an interrupted local upload Campaign to be cancelled', async ({ page }) => {
  let cancelRequested = false
  await page.route('**/api/v1/data-import-campaigns', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [campaign] }),
    })
  })
  await page.route(`**/api/v1/data-import-campaigns/${campaignId}/cancel`, async (route) => {
    cancelRequested = true
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...campaign,
        status: 'cancelled',
        finished_at: '2026-08-27T15:01:00+08:00',
      }),
    })
  })

  const dialog = await openImportDialog(page)
  await dialog.getByRole('button', { name: '打开导入任务 本地文件导入' }).click()
  const cancelButton = dialog.getByRole('button', { name: '取消任务', exact: true })
  await expect(cancelButton).toBeEnabled()
  await cancelButton.click()

  expect(cancelRequested).toBe(true)
  await expect(dialog.locator('.campaign-status')).toHaveText('已取消')
  await dialog.getByText('技术详情', { exact: true }).click()
  await expect(dialog.getByText('cancelled', { exact: true })).toBeVisible()
})

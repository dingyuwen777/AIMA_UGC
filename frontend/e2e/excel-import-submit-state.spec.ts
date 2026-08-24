import { expect, test, type Page } from '@playwright/test'

const keywordPackId = '82345678-1234-5678-1234-567812345678'

const keywordPacks = {
  items: [
    {
      id: keywordPackId,
      name: '爱玛品牌词包',
      description: '',
      enabled: true,
      version: 2,
      keyword_count: 8,
    },
  ],
  total: 1,
  offset: 0,
  limit: 100,
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
          as_of: '2026-08-24T05:00:00Z',
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
    if (url.pathname === '/api/v1/import-batches' && request.method() === 'POST') {
      return route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          batch_id: '12345678-1234-5678-1234-567812345678',
          job_id: '22345678-1234-5678-1234-567812345678',
          status: 'queued',
        }),
      })
    }
    await route.fulfill({ status: 404, body: 'not mocked' })
  })
})

async function openImportDialog(page: Page) {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: /导入 Excel/ }).click()
  return page.getByRole('dialog', { name: '导入 Excel' })
}

test('does not present an incomplete import form as a busy operation', async ({ page }) => {
  const dialog = await openImportDialog(page)
  const submitButton = dialog.getByRole('button', { name: '开始导入' })

  await expect(submitButton).toBeDisabled()
  await expect(submitButton).toHaveCSS('cursor', 'not-allowed')

  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'aima.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('aima'),
  })
  await expect(submitButton).toBeDisabled()
  await expect(submitButton).toHaveCSS('cursor', 'not-allowed')

  await dialog.getByLabel(/爱玛品牌词包/).check()
  await expect(submitButton).toBeEnabled()
  await expect(submitButton).toHaveCSS('cursor', 'pointer')
})

test('shows busy only during the real request and restores a visible dialog error', async ({ page }) => {
  let releaseUpload!: () => void
  const uploadGate = new Promise<void>((resolve) => {
    releaseUpload = resolve
  })
  await page.route('**/api/v1/import-batches', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    await uploadGate
    return route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        title: '上传服务暂不可用',
        status: 503,
        detail: 'Excel 导入创建失败，请稍后重试。',
        request_id: 'req_excel_import_busy_state',
        errors: [],
      }),
    })
  })

  const dialog = await openImportDialog(page)
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'aima.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('aima'),
  })
  await dialog.getByLabel(/爱玛品牌词包/).check()
  const submitButton = dialog.getByRole('button', { name: '开始导入' })

  await submitButton.click()
  await expect(submitButton).toBeDisabled()
  await expect(submitButton).toHaveAttribute('aria-busy', 'true')
  await expect(submitButton).toHaveText('正在创建…')
  await expect(submitButton).toHaveCSS('cursor', 'progress')

  releaseUpload()

  await expect(submitButton).toBeEnabled()
  await expect(submitButton).toHaveAttribute('aria-busy', 'false')
  await expect(submitButton).toHaveText('开始导入')
  await expect(dialog.getByRole('alert')).toContainText('Excel 导入创建失败，请稍后重试。')
  await expect(dialog.getByRole('alert')).toContainText('req_excel_import_busy_state')
})

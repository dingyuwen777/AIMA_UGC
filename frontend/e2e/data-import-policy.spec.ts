import { expect, test } from './fixture'

const keywordPackId = '71111111-2222-4333-8444-555555555555'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/v1/collection-runtime/summary') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 0,
          completed_today_count: 0,
          contents_ingested_today: 0,
          as_of: '2026-09-07T11:00:00+08:00',
        }),
      })
    }
    if (url.pathname === '/api/v1/collection-runtime/runs') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
      })
    }
    if (url.pathname === '/api/v1/data-import-campaigns') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [] }),
      })
    }
    if (url.pathname === '/api/v1/keyword-packs') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            id: keywordPackId,
            name: '爱玛品牌词包',
            description: '',
            enabled: true,
            version: 1,
            keyword_count: 1,
          }],
          total: 1,
          offset: 0,
          limit: 100,
        }),
      })
    }
    if (url.pathname === '/api/v1/data-import-sources/server/directories') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          available: true,
          items: [],
          next_cursor: null,
          has_more: false,
          unavailable_reason: null,
        }),
      })
    }
    return route.fulfill({ status: 404, body: 'not mocked' })
  })
})

test('keeps the selected write policy when switching import sources', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })

  const standard = dialog.getByRole('radio', { name: /标准观测/ })
  const fillOnly = dialog.getByRole('radio', { name: /历史补空/ })
  await expect(standard).toBeChecked()

  await fillOnly.check()
  await expect(fillOnly).toBeChecked()

  await dialog.getByRole('button', { name: '服务器目录' }).click()
  await expect(fillOnly).toBeChecked()

  await dialog.getByRole('button', { name: '本地电脑' }).click()
  await expect(fillOnly).toBeChecked()
  await expect(standard).not.toBeChecked()
})

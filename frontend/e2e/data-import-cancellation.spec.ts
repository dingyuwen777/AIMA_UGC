import { expect, test } from './fixture'

const campaignId = '71111111-2222-4333-8444-555555555555'
const keywordPackId = '81111111-2222-4333-8444-555555555555'

const discoveringCampaign = {
  id: campaignId,
  status: 'discovering',
  source_kind: 'server_path',
  ingestion_policy: 'historical_fill_only',
  declared_file_count: 0,
  root_relative_path: '2026-archive',
  recursive: false,
  discovered_file_count: 0,
  ready_item_count: 0,
  total_rows: 0,
  failed_chunk_count: 0,
  progress: {
    preflight_completed_file_count: 0,
    preflight_percent: 0,
    migration_completed_row_count: 0,
    migration_percent: 0,
  },
  stats: {
    created: 0,
    filled: 0,
    updated: 0,
    unchanged: 0,
    conflict: 0,
    filtered: 0,
    duplicate: 0,
    invalid: 0,
    failed: 0,
  },
  can_start: false,
  error_summary: null,
  created_at: '2026-09-09T11:00:00+08:00',
  started_at: null,
  finished_at: null,
}

test('预检过程中可以取消导入，并持续展示取消状态直到终态', async ({ page }) => {
  /** 用真实页面状态机模拟 discovering → cancelling → cancelled，不伪造本地组件状态。 */
  let cancellationRequested = false
  let postCancelReads = 0
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname === '/api/v1/collection-runtime/summary') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          processing_count: 1,
          completed_today_count: 0,
          contents_ingested_today: 0,
          as_of: '2026-09-09T11:00:00+08:00',
        }),
      })
    }
    if (request.method() === 'GET' && url.pathname === '/api/v1/keyword-packs') {
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
    if (
      request.method() === 'GET'
      && url.pathname === '/api/v1/data-import-sources/server/directories'
    ) {
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
    if (request.method() === 'GET' && url.pathname === '/api/v1/data-import-campaigns') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [discoveringCampaign] }),
      })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/cancel`) {
      cancellationRequested = true
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ ...discoveringCampaign, status: 'cancelling' }),
      })
    }
    if (request.method() === 'GET' && url.pathname === `/api/v1/data-import-campaigns/${campaignId}`) {
      if (!cancellationRequested) {
        return route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify(discoveringCampaign),
        })
      }
      postCancelReads += 1
      const status = postCancelReads === 1 ? 'cancelling' : 'cancelled'
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...discoveringCampaign,
          status,
          finished_at: status === 'cancelled' ? '2026-09-09T11:01:00+08:00' : null,
        }),
      })
    }
    if (
      request.method() === 'GET'
      && url.pathname === `/api/v1/data-import-campaigns/${campaignId}/items`
    ) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total_count: 0, has_more: false }),
      })
    }
    if (
      request.method() === 'GET'
      && url.pathname === `/api/v1/data-import-campaigns/${campaignId}/conflicts`
    ) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total_count: 0, has_more: false }),
      })
    }
    return route.fallback()
  })

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录', exact: true }).click()
  await dialog.getByRole('button', { name: /打开导入任务/ }).click()

  await expect(dialog.locator('.campaign-status')).toHaveText('正在确认数据来源')
  await expect(dialog.getByRole('button', { name: '取消任务', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '取消任务', exact: true }).click()
  await expect(dialog.locator('.campaign-status')).toHaveText('正在取消')
  await expect(dialog.getByRole('button', { name: '取消任务', exact: true })).toBeVisible()
  await expect(dialog.locator('.campaign-status')).toHaveText('已取消', { timeout: 10_000 })
  expect(postCancelReads).toBeGreaterThanOrEqual(2)
})

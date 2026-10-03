import { expect, test } from './fixture'
import type { HistoricalCampaignResponse, WisersOneDownloadResponse } from '../src/generated/api/client'

const downloadId = '11111111-aaaa-4111-8111-111111111111'
const campaignId = '22222222-aaaa-4222-8222-222222222222'
const baseDownload: WisersOneDownloadResponse & { plan_id: string; plan_name: string } = {
  id: downloadId,
  plan_id: '33333333-aaaa-4333-8333-333333333333',
  plan_name: '爱玛网站周期导入',
  occurrence_id: '44444444-aaaa-4444-8444-444444444444',
  campaign_id: null,
  status: 'waiting',
  send_state: 'confirmed',
  website_task_id: 'website-task-1',
  percent: 35,
  error_code: null,
  created_at: '2026-10-03T10:00:00+08:00',
  finished_at: null,
}
const completedCampaign: HistoricalCampaignResponse = {
  id: campaignId,
  status: 'succeeded',
  source_kind: 'server_path',
  ingestion_policy: 'standard_observation',
  root_relative_path: `wisersone/${downloadId}/wisersone_last24h.xlsx`,
  recursive: false,
  declared_file_count: 1,
  discovered_file_count: 1,
  ready_item_count: 1,
  total_rows: 1,
  progress: {
    preflight_completed_file_count: 1, preflight_percent: 100,
    migration_completed_row_count: 1, migration_percent: 100,
  },
  stats: { created: 1 },
  can_start: false,
  created_at: '2026-10-03T10:20:00+08:00',
  started_at: '2026-10-03T10:20:00+08:00',
  finished_at: '2026-10-03T10:21:00+08:00',
}

test.beforeEach(async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-03T10:22:00+08:00') })
  await page.route('**/api/v1/collection-runtime/summary', async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: {
      processing_count: 1, completed_today_count: 0, contents_ingested_today: 0,
      as_of: '2026-10-03T10:22:00+08:00',
    } })
  })
})

test('shows scheduled download progress and cancels the same task without creating another download', async ({ page }) => {
  const writes: string[] = []
  await page.route('**/api/v1/wisersone-downloads', async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: { items: [baseDownload] } })
  })
  await page.route(`**/api/v1/wisersone-downloads/${downloadId}/cancel`, async (route) => {
    const request = route.request()
    writes.push(`${request.method()} ${new URL(request.url()).pathname}`)
    expect(request.method()).toBe('POST')
    expect(request.postData()).toBeNull()
    await route.fulfill({ json: {
      ...baseDownload, status: 'cancelled', cancel_requested_at: '2026-10-03T10:22:00+08:00',
      finished_at: '2026-10-03T10:22:00+08:00',
    } })
  })
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: 'WisersOne 任务', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'WisersOne 下载与导入任务', exact: true })
  await expect(dialog).toContainText('采集策略 → 新建采集计划')
  await expect(dialog.getByRole('option', { name: /爱玛网站周期导入/ })).toHaveCount(1)
  await dialog.getByRole('combobox', { name: '查看已有任务', exact: true }).selectOption(downloadId)
  await expect(dialog).toContainText('网站正在生成 Excel')
  await expect(dialog.getByText('35%', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '查看导入结果', exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: '取消任务', exact: true }).click()
  await expect(dialog.locator('.task-state')).toContainText('已取消')
  await expect(dialog.getByRole('button', { name: '取消任务', exact: true })).toHaveCount(0)
  expect(writes).toEqual([`POST /api/v1/wisersone-downloads/${downloadId}/cancel`])
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toHaveCount(0)
})

test('keeps a failed task selected after retry errors and opens its completed unified import result', async ({ page }) => {
  let current = { ...baseDownload, status: 'failed' as WisersOneDownloadResponse['status'], error_code: 'wisersone_stage_failed' as string | null }
  let attempts = 0
  await page.route('**/api/v1/wisersone-downloads', async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: { items: [current] } })
  })
  await page.route(`**/api/v1/wisersone-downloads/${downloadId}/retry`, async (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().postData()).toBeNull()
    attempts += 1
    if (attempts === 1) {
      await route.fulfill({ status: 503, json: {
        status: 503, title: 'Unavailable', detail: '服务暂不可用，请稍后恢复同一次任务。', request_id: 'wisersone-retry-error',
      } })
      return
    }
    current = { ...current, status: 'waiting', error_code: null }
    await route.fulfill({ json: current })
  })
  await page.route(`**/api/v1/wisersone-downloads/${downloadId}`, async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: { ...current, status: 'succeeded', percent: 100, campaign_id: campaignId, finished_at: completedCampaign.finished_at } })
  })
  await page.route('**/api/v1/data-import-campaigns', async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: { items: [completedCampaign] } })
  })
  await page.route('**/api/v1/keyword-packs?*', async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 100 } })
  })
  await page.route(`**/api/v1/data-import-campaigns/${campaignId}`, async (route) => {
    expect(route.request().method()).toBe('GET')
    await route.fulfill({ json: completedCampaign })
  })
  for (const section of ['items', 'conflicts']) {
    await page.route(`**/api/v1/data-import-campaigns/${campaignId}/${section}*`, async (route) => {
      expect(route.request().method()).toBe('GET')
      await route.fulfill({ json: { items: [], total_count: 0, has_more: false } })
    })
  }
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: 'WisersOne 任务', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'WisersOne 下载与导入任务', exact: true })
  await dialog.getByRole('combobox', { name: '查看已有任务', exact: true }).selectOption(downloadId)
  const retry = dialog.getByRole('button', { name: '恢复同一次任务', exact: true })
  await retry.click()
  await expect(dialog.getByRole('alert').filter({ hasText: '服务暂不可用' })).toBeVisible()
  await expect(dialog.getByRole('combobox', { name: '查看已有任务', exact: true })).toHaveValue(downloadId)
  await retry.click()
  await expect(dialog.locator('.task-state')).toContainText('网站正在生成 Excel')
  const poll = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/v1/wisersone-downloads/${downloadId}`,
  )
  await page.clock.runFor(5000)
  await poll
  await expect(dialog.locator('.task-state')).toContainText('导入完成')
  const campaignRequest = page.waitForRequest((request) =>
    new URL(request.url()).pathname === `/api/v1/data-import-campaigns/${campaignId}` && request.method() === 'GET',
  )
  await dialog.getByRole('button', { name: '查看导入结果', exact: true }).click()
  await campaignRequest
  await expect(dialog).toHaveCount(0)
  const importDialog = page.getByRole('dialog', { name: '导入数据', exact: true })
  await expect(importDialog).toBeVisible()
  await expect(importDialog).toContainText('导入完成')
  await expect(importDialog).toContainText('标准观测')
  await expect(importDialog).toContainText('1 / 1 行已处理')
  expect(attempts).toBe(2)
})

test('shows download list failure and recovers an empty list when the task window reopens', async ({ page }) => {
  let calls = 0
  await page.route('**/api/v1/wisersone-downloads', async (route) => {
    expect(route.request().method()).toBe('GET')
    calls += 1
    if (calls === 1) {
      await route.fulfill({ status: 503, json: {
        status: 503, title: 'Unavailable', detail: '无法读取下载任务。', request_id: 'wisersone-list-error',
      } })
      return
    }
    await route.fulfill({ json: { items: [] } })
  })
  await page.goto('/collection-runtime')
  const trigger = page.getByRole('button', { name: 'WisersOne 任务', exact: true })
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: 'WisersOne 下载与导入任务', exact: true })
  await expect(dialog.getByRole('alert')).toContainText('无法读取下载任务')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await trigger.click()
  await expect(dialog).toContainText('尚无下载任务，启用采集计划后会按执行频率自动运行。')
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  expect(calls).toBe(2)
})

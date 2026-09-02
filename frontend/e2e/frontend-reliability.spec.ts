import { expect, test } from './fixture'

const vehicleId = '71111111-2222-4333-8444-555555555555'
const packId = '81111111-2222-4333-8444-555555555555'

const vehicle = {
  id: vehicleId,
  code: 'AIMA-Q7',
  display_name: '爱玛 Q7',
  status: 'active',
  version: 1,
  catalog_version: 1,
  merged_into_id: null,
  aliases: [],
  keyword_pack_ids: [],
  referenced: false,
  created_at: '2026-09-03T08:00:00+08:00',
  updated_at: '2026-09-03T08:00:00+08:00',
}

function auditEvent(index: number) {
  return {
    id: `91111111-2222-4333-8444-${String(index).padStart(12, '0')}`,
    actor_ref: 'local-administrator',
    event_type: `audit-event-${index}`,
    object_type: 'test',
    object_id: String(index),
    request_id: `request-${index}`,
    safe_detail: { index },
    created_at: '2026-09-03T08:00:00+08:00',
  }
}

test('keeps healthy admin resources usable when audit fails and paginates audit after retry', async ({ page }) => {
  let auditFailurePending = true
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname === '/api/v1/vehicle-models') {
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '200')
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [vehicle], total: 1, catalog_version: 1, offset, limit }),
      })
    }
    if (request.method() === 'GET' && url.pathname === '/api/v1/keyword-packs') {
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '100')
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            id: packId,
            name: '品牌词包',
            description: '',
            enabled: true,
            version: 1,
            keyword_count: 2,
          }],
          total: 1,
          offset,
          limit,
        }),
      })
    }
    if (request.method() === 'GET' && url.pathname === '/api/v1/analysis-schemes') {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
    }
    if (request.method() === 'GET' && url.pathname === '/api/v1/audit-events') {
      if (auditFailurePending) {
        auditFailurePending = false
        return route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 503,
            title: '审计服务暂不可用',
            detail: 'audit temporarily unavailable',
            request_id: 'audit-unavailable',
          }),
        })
      }
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '100')
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: [auditEvent(offset)],
          total: 150,
          offset,
          limit,
        }),
      })
    }
    return route.fallback()
  })

  await page.goto('/admin/configuration')
  await expect(page.getByText('爱玛 Q7')).toBeVisible()
  await expect(page.getByRole('button', { name: '新增车型' })).toBeEnabled()

  await page.getByRole('button', { name: '审计记录' }).click()
  await expect(page.getByText('audit temporarily unavailable')).toBeVisible()
  await page.getByRole('button', { name: '重试当前数据' }).click()
  await expect(page.getByText('audit-event-0')).toBeVisible()
  await expect(page.getByText('共 150 条')).toBeVisible()

  const secondPage = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === '/api/v1/audit-events' && url.searchParams.get('offset') === '100'
  })
  await page.getByRole('button', { name: '下一页' }).click()
  await secondPage
  await expect(page.getByText('audit-event-100')).toBeVisible()
  await expect(page.getByText('第 2 / 2 页')).toBeVisible()
})

import { expect as playwrightExpect, test as base } from '@playwright/test'

export { expect } from '@playwright/test'
export type * from '@playwright/test'

/**
 * Browser Mock 的全局 API 守卫。
 * 只为所有页面都会触发的 Shell/共享目录提供最小稳定响应；业务 API 必须由各 spec 显式声明。
 */
export const test = base.extend<{ apiGuard: void }>({
  apiGuard: [
    async ({ page }, use) => {
      const unexpected: string[] = []
      await page.route('**/api/v1/**', async (route) => {
        const request = route.request()
        const url = new URL(request.url())
        const key = `${request.method()} ${url.pathname}${url.search}`

        if (request.method() === 'GET' && url.pathname === '/api/v1/principal') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({
              principal_id: 'local-administrator',
              display_name: '本地管理员',
              role: 'administrator',
              source: 'development',
              is_administrator: true,
            }),
          })
          return
        }
        if (request.method() === 'GET' && url.pathname === '/api/v1/notifications') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ items: [], unread_count: 0 }),
          })
          return
        }
        if (request.method() === 'PUT' && url.pathname === '/api/v1/notifications/read') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ requested_count: 0, changed_count: 0 }),
          })
          return
        }
        if (request.method() === 'GET' && url.pathname === '/api/v1/vehicle-models') {
          const offset = Number(url.searchParams.get('offset') ?? '0')
          const limit = Number(url.searchParams.get('limit') ?? '50')
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ items: [], total: 0, catalog_version: 1, offset, limit }),
          })
          return
        }
        if (request.method() === 'GET' && url.pathname === '/api/v1/export-columns') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ version: 1, columns: [] }),
          })
          return
        }
        if (request.method() === 'GET' && url.pathname === '/api/v1/analysis/content-runs') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ items: [] }),
          })
          return
        }
        if (request.method() === 'GET' && url.pathname === '/api/v1/collection-runtime/runs') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
          })
          return
        }
        if (request.method() === 'GET' && url.pathname === '/api/v1/data-exports') {
          await route.fulfill({
            contentType: 'application/json',
            body: JSON.stringify({ items: [] }),
          })
          return
        }

        unexpected.push(key)
        await route.fulfill({
          status: 599,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 599,
            title: 'Unhandled Browser Mock API',
            detail: key,
            request_id: 'browser-mock-unhandled',
          }),
        })
      })

      await use()
      playwrightExpect(unexpected, `存在未声明的 Browser Mock API 请求：${unexpected.join(', ')}`).toEqual([])
    },
    { auto: true },
  ],
})

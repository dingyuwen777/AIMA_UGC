import { expect, test } from './fixture'

const campaignId = '11111111-2222-4333-8444-555555555555'
const discoveryJobId = '21111111-2222-4333-8444-555555555555'
const keywordPackId = '31111111-2222-4333-8444-555555555555'

const readyCampaign = {
  id: campaignId,
  status: 'ready',
  source_kind: 'server_path',
  ingestion_policy: 'historical_fill_only',
  declared_file_count: 1,
  root_relative_path: '',
  recursive: false,
  discovered_file_count: 1,
  ready_item_count: 1,
  total_rows: 120,
  progress: {
    preflight_completed_file_count: 1,
    preflight_percent: 100,
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
  can_start: true,
  error_summary: null,
  created_at: '2026-08-26T10:00:00+08:00',
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
          as_of: '2026-08-26T10:00:00+08:00',
        }),
      })
    }
    if (url.pathname === '/api/v1/collection-runtime/runs') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
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
            version: 3,
            keyword_count: 12,
          }],
          total: 1,
          offset: 0,
          limit: 100,
        }),
      })
    }
    if (url.pathname === '/api/v1/data-import-sources/server/directories') {
      const relativePath = url.searchParams.get('relative_path') ?? ''
      const cursor = url.searchParams.get('cursor')
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          available: true,
          items: cursor === 'root-page-2'
            ? [{
                name: 'late-file.xlsx',
                relative_path: 'late-file.xlsx',
                kind: 'file',
                byte_size: 2048,
                modified_at_ns: 2,
              }]
            : relativePath === '2025-archive'
            ? [{
                name: 'part-001.xlsx',
                relative_path: '2025-archive/part-001.xlsx',
                kind: 'file',
                byte_size: 4096,
                modified_at_ns: 1,
              }]
            : [{
                name: '2025-archive',
                relative_path: '2025-archive',
                kind: 'directory',
                byte_size: null,
                modified_at_ns: 1,
              }],
          next_cursor: relativePath === '' && cursor === null ? 'root-page-2' : null,
          has_more: relativePath === '' && cursor === null,
          unavailable_reason: null,
        }),
      })
    }
    if (url.pathname === '/api/v1/data-import-campaigns/server' && request.method() === 'POST') {
      return route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ campaign_id: campaignId, discovery_job_id: discoveryJobId }),
      })
    }
    if (url.pathname === '/api/v1/data-import-campaigns' && request.method() === 'GET') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [readyCampaign] }),
      })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}`) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(readyCampaign) })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/items`) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/conflicts`) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
    }
    if (url.pathname === `/api/v1/data-import-campaigns/${campaignId}/start`) {
      return route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ ...readyCampaign, status: 'queued', can_start: false }),
      })
    }
    return route.fulfill({ status: 404, body: 'not mocked' })
  })
})

test('selects only server-relative files, preflights, and explicitly starts a campaign', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()

  await expect(dialog.getByText('只浏览管理员批准的只读根目录')).toBeVisible()
  await dialog.getByRole('button', { name: /2025-archive/ }).click()
  await dialog.getByLabel('选择 part-001.xlsx').check()
  await dialog.getByLabel(/爱玛品牌词包/).check()

  const createRequest = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === '/api/v1/data-import-campaigns/server' && candidate.method() === 'POST'
  })
  await dialog.getByRole('button', { name: '创建并预检' }).click()
  expect((await createRequest).postDataJSON()).toMatchObject({
    relative_paths: ['2025-archive/part-001.xlsx'],
    keyword_pack_ids: [keywordPackId],
    recursive: false,
  })

  await expect(dialog.getByText('预检完成，可开始导入')).toBeVisible()
  await expect(dialog.getByRole('progressbar', { name: '导入预检进度' })).toHaveAttribute('aria-valuenow', '100')
  await expect(dialog.getByRole('progressbar', { name: '数据导入进度' })).toHaveAttribute('aria-valuenow', '0')
  await expect(dialog.getByText('AI 不会自动执行')).toBeVisible()
  const startRequest = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === `/api/v1/data-import-campaigns/${campaignId}/start`
  })
  await dialog.getByRole('button', { name: '开始导入' }).click()
  await startRequest
  await expect(dialog.getByText('导入任务已进入队列。')).toBeVisible()

  await page.route(`**/api/v1/data-import-campaigns/${campaignId}`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...readyCampaign,
        status: 'succeeded',
        can_start: false,
        stats: { ...readyCampaign.stats, conflict: 1 },
        progress: {
          ...readyCampaign.progress,
          migration_completed_row_count: 120,
          migration_percent: 100,
        },
        finished_at: '2026-08-26T10:05:00+08:00',
      }),
    })
  })
  await expect(dialog.getByRole('button', { name: '查看导入内容' })).toBeVisible({ timeout: 5_000 })
  await dialog.getByRole('button', { name: '查看导入内容' }).click()
  await expect(page).toHaveURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('source_identifier') === campaignId,
  )
})

test('selects a server directory for bounded recursive discovery', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()

  await dialog.getByLabel('选择目录 2025-archive').check()
  await dialog.getByLabel(/选择目录时递归发现/).check()
  await dialog.getByLabel(/爱玛品牌词包/).check()
  const createRequest = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === '/api/v1/data-import-campaigns/server' && candidate.method() === 'POST'
  })
  await dialog.getByRole('button', { name: '创建并预检' }).click()

  expect((await createRequest).postDataJSON()).toMatchObject({
    relative_paths: ['2025-archive'],
    recursive: true,
  })
})

test('continues directory enumeration with the server cursor', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()

  await dialog.getByRole('button', { name: '加载更多目录项' }).click()
  await expect(dialog.getByLabel('选择 late-file.xlsx')).toBeVisible()
})

test('reopens an existing campaign after a page reload', async ({ page }) => {
  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()

  await dialog.getByRole('button', { name: new RegExp(`打开 Campaign ${campaignId}`) }).click()
  await expect(dialog.getByText('预检完成，可开始导入')).toBeVisible()
})

test('does not invent a percentage while directory discovery has no total', async ({ page }) => {
  const discoveringCampaign = {
    ...readyCampaign,
    status: 'discovering',
    discovered_file_count: 0,
    ready_item_count: 0,
    total_rows: 0,
    progress: {
      preflight_completed_file_count: 0,
      preflight_percent: 0,
      migration_completed_row_count: 0,
      migration_percent: 0,
    },
    can_start: false,
  }
  await page.route('**/api/v1/data-import-campaigns', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [discoveringCampaign] }),
    })
  })
  await page.route(`**/api/v1/data-import-campaigns/${campaignId}`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(discoveringCampaign),
    })
  })

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()
  await dialog.getByRole('button', { name: new RegExp(`打开 Campaign ${campaignId}`) }).click()

  const progress = dialog.getByRole('progressbar', { name: '导入预检进度' })
  await expect(progress).not.toHaveAttribute('aria-valuenow')
  await expect(dialog.getByText('正在枚举批准目录，文件总数尚未确定')).toBeVisible()
  await expect(dialog.getByRole('progressbar', { name: '数据导入进度' })).toHaveCount(0)
})

test('keeps polling a cancelling campaign until it reaches cancelled', async ({ page }) => {
  let cancellationRequested = false
  let postCancelReadCount = 0
  await page.route(`**/api/v1/data-import-campaigns/${campaignId}`, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    if (!cancellationRequested) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ ...readyCampaign, status: 'running', can_start: false }),
      })
    }
    postCancelReadCount += 1
    const status = postCancelReadCount === 1 ? 'cancelling' : 'cancelled'
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...readyCampaign,
        status,
        can_start: false,
        started_at: '2026-08-26T10:01:00+08:00',
        finished_at: status === 'cancelled' ? '2026-08-26T10:02:00+08:00' : null,
      }),
    })
  })
  await page.route(
    `**/api/v1/data-import-campaigns/${campaignId}/cancel`,
    async (route) => {
      cancellationRequested = true
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...readyCampaign,
          status: 'cancelling',
          can_start: false,
          started_at: '2026-08-26T10:01:00+08:00',
        }),
      })
    },
  )

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()
  await dialog.getByRole('button', { name: new RegExp(`打开 Campaign ${campaignId}`) }).click()
  await expect(dialog.getByText('状态：running')).toBeVisible()
  await dialog.getByRole('button', { name: '取消任务', exact: true }).click()

  // 取消动作会先立即刷新到 cancelling，最终 cancelled 由下一次约 5 秒轮询取得。
  await expect(dialog.getByText('状态：cancelling')).toBeVisible()
  await expect(dialog.getByText('状态：cancelled')).toBeVisible({ timeout: 10_000 })
  expect(postCancelReadCount).toBeGreaterThanOrEqual(2)
})

test('uses campaign failed-chunk facts even when bounded detail omits failed chunks', async ({ page }) => {
  const partialCampaign = {
    ...readyCampaign,
    status: 'partial_failed',
    can_start: false,
    failed_chunk_count: 1,
    stats: { ...readyCampaign.stats, created: 60, failed: 60 },
    started_at: '2026-08-26T10:01:00+08:00',
    finished_at: '2026-08-26T10:02:00+08:00',
  }
  await page.route(`**/api/v1/data-import-campaigns/${campaignId}`, async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(partialCampaign) })
  })
  await page.route(`**/api/v1/data-import-campaigns/${campaignId}/items`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total_count: 201,
        has_more: true,
      }),
    })
  })
  await page.route(
    `**/api/v1/data-import-campaigns/${campaignId}/retry-failed`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...partialCampaign, status: 'queued', finished_at: null }),
      })
    },
  )

  await page.goto('/collection-runtime')
  await page.getByRole('button', { name: '导入数据' }).click()
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await dialog.getByRole('button', { name: '服务器目录' }).click()
  await dialog.getByRole('button', { name: /2025-archive/ }).click()
  await dialog.getByLabel('选择 part-001.xlsx').check()
  await dialog.getByLabel(/爱玛品牌词包/).check()
  await dialog.getByRole('button', { name: '创建并预检' }).click()
  await expect(dialog.getByText('状态：partial_failed')).toBeVisible()
  const retryRequest = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === `/api/v1/data-import-campaigns/${campaignId}/retry-failed`
  })
  await dialog.getByRole('button', { name: '重试失败项' }).click()
  await retryRequest
  await expect(dialog.getByText('失败项已重新进入导入队列。')).toBeVisible()
})

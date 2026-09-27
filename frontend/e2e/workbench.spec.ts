import { expect, test, type Page } from './fixture'

const schemeId = '11111111-1111-4111-8111-111111111111'
const taxonomyHash = 'a'.repeat(64)
const brandId = '22222222-2222-4222-8222-222222222222'
const vehicleId = '33333333-3333-4333-8333-333333333333'
const taxonomy = {
  prompt_version: 'content-labeling.v4',
  prompt_sha256: 'b'.repeat(64),
  schema_version: 'aima-content-taxonomy.v2',
  taxonomy_sha256: taxonomyHash,
  sentiments: ['正面', '中性', '负面', '混合', '无法判断'],
  voice_types: ['真实用户发声', '品牌官方发声', '无法判断'],
  labels: [
    { primary_label: '外观设计', secondary_labels: ['颜色与配色', '整体造型与颜值'] },
    { primary_label: '电池、续航与充电', secondary_labels: ['续航里程'] },
    { primary_label: '无法分类', secondary_labels: ['无法判断'] },
  ],
}
const modules = [
  { module_id: 'sound-stream', visible: true, order: 0, column_span: 6, row_units: 48 },
  { module_id: 'brand-mind', visible: true, order: 1, column_span: 6, row_units: 48 },
  { module_id: 'ugc-trend', visible: true, order: 2, column_span: 6, row_units: 48 },
]

/** 安装工作台 Browser Mock；只模拟后端 Contract，不在测试端重算业务指标。 */
async function mockWorkbench(page: Page): Promise<void> {
  await page.route('**/api/v1/content-analysis-taxonomy', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(taxonomy) })
  })
  await page.route('**/api/v1/vehicle-brands**', async (route) => {
    const url = new URL(route.request().url())
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: brandId,
          code: 'AIMA',
          display_name: '爱玛',
          role: 'owned',
          status: 'active',
          version: 1,
          catalog_version: 1,
          aliases: [],
          created_at: '2026-09-01T00:00:00+08:00',
          updated_at: '2026-09-01T00:00:00+08:00',
        }],
        total: 1,
        catalog_version: 1,
        offset: Number(url.searchParams.get('offset') ?? '0'),
        limit: Number(url.searchParams.get('limit') ?? '200'),
      }),
    })
  })
  await page.route('**/api/v1/vehicle-models**', async (route) => {
    const url = new URL(route.request().url())
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: vehicleId,
          code: 'AIMA-Q7',
          display_name: 'Q7',
          series_name: 'Q 系列',
          category_name: '电动车',
          brand_id: brandId,
          brand: { id: brandId, code: 'AIMA', display_name: '爱玛', role: 'owned' },
          status: 'active',
          version: 1,
          catalog_version: 1,
          aliases: [],
          created_at: '2026-09-01T00:00:00+08:00',
          updated_at: '2026-09-01T00:00:00+08:00',
        }],
        total: 1,
        catalog_version: 1,
        offset: Number(url.searchParams.get('offset') ?? '0'),
        limit: Number(url.searchParams.get('limit') ?? '200'),
      }),
    })
  })
  await page.route('**/api/v1/workbench/layout', async (route) => {
    if (route.request().method() === 'PUT') {
      const request = route.request().postDataJSON() as { revision: number; modules: typeof modules }
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: 1,
          revision: request.revision + 1,
          modules: request.modules,
          updated_at: '2026-09-27T08:11:00+08:00',
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        schema_version: 1,
        revision: 3,
        modules,
        updated_at: '2026-09-27T08:00:00+08:00',
      }),
    })
  })
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: [{
          content_id: '44444444-4444-4444-8444-444444444444',
          platform: 'xiaohongshu',
          author_display_name: '测试用户',
          published_at: '2026-09-26T15:30:00+08:00',
          title: '爱玛 Q7 奶油白实车',
          text: '奶油白实车很耐看，阳光下高级感满满。',
          sentiment: '正面',
          voice_type: '真实用户发声',
          labels: [{ primary_label: '外观设计', secondary_label: '颜色与配色' }],
          analysis_current: true,
          vehicle_names: ['Q7'],
        }],
      }),
    })
  })
  await page.route('**/api/v1/workbench/mind**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        date_from: '2026-08-29',
        date_to: '2026-09-27',
        previous_date_from: '2026-07-30',
        previous_date_to: '2026-08-28',
        identified_user_count: 100,
        unidentified_content_count: 2,
        analyzed_count: 80,
        analysis_coverage_rate: 0.8,
        dimensions: [
          {
            primary_label: '外观设计',
            user_count: 35,
            user_share: 0.35,
            positive_rate: 0.7,
            user_share_change_pp: 2.2,
            secondary_labels: [{ secondary_label: '颜色与配色', user_count: 20 }],
            change_summary: '外观设计用户占比较紧邻等长上期上升 2.20pp。',
          },
          {
            primary_label: '电池、续航与充电',
            user_count: 28,
            user_share: 0.28,
            positive_rate: 0.55,
            user_share_change_pp: -1.1,
            secondary_labels: [{ secondary_label: '续航里程', user_count: 18 }],
            change_summary: '电池、续航与充电用户占比较紧邻等长上期下降 1.10pp。',
          },
        ],
      }),
    })
  })
  await page.route('**/api/v1/workbench/trend**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        date_from: '2026-08-29',
        date_to: '2026-09-27',
        previous_date_from: '2026-07-30',
        previous_date_to: '2026-08-28',
        total_count: 120,
        daily_average: 4,
        peak_day: '2026-09-20',
        peak_count: 12,
        period_change_rate: 0.12,
        positive_rate: 0.6,
        positive_rate_change_pp: 3.2,
        analyzed_count: 100,
        analysis_coverage_rate: 0.833333,
        daily: [
          { day: '2026-09-19', count: 4 },
          { day: '2026-09-20', count: 12 },
          { day: '2026-09-21', count: 7 },
        ],
        sentiments: [
          { sentiment: '正面', count: 60, share: 0.6 },
          { sentiment: '中性', count: 20, share: 0.2 },
          { sentiment: '混合', count: 10, share: 0.1 },
          { sentiment: '无法判断', count: 5, share: 0.05 },
        ],
        summary: '09/20 为当前周期声量峰值，共 12 条；当前周期总声量较紧邻等长上期上升。',
      }),
    })
  })
}

/** 深链进入声音广场后提供最小页面依赖，保证测试不靠未声明 API。 */
async function mockVoicePlazaAfterDeepLink(page: Page): Promise<void> {
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/content-filter-options', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        platforms: ['xiaohongshu', 'douyin', 'weibo', 'bilibili', 'kuaishou'],
        relevances: ['relevant', 'irrelevant'],
        analysis_statuses: ['completed', 'pending', 'stale'],
        content_types: ['note'],
        sentiments: taxonomy.sentiments.map((value) => ({ value, source: 'active' })),
        voice_types: taxonomy.voice_types.map((value) => ({ value, source: 'active' })),
        labels: taxonomy.labels.map((item) => ({
          primary_label: item.primary_label,
          source: 'active',
          secondary_labels: item.secondary_labels.map((value) => ({ value, source: 'active' })),
        })),
        catalog_status: 'ready',
      }),
    })
  })
  await page.route('**/api/v1/contents/count', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count_mode: 'estimated',
        count: 0,
        count_kind: 'exact',
        as_of: '2026-09-27T08:10:00+08:00',
        truncated: false,
      }),
    })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await mockWorkbench(page)
})

test('工作台按 active Taxonomy 展示真实模块，并使用后端 as_of', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')

  await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '声音流' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '品牌用户心智' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'UGC 声量与情感趋势' })).toBeVisible()
  await expect(page.getByText('基于当前 active Taxonomy，动态查看一级用户心智')).toBeVisible()
  await expect(page.getByText('外观设计', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('电池、续航与充电', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('混合', { exact: true })).toBeVisible()
  await expect(page.getByText('无法判断', { exact: true })).toBeVisible()
  await expect(page.getByText(/2026.*09.*27.*08.*10.*自动刷新/)).toBeVisible()
  await expect(page.getByAltText('工作台开发中')).toHaveCount(0)

  const metrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
})

test('显式编辑态先改草稿，取消恢复；保存一次提交完整 revision', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '+ 编辑工作台' }).click()
  await expect(page.getByText('正在编辑工作台')).toBeVisible()

  const mindShell = page.locator('.module-shell').filter({ has: page.getByRole('heading', { name: '品牌用户心智' }) })
  await mindShell.getByRole('button', { name: '隐藏' }).click()
  await expect(page.getByRole('heading', { name: '品牌用户心智' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '+ 品牌用户心智' })).toBeVisible()

  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.getByRole('heading', { name: '品牌用户心智' })).toBeVisible()

  await page.getByRole('button', { name: '+ 编辑工作台' }).click()
  const mindShellAgain = page.locator('.module-shell').filter({ has: page.getByRole('heading', { name: '品牌用户心智' }) })
  await mindShellAgain.getByRole('button', { name: '隐藏' }).click()
  const saveRequest = page.waitForRequest((request) =>
    request.method() === 'PUT' && new URL(request.url()).pathname === '/api/v1/workbench/layout')
  await page.getByRole('button', { name: '保存完成' }).click()
  const request = await saveRequest
  const payload = request.postDataJSON() as { revision: number; modules: typeof modules }

  expect(payload.revision).toBe(3)
  expect(payload.modules).toHaveLength(3)
  expect(payload.modules.find((item) => item.module_id === 'brand-mind')?.visible).toBe(false)
  await expect(page.getByText('工作台布局已保存。')).toBeVisible()
  await expect(page.getByRole('button', { name: '+ 编辑工作台' })).toBeVisible()
})

test('品牌心智深链把当前日期和一级标签恢复到声音广场', async ({ page }) => {
  await mockVoicePlazaAfterDeepLink(page)
  await page.goto('/')

  await page.getByRole('button', { name: '查看该心智的用户原声 →' }).click()
  await page.waitForURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('primary_label') === '外观设计')

  const url = new URL(page.url())
  expect(url.searchParams.get('primary_label')).toBe('外观设计')
  expect(url.searchParams.get('published_from')).toBeTruthy()
  expect(url.searchParams.get('published_to')).toBeTruthy()
  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()
})

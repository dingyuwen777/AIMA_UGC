import { expect, test, type Page } from './fixture'

const schemeId = '11111111-1111-4111-8111-111111111111'
const taxonomyHash = 'a'.repeat(64)
const brandId = '22222222-2222-4222-8222-222222222222'
const vehicleId = '33333333-3333-4333-8333-333333333333'
const temporaryError = {
  type: 'https://aima.example/problems/service-unavailable',
  title: 'Service unavailable',
  status: 503,
  detail: 'temporary',
  request_id: 'req-workbench-temporary',
}
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
    const sentiments = new URL(route.request().url()).searchParams.getAll('sentiments')
    if (sentiments.includes('混合')) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify(temporaryError) })
      return
    }
    const empty = sentiments.includes('负面')
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: empty ? [] : [{
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
    const sentiments = new URL(route.request().url()).searchParams.getAll('sentiments')
    if (sentiments.includes('混合')) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify(temporaryError) })
      return
    }
    const empty = sentiments.includes('负面')
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
        identified_user_count: empty ? 0 : 100,
        unidentified_content_count: empty ? 0 : 2,
        analyzed_count: empty ? 0 : 80,
        analysis_coverage_rate: empty ? 0 : 0.8,
        dimensions: empty ? [] : [
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
    const sentiments = new URL(route.request().url()).searchParams.getAll('sentiments')
    if (sentiments.includes('混合')) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify(temporaryError) })
      return
    }
    const empty = sentiments.includes('负面')
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
        total_count: empty ? 0 : 120,
        daily_average: empty ? 0 : 4,
        peak_day: empty ? null : '2026-09-20',
        peak_count: empty ? 0 : 12,
        period_change_rate: empty ? null : 0.12,
        positive_rate: empty ? null : 0.6,
        positive_rate_change_pp: empty ? null : 3.2,
        analyzed_count: empty ? 0 : 100,
        analysis_coverage_rate: empty ? 0 : 0.833333,
        daily: empty ? [] : [
          { day: '2026-09-19', count: 4 },
          { day: '2026-09-20', count: 12 },
          { day: '2026-09-21', count: 7 },
        ],
        sentiments: empty ? [] : [
          { sentiment: '正面', count: 60, share: 0.6 },
          { sentiment: '中性', count: 20, share: 0.2 },
          { sentiment: '混合', count: 10, share: 0.1 },
          { sentiment: '无法判断', count: 5, share: 0.05 },
        ],
        summary: empty ? '当前时间范围暂无可展示的 UGC 声量。' : '09/20 为当前周期声量峰值，共 12 条；当前周期总声量较紧邻等长上期上升。',
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
  await expect(page.locator('.mind-card .radar-chart')).toHaveAttribute('data-axis-count', '2')
  await expect(page.locator('.mind-card .radar-chart canvas')).toBeVisible()
  await expect(page.locator('.mind-card .radar-center')).toContainText('爱玛心智图')
  await expect(page.locator('.mind-card .radar-selected-card')).toContainText('外观设计')
  await expect(page.locator('.trend-card .sentiment-list').getByText('混合', { exact: true })).toBeVisible()
  await expect(page.locator('.trend-card .sentiment-list').getByText('无法判断', { exact: true })).toBeVisible()
  await expect(page.getByText(/2026.*09.*27.*08.*10.*每 15 秒检查更新/)).toBeVisible()
  await expect(page.getByAltText('工作台开发中')).toHaveCount(0)

  // Figma 默认态 1440×900：侧栏后两张主卡同排，页面留白不能叠加两层。
  const [streamBox, mindBox] = await Promise.all([
    page.locator('.module-shell').nth(0).boundingBox(),
    page.locator('.module-shell').nth(1).boundingBox(),
  ])
  expect(streamBox).not.toBeNull()
  expect(mindBox).not.toBeNull()
  expect(Math.abs((streamBox?.x ?? 0) - 199)).toBeLessThanOrEqual(12)
  expect(Math.abs((streamBox?.y ?? 0) - 112)).toBeLessThanOrEqual(12)
  expect(Math.abs((mindBox?.x ?? 0) - 818)).toBeLessThanOrEqual(12)
  expect(Math.abs((mindBox?.y ?? 0) - 112)).toBeLessThanOrEqual(12)

  const metrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
  const [radarStage, radarCenter, radarSelection] = await Promise.all([
    page.locator('.mind-card .radar-stage').boundingBox(),
    page.locator('.mind-card .radar-center').boundingBox(),
    page.locator('.mind-card .radar-selected-card').boundingBox(),
  ])
  expect(radarStage).not.toBeNull()
  expect(radarCenter).not.toBeNull()
  expect(radarSelection).not.toBeNull()
  expect((radarCenter?.x ?? 0) + (radarCenter?.width ?? 0))
    .toBeLessThanOrEqual((radarSelection?.x ?? 0) + 1)
  expect(radarSelection?.x ?? 0).toBeGreaterThanOrEqual(radarStage?.x ?? 0)
  expect((radarSelection?.x ?? 0) + (radarSelection?.width ?? 0))
    .toBeLessThanOrEqual((radarStage?.x ?? 0) + (radarStage?.width ?? 0) + 1)
})

test('声音流筛选首次关闭，并在缺少原生 Popover API 时仍可开关', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(HTMLElement.prototype, 'showPopover', {
      configurable: true,
      value: undefined,
    })
    Object.defineProperty(HTMLElement.prototype, 'hidePopover', {
      configurable: true,
      value: undefined,
    })
  })
  await page.goto('/')
  await page.addStyleTag({ content: '[popover] { display: block; }' })

  const trigger = page.getByRole('button', { name: '一级标签', exact: true })
  const panel = page.getByRole('dialog', { name: '选择一级标签' })
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(panel).toBeHidden()

  await trigger.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await expect(panel).toBeVisible()
  const box = await panel.boundingBox()
  const viewport = page.viewportSize()
  expect(box).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(12)
  expect(box?.y ?? -1).toBeGreaterThanOrEqual(12)
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual((viewport?.width ?? 0) - 12)
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual((viewport?.height ?? 0) - 12)

  await panel.getByRole('checkbox').first().focus()
  await expect(panel.getByRole('checkbox').first()).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(panel).toBeHidden()
  await expect(trigger).toBeFocused()

  await trigger.click()
  await page.getByRole('heading', { name: '工作台', exact: true }).click()
  await expect(panel).toBeHidden()
  await trigger.click()
  await page.evaluate(() => window.dispatchEvent(new Event('scroll')))
  await expect(panel).toBeHidden()
})

test('空声音流时原生筛选面板紧贴对应触发器并位于视口内', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: [],
      }),
    })
  })
  await page.goto('/')
  await expect(page.locator('.stream-card > footer')).toContainText('本页 0 条')

  const trigger = page.getByRole('button', { name: '发声', exact: true })
  const panel = page.getByRole('dialog', { name: '选择发声' })
  await trigger.click()
  await expect(panel).toBeVisible()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(await panel.evaluate((element) => element.matches(':popover-open'))).toBe(true)

  const [triggerBox, panelBox] = await Promise.all([trigger.boundingBox(), panel.boundingBox()])
  const viewport = page.viewportSize()
  expect(triggerBox).not.toBeNull()
  expect(panelBox).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(Math.abs((panelBox?.x ?? 0) - (triggerBox?.x ?? 0))).toBeLessThanOrEqual(2)
  expect(panelBox?.y ?? 0).toBeGreaterThanOrEqual((triggerBox?.y ?? 0) + (triggerBox?.height ?? 0))
  expect(panelBox?.y ?? 0).toBeLessThanOrEqual((triggerBox?.y ?? 0) + (triggerBox?.height ?? 0) + 8)
  expect(panelBox?.x ?? -1).toBeGreaterThanOrEqual(12)
  expect((panelBox?.x ?? 0) + (panelBox?.width ?? 0)).toBeLessThanOrEqual((viewport?.width ?? 0) - 12)
  expect((panelBox?.y ?? 0) + (panelBox?.height ?? 0)).toBeLessThanOrEqual((viewport?.height ?? 0) - 12)

  const sentimentTrigger = page.getByRole('button', { name: '情感', exact: true })
  const sentimentPanel = page.getByRole('dialog', { name: '选择情感' })
  await sentimentTrigger.click()
  await expect(panel).toBeHidden()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(sentimentPanel).toBeVisible()
  await expect(sentimentTrigger).toHaveAttribute('aria-expanded', 'true')
})

test('声音流自动滚动时筛选面板保持打开，筛选条滚动时关闭', async ({ page }) => {
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: Array.from({ length: 18 }, (_, index) => ({
          content_id: `44444444-4444-4444-8444-${String(index + 1).padStart(12, '0')}`,
          platform: 'xiaohongshu',
          author_display_name: `用户${index + 1}`,
          published_at: '2026-09-26T15:30:00+08:00',
          text: `第${index + 1}条真实用户声音`,
          sentiment: '正面',
          voice_type: '真实用户发声',
          labels: [],
          analysis_current: true,
          vehicle_names: [],
        })),
      }),
    })
  })
  await page.goto('/')

  const list = page.getByRole('region', { name: '声音流列表' })
  await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(5)
  const trigger = page.getByRole('button', { name: '发声', exact: true })
  const panel = page.getByRole('dialog', { name: '选择发声' })
  await trigger.click()
  await expect(panel).toBeVisible()
  const openedAt = await list.evaluate((element) => element.scrollTop)
  await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(openedAt + 3)
  await expect(panel).toBeVisible()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await expect(panel.getByRole('checkbox', { name: '真实用户发声' })).toBeVisible()

  const filters = page.locator('.workbench-filters')
  const initialScrollLeft = await filters.evaluate((element) => element.scrollLeft)
  await filters.evaluate((element) => element.scrollBy({ left: 40 }))
  await expect.poll(() => filters.evaluate((element) => element.scrollLeft)).toBeGreaterThan(initialScrollLeft)
  await expect(panel).toBeHidden()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
})

test('声音流筛选下拉可操作，选择后同口径刷新三个真实模块请求', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const sentiment = page.locator('.aima-multi-select').filter({ has: page.getByRole('button', { name: '情感', exact: true }) })
  await sentiment.getByRole('button', { name: '情感', exact: true }).click()
  const panelHit = await sentiment.locator('.aima-multi-select__panel').evaluate((panel) => {
    const box = panel.getBoundingClientRect()
    return panel.contains(document.elementFromPoint(box.left + 20, box.top + 15))
  })
  expect(panelHit).toBe(true)
  await sentiment.locator('.aima-multi-select__panel').evaluate((panel) => {
    panel.dispatchEvent(new Event('scroll'))
  })
  await expect(sentiment.getByRole('dialog', { name: '选择情感' })).toBeVisible()
  await sentiment.getByRole('checkbox', { name: '正面' }).check({ timeout: 3000 })

  const paths = ['/api/v1/workbench/stream', '/api/v1/workbench/mind', '/api/v1/workbench/trend']
  for (const path of paths) {
    await expect.poll(() => page.evaluate((target) =>
      performance.getEntriesByType('resource').some((entry) => {
        const url = new URL(entry.name)
        return url.pathname === target && url.searchParams.get('sentiments') === '正面'
      }), path)).toBe(true)
  }
})

test('确认日期后起止日期同时进入声音流、心智与趋势查询', async ({ page }) => {
  await page.goto('/')
  const today = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date())
  const from = new Date(`${today}T00:00:00Z`)
  from.setUTCDate(from.getUTCDate() - 6)
  const expectedFrom = from.toISOString().slice(0, 10)
  const requests: URL[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname.startsWith('/api/v1/workbench/') && url.pathname !== '/api/v1/workbench/layout') {
      requests.push(url)
    }
  })

  await page.getByRole('button', { name: '工作台时间范围' }).click()
  await page.getByRole('button', { name: '近7天' }).click()
  await page.getByRole('button', { name: '确定' }).click()
  await expect.poll(() => requests.length).toBeGreaterThanOrEqual(3)

  for (const path of ['/api/v1/workbench/stream', '/api/v1/workbench/mind', '/api/v1/workbench/trend']) {
    const request = requests.findLast((item) => item.pathname === path)
    expect(request?.searchParams.get('date_from')).toBe(expectedFrom)
    expect(request?.searchParams.get('date_to')).toBe(today)
  }
})

test('反向点击日期也形成合法范围并立即请求三个模块', async ({ page }) => {
  await page.goto('/')
  const requests: URL[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (['stream', 'mind', 'trend'].some((module) => url.pathname.endsWith(`/workbench/${module}`))) requests.push(url)
  })
  await page.getByRole('button', { name: '工作台时间范围' }).click()
  const dates = await page.locator('.calendar-days [data-date]').evaluateAll((buttons) =>
    buttons.map((button) => button.getAttribute('data-date')).filter((value): value is string => !!value))
  const earlier = dates[4]!
  const later = dates[5]!
  await page.getByRole('button', { name: later, exact: true }).click()
  await page.getByRole('button', { name: earlier, exact: true }).click()
  await page.getByRole('button', { name: '确定' }).click()
  await expect.poll(() => requests.length).toBeGreaterThanOrEqual(3)
  for (const module of ['stream', 'mind', 'trend']) {
    const url = requests.findLast((item) => item.pathname.endsWith(`/workbench/${module}`))
    expect(url?.searchParams.get('date_from')).toBe(earlier)
    expect(url?.searchParams.get('date_to')).toBe(later)
  }
  await expect(page.getByRole('button', { name: '工作台时间范围' })).toContainText(`${earlier}—${later}`)
})

test('日期取消、单日确认、清空后的默认范围始终一致', async ({ page }) => {
  await page.goto('/')
  const trigger = page.getByRole('button', { name: '工作台时间范围' })
  const original = await trigger.textContent()
  await trigger.click()
  await page.getByRole('button', { name: '近7天' }).click()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(trigger).toHaveText(original ?? '')

  await trigger.click()
  const selectedDay = await page.locator('.calendar-days [data-date]').first().getAttribute('data-date')
  expect(selectedDay).toBeTruthy()
  await page.getByRole('button', { name: selectedDay!, exact: true }).click()
  const singleDayRequest = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return url.pathname === '/api/v1/workbench/stream'
      && url.searchParams.get('date_from') === selectedDay
      && url.searchParams.get('date_to') === selectedDay
  })
  await page.getByRole('button', { name: '确定' }).click()
  await singleDayRequest
  await expect(trigger).toContainText(`${selectedDay}—${selectedDay}`)

  await trigger.click()
  await page.getByRole('button', { name: '清空' }).click()
  await page.getByRole('button', { name: '确定' }).click()
  await expect(trigger).toHaveText(original ?? '')
})

test('一级标签多选只开放对应二级候选，并在父级取消后清理失效子项', async ({ page }) => {
  await page.goto('/')

  const primaryTrigger = page.getByRole('button', { name: '一级标签', exact: true })
  const secondaryTrigger = page.getByRole('button', { name: '二级标签', exact: true })
  await expect(secondaryTrigger).toBeDisabled()

  await primaryTrigger.click()
  const primaryPanel = page.getByRole('dialog', { name: '选择一级标签' })
  await primaryPanel.getByRole('checkbox', { name: '外观设计' }).check()
  await expect(secondaryTrigger).toBeEnabled()

  await secondaryTrigger.click()
  const secondaryPanel = page.getByRole('dialog', { name: '选择二级标签' })
  await expect(secondaryPanel.getByRole('checkbox', { name: '外观设计 / 颜色与配色' })).toBeVisible()
  await expect(secondaryPanel.getByText('电池、续航与充电 / 续航里程')).toHaveCount(0)

  await primaryTrigger.click()
  await primaryPanel.getByRole('checkbox', { name: '电池、续航与充电' }).check()
  await secondaryTrigger.click()
  await expect(secondaryPanel.getByRole('checkbox', { name: '电池、续航与充电 / 续航里程' })).toBeVisible()
  await secondaryPanel.getByRole('checkbox', { name: '电池、续航与充电 / 续航里程' }).check()
  await expect(secondaryTrigger).toContainText('续航里程')

  await primaryTrigger.click()
  await primaryPanel.getByRole('checkbox', { name: '电池、续航与充电' }).uncheck()
  await expect(secondaryTrigger).toContainText('全部二级标签')
})

test('筛选后的后端结果同步替换三个模块，重置后恢复', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.stream-list article')).toHaveCount(1)
  await expect(page.locator('.mind-card .radar-accessible-list > button')).toHaveCount(2)
  await expect(page.locator('.trend-card .kpis > div').first()).toContainText('120')

  await page.getByRole('button', { name: '情感', exact: true }).click()
  await page.getByRole('checkbox', { name: '负面' }).check()
  await expect(page.locator('.stream-card')).toContainText('当前筛选范围暂无声音记录')
  await expect(page.locator('.mind-card')).toContainText('当前筛选范围暂无可统计的用户心智')
  await expect(page.locator('.trend-card .kpis > div').first()).toContainText('0')
  await expect(page.locator('.trend-card')).toContainText('当前时间范围暂无可展示的 UGC 声量')

  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.locator('.stream-list article')).toHaveCount(1)
  await expect(page.locator('.mind-card .radar-accessible-list > button')).toHaveCount(2)
  await expect(page.locator('.trend-card .kpis > div').first()).toContainText('120')
})

test('新筛选请求失败时不把上一筛选结果冒充当前数据', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.stream-cycle:first-child article')).toHaveCount(1)
  await expect(page.locator('.mind-card .radar-accessible-list > button')).toHaveCount(2)
  await expect(page.locator('.trend-card .kpis > div').first()).toContainText('120')

  await page.getByRole('button', { name: '情感', exact: true }).click()
  await page.getByRole('checkbox', { name: '混合' }).check()

  await expect(page.getByText('声音流暂时无法更新')).toBeVisible()
  await expect(page.getByText('品牌用户心智暂时无法更新')).toBeVisible()
  await expect(page.getByText('趋势数据暂时无法更新')).toBeVisible()
  await expect(page.locator('.module-state--inline')).toHaveCount(0)
  await expect(page.locator('.stream-cycle:first-child article')).toHaveCount(0)
  await expect(page.locator('.mind-card .radar-accessible-list > button')).toHaveCount(0)
  await expect(page.locator('.trend-card .kpis > div')).toHaveCount(0)
})

test('品牌心智失败只重试自身，不耦合刷新声音流和趋势', async ({ page }) => {
  let failMind = true
  const reads = { stream: 0, mind: 0, trend: 0 }
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (path.endsWith('/workbench/stream')) reads.stream += 1
    if (path.endsWith('/workbench/mind')) reads.mind += 1
    if (path.endsWith('/workbench/trend')) reads.trend += 1
  })
  await page.route('**/api/v1/workbench/mind**', async (route) => {
    if (failMind) {
      failMind = false
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify(temporaryError) })
      return
    }
    await route.fallback()
  })
  await page.goto('/')
  await expect(page.getByText('品牌用户心智暂时无法更新')).toBeVisible()
  const beforeRetry = { ...reads }

  await page.locator('.mind-card').getByRole('button', { name: '重试' }).click()

  await expect(page.getByText('品牌用户心智暂时无法更新')).toHaveCount(0)
  await expect(page.locator('.mind-card .radar-accessible-list > button')).toHaveCount(2)
  expect(reads.mind).toBe(beforeRetry.mind + 1)
  expect(reads.stream).toBe(beforeRetry.stream)
  expect(reads.trend).toBe(beforeRetry.trend)
})

test('声音流展示完整返回列表并自动向上滚动，悬停、聚焦和减少动画时暂停', async ({ page }) => {
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: Array.from({ length: 18 }, (_, index) => ({
          content_id: `44444444-4444-4444-8444-${String(index + 1).padStart(12, '0')}`,
          platform: 'xiaohongshu',
          author_display_name: `用户${index + 1}`,
          published_at: '2026-09-26T15:30:00+08:00',
          text: `第${index + 1}条真实用户声音`,
          sentiment: '正面',
          voice_type: '真实用户发声',
          labels: [],
          analysis_current: true,
          vehicle_names: [],
        })),
      }),
    })
  })
  await page.goto('/')
  const list = page.getByRole('region', { name: '声音流列表' })
  await expect(list.locator('.stream-cycle:first-child article')).toHaveCount(18)
  await expect(page.locator('.stream-card > footer')).toContainText('本页 18 条')
  await expect(list.locator('.stream-cycle:first-child time').first()).toContainText('09/26 15:30')
  await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(5)

  await list.hover()
  const hoveredAt = await list.evaluate((element) => element.scrollTop)
  await page.waitForTimeout(240)
  expect(await list.evaluate((element) => element.scrollTop)).toBe(hoveredAt)

  await page.mouse.move(0, 0)
  await list.focus()
  const focusedAt = await list.evaluate((element) => element.scrollTop)
  await page.waitForTimeout(240)
  expect(await list.evaluate((element) => element.scrollTop)).toBe(focusedAt)

  await page.getByRole('heading', { name: '工作台', exact: true }).click()
  await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(focusedAt + 5)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const reducedAt = await list.evaluate((element) => element.scrollTop)
  await page.waitForTimeout(240)
  expect(await list.evaluate((element) => element.scrollTop)).toBe(reducedAt)
})

test('声音流滚完一页后使用签名游标继续下一页，末页不会重复上一页', async ({ page }) => {
  const requestCursors: Array<string | null> = []
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    const cursor = new URL(route.request().url()).searchParams.get('cursor')
    requestCursors.push(cursor)
    const secondPage = cursor === 'signed-page-2'
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: Array.from({ length: 12 }, (_, index) => ({
          content_id: `44444444-4444-4444-${secondPage ? '9444' : '8444'}-${String(index + 1).padStart(12, '0')}`,
          platform: index % 2 ? 'douyin' : 'xiaohongshu',
          author_display_name: `用户${index + 1}`,
          published_at: `2026-09-${secondPage ? '25' : '26'}T15:30:00+08:00`,
          text: `${secondPage ? '第二页' : '第一页'}第${index + 1}条声音`,
          sentiment: '正面',
          voice_type: '真实用户发声',
          labels: [],
          analysis_current: true,
          vehicle_names: [],
        })),
        next_cursor: secondPage ? null : 'signed-page-2',
        has_more: !secondPage,
      }),
    })
  })
  await page.goto('/')
  const list = page.getByRole('region', { name: '声音流列表' })
  await expect(list.locator('.stream-cycle:first-child')).toContainText('第一页第1条声音')
  const cycleHeight = await list.locator('.stream-cycle:first-child').evaluate(
    (element) => (element as HTMLElement).offsetHeight + 6,
  )
  await list.evaluate((element, target) => { element.scrollTop = target - 1 }, cycleHeight)

  await expect.poll(() => requestCursors.includes('signed-page-2')).toBe(true)
  await expect(list.locator('.stream-cycle:first-child')).toContainText('第二页第1条声音')
  await expect(list.locator('.stream-cycle:first-child')).not.toContainText('第一页第1条声音')
})

test('短声音流按 Figma 连续滚动，平台标识复用声音广场样式', async ({ page }) => {
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        analysis_scheme_version_id: schemeId,
        taxonomy_sha256: taxonomyHash,
        as_of: '2026-09-27T08:10:00+08:00',
        items: ['xiaohongshu', 'douyin', 'bilibili'].map((platform, index) => ({
          content_id: `44444444-4444-4444-8444-${String(index + 1).padStart(12, '0')}`,
          platform,
          author_display_name: `用户${index + 1}`,
          published_at: '2026-09-26T15:30:00+08:00',
          text: `第${index + 1}条声音`,
          sentiment: '正面',
          voice_type: '真实用户发声',
          labels: [],
          analysis_current: true,
          vehicle_names: [],
        })),
      }),
    })
  })
  await page.goto('/')
  const list = page.getByRole('region', { name: '声音流列表' })
  await expect(list.locator('.stream-cycle:first-child article')).toHaveCount(3)
  await expect(list.locator('.stream-cycle:first-child .platform-mark')).toHaveText(['书', '抖', 'B'])
  await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(5)
})

test('页面保持可见时按 15 秒补读聚合且不重置声音流游标', async ({ page }) => {
  await page.clock.install()
  const requests: string[] = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (['stream', 'mind', 'trend'].some((module) => path.endsWith(`/workbench/${module}`))) requests.push(path)
  })
  await page.goto('/')
  await expect.poll(() => requests.length).toBeGreaterThanOrEqual(3)
  const initialStream = requests.filter((path) => path.endsWith('/stream')).length
  const initialMind = requests.filter((path) => path.endsWith('/mind')).length
  const initialTrend = requests.filter((path) => path.endsWith('/trend')).length
  await page.clock.fastForward(15_000)
  await expect.poll(() => requests.filter((path) => path.endsWith('/mind')).length)
    .toBeGreaterThanOrEqual(initialMind + 1)
  await expect.poll(() => requests.filter((path) => path.endsWith('/trend')).length)
    .toBeGreaterThanOrEqual(initialTrend + 1)
  expect(requests.filter((path) => path.endsWith('/stream'))).toHaveLength(initialStream)
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
  await expect(page.getByText('工作台布局已保存。')).toHaveCount(0, { timeout: 4_000 })
  await expect(page.getByRole('button', { name: '+ 编辑工作台' })).toBeVisible()
})

test('趋势模块横向按单列缩放，窄模块内部自适应且不重叠', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByRole('button', { name: '+ 编辑工作台' }).click()
  const trendShell = page.locator('.module-shell').filter({ has: page.getByRole('heading', { name: 'UGC 声量与情感趋势' }) })
  const handle = trendShell.getByRole('button', { name: '调整模块尺寸' })
  await handle.scrollIntoViewIfNeeded()
  const handleBox = await handle.boundingBox()
  expect(handleBox).not.toBeNull()
  await page.mouse.move((handleBox?.x ?? 0) + 12, (handleBox?.y ?? 0) + 12)
  await page.mouse.down()
  await page.mouse.move((handleBox?.x ?? 0) - 320, (handleBox?.y ?? 0) + 12, { steps: 12 })
  await page.mouse.up()

  const [mainBox, asideBox] = await Promise.all([
    trendShell.locator('.trend-main').boundingBox(),
    trendShell.locator('aside').boundingBox(),
  ])
  expect(mainBox).not.toBeNull()
  expect(asideBox).not.toBeNull()
  expect(asideBox?.y ?? 0).toBeGreaterThanOrEqual((mainBox?.y ?? 0) + (mainBox?.height ?? 0) - 1)

  const saveRequest = page.waitForRequest((request) =>
    request.method() === 'PUT' && new URL(request.url()).pathname === '/api/v1/workbench/layout')
  await page.getByRole('button', { name: '保存完成' }).click()
  const request = await saveRequest
  const payload = request.postDataJSON() as { modules: typeof modules }
  expect(payload.modules.find((item) => item.module_id === 'ugc-trend')?.column_span).toBe(4)
  expect(payload.modules.find((item) => item.module_id === 'sound-stream')?.column_span).toBe(6)
  expect(payload.modules.find((item) => item.module_id === 'brand-mind')?.column_span).toBe(6)
})

test('三个模块在各自最窄宽度下独立重排且不产生横向溢出', async ({ page }) => {
  await page.unroute('**/api/v1/workbench/layout')
  await page.route('**/api/v1/workbench/layout', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        schema_version: 1,
        revision: 4,
        modules: modules.map((item) => ({ ...item, column_span: 4 })),
        updated_at: '2026-09-27T08:12:00+08:00',
      }),
    })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')

  const shells = page.locator('.module-shell')
  await expect(shells).toHaveCount(3)
  for (let index = 0; index < 3; index += 1) {
    const metrics = await shells.nth(index).evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }))
    expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
  }

  const [trendMain, trendAside, mindRanking, mindDetail, streamMain, streamTags] = await Promise.all([
    page.locator('.trend-card .trend-main').boundingBox(),
    page.locator('.trend-card aside').boundingBox(),
    page.locator('.mind-card .mind-radar').boundingBox(),
    page.locator('.mind-card .mind-detail').boundingBox(),
    page.locator('.stream-card .stream-main').first().boundingBox(),
    page.locator('.stream-card .stream-tags').first().boundingBox(),
  ])
  expect(trendAside?.y ?? 0).toBeGreaterThanOrEqual((trendMain?.y ?? 0) + (trendMain?.height ?? 0) - 1)
  expect(mindDetail?.y ?? 0).toBeGreaterThanOrEqual((mindRanking?.y ?? 0) + (mindRanking?.height ?? 0) - 1)
  expect(streamTags?.y ?? 0).toBeGreaterThanOrEqual(streamMain?.y ?? 0)
})

test('品牌心智深链把当前日期和一级标签恢复到声音广场', async ({ page }) => {
  await mockVoicePlazaAfterDeepLink(page)
  await page.goto('/')

  await page.getByRole('button', { name: '查看该心智的用户原声 →' }).click()
  await page.waitForURL((url) =>
    url.pathname === '/voice-plaza' && url.searchParams.get('primary_labels') === '外观设计')

  const url = new URL(page.url())
  expect(url.searchParams.get('primary_labels')).toBe('外观设计')
  expect(url.searchParams.get('published_from')).toBeTruthy()
  expect(url.searchParams.get('published_to')).toBeTruthy()
  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()
})

test('点击声音流笔记携带真实 Content ID 定位声音广场', async ({ page }) => {
  await mockVoicePlazaAfterDeepLink(page)
  await page.goto('/')
  await page.locator('.stream-cycle:first-child article').first().click()
  await page.waitForURL((url) => url.pathname === '/voice-plaza'
    && url.searchParams.get('content_id') === '44444444-4444-4444-8444-444444444444')
})

test('Analysis Run 新结果及终态分别触发工作台合并刷新', async ({ page }) => {
  let runPolls = 0
  let streamReads = 0
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    runPolls += 1
    const finished = runPolls >= 3
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: '55555555-5555-4555-8555-555555555555',
          sequence_no: 1,
          status: finished ? 'succeeded' : 'running',
          target_count: 1,
          stats: { succeeded: runPolls >= 2 ? 1 : 0, failed: 0, stale: 0, cancelled: 0 },
          created_at: '2026-09-27T08:00:00+08:00',
          finished_at: finished ? '2026-09-27T08:10:00+08:00' : null,
        }],
      }),
    })
  })
  await page.route('**/api/v1/workbench/stream**', async (route) => {
    streamReads += 1
    await route.fallback()
  })

  await page.goto('/')
  await expect.poll(() => runPolls).toBeGreaterThanOrEqual(3)
  await expect.poll(() => streamReads).toBeGreaterThanOrEqual(3)
  expect(streamReads).toBeLessThanOrEqual(4)
})

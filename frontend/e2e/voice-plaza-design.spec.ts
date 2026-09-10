import { expect, test, type Page } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'

const contentId = '42345678-1234-5678-1234-567812345678'
const content = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'voice-plaza-figma-1',
  content_type: 'note',
  title: '爱玛 Q7 的坐垫舒适，但续航仍有提升空间',
  text: '日常通勤约 12 公里，坐垫很舒服，希望后续优化低温续航。',
  author_display_name: '测试用户',
  published_at: '2026-08-29T01:42:00Z',
  last_seen_at: '2026-08-29T02:00:00Z',
  content_url: 'https://example.com/voice-plaza-figma-1',
  metrics: {
    like_count: 128,
    comment_count: 18,
    share_count: 6,
    repost_count: null,
    favorite_count: 32,
    play_count: null,
    view_count: 1284,
  },
  analysis: {
    status: 'completed',
    relevance: 'relevant',
    voice_type: '真实用户发声',
    sentiment: '负面',
    labels: [{ primary_label: '产品体验', secondary_label: '续航表现' }],
    analyzed_at: '2026-08-29T02:30:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  effective_relevance: 'relevant',
  relevance_source: 'ai',
  source: { provider_name: 'fixture' },
}

const normalItems = [
  content,
  {
    ...content,
    id: '43345678-1234-5678-1234-567812345678',
    external_content_id: 'voice-plaza-figma-2',
    title: '新提的爱玛露娜，奶油白配色实车比照片更耐看',
    author_display_name: '测试用户 B',
    analysis: { ...content.analysis, sentiment: '正面' },
  },
  {
    ...content,
    id: '44345678-1234-5678-1234-567812345678',
    external_content_id: 'voice-plaza-figma-3',
    title: '同价位怎么选？通勤 20 公里更看重舒适和售后',
    author_display_name: '测试用户 C',
    analysis: { ...content.analysis, sentiment: '中性' },
  },
]

const normalRun = {
  id: '62345678-1234-5678-1234-567812345678',
  planner_job_id: '63345678-1234-5678-1234-567812345678',
  sequence_no: 12,
  status: 'succeeded',
  run_intent: 'manual_reanalysis',
  scope: 'selected',
  target_count: 3,
  shard_count: 1,
  shard_size: 3,
  prompt_version: 'content_labeling_v3',
  prompt_sha256: 'a'.repeat(64),
  taxonomy_sha256: 'b'.repeat(64),
  model_provider: 'openai-compatible',
  model: 'fixture-model',
  generation_config: { temperature: 0 },
  generation_config_hash: 'c'.repeat(64),
  stats: { pending: 0, succeeded: 3, failed: 0, cancelled: 0, stale: 0 },
  shards: [],
  created_at: '2026-08-29T02:00:00Z',
  started_at: '2026-08-29T02:00:01Z',
  finished_at: '2026-08-29T02:00:03Z',
}

test.use({ viewport: { width: 1440, height: 900 } })

/** 为 Design-to-Code 状态测试固定与目标状态无关的能力、Run 和 Export 只读响应。 */
async function stubCommonRoutes(page: Page): Promise<void> {
  await stubVoicePlazaTaxonomy(page)
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: true }),
    })
  })

  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/analysis/content-runs') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })

  await page.route('**/api/v1/data-exports**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/data-exports') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })
}

/** 允许 1px 浏览器布局取整误差地核对 Figma 的正式关键尺寸。 */
function expectNear(actual: number | undefined, expected: number): void {
  expect(actual).toBeDefined()
  expect(Math.abs((actual ?? 0) - expected)).toBeLessThanOrEqual(1)
}

/** 默认使用三行内容；多屏幕检查可传入覆盖全部平台的同结构列表。 */
async function stubNormalContents(page: Page, items = normalItems): Promise<void> {
  await page.route('**/api/v1/contents**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === `/api/v1/contents/${content.id}`) {
      await route.fulfill({ json: { ...content, vehicles: [], media: [], comments: [] } })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items, next_cursor: 'figma-next', has_more: true }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await stubCommonRoutes(page)
})

for (const width of [1180, 1280, 1440, 1600, 1920, 2560]) {
  test(`matches Figma column geometry and keeps the viewport usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const platforms = ['xiaohongshu', 'douyin', 'kuaishou', 'weibo', 'bilibili']
    await stubNormalContents(page, platforms.map((platform, index) => ({
      ...content,
      id: index === 0 ? content.id : `42345678-1234-5678-1234-56781234567${index + 1}`,
      platform,
      author_follower_count: index === 0 ? null : (index + 1) * 12800,
      ...(index === 0 ? {
        title: '爱玛 Q7 长期通勤体验：坐垫舒适、低温续航与充电便利性如何，和爱玛露娜、爱玛探索者跨车型比较，再记录带人骑行与售后沟通中值得持续跟进的问题',
        analysis: { ...content.analysis, labels: [
          { primary_label: '电池、续航与充电', secondary_label: '实际续航表现' },
          { primary_label: '驾乘体验', secondary_label: '坐垫舒适性' },
          { primary_label: '售后服务', secondary_label: '客服与服务态度' },
        ] },
        vehicles: ['爱玛 Q7', '爱玛露娜', '爱玛探索者长续航特别版'].map((display_name, vehicleIndex) => ({
          vehicle_model_id: `52345678-1234-5678-1234-56781234567${vehicleIndex}`,
          display_name, code: `MODEL-${vehicleIndex}`, series_name: '通勤系列', category_name: '电动两轮车', evidences: [],
        })),
      } : {}),
    })))
    await page.goto('/voice-plaza')
    await expect(page.locator('.content-row')).toHaveCount(5)
    for (const [platform, label, mark] of [
      ['xiaohongshu', '小红书', '书'], ['douyin', '抖音', '抖'], ['kuaishou', '快手', '快'],
      ['weibo', '微博', '微'], ['bilibili', 'B站', 'B'],
    ]) {
      const badge = page.locator(`.platform-mark--${platform}`)
      await expect(badge).toHaveText(mark)
      await expect(badge).toHaveAttribute('title', label)
    }
    const table = await page.locator('.content-list').boundingBox()
    expectNear(table?.x, 204)
    expectNear(table?.width, width - 228)
    const expected = [16, Math.max(1212, width - 228) - 836, 76, 190, 230, 110, 110]
    const header = await page.locator('.table-head > *').evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().width))
    const row = await page.locator('.content-row').first().locator(':scope > *').evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().width))
    expected.forEach((size, index) => { expectNear(header[index], size); expectNear(row[index], size) })
    const complexRow = page.locator('.content-row').first()
    await expect(complexRow.locator('.label-tag')).toHaveCount(3)
    await expect(complexRow.locator('.vehicle-cell > div')).toHaveCount(3)
    const fits = await complexRow.evaluate((node) => {
      const bounds = node.getBoundingClientRect()
      return [...node.querySelectorAll<HTMLElement>('.content-title, .label-tag, .vehicle-cell, .row-actions')].every((child) => {
        const box = child.getBoundingClientRect()
        return child.scrollWidth <= child.clientWidth + 1 && box.top >= bounds.top && box.bottom <= bounds.bottom
      })
    })
    expect(fits).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
    await expect(page.locator('.inbox-trigger img')).toHaveJSProperty('naturalWidth', 18)
    await expect(page.locator('.inbox-trigger')).toContainText('消息中心')
    if (width < 1440) {
      await page.locator('.content-list').evaluate((node) => { node.scrollLeft = node.scrollWidth })
      await page.locator('.content-row').first().getByRole('button', { name: '查看详情' }).click()
      await expect(page.getByRole('dialog', { name: '内容详情' })).toBeVisible()
      await page.keyboard.press('Escape')
    }
    if (process.env.AIMA_CAPTURE_VISUAL === '1') await page.screenshot({ path: `test-results/voice-plaza-${width}.png`, fullPage: true, animations: 'disabled' })
  })
}

test('vehicle groups use catalog data and confirm drafts without losing keyboard focus', async ({ page }) => {
  await stubNormalContents(page)
  await page.route('**/api/v1/vehicle-models**', async (route) => route.fulfill({ json: {
    items: [
      { id: 'q7', code: 'Q7', display_name: '爱玛 Q7', series_name: 'Q 系列', category_name: '电动两轮车', aliases: [] },
      { id: 'q8', code: 'Q8', display_name: '爱玛 Q8', series_name: 'Q 系列', category_name: '电动两轮车', aliases: [] },
      { id: 'luna', code: 'LUNA', display_name: '爱玛露娜', series_name: '时尚系列', category_name: '电动两轮车', aliases: [{ text: '奶油白' }] },
    ], total: 3, offset: 0, limit: 200, catalog_version: 2,
  } }))
  await page.goto('/voice-plaza')
  const trigger = page.getByRole('button', { name: '选择车型', exact: true })
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: '选择车型', exact: true })
  expectNear((await dialog.boundingBox())?.width, 620)
  await dialog.getByRole('button', { name: /Q 系列/ }).click()
  await dialog.getByRole('checkbox', { name: '爱玛 Q7', exact: true }).check()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(trigger).toBeFocused()
  await expect(trigger).toContainText('全部车型')
  await trigger.click()
  await dialog.getByLabel('搜索车型').fill('奶油白')
  await expect(dialog.getByRole('checkbox')).toHaveCount(1)
  await dialog.getByRole('checkbox', { name: '爱玛露娜' }).check()
  await dialog.getByRole('button', { name: '确定', exact: true }).click()
  await expect(trigger).toContainText('爱玛露娜')
  const query = page.waitForRequest((request) => new URL(request.url()).searchParams.getAll('vehicle_model_ids').includes('luna'))
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await query
  await trigger.click()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(trigger).toBeFocused()
})

test('date range supports keyboard selection and sends Beijing boundaries only after confirmation', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-09-08T03:00:00Z'))
  await stubNormalContents(page)
  await page.goto('/voice-plaza')
  const trigger = page.getByRole('button', { name: '发布时间范围', exact: true })
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: '选择发布时间范围' })
  await expect(dialog.getByRole('button', { name: '2026-09-08', exact: true })).toBeFocused()
  await page.keyboard.press('ArrowLeft')
  await page.keyboard.press('Enter')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('Enter')
  await dialog.getByRole('button', { name: '确定', exact: true }).click()
  await expect(trigger).toContainText('2026-09-07')
  await expect(trigger).toContainText('2026-09-08')
  const query = page.waitForRequest((request) => new URL(request.url()).searchParams.has('published_from'))
  await page.getByRole('button', { name: '查询', exact: true }).click()
  const params = new URL((await query).url()).searchParams
  expect(params.get('published_from')).toBe('2026-09-06T16:00:00.000Z')
  expect(params.get('published_to')).toBe('2026-09-08T15:59:59.999Z')
  await trigger.click()
  await dialog.getByRole('button', { name: '近30天', exact: true }).click()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(trigger).toContainText('2026-09-07')
})

test('late export catalog initializes defaults without replacing edited columns', async ({ page }) => {
  await stubNormalContents(page)
  let release!: () => void
  const ready = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/export-columns', async (route) => {
    await ready
    await route.fulfill({ json: { version: 1, columns: [{ key: 'platform', label: '平台', sensitive: false, default_selected: true }] } })
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '导出记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(dialog.getByText('列目录加载中…')).toBeVisible()
  release()
  await expect(dialog.getByRole('checkbox', { name: '平台' })).toBeChecked()
  await expect(dialog.getByRole('button', { name: /开始导出/ })).toBeEnabled()
  await dialog.getByRole('checkbox', { name: '平台' }).uncheck()
  await expect(dialog.getByRole('button', { name: /开始导出/ })).toBeDisabled()
  await dialog.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(dialog.getByRole('checkbox', { name: '平台' })).not.toBeChecked()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('button', { name: '导出记录', exact: true })).toBeFocused()
})

test('keeps terminal analysis history out of the formal data canvas and available in the task center', async ({ page }) => {
  await stubNormalContents(page)
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/analysis/content-runs') return route.fallback()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [normalRun] }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()
  await expect(page.getByLabel('AI Analysis Run 历史')).toHaveCount(0)
  await expect(page.getByText('Run #12')).toHaveCount(0)
  await expect(page.locator('.content-row')).toHaveCount(3)
  await expect(page.getByText('标题内容', { exact: true })).toBeVisible()
  await expect(page.locator('.pagination').getByText('已显示 3 条')).toBeVisible()
  await expect(page.getByRole('button', { name: '加载更多 →' })).toBeEnabled()

  await page.getByRole('button', { name: /任务中心/ }).click()
  const taskCenter = page.getByRole('complementary', { name: '任务中心' })
  await expect(taskCenter).toBeVisible()
  await expect(taskCenter).toContainText('AI 打标任务 12')
  await expect(taskCenter).toContainText('已完成')

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-normal.png', fullPage: true })
  }
})

test('matches the formal 1440 desktop shell and empty-state composition', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
  await expect(page.getByText('当前没有可加载的下一页，不显示虚构页码。')).toBeVisible()
  await expect(page.getByText('游标分页不会虚构总页数')).toHaveCount(0)
  await expect(page.getByText('标题内容', { exact: true })).toHaveCount(0)
  await expect(page.locator('[data-aima-icon="empty"]')).toBeVisible()

  const sidebar = await page.locator('.sidebar').boundingBox()
  await expect(page.locator('.topbar')).toHaveCount(0)
  const pageHeader = await page.locator('.aima-page-header').boundingBox()
  const filters = await page.locator('.filters').boundingBox()
  const emptyState = await page.locator('.table-state--empty').boundingBox()
  expectNear(sidebar?.width, 180)
  expectNear(pageHeader?.y, 24)
  expectNear(pageHeader?.height, 64)
  expectNear(filters?.width, 1212)
  expectNear(emptyState?.height, 376)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-empty.png', fullPage: true })
  }
})

test('renders the formal loading state while the content request is in flight', async ({ page }) => {
  let releaseContents!: () => void
  const contentRelease = new Promise<void>((resolve) => {
    releaseContents = resolve
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await contentRelease
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('正在加载声音记录…')).toBeVisible()
  await expect(page.getByText('正在获取内容列表、AI 状态与运行记录')).toBeVisible()
  await expect(page.locator('.skeleton')).toHaveCount(3)
  await expect(page.getByText('标题内容', { exact: true })).toHaveCount(0)
  expectNear((await page.locator('.table-state--loading').boundingBox())?.height, 376)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-loading.png', fullPage: true })
  }

  releaseContents()
  await expect(page.getByText('暂无符合条件的内容')).toBeVisible()
})

test('renders the formal error banner and recoverable list error state', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        title: '声音广场暂不可用',
        status: 503,
        detail: '内容列表服务暂不可用，请使用 request_id 联系管理员。',
        request_id: 'req_voice_plaza_figma_error',
        errors: [],
      }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText('加载声音广场失败')).toBeVisible()
  await expect(page.getByText('暂时无法加载声音记录')).toBeVisible()
  await expect(page.getByText('检查网络或服务状态后点击“刷新数据”重试。')).toBeVisible()
  await expect(page.locator('.page-error')).toContainText('req_voice_plaza_figma_error')
  await expect(page.getByText('标题内容', { exact: true })).toHaveCount(0)
  expectNear((await page.locator('.table-state--error').boundingBox())?.height, 306)

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-error.png', fullPage: true })
  }
})

test('keeps the formal runtime-unavailable warning while the content list stays usable', async ({ page }) => {
  await stubNormalContents(page)
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: false }),
    })
  })

  await page.goto('/voice-plaza')
  const warning = page.locator('.capability-warning')
  await expect(warning).toContainText('AI 打标暂不可用：管理员尚未完成 AI 模型配置。')
  await expect(page.getByRole('button', { name: 'AI 分析', exact: true })).toBeDisabled()
  await expect(page.locator('.content-row')).toHaveCount(3)
  await expect(page.getByRole('button', { name: '查看详情' }).first()).toBeEnabled()
  await expect(page.getByRole('button', { name: '查询' })).toBeEnabled()

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-runtime-unavailable.png', fullPage: true })
  }
})

test('matches the formal detail, analysis and export overlay geometry', async ({ page }) => {
  await page.route('**/api/v1/contents**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === `/api/v1/contents/${contentId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...content,
          media: [],
          comments: [],
          comment_coverage: null,
          source_records: [content.source],
          supplement_status: null,
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [content], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        target_count: 1,
        shard_count: 1,
        shard_size: 1,
        prompt_version: 'content_labeling_v3',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '仅在确认创建后产生实际模型调用。',
      }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByRole('button', { name: '查看详情' })).toBeVisible()

  await page.getByRole('button', { name: '查看详情' }).click()
  const drawer = page.getByRole('dialog', { name: '内容详情' })
  await expect(drawer).toBeVisible()
  const drawerBox = await drawer.boundingBox()
  expectNear(drawerBox?.x, 830)
  expectNear(drawerBox?.y, 0)
  expectNear(drawerBox?.width, 610)
  expectNear(drawerBox?.height, 900)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-detail.png', fullPage: true })
  }
  await drawer.getByRole('button', { name: '关闭' }).click()

  await page.getByLabel('选择当前已加载内容').check()
  const analysisButton = page.getByRole('button', { name: 'AI 分析', exact: true })
  await expect(analysisButton).toBeEnabled()
  await analysisButton.click()
  const analysisDialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  await expect(analysisDialog).toBeVisible()
  await expect(analysisDialog.getByText('预计分析 1 条内容 · 1 个分片 · 每片最多 1 条')).toBeVisible()
  await expect(analysisDialog.getByRole('button', { name: '确认开始分析' })).toBeEnabled()
  const analysisBox = await analysisDialog.boundingBox()
  expectNear(analysisBox?.x, 410)
  expectNear(analysisBox?.y, 195)
  expectNear(analysisBox?.width, 620)
  expectNear(analysisBox?.height, 510)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-analysis.png', fullPage: true })
  }
  await analysisDialog.locator('.close-button').click()

  await page.getByRole('button', { name: '导出记录' }).click()
  const exportDialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(exportDialog).toBeVisible()
  const exportBox = await exportDialog.boundingBox()
  expectNear(exportBox?.x, 440)
  expectNear(exportBox?.y, 115.5)
  expectNear(exportBox?.width, 560)
  expectNear(exportBox?.height, 669)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/voice-plaza-figma-export.png', fullPage: true })
  }
})

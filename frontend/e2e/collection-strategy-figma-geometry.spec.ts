import { expect, test, type Locator, type Page } from './fixture'

const packId = '11111111-1111-4111-8111-111111111111'
const secondaryPackId = '22222222-2222-4222-8222-222222222222'
const planId = '33333333-3333-4333-8333-333333333333'
const providerId = '44444444-4444-4444-8444-444444444444'
const activeBrandId = '88888888-8888-4888-8888-888888888888'

const packs = [
  { id: packId, name: '爱玛品牌词包', description: '新品车型及用户讨论', enabled: true, version: 4, keyword_count: 28 },
  { id: secondaryPackId, name: '门店活动词包', description: '门店活动与用户讨论发现', enabled: true, version: 2, keyword_count: 16 },
]
const activeBrand = {
  id: activeBrandId,
  code: 'AIMA',
  display_name: '爱玛',
  role: 'owned',
  status: 'active',
  version: 1,
  catalog_version: 18,
  aliases: [],
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-28T00:00:00Z',
}

const plan = {
  id: planId,
  name: '爱玛新品口碑追踪',
  enabled: true,
  schedule_expr: '0 */6 * * *',
  timezone: 'Asia/Shanghai',
  schedule_version: 3,
  next_run_at: '2026-08-28T01:00:00Z',
  last_scheduled_at: null,
  detail_policy: 'on_change',
  comment_policy: 'adaptive',
  platforms: [{ platform: 'xiaohongshu', provider_config_id: providerId, search_config: {} }],
  keyword_pack_ids: [packId],
  brand_ids: [activeBrandId],
  created_at: '2026-08-21T00:00:00Z',
  updated_at: '2026-08-21T00:00:00Z',
}

async function mockStrategyApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (url.pathname === '/api/v1/principal') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          principal_id: 'admin-1',
          display_name: '爱玛',
          role: 'administrator',
          source: 'development',
          is_administrator: true,
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/notifications') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [], unread_count: 0 }) })
      return
    }
    if (url.pathname === '/api/v1/keyword-packs' && request.method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: packs, total: 2, offset: 0, limit: Number(url.searchParams.get('limit') ?? '20') }),
      })
      return
    }
    if (url.pathname === `/api/v1/keyword-packs/${packId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...packs[0],
          keywords: [
            { id: 'kw-1', text: '爱玛 Q7', platform_scope: 'all', enabled: true, priority: 100, note: '' },
            { id: 'kw-2', text: '爱玛电动车', platform_scope: 'all', enabled: true, priority: 100, note: '' },
            { id: 'kw-3', text: '爱玛门店', platform_scope: 'all', enabled: true, priority: 100, note: '' },
          ],
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/vehicle-brands' && request.method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [activeBrand], total: 1, catalog_version: 18, offset: 0, limit: 200 }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-capabilities') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          provider_configs: [{ id: providerId, provider: 'tikhub', display_name: '主采集渠道' }],
          capabilities: [{
            provider: 'tikhub',
            platform: 'xiaohongshu',
            operations: ['keyword_search'],
            search: {
              supported_sort_modes: ['latest'],
              supported_time_filters: ['1d'],
              supported_duration_filters: [],
              supported_content_types: ['all'],
              manual_default: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
            },
          }],
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/collection-plans' && request.method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [plan], total: 24, enabled_count: 18, offset: 0, limit: 20 }),
      })
      return
    }

    await route.fulfill({ status: 404, body: 'not mocked' })
  })
}

async function expectBox(
  locator: Locator,
  expected: { x?: number; y?: number; width?: number; height?: number },
): Promise<void> {
  await expect(locator).toBeVisible()
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  for (const [key, value] of Object.entries(expected)) {
    const actual = box?.[key as keyof typeof expected]
    expect(Math.abs(Number(actual) - Number(value)), `${key}: ${actual} ≈ ${value}`).toBeLessThanOrEqual(1)
  }
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockStrategyApi(page)
})

test('matches the formal 1440×900 Figma geometry for the strategy workspace', async ({ page }) => {
  await page.goto('/collection-strategy')

  await expectBox(page.locator('.aima-page-header'), { x: 204, y: 28, width: 1212, height: 64 })
  await expectBox(page.locator('.strategy-summary'), { x: 204, y: 112, width: 1212, height: 88 })
  await expectBox(page.locator('.tabs'), { x: 204, y: 220, width: 1212, height: 46 })
  await expectBox(page.locator('.filters'), { x: 204, y: 286, width: 1212, height: 72 })
  await expectBox(page.locator('.plan-card > .aima-feedback'), { x: 204, y: 378, width: 1212, height: 44 })
  await expectBox(page.locator('.table-wrap'), { x: 204, y: 484, width: 1212, height: 227 })

  await page.getByRole('button', { name: '关键词包' }).click()
  await expectBox(page.locator('.panel-grid'), { x: 204, y: 286, width: 1212 })
  await expectBox(page.locator('.table-card'), { x: 204, y: 286, width: 823 })
  await expectBox(page.locator('.detail-card'), { x: 1043, y: 286, width: 373 })
  await expectBox(page.locator('.table-head'), { height: 54 })
  await expectBox(page.locator('.pack-row').first(), { height: 74 })
  await expect(page.locator('.detail-card').getByRole('button', { name: '编辑', exact: true })).toBeVisible()
})

test('matches the formal keyword modal and collection plan drawer geometry', async ({ page }) => {
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包' }).click()
  await page.locator('.table-head').getByRole('button', { name: /新建词包/ }).click()

  const packDialog = page.getByRole('dialog', { name: '新建关键词包' })
  await expectBox(packDialog, { x: 405, y: 187, width: 630, height: 526 })
  await expectBox(packDialog.locator('textarea'), { height: 120 })
  await expectBox(packDialog.locator('footer'), { height: 76 })
  await packDialog.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: /新建采集计划/ }).click()
  const drawer = page.getByRole('dialog', { name: '新建采集计划' })
  await expectBox(drawer, { x: 930, y: 0, width: 510, height: 900 })
  await expectBox(drawer.locator('header'), { height: 84 })
  await expectBox(drawer.locator('.body'), { y: 84, height: 742 })
  await expectBox(drawer.locator('footer'), { y: 826, height: 74 })
  await expectBox(drawer.locator('.platform').first(), { height: 68 })

  await drawer.getByText('指定品牌', { exact: true }).click()
  const brandSelect = drawer.locator('.brand-select')
  await expect(brandSelect).toHaveCSS('border-top-width', '0px')
  await expect(brandSelect.locator('.brand-select__options label').first()).toHaveCSS('border-top-width', '0px')
  await expectBox(brandSelect.locator('.brand-select__options label').first(), { height: 32 })
})

test('removes the global relevance entry and matches the formal plan detail drawer geometry', async ({ page }) => {
  await page.goto('/collection-strategy')
  await expect(page.getByRole('button', { name: '全局相关性' })).toHaveCount(0)

  const planRow = page.locator('.plan-table tbody tr').filter({ hasText: '爱玛新品口碑追踪' })
  await planRow.getByRole('button', { name: '查看详情' }).click()

  const detail = page.getByRole('dialog', { name: '采集计划详情' })
  await expectBox(detail, { x: 990, y: 0, width: 450, height: 900 })
  await expectBox(detail.locator('header'), { height: 84 })
  await expectBox(detail.locator('.body'), { y: 84, height: 816 })
  await expectBox(detail.locator('dl > div').first(), { width: 196 })
  await expectBox(detail.locator('dl > div').nth(1), { width: 196 })
})

test('keeps compact strategy panels inside the workspace and long keywords inside their card', async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 900 })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  const card = page.locator('.detail-card')
  await expect(card).toBeVisible()
  const box = await card.boundingBox()
  expect(box!.x + box!.width).toBeLessThanOrEqual(1157)
})

test('preserves keyword pack edit, copy and add drafts after rejected requests', async ({ page }) => {
  await page.route('**/api/v1/keyword-packs/**', async (route) => {
    if (route.request().method() === 'GET') return route.fallback()
    await route.fulfill({ status: 409, json: { status: 409, title: 'Conflict', detail: '测试保存冲突，请重试。', request_id: 'strategy-draft-conflict' } })
  })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  const detail = page.locator('.detail-card')
  await detail.getByRole('button', { name: '编辑', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '编辑关键词包' })
  await expect(editor.getByLabel('词包名称', { exact: true })).toHaveValue(packs[0]!.name)
  await editor.getByLabel('词包名称', { exact: true }).fill('保留名称草稿')
  await editor.getByRole('button', { name: '保存词包', exact: true }).click()
  await expect(editor.getByRole('alert')).toBeVisible()
  await expect(editor.getByLabel('词包名称', { exact: true })).toHaveValue('保留名称草稿')
  await editor.getByRole('button', { name: '取消', exact: true }).click()
  await detail.getByRole('button', { name: '复制', exact: true }).click()
  await detail.getByLabel('副本名称').clear()
  await expect(detail.getByLabel('副本名称')).toBeVisible()
  await detail.getByLabel('副本名称').fill('保留副本草稿')
  await detail.getByRole('button', { name: '创建副本' }).click()
  await expect(detail.getByLabel('副本名称')).toHaveValue('保留副本草稿')
  await detail.getByRole('button', { name: '取消', exact: true }).click()
  await detail.getByRole('button', { name: '编辑', exact: true }).click()
  await editor.getByLabel('关键词（每行一个）').fill('保留新增关键词')
  await editor.getByRole('button', { name: '保存词包', exact: true }).click()
  await expect(editor.getByRole('textbox', { name: /^关键词 \d+$/ }).last()).toHaveValue('保留新增关键词')
})

for (const memberCount of [1, 501]) {
test(`edits a ${memberCount}-member existing pack in the shared dialog without changing original attributes`, async ({ page }) => {
  const members = Array.from({ length: memberCount }, (_, i) => ({ text: `爱玛 Q7 ${i}`, platform_scope: 'all', enabled: true, priority: 100, note: '  保留备注  ' }))
  const original = { ...packs[0]!, keywords: members.map((item, i) => ({ ...item, id: `kw-${i}` })) }
  let current = original
  let submitted: unknown
  await page.route(`**/api/v1/keyword-packs/${packId}`, async (route) => {
    if (route.request().method() === 'PUT') {
      submitted = route.request().postDataJSON()
      current = { ...original, name: '更新后的词包', description: '更新后的说明', version: 5 }
    }
    await route.fulfill({ json: current })
  })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  await page.locator('.detail-card').getByRole('button', { name: '编辑', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '编辑关键词包' })
  await expectBox(editor, { x: 405, y: 187, width: 630, height: 526 })
  await expect(editor.getByLabel('词包名称', { exact: true })).toHaveValue(original.name)
  await expect(editor.getByLabel('描述', { exact: true })).toHaveValue(original.description)
  await expect(editor.getByRole('textbox', { name: '关键词 1', exact: true })).toBeDisabled()
  await expect(editor.getByRole('button', { name: '移除关键词 1', exact: true })).toBeDisabled()
  await editor.getByLabel('词包名称', { exact: true }).fill('更新后的词包')
  await editor.getByLabel('描述', { exact: true }).fill('更新后的说明')
  await page.screenshot({ path: '../.runtime/strategy-figma-test/keyword-edit-modal.png', fullPage: true })
  await editor.getByRole('button', { name: '保存词包', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(submitted).toEqual({ expected_version: 4, name: '更新后的词包', description: '更新后的说明', keywords: members })
  await expect(page.locator('.detail-card')).toContainText('更新后的词包')
  await expect(page.locator('.detail-card')).toContainText('v5')
})
}

test('opens complete current pack details from plan references and returns to the plan', async ({ page }) => {
  let rejectNextDetail = false
  await page.route(`**/api/v1/keyword-packs/${packId}`, async (route) => {
    if (rejectNextDetail) {
      rejectNextDetail = false
      return route.fulfill({ status: 503, json: { status: 503, title: 'Unavailable', detail: '资源详情暂时不可用，请重试。', request_id: 'resource-detail-retry' } })
    }
    await route.fulfill({ json: {
      ...packs[0], keywords: Array.from({ length: 35 }, (_, index) => ({
        id: `keyword-${index}`, text: `完整关键词 ${index + 1}`, platform_scope: 'xiaohongshu',
        priority: index + 1, enabled: index !== 34, note: `完整备注 ${index + 1}`,
      })),
    } })
  })
  await page.goto('/collection-strategy')
  await page.locator('.table-wrap').getByRole('button', { name: '查看' }).first().click()
  const planDetail = page.getByRole('dialog', { name: '采集计划详情' })
  const packLink = planDetail.getByRole('button', { name: '爱玛品牌词包 · v4' })
  rejectNextDetail = true
  await packLink.click()
  const packDetail = page.getByRole('dialog', { name: '关键词包详情', exact: true })
  await expect(packDetail.getByRole('alert')).toContainText('资源详情暂时不可用')
  await packDetail.getByRole('button', { name: '重试', exact: true }).click()
  await expect(packDetail).toContainText('当前配置')
  await expect(packDetail).toContainText('新品车型及用户讨论')
  await expect(packDetail).toContainText('完整关键词 35')
  await expect(packDetail).toContainText('完整备注 35')
  await expect(packDetail.getByRole('row').last()).toContainText('已停用')
  await page.keyboard.press('Escape')
  await expect(packDetail).toBeHidden()
  await expect(packLink).toBeFocused()
  await expect(planDetail.getByRole('heading', { name: '内容过滤条件 · 品牌' })).toBeVisible()
  await expect(planDetail.getByText('爱玛 · 自有')).toBeVisible()
  await expect(planDetail.getByRole('button', { name: /车型/ })).toHaveCount(0)
  await expect(planDetail).toBeVisible()
})

test('preserves plan copy drafts and displays the failure inside the detail drawer', async ({ page }) => {
  await page.route('**/api/v1/collection-plans/*/copy', async (route) => {
    await route.fulfill({ status: 409, json: { status: 409, title: 'Conflict', detail: '计划名称冲突，请修改后重试。', request_id: 'plan-copy-conflict' } })
  })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '采集计划详情' })
  await detail.getByRole('button', { name: '复制', exact: true }).click()
  await detail.getByLabel('副本名称').clear()
  await expect(detail.getByLabel('副本名称')).toBeVisible()
  await detail.getByLabel('副本名称').fill('计划副本草稿')
  await detail.getByRole('button', { name: '创建副本' }).click()
  await expect(detail.getByRole('alert')).toContainText('计划名称冲突')
  await expect(detail.getByLabel('副本名称')).toHaveValue('计划副本草稿')
})

test('supports Escape and returns keyboard focus for every strategy overlay', async ({ page }) => {
  await page.goto('/collection-strategy')
  const create = page.getByRole('button', { name: '新建采集计划', exact: true })
  await create.click()
  await expect(page.getByRole('dialog', { name: '新建采集计划', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '新建采集计划', exact: true })).toHaveCount(0)
  await expect(create).toBeFocused()
  const detail = page.getByRole('button', { name: '查看详情' })
  await detail.click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '采集计划详情' })).toHaveCount(0)
  await expect(detail).toBeFocused()
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  const pack = page.getByRole('button', { name: '新建词包' })
  await pack.click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '新建关键词包' })).toHaveCount(0)
  await expect(pack).toBeFocused()
})

test('edits the selected plan through a single drawer and preserves its identity', async ({ page }) => {
  await page.route(`**/api/v1/collection-plans/${planId}`, async (route) => {
    await route.fulfill({ json: { ...plan, name: '编辑后的计划', schedule_version: 4 } })
  })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '查看详情' }).click()
  await page.getByRole('button', { name: '编辑计划', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '编辑采集计划', exact: true })
  await expect(editor).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await expect(editor.getByText('指定品牌', { exact: true })).toBeVisible()
  await expect(editor.getByText('爱玛', { exact: true })).toBeVisible()
  await editor.getByPlaceholder('例如：爱玛新品口碑追踪').fill('编辑后的计划')
  await editor.getByLabel('小红书排序').selectOption('latest')
  await editor.getByLabel('小红书发布时间').selectOption('1d')
  await editor.getByLabel('小红书内容类型').selectOption('all')
  const request = page.waitForRequest((item) => new URL(item.url()).pathname === `/api/v1/collection-plans/${planId}` && item.method() === 'PUT')
  await editor.getByRole('button', { name: '保存计划修改' }).click()
  const payload = (await request).postDataJSON()
  expect(payload).toMatchObject({
    name: '编辑后的计划',
    expected_version: 3,
    brand_ids: [activeBrandId],
  })
  expect(payload).not.toHaveProperty('vehicle_model_ids')
  await expect(editor).toHaveCount(0)
})

test('keeps long plan names and filters readable across supported desktop widths', async ({ page }) => {
  await page.route('**/api/v1/collection-plans?*', async (route) => {
    await route.fulfill({ json: { items: [{ ...plan, name: 'PlanLongName'.repeat(15) }], total: 1, enabled_count: 1, offset: 0, limit: 20 } })
  })
  await page.goto('/collection-strategy')
  await expect(page.getByRole('button', { name: '查看详情' })).toBeVisible()
  for (const width of [1100, 1180, 1200, 1260, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 })
    const geometry = await page.locator('.plan-table tbody td').evaluateAll((cells) => cells.map((cell) => ({ scroll: cell.scrollWidth, client: cell.clientWidth })))
    for (const cell of geometry) expect(cell.scroll).toBeLessThanOrEqual(cell.client + 1)
    const overflow = await page.locator('.workspace-main').evaluate((node) => node.scrollWidth - node.clientWidth)
    expect(overflow, `workspace at ${width}`).toBeLessThanOrEqual(1)
    await expect(page.getByRole('button', { name: '查询', exact: true })).toBeInViewport()
    await page.locator('.table-wrap').evaluate((node) => { node.scrollLeft = node.scrollWidth })
    await expect(page.locator('.table-wrap').getByRole('button', { name: '查看详情', exact: true }).first()).toBeInViewport()
  }
})

test('keeps keyword edits and creation inputs visible after server validation fails', async ({ page }) => {
  await page.route('**/api/v1/keyword-packs/**', async (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: { ...packs[0], enabled: false, keywords: [{ id: 'kw-1', text: '爱玛 Q7', platform_scope: 'all', enabled: true, priority: 100, note: '' }] } })
    }
    await route.fulfill({ status: 409, json: { status: 409, title: 'Conflict', detail: '词包版本已变化，请核对后重试。', request_id: 'keyword-edit-conflict' } })
  })
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  const detail = page.locator('.detail-card')
  await detail.getByRole('button', { name: '编辑', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '编辑关键词包' })
  await editor.getByRole('textbox', { name: '关键词 1', exact: true }).fill('待保存关键词')
  await editor.getByRole('button', { name: '保存词包', exact: true }).click()
  await expect(editor.getByRole('alert')).toContainText('词包版本已变化')
  await expect(editor.getByRole('textbox', { name: '关键词 1', exact: true })).toHaveValue('待保存关键词')
  await editor.getByRole('button', { name: '关闭', exact: true }).click()
  await page.route('**/api/v1/keyword-packs', async (route) => {
    if (route.request().method() === 'GET') return route.fallback()
    await route.fulfill({ status: 409, json: { status: 409, title: 'Conflict', detail: '词包名称已存在。', request_id: 'pack-create-conflict' } })
  })
  await page.getByRole('button', { name: '新建词包' }).click()
  const dialog = page.getByRole('dialog', { name: '新建关键词包' })
  await dialog.getByLabel('词包名称', { exact: true }).fill('保留创建草稿')
  await dialog.getByLabel('关键词（每行一个）').fill('爱玛')
  await dialog.getByRole('button', { name: '保存词包' }).click()
  await expect(dialog.getByRole('alert')).toContainText('词包名称已存在')
  await expect(dialog.getByLabel('词包名称', { exact: true })).toHaveValue('保留创建草稿')
  await expect(dialog.getByRole('button', { name: '保存词包' })).toBeInViewport()
})

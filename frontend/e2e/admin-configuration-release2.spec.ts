import type {
  AnalysisSchemeResponse,
  BrandResponse,
  ProviderConfigResponse,
  VehicleModelResponse,
} from '../src/generated/api/client'
import { expect, test, type Page, type Route } from './fixture'

const now = '2026-09-17T12:00:00+08:00'
const brandId = '81111111-1111-4111-8111-111111111111'
const schemeId = '82111111-1111-4111-8111-111111111111'
const versionId = '83111111-1111-4111-8111-111111111111'

function provider(kind: 'llm' | 'collection'): ProviderConfigResponse {
  return {
    id: kind === 'llm'
      ? '84111111-1111-4111-8111-111111111111'
      : '84111111-1111-4111-8111-222222222222',
    provider_kind: kind,
    provider: kind === 'llm' ? 'openai_compatible' : 'tikhub',
    display_name: kind === 'llm' ? '默认 AI 模型' : 'TikHub 默认配置',
    base_url: kind === 'llm' ? 'https://provider.example/v1' : 'https://api.tikhub.io',
    model: kind === 'llm' ? 'deepseek-chat' : null,
    enabled: true,
    is_default: kind === 'llm',
    timeout_seconds: 45,
    max_retries: 3,
    max_concurrency: 5,
    max_rps: null,
    revision: 1,
    secret_configured: true,
  }
}

const brands: BrandResponse[] = [
  {
    id: brandId,
    code: 'AIMA',
    display_name: '爱玛',
    role: 'owned',
    status: 'active',
    version: 1,
    catalog_version: 18,
    aliases: [
      { id: '85111111-1111-4111-8111-111111111111', text: '爱玛', normalized_text: '爱玛' },
      { id: '85111111-1111-4111-8111-222222222222', text: 'AIMA', normalized_text: 'aima' },
      { id: '85111111-1111-4111-8111-333333333333', text: '爱玛电动车', normalized_text: '爱玛电动车' },
    ],
    created_at: now,
    updated_at: now,
  },
  {
    id: '81111111-1111-4111-8111-222222222222',
    code: 'YADEA',
    display_name: '雅迪',
    role: 'competitor',
    status: 'active',
    version: 1,
    catalog_version: 18,
    aliases: [
      { id: '85111111-1111-4111-8111-444444444444', text: '雅迪', normalized_text: '雅迪' },
      { id: '85111111-1111-4111-8111-555555555555', text: 'YADEA', normalized_text: 'yadea' },
    ],
    created_at: now,
    updated_at: now,
  },
]

const vehicles: VehicleModelResponse[] = [
  {
    id: '86111111-1111-4111-8111-111111111111',
    code: 'AIMA-MDOU-AIR',
    display_name: 'M豆Air',
    status: 'active',
    version: 1,
    catalog_version: 18,
    referenced: true,
    series_name: '时尚女性系列',
    category_name: '通勤',
    aliases: [{ id: '87111111-1111-4111-8111-111111111111', text: 'M豆 Air', normalized_text: 'm豆 air' }],
    brand_id: brandId,
    keyword_pack_ids: [],
    created_at: now,
    updated_at: now,
  },
  {
    id: '86111111-1111-4111-8111-222222222222',
    code: 'AIMA-XIAI-PRO',
    display_name: '喜爱2026Pro-Z',
    status: 'active',
    version: 1,
    catalog_version: 18,
    referenced: false,
    series_name: '时尚女性系列',
    category_name: '通勤',
    aliases: [],
    brand_id: brandId,
    keyword_pack_ids: [],
    created_at: now,
    updated_at: now,
  },
]

const scheme: AnalysisSchemeResponse = {
  id: schemeId,
  name: '爱玛舆情分析规则',
  is_active: true,
  active_version_id: versionId,
  created_at: now,
  updated_at: now,
  versions: [
    {
      id: '83111111-1111-4111-8111-222222222222',
      scheme_id: schemeId,
      version: 4,
      status: 'draft',
      description: '编辑中',
      created_at: now,
      created_by: 'local-administrator',
      prompt_sha256: '0'.repeat(64),
      taxonomy_sha256: '1'.repeat(64),
      definition: {
        prompt_template: '{{AIMA_TAXONOMY_JSON}}',
        voice_types: ['真实用户发声', '品牌官方发声'],
        sentiments: ['正面', '中性', '负面', '混合', '无法判断'],
        labels: { 外观设计: ['整体造型与颜值'], 无法分类: ['无法判断'] },
      },
    },
    {
      id: versionId,
      scheme_id: schemeId,
      version: 3,
      status: 'published',
      description: '当前线上生效规则',
      created_at: now,
      created_by: 'local-administrator',
      prompt_sha256: '0'.repeat(64),
      taxonomy_sha256: '1'.repeat(64),
      definition: {
        prompt_template: '{{AIMA_TAXONOMY_JSON}}',
        voice_types: ['真实用户发声', '品牌官方发声'],
        sentiments: ['正面', '中性', '负面', '混合', '无法判断'],
        labels: { 外观设计: ['整体造型与颜值'], 无法分类: ['无法判断'] },
      },
    },
  ],
}

/** 返回符合当前 generated client 的 Browser Mock。 */
async function json(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

/** 只 Mock 本测试负责的前端公开边界；请求结构仍来自当前正式 Contract。 */
async function mockAdmin(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() !== 'GET') return route.fallback()
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const limit = Number(url.searchParams.get('limit') ?? '100')
    if (url.pathname === '/api/v1/vehicle-models') {
      return json(route, { items: vehicles, total: vehicles.length, catalog_version: 18, offset, limit })
    }
    if (url.pathname === '/api/v1/vehicle-brands') {
      return json(route, { items: brands, total: brands.length, catalog_version: 18, offset, limit })
    }
    if (url.pathname === '/api/v1/analysis-schemes') return json(route, { items: [scheme] })
    if (url.pathname === '/api/v1/audit-events') {
      return json(route, {
        items: [{
          id: '88111111-1111-4111-8111-111111111111',
          actor_ref: 'local-administrator',
          event_type: 'provider_config_updated',
          object_type: 'provider_config',
          object_id: provider('llm').id,
          request_id: 'admin-figma-acceptance',
          safe_detail: { display_name: '默认 AI 模型', revision: 2 },
          created_at: now,
        }],
        total: 1,
        offset,
        limit,
      })
    }
    if (url.pathname === '/api/v1/provider-configs') {
      const kind = url.searchParams.get('provider_kind') === 'collection' ? 'collection' : 'llm'
      return json(route, { items: [provider(kind)] })
    }
    return route.fallback()
  })
}

/** 页面级横向滚动会破坏固定侧栏和弹性工作区，窄内容只能在局部容器滚动。 */
async function expectNoGlobalHorizontalScroll(page: Page): Promise<void> {
  const bounds = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(bounds.scroll).toBeLessThanOrEqual(bounds.client + 1)
}

test('admin exposes the six approved tabs including the frontend report strategy', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  const nav = page.getByRole('navigation', { name: '管理员配置分类' })
  await expect(nav.getByRole('button')).toHaveCount(6)
  for (const name of ['品牌与车型', 'AI 模型', 'TikHub', 'AI 分析规则', '操作记录', '报告策略']) {
    await expect(nav.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await nav.getByRole('button', { name: '报告策略', exact: true }).click()
  await expect(page.getByRole('heading', { name: '飞书报告发布' })).toBeVisible()
  await expect(page.getByText('上传本期和上期 XLSX')).toBeVisible()
})

test('report strategy submits the two workbooks and renders the dry-run Job result', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: '报告策略', exact: true }).click()

  const submit = page.getByRole('button', { name: '生成报告并同步到飞书', exact: true })
  await expect(submit).toBeDisabled()
  await page.getByLabel('本期 XLSX').setInputFiles({
    name: '本期报告.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('local-current-period'),
  })
  await page.getByLabel('上期 XLSX').setInputFiles({
    name: '上期报告.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('local-prior-period'),
  })
  await page.getByLabel('开始日期').fill('2026-09-10')
  await page.getByLabel('结束日期').fill('2026-09-01')
  await expect(submit).toBeEnabled()
  await submit.click()
  await expect(page.getByRole('alert')).toContainText('结束日期不早于开始日期')

  await page.getByLabel('结束日期').fill('2026-09-17')
  const jobId = '89111111-1111-4111-8111-111111111111'
  let publicationPosts = 0
  await page.route('**/api/v1/admin/feishu-report-publications', async (route) => {
    expect(route.request().method()).toBe('POST')
    publicationPosts += 1
    await json(route, { job_id: jobId, kind: 'report', status: 'queued' }, 202)
  })
  let jobReads = 0
  await page.route(`**/api/v1/admin/feishu-publication-jobs/${jobId}`, async (route) => {
    jobReads += 1
    if (jobReads === 1) {
      return json(route, {
        status: 503,
        detail: 'job status temporarily unavailable',
        request_id: 'e2e-temporary-job-read',
        errors: [],
      }, 503)
    }
    await json(route, {
      id: jobId,
      kind: 'report',
      status: 'succeeded',
      attempt: 1,
      max_attempts: 3,
      progress: 100,
      error_code: null,
      source_filenames: ['本期报告.xlsx', '上期报告.xlsx'],
      result: {
        kind: 'report',
        dry_run: true,
        native_document_url: null,
        editable_chart_sheet_url: null,
        representative_table_url: null,
        representative_table_name: null,
        representative_count: 4,
        representative_created_count: 0,
        representative_updated_count: 0,
        representative_verified_count: 0,
        content_rows: 12,
        label_rows: 12,
        comment_rows: 8,
        start_date: '2026-09-01',
        end_date: '2026-09-17',
      },
      created_at: now,
      started_at: now,
      finished_at: now,
    })
  })
  await submit.click()
  await expect(page.getByRole('status')).toContainText('Dry Run 已完成', { timeout: 12_000 })
  expect(publicationPosts).toBe(1)
  expect(jobReads).toBeGreaterThanOrEqual(2)
  await expect(page.getByRole('region', { name: '报告任务结果' })).toContainText('代表性内容 4 条')
  await expect(page.getByText('Dry Run 未生成真实飞书链接。')).toBeVisible()

  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.getByLabel('开始日期')).toHaveValue('')
  await expect(page.getByText('本期报告.xlsx')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '生成报告并同步到飞书', exact: true })).toBeDisabled()
})

test('brand catalog follows the 1440 wide geometry and keeps tables locally scrollable', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')

  const directoryBox = await page.locator('.brand-directory-card').boundingBox()
  const detailBox = await page.locator('.brand-detail-card').boundingBox()
  expect(directoryBox).not.toBeNull()
  expect(detailBox).not.toBeNull()
  expect(directoryBox!.width).toBeGreaterThan(600)
  expect(detailBox!.width).toBeGreaterThanOrEqual(360)
  expect(detailBox!.width).toBeLessThanOrEqual(410)
  expect(Math.abs(directoryBox!.y - detailBox!.y)).toBeLessThanOrEqual(1)
  expect(detailBox!.x - (directoryBox!.x + directoryBox!.width)).toBeGreaterThanOrEqual(20)

  const brandTable = page.getByRole('region', { name: '品牌目录表格' })
  const vehicleTable = page.getByRole('region', { name: '车型目录表格' })
  await expect(brandTable).toHaveCSS('overflow-x', 'auto')
  await expect(brandTable.locator('table')).toHaveCSS('min-width', '726px')
  await expect(vehicleTable).toHaveCSS('overflow-x', 'auto')
  await expect(vehicleTable.locator('table')).toHaveCSS('min-width', '726px')
  await expectNoGlobalHorizontalScroll(page)
})

test('1180 compact stacks brand and provider editors instead of overflowing the page', async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 900 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')

  const directoryBox = await page.locator('.brand-directory-card').boundingBox()
  const detailBox = await page.locator('.brand-detail-card').boundingBox()
  expect(directoryBox).not.toBeNull()
  expect(detailBox).not.toBeNull()
  expect(detailBox!.y).toBeGreaterThanOrEqual(directoryBox!.y + directoryBox!.height)
  expect(Math.abs(directoryBox!.width - detailBox!.width)).toBeLessThanOrEqual(2)
  await expectNoGlobalHorizontalScroll(page)

  await page.getByRole('button', { name: 'AI 模型', exact: true }).click()
  const listBox = await page.locator('.provider-list').boundingBox()
  const formBox = await page.locator('.provider-form').boundingBox()
  expect(listBox).not.toBeNull()
  expect(formBox).not.toBeNull()
  expect(formBox!.y).toBeGreaterThanOrEqual(listBox!.y + listBox!.height)
  expect(Math.abs(listBox!.width - formBox!.width)).toBeLessThanOrEqual(2)
  await expectNoGlobalHorizontalScroll(page)
})

test('1440 provider and scheme layouts keep fixed readable lists plus flexible editors', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')

  await page.getByRole('button', { name: 'AI 模型', exact: true }).click()
  const providerListBox = await page.locator('.provider-list').boundingBox()
  const providerFormBox = await page.locator('.provider-form').boundingBox()
  expect(providerListBox).not.toBeNull()
  expect(providerFormBox).not.toBeNull()
  expect(providerListBox!.width).toBeGreaterThanOrEqual(390)
  expect(providerListBox!.width).toBeLessThanOrEqual(405)
  expect(providerFormBox!.width).toBeGreaterThan(providerListBox!.width)
  expect(Math.abs(providerListBox!.y - providerFormBox!.y)).toBeLessThanOrEqual(1)

  await page.getByRole('button', { name: 'AI 分析规则', exact: true }).click()
  const historyBox = await page.locator('.scheme-history').boundingBox()
  const editorBox = await page.locator('.scheme-editor').boundingBox()
  expect(historyBox).not.toBeNull()
  expect(editorBox).not.toBeNull()
  expect(historyBox!.width).toBeGreaterThanOrEqual(260)
  expect(historyBox!.width).toBeLessThanOrEqual(276)
  expect(editorBox!.width).toBeGreaterThan(760)
  expect(Math.abs(historyBox!.y - editorBox!.y)).toBeLessThanOrEqual(1)
  await expectNoGlobalHorizontalScroll(page)
})

test('vehicle create and edit use the business vehicle name without exposing category', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')

  await page.getByRole('button', { name: '新增车型', exact: true }).click()
  const createDialog = page.getByRole('dialog', { name: '新增车型' })
  await expect(createDialog).toBeVisible()
  await expect(createDialog.getByText('车型编码', { exact: true })).toHaveCount(0)
  await expect(createDialog.getByLabel('车型名称', { exact: true })).toBeVisible()
  await expect(createDialog.getByText('显示名称', { exact: true })).toHaveCount(0)
  await expect(createDialog.getByPlaceholder('用于车型筛选分组')).toBeVisible()
  await expect(createDialog.getByText('类别（可选）', { exact: true })).toHaveCount(0)
  await expect(createDialog.getByPlaceholder('用于车型信息展示')).toHaveCount(0)
  await expect(createDialog.getByPlaceholder('Q7\n爱玛Q7')).toBeVisible()
  await expect(createDialog.getByText('内部编码由服务端自动生成', { exact: false })).toBeVisible()
  await createDialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(createDialog).not.toBeVisible()

  const vehicleRegion = page.getByRole('region', { name: '车型目录表格' })
  await vehicleRegion.getByRole('button', { name: '编辑', exact: true }).first().click()
  const editDialog = page.getByRole('dialog', { name: '编辑车型' })
  await expect(editDialog).toBeVisible()
  await expect(editDialog.getByText('车型编码', { exact: true })).toHaveCount(0)
  await expect(editDialog.getByLabel('车型名称', { exact: true })).toBeVisible()
  await expect(editDialog.getByText('类别（可选）', { exact: true })).toHaveCount(0)
  await expect(editDialog.getByText('已启用', { exact: true })).toBeVisible()
  await expect(editDialog.getByText('合并重复车型', { exact: true })).toBeVisible()
})

test('brand creation hides internal code while normal detail keeps it technical', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')

  await page.getByRole('button', { name: '新增品牌', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增品牌' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('品牌编码', { exact: true })).toHaveCount(0)
  await expect(dialog.getByText('内部编码由服务端自动生成', { exact: false })).toBeVisible()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()

  await expect(page.getByText('品牌编码', { exact: true })).not.toBeVisible()
  await page.getByText('技术信息', { exact: true }).click()
  await expect(page.getByText('品牌编码', { exact: true })).toBeVisible()
})

test('audit keeps its 1176px table inside the local viewport with controls outside it', async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 900 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: '操作记录', exact: true }).click()

  const tableRegion = page.getByRole('region', { name: '操作记录表格' })
  await expect(tableRegion).toHaveCSS('overflow-x', 'auto')
  await expect(tableRegion.locator('table')).toHaveCSS('min-width', '1176px')
  await tableRegion.evaluate((element) => { element.scrollLeft = element.scrollWidth })
  await expect(tableRegion.getByText('技术详情', { exact: true })).toBeInViewport()
  await expect(page.getByRole('button', { name: '刷新', exact: true })).toBeInViewport()
  await expect(page.getByRole('navigation', { name: '操作记录分页' })).toBeVisible()
  await expectNoGlobalHorizontalScroll(page)
})

import type {
  AnalysisSchemeResponse,
  BrandResponse,
  ProviderConfigResponse,
  ResourceLifecycleResponse,
  ReportResponse,
  VehicleModelResponse,
} from '../src/generated/api/client'
import { expect, test, type Page, type Route } from './fixture'
import { captureScrollbarEvidence } from './scrollbarEvidence'

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
async function mockAdmin(
  page: Page,
  options: { archivedSchemes?: ResourceLifecycleResponse[] } = {},
): Promise<void> {
  let archivedSchemes = [...(options.archivedSchemes ?? [])]
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (
      request.method() === 'DELETE'
      && /^\/api\/v1\/analysis-schemes\/[^/]+$/.test(url.pathname)
    ) {
      const schemeId = url.pathname.split('/').at(-1)
      archivedSchemes = archivedSchemes.filter((item) => item.id !== schemeId)
      return route.fulfill({ status: 204 })
    }
    if (request.method() !== 'GET') return route.fallback()
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const limit = Number(url.searchParams.get('limit') ?? '100')
    if (url.pathname === '/api/v1/vehicle-models') {
      return json(route, { items: vehicles, total: vehicles.length, catalog_version: 18, offset, limit })
    }
    if (url.pathname === '/api/v1/vehicle-brands') {
      return json(route, { items: brands, total: brands.length, catalog_version: 18, offset, limit })
    }
    if (url.pathname === '/api/v1/reports') return json(route, { items: [] })
    if (url.pathname === '/api/v1/analysis-schemes') return json(route, { items: [scheme] })
    if (url.pathname === '/api/v1/analysis-schemes/lifecycle/archived') {
      return json(route, { items: archivedSchemes })
    }
    const schemeDeleteEligibility = url.pathname.match(
      /^\/api\/v1\/analysis-schemes\/([^/]+)\/delete-eligibility$/,
    )
    if (schemeDeleteEligibility) {
      return json(route, {
        id: schemeDeleteEligibility[1],
        eligible: true,
        blocking_reasons: [],
      })
    }
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

test('管理员目录和配置编辑滚动条三状态保持几何', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 680 })
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  const brandDetail = page.locator('.brand-detail-card')
  await expect(brandDetail).toBeVisible()
  await captureScrollbarEvidence(page, brandDetail, testInfo, 'admin-catalog')
  await page.getByRole('button', { name: 'AI 分析规则', exact: true }).click()
  const scheme = page.locator('.scheme-editor')
  await expect(scheme).toBeVisible()
  await captureScrollbarEvidence(page, scheme, testInfo, 'admin-scheme')
})

test('admin exposes database reports in the six approved tabs', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  const nav = page.getByRole('navigation', { name: '管理员配置分类' })
  await expect(nav.getByRole('button')).toHaveCount(6)
  for (const name of ['品牌与车型', 'AI 模型', 'TikHub', 'AI 分析规则', '操作记录', '报告生成']) {
    await expect(nav.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await nav.getByRole('button', { name: '报告生成', exact: true }).click()
  await expect(page.getByRole('heading', { name: '报告生成', exact: true })).toBeVisible()
  await expect(page.getByLabel('报告品牌')).toBeVisible()
  await expect(page.locator('input[type="file"]')).toHaveCount(0)
})

test('database report preflight, polling recovery, downloads and independent publication', async ({ page }) => {
  await mockAdmin(page)
  const reportId = '89111111-1111-4111-8111-111111111111'
  const jobId = '89111111-1111-4111-8111-222222222222'
  let report: ReportResponse | null = null
  let readsAfterCreate = 0
  let createCount = 0
  let publishCount = 0
  let initialRead: Route | null = null
  await page.route('**/api/v1/reports**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname.endsWith('/preflight')) {
      expect(request.postDataJSON()).toEqual({ brand_id: brandId, vehicle_model_ids: [vehicles[0]!.id], start_date: '2026-09-10', end_date: '2026-09-17' })
      return json(route, { content_count: 12, previous_content_count: 8, analyzed_count: 10, real_user_count: 6, comment_count: 8, model: 'deepseek-chat', provider: 'openai_compatible', prompt_version: 'v4.6', taxonomy_sha256: 'a'.repeat(64), ready: true, warnings: ['2 条内容尚无分析结果，仅参与全量声量统计'] })
    }
    if (url.pathname === '/api/v1/reports' && request.method() === 'POST') {
      createCount += 1
      report = { id: reportId, name: '爱玛舆情报告', brand_id: brandId, vehicle_model_ids: [vehicles[0]!.id], start_date: '2026-09-10', end_date: '2026-09-17', status: 'queued', generation_job: { id: jobId, job_type: 'reporting.report-generation.v1', status: 'queued', attempt: 0, max_attempts: 4, progress: 0, error_code: null, created_at: now, available_at: now, timeout_seconds: 1800, cancel_requested: false }, files: [], created_at: now, model: 'deepseek-chat', prompt_version: 'v4.6', provider_config_id: jobId, provider_revision: 2, scheme_version_id: jobId, prompt_sha256: 'a'.repeat(64), taxonomy_sha256: 'b'.repeat(64), selection_prompt_sha256: 'c'.repeat(64), content_count: 12, publication_enabled: true }
      return json(route, report, 202)
    }
    if (url.pathname === '/api/v1/reports' && request.method() === 'GET') {
      if (!report) { initialRead = route; return }
      if (report) {
        readsAfterCreate += 1
        if (readsAfterCreate === 1) return json(route, { detail: 'temporary status outage' }, 503)
        report = { ...report, status: report.status === 'queued' ? 'generated' : report.status, generation_job: { ...report.generation_job, status: 'succeeded', progress: 100 }, completed_at: now, expires_at: '2026-11-16T12:00:00+08:00', files: [{ artifact_id: jobId, artifact_type: 'word_report', filename: 'report.docx', content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', byte_size: 1000, download_url: `/api/v1/reports/${reportId}/artifacts/${jobId}/download` }, { artifact_id: reportId, artifact_type: 'excel_report', filename: 'report-data.xlsx', content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', byte_size: 1200, download_url: `/api/v1/reports/${reportId}/artifacts/${reportId}/download` }] }
      }
      return json(route, { items: report ? [report] : [] })
    }
    if (url.pathname.endsWith('/publish') && report) {
      publishCount += 1
      report = { ...report, status: publishCount === 1 ? 'generated' : 'published', publication_job: { ...report.generation_job, id: reportId, job_type: 'reporting.report-publication.v1', status: publishCount === 1 ? 'failed' : 'succeeded', error_code: publishCount === 1 ? 'report_feishu_api_error' : null }, native_document_url: publishCount === 1 ? null : 'https://example.test/document' }
      return json(route, report)
    }
    return route.fallback()
  })
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: '报告生成', exact: true }).click()
  const panel = page.getByRole('region', { name: '数据库报告生成' })
  const submit = panel.getByRole('button', { name: '生成报告', exact: true })
  await expect(submit).toBeDisabled()
  await page.getByLabel('报告品牌').selectOption(brandId)
  await page.getByLabel('报告车型').selectOption([vehicles[0]!.id])
  await page.getByLabel('报告开始日期').fill('2026-09-10')
  await page.getByLabel('报告结束日期').fill('2026-09-01')
  await expect(panel.getByRole('button', { name: '检查数据与模型' })).toBeDisabled()
  await page.getByLabel('报告结束日期').fill('2026-09-17')
  await panel.getByRole('button', { name: '检查数据与模型' }).click()
  await expect(panel.getByRole('region', { name: '报告预检' })).toContainText('本期 12 条 · 上期 8 条')
  await expect(submit).toBeEnabled()
  await submit.click()
  await expect(panel.getByRole('button', { name: '取消任务' })).toBeVisible()
  expect(initialRead).not.toBeNull()
  const beforeFailure = await panel.locator('.report-card').first().boundingBox()
  await json(initialRead!, { items: [] })
  // 创建前的旧空列表不得覆盖已经创建的任务，也不能因此停止轮询。
  await expect(panel.getByRole('button', { name: '取消任务' })).toBeVisible()
  await expect(panel.getByText('状态同步暂时失败', { exact: false })).toBeVisible({ timeout: 12000 })
  expect(await panel.locator('.report-card').first().boundingBox()).toEqual(beforeFailure)
  await expect(panel.getByRole('link', { name: '下载 Word' })).toBeVisible({ timeout: 12000 })
  await expect(panel.getByRole('link', { name: '下载 Excel 数据' })).toBeVisible()
  expect(createCount).toBe(1)
  expect(readsAfterCreate).toBeGreaterThanOrEqual(2)
  await panel.getByRole('button', { name: '发布到飞书' }).click()
  await expect(panel.getByText('失败，报告文件仍可下载', { exact: false })).toBeVisible()
  await expect(panel.getByRole('link', { name: '下载 Word' })).toBeVisible()
  await panel.getByRole('button', { name: '重试飞书发布' }).click()
  await expect(panel.getByRole('link', { name: '打开飞书报告' })).toHaveAttribute('href', 'https://example.test/document')
  expect(createCount).toBe(1)
  expect(publishCount).toBe(2)
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

test('analysis rules group versions and archived rules can be removed without cluttering the main list', async ({ page }) => {
  const archivedSchemeId = '82111111-1111-4111-8111-999999999999'
  await mockAdmin(page, {
    archivedSchemes: [{
      id: archivedSchemeId,
      resource_type: 'analysis_scheme',
      name: '历史测试规则',
      archived_at: now,
    }],
  })
  page.on('dialog', (dialog) => { void dialog.accept() })
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析规则', exact: true }).click()

  const group = page.locator('.scheme-group')
  await expect(group).toHaveCount(1)
  await expect(group.locator('summary')).toContainText('爱玛舆情分析规则')
  await expect(group.locator('summary')).toContainText('2 个版本')

  const archived = page.locator('details.archived-schemes')
  await expect(archived).toHaveJSProperty('open', false)
  await archived.locator('summary').click()
  await expect(archived.locator('summary')).toContainText('1 项')
  await expect(archived.getByText('历史测试规则', { exact: true })).toBeVisible()
  await expect(archived).toContainText('历史分析所需的不可变版本快照')

  await archived.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByText('AI 分析规则已从配置管理中删除；历史分析所需版本快照不会被破坏。')).toBeVisible()
  await expect(archived.getByText('历史测试规则', { exact: true })).toHaveCount(0)
  await expect(archived.locator('summary')).toContainText('0 项')
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

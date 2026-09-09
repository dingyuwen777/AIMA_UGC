import type { AnalysisSchemeResponse, ProviderConfigResponse, VehicleModelResponse } from '../src/generated/api/client'
import { expect, test, type Page, type Route } from './fixture'

const now = '2026-09-09T04:00:00+08:00'
const packId = '71111111-1111-4111-8111-111111111111'
const schemeId = '72111111-1111-4111-8111-111111111111'
const versionId = '73111111-1111-4111-8111-111111111111'

function provider(index: number, kind: 'llm' | 'collection' = 'llm'): ProviderConfigResponse {
  return {
    id: `74111111-1111-4111-8111-${String(index).padStart(12, '0')}`,
    provider_kind: kind, provider: kind === 'llm' ? 'openai_compatible' : 'tikhub',
    display_name: `${kind === 'llm' ? '模型' : 'TikHub'}配置 ${index}`,
    base_url: kind === 'llm' ? 'https://provider.example/v1' : 'https://api.tikhub.io',
    model: kind === 'llm' ? 'example-model' : null, enabled: true, is_default: index === 1 && kind === 'llm',
    timeout_seconds: 45, max_retries: 3, max_concurrency: 5, max_rps: null, revision: 1, secret_configured: true,
  }
}

const vehicles: VehicleModelResponse[] = [1, 2].map((index) => ({
  id: `75111111-1111-4111-8111-${String(index).padStart(12, '0')}`,
  code: `AIMA-${index}`, display_name: `爱玛车型 ${index}`, status: 'active', version: 1,
  catalog_version: 1, referenced: index === 1, series_name: '城市系列', category_name: '通勤',
  aliases: [{ id: `76111111-1111-4111-8111-${String(index).padStart(12, '0')}`, text: `完整车型别名 ${index}`, normalized_text: `完整车型别名 ${index}` }],
  keyword_pack_ids: index === 1 ? [packId] : [], created_at: now, updated_at: now,
}))

const scheme: AnalysisSchemeResponse = {
  id: schemeId, name: '业务分析规则', is_active: false, active_version_id: null, created_at: now, updated_at: now,
  versions: [{
    id: versionId, scheme_id: schemeId, version: 1, status: 'draft', description: '保留业务规则',
    created_at: now, created_by: 'local-administrator', prompt_sha256: '0'.repeat(64), taxonomy_sha256: '1'.repeat(64),
    definition: { prompt_template: '{{AIMA_TAXONOMY_JSON}}', voice_types: ['真实用户发声'], sentiments: ['中性'], labels: { 外观设计: ['整体造型'], 无法分类: ['无法判断'] } },
  }],
}

async function json(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

/** 只提供正式管理Contract的固定响应；具体写请求由各验收场景声明。 */
async function mockAdmin(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (route.request().method() !== 'GET') return route.fallback()
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const limit = Number(url.searchParams.get('limit') ?? '100')
    if (url.pathname === '/api/v1/vehicle-models') return json(route, { items: vehicles, total: vehicles.length, catalog_version: 1, offset, limit })
    if (url.pathname === '/api/v1/keyword-packs') return json(route, { items: [{ id: packId, name: '品牌词包', description: '当前配置', enabled: true, version: 1, keyword_count: 2 }], total: 1, offset, limit })
    if (url.pathname === '/api/v1/analysis-schemes') return json(route, { items: [scheme] })
    if (url.pathname === '/api/v1/audit-events') return json(route, {
      items: [{ id: '77111111-1111-4111-8111-111111111111', actor_ref: 'local-administrator', event_type: 'provider_config_updated', object_type: 'provider_config', object_id: provider(1).id, request_id: 'admin-browser-request', safe_detail: { display_name: '模型配置 1', revision: 2 }, created_at: now }], total: 1, offset, limit,
    })
    if (url.pathname === '/api/v1/provider-configs') {
      const kind = url.searchParams.get('provider_kind') === 'collection' ? 'collection' : 'llm'
      return json(route, { items: [provider(1, kind), provider(2, kind)] })
    }
    return route.fallback()
  })
}

async function openProvider(page: Page, name = 'AI 模型'): Promise<void> {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name, exact: true }).click()
  await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue(name === 'AI 模型' ? '模型配置 1' : 'TikHub配置 1')
}

for (const kind of ['llm', 'collection'] as const) {
  test(`${kind} tests only saved configuration and preserves unsaved input`, async ({ page }) => {
    await openProvider(page, kind === 'llm' ? 'AI 模型' : 'TikHub')
    const calls: string[] = []
    await page.route('**/provider-configs/*/test-connection', async (route) => {
      calls.push(route.request().url())
      await json(route, { ok: true, message: '连接成功', latency_ms: 28 })
    })
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('连接测试通过')
    expect(calls).toHaveLength(1)
    expect(calls[0]).toContain(provider(1, kind).id)
    await expect(page.getByLabel(/^访问密钥/)).toHaveValue('')
    await page.getByLabel('配置名称', { exact: true }).fill('尚未保存的配置名称')
    await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeDisabled()
    await expect(page.getByText('连接测试通过', { exact: true })).not.toBeVisible()
    await expect(page.getByText('配置有未保存修改，请先保存后再测试连接。', { exact: true })).toBeVisible()
    await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue('尚未保存的配置名称')
  })
}

for (const outcome of ['success', 'error'] as const) {
  test(`ignores ${outcome} from a connection test after another configuration is selected`, async ({ page }) => {
    await openProvider(page)
    let release!: () => void
    const pending = new Promise<void>((resolve) => { release = resolve })
    await page.route(`**/provider-configs/${provider(1).id}/test-connection`, async (route) => {
      await pending
      await json(route, outcome === 'success'
        ? { ok: true, message: '第一个配置的迟到结果', latency_ms: 800 }
        : { status: 503, title: '测试暂不可用', detail: '第一个配置的迟到错误', request_id: 'test-delayed' }, outcome === 'success' ? 200 : 503)
    })
    const started = page.waitForRequest((request) => request.url().endsWith(`${provider(1).id}/test-connection`))
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await started
    await page.getByRole('button', { name: /模型配置 2/ }).click()
    await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue('模型配置 2')
    const finished = page.waitForResponse((response) => response.url().endsWith(`${provider(1).id}/test-connection`))
    release()
    await finished
    await expect(page.getByText(/第一个配置的迟到/)).not.toBeVisible()
    await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeEnabled()
  })
}

test('preserves provider draft on save failure and prevents edits during its submission', async ({ page }) => {
  await openProvider(page)
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  let requests = 0
  await page.route(`**/provider-configs/${provider(1).id}`, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    requests += 1
    expect(route.request().postDataJSON()).toMatchObject({ display_name: '保存失败后保留', base_url: provider(1).base_url })
    expect(route.request().postDataJSON()).not.toHaveProperty('api_key')
    await pending
    await json(route, { status: 409, title: '配置冲突', detail: '服务配置暂不能保存', request_id: 'save-conflict' }, 409)
  })
  await page.getByLabel('配置名称', { exact: true }).fill('保存失败后保留')
  const started = page.waitForRequest((request) => request.method() === 'PUT')
  await page.getByRole('button', { name: '保存并生效', exact: true }).click()
  await started
  await expect(page.getByLabel('配置名称', { exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: /模型配置 2/ })).toBeDisabled()
  release()
  await expect(page.getByRole('alert')).toContainText('服务配置暂不能保存')
  await expect(page.getByLabel('配置名称', { exact: true })).toBeEnabled()
  await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue('保存失败后保留')
  expect(requests).toBe(1)
})

test('keeps vehicle and audit table scrolling separate from headings and page controls', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  for (const width of [1180, 1281, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 })
    await page.getByRole('button', { name: '车型管理', exact: true }).click()
    const vehicleTable = page.getByRole('region', { name: '车型目录表格', exact: true })
    await expect(vehicleTable).toHaveCSS('overflow-x', 'auto')
    await expect(vehicleTable.locator('table')).toHaveCSS('min-width', '726px')
    await vehicleTable.evaluate((element) => { element.scrollLeft = element.scrollWidth })
    await expect(vehicleTable.getByRole('button', { name: '编辑', exact: true }).first()).toBeInViewport()
    await expect(page.getByRole('button', { name: '新增车型', exact: true })).toBeInViewport()
    await page.getByRole('button', { name: '操作记录', exact: true }).click()
    const auditTable = page.getByRole('region', { name: '操作记录表格', exact: true })
    await expect(auditTable).toHaveCSS('overflow-x', 'auto')
    await expect(auditTable.locator('table')).toHaveCSS('min-width', '1176px')
    await auditTable.evaluate((element) => { element.scrollLeft = element.scrollWidth })
    await expect(auditTable.getByText('技术详情', { exact: true })).toBeInViewport()
    await expect(page.getByRole('button', { name: '刷新', exact: true })).toBeInViewport()
    const bounds = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
    expect(bounds.scroll).toBeLessThanOrEqual(bounds.client + 1)
  }
})

test('locks the current analysis rule while publishing and keeps its draft after a conflict', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析原则', exact: true }).click()
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  await page.route(`**/analysis-scheme-versions/${versionId}/publish`, async (route) => {
    expect(route.request().postDataJSON()).toEqual({ expected_version: 1 })
    await pending
    await json(route, { status: 409, title: '发布冲突', detail: '版本已被修改，请刷新', request_id: 'publish-conflict' }, 409)
  })
  page.once('dialog', (dialog) => dialog.accept())
  const started = page.waitForRequest((request) => request.url().endsWith(`${versionId}/publish`))
  await page.getByRole('button', { name: '发布', exact: true }).click()
  await started
  await expect(page.getByRole('button', { name: '发布', exact: true })).toBeDisabled()
  await expect(page.getByLabel('说明', { exact: true })).toBeDisabled()
  release()
  await expect(page.getByRole('alert')).toContainText('版本已被修改，请刷新')
  await expect(page.getByLabel('说明', { exact: true })).toHaveValue('保留业务规则')
  await expect(page.getByRole('button', { name: '发布', exact: true })).toBeEnabled()
})

test('opens the active analysis principle instead of a newer draft', async ({ page }) => {
  await mockAdmin(page)
  const activeVersionId = '73111111-1111-4111-8111-333333333333'
  const activeScheme: AnalysisSchemeResponse = {
    ...scheme,
    is_active: true,
    active_version_id: activeVersionId,
    versions: [
      scheme.versions[0]!,
      {
        ...scheme.versions[0]!,
        id: activeVersionId,
        version: 2,
        status: 'published',
        description: '当前线上生效原则',
      },
    ],
  }
  await page.route('**/api/v1/analysis-schemes', async (route) => {
    await json(route, { items: [activeScheme] })
  })

  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析原则', exact: true }).click()

  await expect(page.getByText('版本 2 · 当前生效', { exact: true })).toBeVisible()
  await expect(page.getByText('版本 1 · 草稿，尚未生效', { exact: true })).toBeVisible()
  await expect(page.getByLabel('说明', { exact: true })).toHaveValue('当前线上生效原则')
})


test('provider advanced rate limit saves a numeric value and can be cleared', async ({ page }) => {
  await openProvider(page)
  let saved = provider(1)
  await page.route('**/provider-configs?provider_kind=llm', async (route) => json(route, { items: [saved, provider(2)] }))
  const bodies: unknown[] = []
  await page.route(`**/provider-configs/${saved.id}`, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    const body = route.request().postDataJSON()
    bodies.push(body)
    saved = { ...saved, ...body, revision: saved.revision + 1 }
    await json(route, saved)
  })
  await page.getByText('高级设置', { exact: true }).click()
  const rate = page.getByLabel('每秒请求启动上限', { exact: false })
  await rate.fill('12')
  await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '保存并生效', exact: true }).click()
  await expect(page.getByText('配置已保存；新任务将使用新配置，正在运行的任务不受影响。', { exact: true })).toBeVisible()
  expect(bodies[0]).toMatchObject({ max_rps: 12 })
  await expect(rate).toHaveValue('12')
  await rate.fill('')
  await page.getByRole('button', { name: '保存并生效', exact: true }).click()
  await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeEnabled()
  expect(bodies[1]).toMatchObject({ max_rps: null })
})


test('keeps an in-flight connection test locked after equivalent edits or selection changes', async ({ page }) => {
  await openProvider(page)
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  let calls = 0
  await page.route(`**/provider-configs/${provider(1).id}/test-connection`, async (route) => {
    calls += 1
    await pending
    await json(route, { ok: true, message: '旧输入状态下的测试结果', latency_ms: 70 })
  })
  const started = page.waitForRequest((request) => request.url().endsWith('/test-connection'))
  await page.getByRole('button', { name: '测试连接', exact: true }).click()
  await started
  await page.getByLabel('配置名称', { exact: true }).fill('模型配置 1 ')
  await expect(page.getByRole('button', { name: '测试中…', exact: true })).toBeDisabled()
  await page.getByLabel('配置名称', { exact: true }).fill('改后还原')
  await page.getByLabel('配置名称', { exact: true }).fill('模型配置 1')
  await expect(page.getByRole('button', { name: '测试中…', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: /模型配置 2/ }).click()
  await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: /模型配置 1/ }).click()
  await expect(page.getByRole('button', { name: '测试中…', exact: true })).toBeDisabled()
  release()
  await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeEnabled()
  await expect(page.getByText('旧输入状态下的测试结果', { exact: true })).not.toBeVisible()
  expect(calls).toBe(1)
})


test('analysis rule must save visible changes before publishing its persisted version', async ({ page }) => {
  await mockAdmin(page)
  let current = structuredClone(scheme)
  let published = 0
  const savedVersionId = '73111111-1111-4111-8111-222222222222'
  await page.route('**/analysis-schemes', async (route) => json(route, { items: [current] }))
  await page.route(`**/analysis-scheme-versions/${versionId}`, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    const body = route.request().postDataJSON()
    expect(body.description).toBe('  必须发布已保存的新说明  ')
    const old = current.versions[0]!
    current.versions = [
      { ...old, status: 'retired' },
      { ...old, id: savedVersionId, description: body.description.trim(), definition: { ...body.definition, labels: Object.fromEntries(Object.entries(body.definition.labels).reverse()) }, version: 2 },
    ]
    await json(route, current)
  })
  await page.route(`**/analysis-scheme-versions/${savedVersionId}/publish`, async (route) => {
    published += 1
    expect(route.request().postDataJSON()).toEqual({ expected_version: 2 })
    current = { ...current, is_active: true, active_version_id: savedVersionId, versions: current.versions.map((version) => version.id === savedVersionId ? { ...version, status: 'published' } : version) }
    await json(route, current)
  })
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析原则', exact: true }).click()
  await page.getByLabel('一级标签名称', { exact: true }).first().fill('')
  await expect(page.getByRole('button', { name: '发布', exact: true })).toBeDisabled()
  await page.getByLabel('一级标签名称', { exact: true }).first().fill('外观设计')
  await page.getByRole('button', { name: '新增一级标签', exact: true }).click()
  await page.getByLabel('一级标签名称', { exact: true }).last().fill('动力表现')
  await page.getByRole('textbox', { name: '二级标签 1', exact: true }).last().fill('起步响应')
  await page.getByLabel('说明', { exact: true }).fill('  必须发布已保存的新说明  ')
  await expect(page.getByRole('button', { name: '发布', exact: true })).toBeDisabled()
  await expect(page.getByText('原则有未保存修改，请先保存草稿后再发布。', { exact: true })).toBeVisible()
  expect(published).toBe(0)
  await page.getByRole('button', { name: '保存草稿', exact: true }).click()
  await expect(page.getByRole('button', { name: '发布', exact: true })).toBeEnabled()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '发布', exact: true }).click()
  await expect(page.getByText('AI 分析原则已发布并记录操作。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('说明', { exact: true })).toHaveValue('必须发布已保存的新说明')
  expect(published).toBe(1)
})


test('keeps the analysis-rule copy editor open while its name is cleared', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析原则', exact: true }).click()
  await page.getByRole('button', { name: '复制原则', exact: true }).click()
  await page.getByLabel('副本名称', { exact: true }).fill('')
  await expect(page.getByLabel('副本名称', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '创建副本', exact: true })).toBeDisabled()
  await page.getByLabel('副本名称', { exact: true }).fill('新的规则副本')
  await expect(page.getByRole('button', { name: '创建副本', exact: true })).toBeEnabled()
})


test('six admin tabs keep their real controls and desktop layouts reachable', async ({ page }) => {
  await mockAdmin(page)
  await page.goto('/admin/configuration')
  const tabs = [
    ['车型管理', '车型目录', 'vehicles'], ['词包关联', '选择词包', 'links'],
    ['AI 模型', 'AI 模型服务', 'llm'], ['TikHub', 'TikHub 采集服务', 'tikhub'],
    ['AI 分析原则', '版本历史', 'scheme'], ['操作记录', '操作记录', 'audit'],
  ] as const
  for (const width of [1440, 1180]) {
    await page.setViewportSize({ width, height: 900 })
    for (const [name, heading, slug] of tabs) {
      await page.getByRole('button', { name, exact: true }).click()
      await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name, exact: true })).toHaveClass(/active/)
      const bounds = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
      expect(bounds.scroll).toBeLessThanOrEqual(bounds.client + 1)
      if (name === '词包关联') {
        await expect(page.getByRole('button', { name: /品牌词包/ })).not.toContainText('版本')
        if (width === 1440) {
          const list = await page.locator('.list-card').boundingBox()
          const editor = await page.locator('.form-card').boundingBox()
          expect(list!.width).toBeLessThan(editor!.width)
          expect(Math.abs(list!.y - editor!.y)).toBeLessThanOrEqual(1)
        }
      }
      if (process.env.AIMA_ADMIN_SCREENSHOT_DIR) {
        await page.screenshot({ path: `${process.env.AIMA_ADMIN_SCREENSHOT_DIR}/${slug}-${width}.png`, fullPage: true })
      }
    }
  }
})


test('retries a provider-directory load failure before enabling an empty configuration form', async ({ page }) => {
  await mockAdmin(page)
  let calls = 0
  await page.route('**/provider-configs?provider_kind=llm', async (route) => {
    calls += 1
    if (calls === 1) return json(route, { status: 503, title: '读取失败', detail: '服务配置目录暂不可用', request_id: 'directory-failed' }, 503)
    await json(route, { items: [] })
  })
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 模型', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('服务配置目录暂不可用')
  await expect(page.getByLabel('配置名称', { exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '重新读取配置', exact: true }).click()
  await expect(page.getByText('尚未创建 AI 模型配置。填写右侧信息后即可使用。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('配置名称', { exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: '测试连接', exact: true })).not.toBeVisible()
  await expect(page.getByRole('button', { name: '保存并生效', exact: true })).toBeDisabled()
  expect(calls).toBe(2)
})

test('shows a failed connection result and can test again without losing saved configuration', async ({ page }) => {
  await openProvider(page, 'TikHub')
  let calls = 0
  await page.route('**/provider-configs/*/test-connection', async (route) => {
    calls += 1
    await json(route, { ok: calls > 1, message: calls === 1 ? '认证失败，请检查 API Key' : '连接成功', latency_ms: 21 })
  })
  await page.getByRole('button', { name: '测试连接', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('连接测试未通过')
  await expect(page.getByRole('status')).toContainText('认证失败，请检查 API Key')
  await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue('TikHub配置 1')
  await page.getByRole('button', { name: '测试连接', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('连接测试通过')
  await expect(page.getByText('认证失败，请检查 API Key', { exact: true })).not.toBeVisible()
  expect(calls).toBe(2)
})

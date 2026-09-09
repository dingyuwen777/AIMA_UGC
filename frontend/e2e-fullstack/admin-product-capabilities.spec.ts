import { expect, test, type APIRequestContext } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const vehicleContentTitle = '爱玛 U2 车型证据全栈导入'

interface AnalysisRun {
  id: string
  analysis_scheme_version_id: string | null
  status: string
}

async function createKeywordPack(request: APIRequestContext, suffix: string): Promise<{ id: string; name: string }> {
  const name = `U1 词包车型关联 ${suffix}`
  const created = await request.post('/api/v1/keyword-packs', {
    data: {
      name,
      keywords: [{ text: '爱玛', priority: 10, enabled: true }],
    },
  })
  expect(created.status()).toBe(201)
  const pack = await created.json() as { id: string; keywords: { text: string }[] }
  expect(pack.keywords.map((item) => item.text)).toEqual(['爱玛'])
  return { id: pack.id, name }
}

async function uploadVehicleContent(
  request: APIRequestContext,
  fixturePath: string,
  packId: string,
  vehicleId: string,
): Promise<void> {
  const created = await request.post('/api/v1/import-batches', {
    multipart: {
      file: {
        name: 'admin-product.xlsx',
        mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        buffer: await readFile(fixturePath),
      },
      keyword_pack_ids: packId,
      vehicle_model_ids: vehicleId,
    },
  })
  expect(created.status()).toBe(202)
  const batch = await created.json() as { batch_id: string }
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/import-batches/${batch.batch_id}`)
    if (response.status() !== 200) return `http-${response.status()}`
    return (await response.json() as { status: string }).status
  }, { timeout: 60_000 }).toBe('succeeded')
}

async function createAnalysisRun(
  request: APIRequestContext,
  contentId: string,
  suffix: string,
): Promise<AnalysisRun> {
  const targets = { scope: 'selected', content_ids: [contentId] }
  const previewResponse = await request.post('/api/v1/analysis/content-runs/preview', {
    data: { targets },
  })
  expect(previewResponse.status()).toBe(200)
  const preview = await previewResponse.json() as {
    target_count: number
    configuration_hash: string
  }
  const createResponse = await request.post('/api/v1/analysis/content-runs', {
    data: {
      client_idempotency_key: `u4-fullstack-${suffix}`,
      targets,
      expected_target_count: preview.target_count,
      expected_configuration_hash: preview.configuration_hash,
      run_intent: 'manual_reanalysis',
    },
  })
  expect(createResponse.status()).toBe(202)
  const created = await createResponse.json() as { run_id: string }
  let run: AnalysisRun | null = null
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/analysis/content-runs/${created.run_id}`)
    if (response.status() !== 200) return `http-${response.status()}`
    run = await response.json() as AnalysisRun
    return run.status
  }, { timeout: 60_000 }).toBe('succeeded')
  expect(run).not.toBeNull()
  return run!
}

async function firstRelevantContentId(request: APIRequestContext): Promise<string> {
  const response = await request.get(
    '/api/v1/contents?analysis_status=completed&relevance=relevant&limit=1',
  )
  expect(response.status()).toBe(200)
  const body = await response.json() as { items: { id: string }[] }
  expect(body.items.length).toBeGreaterThan(0)
  return body.items[0]!.id
}

async function contentIdBySearch(request: APIRequestContext, search: string): Promise<string> {
  const response = await request.get(`/api/v1/contents?search=${encodeURIComponent(search)}&limit=10`)
  expect(response.status()).toBe(200)
  const body = await response.json() as { items: { id: string; title: string | null }[] }
  const item = body.items.find((candidate) => candidate.title === search)
  expect(item, `必须能按标题重读本用例创建的内容：${search}`).toBeTruthy()
  return item!.id
}

test('车型、词包、Excel 匹配、声音广场筛选与详情形成真实闭环', async ({ page, request }) => {
  const fixturePath = process.env.AIMA_ADMIN_PRODUCT_EXCEL_FIXTURE
  expect(fixturePath, 'AIMA_ADMIN_PRODUCT_EXCEL_FIXTURE 必须指向车型验收 Fixture').toBeTruthy()
  const suffix = Date.now().toString()
  const code = `FS-${suffix}`
  const displayName = `全栈车型 ${suffix}`
  const alias = '爱玛 U2 车型证据全栈导入'
  const pack = await createKeywordPack(request, suffix)

  await page.goto('/admin/configuration')
  await expect(page.getByRole('heading', { name: '管理员配置', exact: true })).toBeVisible()
  await page.getByLabel('车型编码').fill(code)
  await page.getByLabel('显示名称').fill(displayName)
  await page.getByLabel('系列（可选）').fill('全栈系列')
  await page.getByLabel('类别（可选）').fill('电动两轮车')
  await page.getByLabel(/别名/).fill(alias)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('车型已创建并记录操作。', { exact: true })).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: displayName })).toBeVisible()

  const vehiclesResponse = await request.get('/api/v1/vehicle-models?limit=200')
  expect(vehiclesResponse.status()).toBe(200)
  const vehicles = await vehiclesResponse.json() as { items: { id: string; code: string; series_name: string; category_name: string }[] }
  const vehicle = vehicles.items.find((item) => item.code === code)
  expect(vehicle, '浏览器创建的车型必须能从正式目录 API 重读').toBeTruthy()
  expect(vehicle?.series_name).toBe('全栈系列')
  expect(vehicle?.category_name).toBe('电动两轮车')

  await page.getByRole('button', { name: '词包关联', exact: true }).click()
  await page.getByRole('button', { name: new RegExp(pack.name) }).click()
  await page.getByRole('group', { name: /关联车型/ }).getByLabel(new RegExp(displayName)).check()
  await page.getByRole('button', { name: '保存关联', exact: true }).click()
  await expect(page.getByText('词包与车型关联已更新并记录操作。', { exact: true })).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: '词包关联', exact: true }).click()
  await page.getByRole('button', { name: new RegExp(pack.name) }).click()
  await expect(
    page.getByRole('group', { name: /关联车型/ }).getByLabel(new RegExp(displayName)),
  ).toBeChecked()

  await uploadVehicleContent(request, fixturePath!, pack.id, vehicle!.id)

  await page.getByRole('button', { name: '操作记录', exact: true }).click()
  const auditRow = page.getByRole('row').filter({ hasText: '新增车型' }).first()
  await expect(auditRow).toContainText('车型')
  await expect(auditRow).toContainText('local-administrator')
  const auditTechnicalDetails = auditRow.locator('details')
  await expect(auditTechnicalDetails).not.toHaveAttribute('open', '')
  await expect(
    auditTechnicalDetails.getByText('vehicle_model_created', { exact: true }),
  ).not.toBeVisible()

  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '选择车型', exact: true }).click()
  const vehicleFilter = page.getByRole('dialog', { name: '选择车型', exact: true })
  await vehicleFilter.getByRole('button', { name: /全栈系列/ }).click()
  await vehicleFilter.getByLabel(displayName, { exact: true }).check()
  await vehicleFilter.getByRole('button', { name: '确定', exact: true }).click()
  await page.getByRole('button', { name: '查询', exact: true }).click()
  const contentRow = page.locator('article.content-row').filter({ hasText: vehicleContentTitle })
  await expect(contentRow.getByText(vehicleContentTitle, { exact: true })).toBeVisible()
  await expect(contentRow).toContainText('全栈系列 · 电动两轮车')
  const sortingResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/contents' && new URL(response.url()).searchParams.get('sort_by') === 'follower_count')
  await page.getByRole('button', { name: '按粉丝数排序' }).click()
  expect((await sortingResponse).status()).toBe(200)
  await contentRow.getByRole('button', { name: '查看详情', exact: true }).click()
  const detail = page.getByRole('dialog', { name: '内容详情' })
  await detail.getByRole('button', { name: '修改车型', exact: true }).click()
  const vehicleEvidence = detail.locator('article').filter({ hasText: displayName })
  await expect(vehicleEvidence.getByRole('strong').filter({ hasText: displayName })).toBeVisible()
  await expect(vehicleEvidence).toContainText('系统识别')
  await expect(vehicleEvidence).toContainText(`命中“${alias}”`)
  await expect(vehicleEvidence).not.toContainText('catalog v')
})

test('导出 Worker 终态进入当前 Principal 通知并可从声音广场下载', async ({ page, request }) => {
  const contentId = await firstRelevantContentId(request)
  const createdResponse = await request.post('/api/v1/data-exports', {
    data: {
      format: 'xlsx',
      targets: { scope: 'selected', content_ids: [contentId] },
    },
  })
  expect(createdResponse.status()).toBe(202)
  const created = await createdResponse.json() as { export_id: string }

  await expect.poll(async () => {
    const response = await request.get(`/api/v1/data-exports/${created.export_id}`)
    if (response.status() !== 200) return `http-${response.status()}`
    const body = await response.json() as { job: { status: string } }
    return body.job.status
  }).toBe('succeeded')

  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '站内通知' }).click()
  const notification = page.getByRole('button').filter({ hasText: '数据导出已完成' }).first()
  await expect(notification).toContainText('导出文件已可下载。')
  await notification.click()

  await page.getByRole('button', { name: '导出记录' }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  const record = dialog.locator('article').filter({ hasText: created.export_id })
  await expect(record).toContainText('已完成')
  const downloadPromise = page.waitForEvent('download')
  await record.getByRole('button', { name: '下载', exact: true }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(
    `aima-ugc-voice-plaza-${created.export_id}.xlsx`,
  )
  expect(await download.failure()).toBeNull()
})

/** 显式管理过 Provider 后不再回退环境默认值；各流程复用本机 Fake 的持久默认配置。 */
async function ensureFullstackModel(request: APIRequestContext): Promise<void> {
  const response = await request.get('/api/v1/provider-configs?provider_kind=llm')
  expect(response.status()).toBe(200)
  const { items } = await response.json() as { items: { enabled: boolean; is_default: boolean; base_url: string }[] }
  if (items.some((item) => item.enabled && item.is_default && item.base_url === 'http://127.0.0.1:8091/v1')) return
  const created = await request.post('/api/v1/provider-configs', {
    data: {
      provider_kind: 'llm', provider: 'openai_compatible', display_name: '本机全栈默认模型',
      base_url: 'http://127.0.0.1:8091/v1', model: 'deepseek-v4-pro',
      api_key: 'local-fake-provider-credential', enabled: true, is_default: true,
    },
  })
  expect(created.status()).toBe(201)
}

test('管理员发布原子 Scheme 后新 Run 冻结新版本且旧 Run 身份不变', async ({ page, request }) => {
  await ensureFullstackModel(request)
  const contentId = await contentIdBySearch(request, vehicleContentTitle)
  const schemesBeforeResponse = await request.get('/api/v1/analysis-schemes')
  expect(schemesBeforeResponse.status()).toBe(200)
  const schemesBefore = await schemesBeforeResponse.json() as {
    items: Array<{
      active_version_id: string | null
      versions: Array<{ id: string; version: number; status: string }>
    }>
  }
  const activeBefore = schemesBefore.items
    .flatMap((scheme) => scheme.versions)
    .find((version) => schemesBefore.items.some((scheme) => scheme.active_version_id === version.id))
  expect(activeBefore).toBeTruthy()
  const oldRun = await createAnalysisRun(request, contentId, `before-${Date.now()}`)
  expect(oldRun.analysis_scheme_version_id).toBe(activeBefore!.id)

  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 分析原则', exact: true }).click()
  const activeVersionButton = page.getByRole('button', {
    name: new RegExp(`版本 ${activeBefore!.version} · 当前生效`),
  })
  await expect(activeVersionButton).toHaveClass(/active/)
  await page.getByLabel('说明').fill(`U4 全栈发布 ${Date.now()}`)
  await page.getByRole('button', { name: '基于此版本新建草稿', exact: true }).click()
  await expect(page.getByText('AI 分析原则草稿已保存并记录操作。', { exact: true })).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '发布', exact: true }).click()
  await expect(page.getByText('AI 分析原则已发布并记录操作。', { exact: true })).toBeVisible()

  const schemesAfterResponse = await request.get('/api/v1/analysis-schemes')
  expect(schemesAfterResponse.status()).toBe(200)
  const schemesAfter = await schemesAfterResponse.json() as {
    items: Array<{ active_version_id: string | null }>
  }
  const activeAfterId = schemesAfter.items.find((scheme) => scheme.active_version_id)?.active_version_id
  expect(activeAfterId).toBeTruthy()
  expect(activeAfterId).not.toBe(activeBefore!.id)

  const newRun = await createAnalysisRun(request, contentId, `after-${Date.now()}`)
  expect(newRun.analysis_scheme_version_id).toBe(activeAfterId)
  const oldRunResponse = await request.get(`/api/v1/analysis/content-runs/${oldRun.id}`)
  expect(oldRunResponse.status()).toBe(200)
  const oldRunAfterPublish = await oldRunResponse.json() as AnalysisRun
  expect(oldRunAfterPublish.analysis_scheme_version_id).toBe(activeBefore!.id)
  expect(oldRunAfterPublish.status).toBe('succeeded')
})


test('真实审计历史翻到第二页', async ({ page, request }) => {
  const suffix = Date.now().toString()
  for (let index = 0; index < 105; index += 1) {
    const response = await request.post('/api/v1/keyword-packs', {
      data: { name: `audit-page-${suffix}-${index}` },
    })
    expect(response.status()).toBe(201)
  }

  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: '操作记录', exact: true }).click()
  const secondPageRequest = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === '/api/v1/audit-events' && url.searchParams.get('offset') === '100'
  })
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  await secondPageRequest
  await expect(page.getByText(/第 2 \/ \d+ 页/)).toBeVisible()
})

test('未引用关键词包可以从业务界面归档、恢复并安全永久删除', async ({ page, request }) => {
  const pack = await createKeywordPack(request, `lifecycle-${Date.now()}`)

  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  let packRow = page.locator('.pack-row').filter({ hasText: pack.name })
  await expect(packRow).toBeVisible()
  await packRow.click()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档', exact: true }).click()
  await expect(page.getByText('词包已归档。', { exact: true })).toBeVisible()
  await expect(page.locator('.pack-row').filter({ hasText: pack.name })).toHaveCount(0)

  const archivedDetails = page.locator('details.archived-card')
  if (!await archivedDetails.evaluate((element) => (element as HTMLDetailsElement).open)) {
    await archivedDetails.locator('summary').click()
  }
  let archivedRow = archivedDetails.locator('.archived-row').filter({ hasText: pack.name })
  await expect(archivedRow).toBeVisible()
  await archivedRow.getByRole('button', { name: '恢复', exact: true }).click()
  await expect(page.getByText('词包已恢复，当前保持停用。', { exact: true })).toBeVisible()

  packRow = page.locator('.pack-row').filter({ hasText: pack.name })
  await expect(packRow).toBeVisible()
  await expect(packRow).toContainText('已停用')
  await packRow.click()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档', exact: true }).click()
  await expect(page.getByText('词包已归档。', { exact: true })).toBeVisible()
  archivedRow = archivedDetails.locator('.archived-row').filter({ hasText: pack.name })
  await expect(archivedRow).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await archivedRow.getByRole('button', { name: '永久删除', exact: true }).click()
  await expect(page.getByText('未被业务引用的归档词包已永久删除。', { exact: true })).toBeVisible()
  await expect(archivedDetails.locator('.archived-row').filter({ hasText: pack.name })).toHaveCount(0)

  const deleted = await request.get(`/api/v1/keyword-packs/${pack.id}`)
  expect(deleted.status()).toBe(404)
})


test('管理员服务配置通过真实 API 保存、测试连接、归档恢复及安全删除', async ({ page, request }) => {
  await ensureFullstackModel(request)
  const name = `管理员连接验收 ${Date.now()}`
  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: 'AI 模型', exact: true }).click()
  await page.getByRole('button', { name: '新增配置', exact: true }).click()
  await page.getByLabel('配置名称', { exact: true }).fill(name)
  await page.getByLabel('模型标识', { exact: true }).fill('deepseek-v4-pro')
  await page.getByLabel('服务地址', { exact: true }).fill('http://127.0.0.1:8091/v1')
  await page.getByLabel('访问密钥', { exact: true }).fill('local-fake-provider-credential')
  await page.getByLabel('设为默认 AI 模型', { exact: false }).uncheck()
  const createdResponse = page.waitForResponse((response) => response.url().endsWith('/provider-configs') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '保存并生效', exact: true }).click()
  const created = await createdResponse
  expect(created.status()).toBe(201)
  const config = await created.json() as { id: string; revision: number; secret_configured: boolean }
  expect(config.secret_configured).toBe(true)
  expect(config).not.toHaveProperty('api_key')
  await expect(page.getByLabel(/^访问密钥/)).toHaveValue('')
  await page.getByRole('button', { name: '测试连接', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('连接测试通过')
  await page.getByLabel('配置名称', { exact: true }).fill(`${name} 已更新`)
  await expect(page.getByRole('button', { name: '测试连接', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '保存并生效', exact: true }).click()
  await expect(page.getByText('配置已保存；新任务将使用新配置，正在运行的任务不受影响。', { exact: true })).toBeVisible()
  const read = await request.get('/api/v1/provider-configs?provider_kind=llm')
  const saved = (await read.json() as { items: { id: string; display_name: string; revision: number; enabled: boolean; is_default: boolean }[] }).items.find((item) => item.id === config.id)
  expect(saved).toMatchObject({ display_name: `${name} 已更新`, revision: config.revision + 1 })
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档', exact: true }).click()
  await expect(page.getByText('服务配置已归档。', { exact: true })).toBeVisible()
  await page.getByText('已归档配置（全部服务类型）', { exact: true }).click()
  const archived = page.locator('.archived-item').filter({ hasText: `${name} 已更新` })
  await archived.getByRole('button', { name: '恢复', exact: true }).click()
  await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue(`${name} 已更新`)
  await expect(page.getByLabel('启用配置', { exact: false })).not.toBeChecked()
  await expect(page.getByLabel('设为默认 AI 模型', { exact: false })).not.toBeChecked()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档', exact: true }).click()
  await expect(archived).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await archived.getByRole('button', { name: '永久删除', exact: true }).click()
  await expect(page.getByText('未进入业务历史的服务配置已永久删除。', { exact: true })).toBeVisible()
  await expect(archived).not.toBeVisible()
  const remaining = await request.get('/api/v1/provider-configs?provider_kind=llm')
  expect((await remaining.json() as { items: { id: string }[] }).items.some((item) => item.id === config.id)).toBe(false)
})

import { expect, test } from './fixture'
import { captureScrollbarEvidence } from './scrollbarEvidence'
import type { Page } from '@playwright/test'

import {
  stubVoicePlazaTaxonomy,
  voicePlazaFilterOptionsFixture,
  voicePlazaTaxonomyFixture,
} from './voicePlazaTaxonomy'

const contentId = '42345678-1234-5678-1234-567812345678'
const analysisJobId = '52345678-1234-5678-1234-567812345678'
const analysisRunId = '62345678-1234-5678-1234-567812345678'
const exportId = '72345678-1234-5678-1234-567812345678'
const exportJobId = '82345678-1234-5678-1234-567812345678'
const brandId = '92345678-1234-4678-9234-567812345678'
const vehicleId = 'a2345678-1234-4678-9234-567812345678'

async function personalColumnCatalog(page: Page): Promise<void> {
  await page.route('**/api/v1/export-columns', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ version: 3, columns: [
      { key: 'platform', label: '平台', group: '内容', default_selected: true },
      { key: 'title', label: '标题', group: '内容', default_selected: false },
      { key: 'text', label: '正文', group: '内容', default_selected: true },
      { key: 'author', label: '作者', group: '内容', default_selected: false },
    ] }) })
  })
}

const analysisRun = {
  id: analysisRunId,
  planner_job_id: analysisJobId,
  sequence_no: 1,
  status: 'running',
  run_intent: 'manual_reanalysis',
  scope: 'query',
  target_count: 20,
  shard_count: 2,
  shard_size: 6,
  prompt_version: 'content-labeling.v3.0',
  prompt_sha256: 'a'.repeat(64),
  taxonomy_sha256: 'b'.repeat(64),
  model_provider: 'openai-compatible',
  model: 'fixture-model',
  generation_config: { temperature: 0 },
  generation_config_hash: 'c'.repeat(64),
  stats: { pending: 16, succeeded: 4, failed: 0, cancelled: 0, stale: 0 },
  shards: [
    { request_id: '63345678-1234-5678-1234-567812345678', job_id: '64345678-1234-5678-1234-567812345678', shard_no: 0, target_count: 4, status: 'running', progress: 50, error_code: null },
    { request_id: '65345678-1234-5678-1234-567812345678', job_id: '66345678-1234-5678-1234-567812345678', shard_no: 1, target_count: 6, status: 'running', progress: 25, error_code: null },
  ],
  created_at: '2026-08-21T03:00:00Z',
  started_at: null,
  finished_at: null,
}

const item = {
  id: contentId,
  platform: 'xiaohongshu',
  external_content_id: 'note-stage8d-1',
  content_type: 'note',
  title: '爱玛 Q7 的坐垫舒适，但续航仍有提升空间',
  text: '日常通勤约 12 公里，坐垫很舒服，希望后续优化低温续航。',
  author_display_name: '小满的通勤日记',
  published_at: '2026-08-21T01:42:00Z',
  last_seen_at: '2026-08-21T02:00:00Z',
  content_version: 1,
  brands: [{
    id: brandId, code: 'AIMA', display_name: '爱玛', role: 'owned',
    evidences: [{ source: 'vehicle_match', matched_text: '爱玛 Q7', source_field: 'title', catalog_version: 18, derived_vehicle_model_id: vehicleId }],
  }],
  vehicles: [{
    vehicle_model_id: vehicleId, code: 'AIMA-Q7', display_name: '爱玛 Q7', series_name: 'Q 系列', category_name: '通勤',
    brand: { id: brandId, code: 'AIMA', display_name: '爱玛', role: 'owned' },
    evidences: [{ source: 'alias_match', matched_text: 'Q7', source_field: 'title', catalog_version: 18 }],
  }],
  competition_scope: 'owned_only',
  content_url: 'https://example.com/note-stage8d-1',
  metrics: { like_count: 128, comment_count: 18, share_count: 6, favorite_count: 32 },
  analysis: {
    status: 'completed',
    relevance: 'relevant',
    voice_type: '真实用户发声',
    sentiment: '负面',
    labels: [
      { primary_label: '电池、续航与充电', secondary_label: '实际续航表现' },
      { primary_label: '驾乘体验', secondary_label: '坐垫舒适性' },
      { primary_label: '售后服务', secondary_label: '客服与服务态度' },
    ],
    analyzed_at: '2026-08-21T02:30:00Z',
    model_provider: 'fixture',
    model: 'fixture-model',
  },
  effective_relevance: 'relevant',
  relevance_source: 'ai',
  source: {
    provider_name: 'file-import',
    import_batch_id: '12345678-1234-5678-1234-567812345678',
  },
}

const job = (id: string, jobType: string) => ({
  id,
  job_type: jobType,
  status: 'queued',
  attempt: 0,
  max_attempts: 3,
  progress: 0,
  error_code: null,
  result: null,
  created_at: '2026-08-21T03:00:00Z',
  started_at: null,
  finished_at: null,
})

const runningExport = {
  id: exportId,
  job: {
    ...job(exportJobId, 'reporting.content-export-excel.v1'),
    status: 'running',
    progress: 64,
  },
  artifact_id: null,
  filename: null,
  stats: null,
  created_at: '2026-08-21T03:00:00Z',
  completed_at: null,
}

test.beforeEach(async ({ page }) => {
  await stubVoicePlazaTaxonomy(page)

  await page.route('**/api/v1/export-columns', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        version: 1,
        columns: [
          { key: 'platform', label: '平台', sensitive: false, default_selected: true },
        ],
      }),
    })
  })

  await page.route('**/api/v1/vehicle-models**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
        catalog_version: 1,
        offset: 0,
        limit: 200,
      }),
    })
  })

  await page.route('**/api/v1/vehicle-brands**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ id: brandId, code: 'AIMA', display_name: '爱玛', role: 'owned', status: 'active', version: 1, catalog_version: 18, aliases: [], created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-28T00:00:00Z' }],
        total: 1,
        catalog_version: 18,
        offset: 0,
        limit: 200,
      }),
    })
  })

  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: true }),
    })
  })

  await page.route('**/api/v1/contents**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === `/api/v1/contents/${contentId}/comments`) {
      const isReplyPage = url.searchParams.get('root_comment_id') === 'comment-root-1'
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: isReplyPage ? [
            {
              id: '92345678-1234-5678-1234-567812345679',
              external_comment_id: 'comment-reply-1',
              root_comment_id: 'comment-root-1',
              parent_comment_id: 'comment-root-1',
              parent_author_display_name: '用户乙',
              author_display_name: '内容作者',
              text: '低温时我也遇到了，充电后会好一些。',
              published_at: '2026-08-21T02:15:00Z',
              like_count: 1,
              reply_count: 0,
              ingested_reply_count: 0,
              is_by_content_author: true,
            },
          ] : [
            {
              id: '92345678-1234-5678-1234-567812345678',
              external_comment_id: 'comment-root-1',
              root_comment_id: 'comment-root-1',
              parent_comment_id: null,
              parent_author_display_name: null,
              author_display_name: '用户乙',
              text: '我也关注冬季续航。',
              published_at: '2026-08-21T02:10:00Z',
              like_count: 3,
              reply_count: 1,
              ingested_reply_count: 1,
              is_by_content_author: false,
            },
          ],
          next_cursor: null,
          has_more: false,
          total_count: 1,
          ingested_total_count: 2,
        }),
      })
      return
    }
    if (url.pathname === `/api/v1/contents/${contentId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          ...item,
          media: [],
          comments: [
            {
              id: '92345678-1234-5678-1234-567812345678',
              external_comment_id: 'comment-1',
              author_display_name: '用户乙',
              text: '我也关注冬季续航。',
              published_at: '2026-08-21T02:10:00Z',
              like_count: 3,
              reply_count: 0,
            },
          ],
          comment_coverage: {
            coverage: 'partial',
            reported_total: 18,
            collected_count: 1,
            observed_at: '2026-08-21T02:20:00Z',
          },
          source_records: [item.source],
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [item], next_cursor: null, has_more: false }),
    })
  })

  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        target_count: 1,
        shard_count: 1,
        shard_size: 1,
        prompt_version: 'content-labeling.v3.0',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '当前无法可靠估算费用；运行后以实际审计为准。',
      }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: analysisRunId,
          planner_job_id: analysisJobId,
          target_count: 1,
          shard_count: 1,
          status: 'queued',
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })
  await page.route(`**/api/v1/analysis/content-runs/${analysisRunId}`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(analysisRun),
    })
  })
  await page.route(`**/api/v1/analysis/content-runs/${analysisRunId}/cancel`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: analysisRunId,
        planner_job_id: analysisJobId,
        sequence_no: 1,
        status: 'cancelled',
        run_intent: 'manual_reanalysis',
        scope: 'query',
        target_count: 1,
        shard_count: 1,
        shard_size: 1,
        prompt_version: 'content-labeling.v3.0',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        stats: { pending: 0, succeeded: 0, failed: 0, cancelled: 1, stale: 0 },
        shards: [],
        created_at: '2026-08-21T03:00:00Z',
        started_at: null,
        finished_at: '2026-08-21T03:01:00Z',
      }),
    })
  })

  await page.route('**/api/v1/data-exports**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'POST') {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          export_id: exportId,
          job_id: exportJobId,
          target_count: 1,
          status: 'queued',
        }),
      })
      return
    }
    if (url.pathname === `/api/v1/data-exports/${exportId}`) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          id: exportId,
          job: job(exportJobId, 'reporting.content-export-excel.v1'),
          artifact_id: null,
          filename: null,
          stats: null,
          created_at: '2026-08-21T03:00:00Z',
          completed_at: null,
        }),
      })
      return
    }
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [runningExport] }),
    })
  })
})

test('renders every AI label and opens the text-first content detail', async ({ page }) => {
  let replyRequestCount = 0
  let detailSkippedEmbeddedComments = false
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname === `/api/v1/contents/${contentId}`) {
      detailSkippedEmbeddedComments = url.searchParams.get('include_comments') === 'false'
    }
    if (
      url.pathname === `/api/v1/contents/${contentId}/comments`
      && url.searchParams.get('root_comment_id') === 'comment-root-1'
    ) replyRequestCount += 1
  })
  await page.goto('/voice-plaza')

  await expect(page.getByRole('heading', { name: '声音广场' })).toBeVisible()
  await expect(page.getByPlaceholder('搜索标题、正文或作者')).toBeVisible()
  await expect(page.getByText('统计准确数量', { exact: true })).toHaveCount(0)
  await expect(page.getByTitle('电池、续航与充电 / 实际续航表现', { exact: true })).toBeVisible()
  await expect(page.getByTitle('驾乘体验 / 坐垫舒适性', { exact: true })).toBeVisible()
  await expect(page.getByTitle('售后服务 / 客服与服务态度', { exact: true })).toBeVisible()
  await expect(page.getByText('自有品牌', { exact: true }).first()).toBeVisible()
  await expect(page.locator('.content-row .competition-scope')).toHaveText('仅自有品牌')

  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/stage8d-voice-plaza.png', fullPage: true })
  }

  await page.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByRole('dialog', { name: '内容详情' })).toBeVisible()
  expect(detailSkippedEmbeddedComments).toBe(true)
  await expect(page.getByText('内容与 AI 信息')).toBeVisible()
  await expect(page.getByRole('dialog', { name: '内容详情' }).locator('.info-grid')).toContainText('电池、续航与充电 / 实际续航表现')
  await expect(page.getByRole('dialog', { name: '内容详情' }).locator('.info-grid')).toContainText('驾乘体验 / 坐垫舒适性')
  await expect(page.getByRole('dialog', { name: '内容详情' }).locator('.info-grid')).toContainText('售后服务 / 客服与服务态度')
  await expect(page.getByText('我也关注冬季续航。')).toBeVisible()
  await expect(page.getByText('已采集')).toBeVisible()
  await expect(page.getByText('低温时我也遇到了，充电后会好一些。')).toHaveCount(0)
  expect(replyRequestCount).toBe(0)
  await page.getByRole('button', { name: '查看 1 条回复' }).click()
  await expect(page.getByText('低温时我也遇到了，充电后会好一些。')).toBeVisible()
  expect(replyRequestCount).toBe(1)
  await expect(page.getByText('回复 用户乙')).toBeVisible()
  await expect(page.getByText('原作者', { exact: true })).toBeVisible()
  await expect(page.getByRole('dialog', { name: '内容详情' }).locator('.info-grid')).toContainText('真实用户发声')
  await expect(page.getByRole('dialog', { name: '内容详情' }).getByText('技术详情', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: '内容详情' }).getByText('Content ID', { exact: true })).toHaveCount(0)
  await expect(page.getByText('原始内容媒体')).toHaveCount(0)
  if (process.env.AIMA_CAPTURE_VISUAL === '1') {
    await page.screenshot({ path: 'test-results/stage8d-content-detail.png', fullPage: true })
  }
})

test('工作台内容深链跨分页直接定位声音广场真实笔记', async ({ page }) => {
  await page.route('**/api/v1/contents?*', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })
  await page.goto(`/voice-plaza?content_id=${contentId}`)
  const detail = page.getByRole('dialog', { name: '内容详情' })
  await expect(detail).toBeVisible()
  await expect(detail).toContainText('小满的通勤日记')
  await expect(detail).toContainText('爱玛 Q7 的坐垫舒适')
})

test('导入记录查看声音时不继承会话中陈旧筛选', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('aima.applied-filters.principal.v1', JSON.stringify(['local-administrator', 'administrator', 'development']))
    sessionStorage.setItem('aima.voice-plaza.applied-search.v1', JSON.stringify({
      filters: { search: '旧关键词', publishedFrom: '2020-01-01', sourceIdentifier: '旧来源' },
      sortBy: 'published_at',
      sortDirection: 'desc',
    }))
  })
  const listRequest = page.waitForRequest((request) =>
    new URL(request.url()).pathname === '/api/v1/contents'
      && request.method() === 'GET')
  await page.goto('/voice-plaza?source_identifier=12345678-1234-5678-1234-567812345678')
  const url = new URL((await listRequest).url())
  expect(url.searchParams.get('source_identifier')).toBe('12345678-1234-5678-1234-567812345678')
  expect(url.searchParams.get('published_from')).toBeNull()
  expect(url.searchParams.get('search')).toBeNull()
})

test('旧 secondary-only 深链跨 building 到 ready 始终保持原查询语义', async ({ page }) => {
  await page.unroute('**/api/v1/content-filter-options')
  let filterOptionsReads = 0
  await page.route('**/api/v1/content-filter-options', async (route) => {
    filterOptionsReads += 1
    const labels = filterOptionsReads === 1
      ? [{
          primary_label: '产品体验',
          source: 'active',
          secondary_labels: [{ value: '续航表现', source: 'active' }],
        }]
      : [
          {
            primary_label: '产品体验',
            source: 'active',
            secondary_labels: [{ value: '续航表现', source: 'active' }],
          },
          {
            primary_label: '服务体验',
            source: 'active',
            secondary_labels: [{ value: '续航表现', source: 'active' }],
          },
        ]
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...voicePlazaFilterOptionsFixture,
        catalog_status: filterOptionsReads === 1 ? 'building' : 'ready',
        labels,
      }),
    })
  })

  const listRequests: URLSearchParams[] = []
  const countFilters: Array<{ primary_labels?: string[], secondary_labels?: string[] }> = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname === '/api/v1/contents') {
      listRequests.push(url.searchParams)
    }
    if (request.method() === 'POST' && url.pathname === '/api/v1/contents/count') {
      const body = request.postDataJSON() as {
        filters?: { primary_labels?: string[], secondary_labels?: string[] }
      }
      countFilters.push(body.filters ?? {})
    }
  })

  await page.goto('/voice-plaza?secondary_label=续航表现')
  await expect(page.getByText(/当前保留旧版兼容筛选：二级「续航表现」/)).toBeVisible()
  await expect.poll(() => filterOptionsReads, { timeout: 20_000 }).toBeGreaterThanOrEqual(2)

  const secondaryOnlyLists = listRequests.filter((params) =>
    params.getAll('secondary_labels').includes('续航表现'),
  )
  expect(secondaryOnlyLists.length).toBeGreaterThan(0)
  expect(secondaryOnlyLists.every((params) => params.getAll('primary_labels').length === 0)).toBe(true)
  const secondaryOnlyCounts = countFilters.filter((filters) =>
    filters.secondary_labels?.includes('续航表现') === true,
  )
  expect(secondaryOnlyCounts.length).toBeGreaterThan(0)
  expect(secondaryOnlyCounts.every((filters) => (filters.primary_labels?.length ?? 0) === 0)).toBe(true)

  const persisted = await page.evaluate(() => JSON.parse(
    sessionStorage.getItem('aima.voice-plaza.applied-search.v1') ?? '{}',
  ))
  expect(persisted.filters).toMatchObject({
    primaryLabels: [],
    secondaryLabels: ['续航表现'],
  })
  expect(persisted.legacyLabelCompatibility).toEqual({
    primaryLabels: [],
    secondaryLabels: ['续航表现'],
  })

  // 用户主动选择当前父级并提交，compatibility 才清除并进入层级规则。
  const filters = page.locator('section.filters')
  const primaryField = filters.locator('.filter-row--tertiary .field').nth(0)
  await filters.getByLabel('一级标签', { exact: true }).click()
  await primaryField.getByRole('checkbox', { name: '服务体验' }).check()
  const currentQuery = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return request.method() === 'GET'
      && url.pathname === '/api/v1/contents'
      && url.searchParams.getAll('primary_labels').includes('服务体验')
      && url.searchParams.getAll('secondary_labels').includes('续航表现')
  })
  await page.getByRole('button', { name: '查询' }).click()
  await currentQuery
  await expect(page.getByText(/当前保留旧版兼容筛选/)).toHaveCount(0)

  const migrated = await page.evaluate(() => JSON.parse(
    sessionStorage.getItem('aima.voice-plaza.applied-search.v1') ?? '{}',
  ))
  expect(migrated.legacyLabelCompatibility).toBeNull()
  expect(migrated.filters).toMatchObject({
    primaryLabels: ['服务体验'],
    secondaryLabels: ['续航表现'],
  })
})

test('旧 cross-parent singular 深链在目录加载后保持原 AND 语义并明确提示', async ({ page }) => {
  const listRequests: URLSearchParams[] = []
  const countFilters: Array<{ primary_labels?: string[], secondary_labels?: string[] }> = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname === '/api/v1/contents') {
      listRequests.push(url.searchParams)
    }
    if (request.method() === 'POST' && url.pathname === '/api/v1/contents/count') {
      const body = request.postDataJSON() as {
        filters?: { primary_labels?: string[], secondary_labels?: string[] }
      }
      countFilters.push(body.filters ?? {})
    }
  })

  await page.goto(
    '/voice-plaza?primary_label=产品体验&secondary_label=客服与服务态度',
  )
  await expect(page.getByText(/当前保留旧版兼容筛选：一级「产品体验」 AND 二级「客服与服务态度」/))
    .toBeVisible()

  await expect.poll(() => listRequests.length).toBeGreaterThan(0)
  await expect.poll(() => countFilters.length).toBeGreaterThan(0)
  expect(listRequests.some((params) =>
    params.getAll('primary_labels').includes('产品体验')
      && params.getAll('secondary_labels').includes('客服与服务态度'),
  )).toBe(true)
  expect(listRequests.some((params) =>
    params.getAll('primary_labels').includes('产品体验')
      && params.getAll('secondary_labels').length === 0,
  )).toBe(false)
  expect(countFilters.some((filters) =>
    filters.primary_labels?.includes('产品体验') === true
      && filters.secondary_labels?.includes('客服与服务态度') === true,
  )).toBe(true)
  expect(countFilters.some((filters) =>
    filters.primary_labels?.includes('产品体验') === true
      && (filters.secondary_labels?.length ?? 0) === 0,
  )).toBe(false)

  const persisted = await page.evaluate(() => JSON.parse(
    sessionStorage.getItem('aima.voice-plaza.applied-search.v1') ?? '{}',
  ))
  expect(persisted.filters).toMatchObject({
    primaryLabels: ['产品体验'],
    secondaryLabels: ['客服与服务态度'],
  })
  expect(persisted.legacyLabelCompatibility).toEqual({
    primaryLabels: ['产品体验'],
    secondaryLabels: ['客服与服务态度'],
  })
})

test('旧 catalog-missing singular 深链在目录加载后仍保留精确条件', async ({ page }) => {
  const listRequests: URLSearchParams[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname === '/api/v1/contents') {
      listRequests.push(url.searchParams)
    }
  })

  await page.goto(
    '/voice-plaza?primary_label=已下线一级&secondary_label=已下线二级',
  )
  await expect(page.getByText(/当前保留旧版兼容筛选：一级「已下线一级」 AND 二级「已下线二级」/))
    .toBeVisible()

  await expect.poll(() => listRequests.length).toBeGreaterThan(0)
  expect(listRequests.some((params) =>
    params.getAll('primary_labels').includes('已下线一级')
      && params.getAll('secondary_labels').includes('已下线二级'),
  )).toBe(true)
  expect(listRequests.some((params) =>
    params.getAll('primary_labels').length === 0
      && params.getAll('secondary_labels').length === 0,
  )).toBe(false)

  const persisted = await page.evaluate(() => JSON.parse(
    sessionStorage.getItem('aima.voice-plaza.applied-search.v1') ?? '{}',
  ))
  expect(persisted.legacyLabelCompatibility).toEqual({
    primaryLabels: ['已下线一级'],
    secondaryLabels: ['已下线二级'],
  })
})

test('loads backend filter options and submits voice type with dependent labels', async ({ page }) => {
  await page.goto('/voice-plaza')

  await expect(page.getByLabel('发声类型', { exact: true })).toBeVisible()
  await page.getByLabel('发声类型', { exact: true }).click()
  await page.getByRole('checkbox', { name: '真实用户发声' }).check()
  await page.getByLabel('情感', { exact: true }).click()
  await page.getByRole('checkbox', { name: '负面' }).check()

  const filters = page.locator('section.filters')
  const primaryField = filters.locator('.filter-row--tertiary .field').nth(0)
  const secondaryField = filters.locator('.filter-row--tertiary .field').nth(1)
  await filters.getByLabel('一级标签', { exact: true }).click()
  await primaryField.getByRole('checkbox', { name: '电池、续航与充电' }).check()
  await filters.getByLabel('二级标签', { exact: true }).click()
  await secondaryField.getByRole('checkbox', { name: '实际续航表现', exact: true }).check()

  await page.getByRole('button', { name: '选择品牌', exact: true }).click()
  const brandDialog = page.getByRole('dialog', { name: '选择品牌', exact: true })
  await brandDialog.getByLabel(/爱玛/).check()
  await brandDialog.getByRole('button', { name: '确定', exact: true }).click()
  const requestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return url.pathname === '/api/v1/contents' && url.searchParams.has('voice_types')
  })
  await page.getByRole('button', { name: '查询' }).click()
  const request = await requestPromise
  const params = new URL(request.url()).searchParams

  expect(params.getAll('voice_types')).toEqual(['真实用户发声'])
  expect(params.getAll('sentiments')).toEqual(['负面'])
  expect(params.getAll('primary_labels')).toEqual(['电池、续航与充电'])
  expect(params.getAll('secondary_labels')).toEqual(['实际续航表现'])
  expect(params.get('primary_label')).toBeNull()
  expect(params.get('secondary_label')).toBeNull()
  expect(params.get('brand_ids')).toBe(brandId)
})

test('renders the newest first page before slow filter options are ready', async ({ page }) => {
  await page.unroute('**/api/v1/content-filter-options')
  let releaseFilterOptions!: () => void
  const filterOptionsReady = new Promise<void>((resolve) => { releaseFilterOptions = resolve })
  await page.route('**/api/v1/content-filter-options', async (route) => {
    await filterOptionsReady
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(voicePlazaFilterOptionsFixture),
    })
  })

  const firstPageRequest = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return request.method() === 'GET' && url.pathname === '/api/v1/contents'
  })
  await page.goto('/voice-plaza')
  const request = await firstPageRequest
  const params = new URL(request.url()).searchParams
  expect(params.get('limit')).toBe('20')
  expect(params.get('sort_by')).toBe('published_at')
  expect(params.get('sort_direction')).toBe('desc')
  await expect(page.getByText(item.title), '最新倒序第一页不应等待筛选目录').toBeVisible({
    timeout: 2_000,
  })
  await expect(page.locator('section.filters').getByLabel('平台', { exact: true })).toBeEnabled()
  releaseFilterOptions()
  await expect(page.getByLabel('发声类型', { exact: true })).toBeEnabled()
})

test('keeps filters and content usable when manual-edit taxonomy is unavailable', async ({ page }) => {
  await page.unroute('**/api/v1/content-analysis-taxonomy')
  await page.route('**/api/v1/content-analysis-taxonomy', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'https://aima.example/problems/content_analysis_taxonomy_unavailable',
        title: 'AI 分类配置暂不可用',
        status: 503,
        detail: '当前 Prompt Taxonomy 无法安全读取或校验。',
        request_id: 'request-taxonomy',
        errors: [],
      }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByRole('alert').getByText('当前 AI 分析规则暂不可用', { exact: true })).toBeVisible()
  const taxonomyWarning = page.locator('.taxonomy-warning')
  await expect(taxonomyWarning.getByText('技术详情', { exact: true })).toHaveCount(0)
  await expect(taxonomyWarning.getByText(/request-taxonomy/)).toHaveCount(0)
  await expect(page.getByLabel('发声类型', { exact: true })).toBeEnabled()
  await expect(page.getByText(item.title)).toBeVisible()
  await expect(page.getByRole('button', { name: /导出记录/ })).toBeEnabled()
})

test('does not block the initial content list on a slow manual-edit taxonomy', async ({ page }) => {
  await page.unroute('**/api/v1/content-analysis-taxonomy')
  let releaseTaxonomy!: () => void
  const taxonomyReady = new Promise<void>((resolve) => { releaseTaxonomy = resolve })
  await page.route('**/api/v1/content-analysis-taxonomy', async (route) => {
    await taxonomyReady
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(voicePlazaTaxonomyFixture),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByText(item.title), '内容列表只依赖已加载的筛选目录').toBeVisible({
    timeout: 2_000,
  })
  releaseTaxonomy()
})

test('keeps stable filters and content usable when dynamic filter options are unavailable', async ({ page }) => {
  await page.unroute('**/api/v1/content-filter-options')
  await page.route('**/api/v1/content-filter-options', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'about:blank',
        title: '筛选项暂不可用',
        status: 503,
        detail: '当前筛选目录无法读取。',
        request_id: 'request-filter-options',
        errors: [],
      }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByRole('alert').getByText('部分动态筛选项暂不可用', { exact: true })).toBeVisible()
  const filters = page.locator('section.filters')
  for (const label of ['平台', '相关性', '状态']) {
    await expect(filters.getByLabel(label, { exact: true })).toBeEnabled()
  }
  for (const label of ['情感', '发声类型']) {
    await expect(filters.getByLabel(label, { exact: true })).toBeDisabled()
  }
  await expect(filters.getByLabel('内容类型', { exact: true })).toHaveCount(0)
  for (const label of ['一级标签', '二级标签']) {
    await expect(filters.getByLabel(label, { exact: true })).toHaveAttribute('aria-disabled', 'true')
  }
  await expect(page.getByText(item.title)).toBeVisible()
})

test('标签多选使用不改变布局且可按常见方式关闭的互斥浮层', async ({ page }) => {
  await page.goto('/voice-plaza')
  const filters = page.locator('section.filters')
  const primaryTrigger = filters.getByRole('button', { name: /^一级标签/ })
  const secondaryTrigger = filters.getByRole('button', { name: /^二级标签/ })
  const primaryDialog = page.getByRole('dialog', { name: '选择一级标签', exact: true })
  const secondaryDialog = page.getByRole('dialog', { name: '选择二级标签', exact: true })
  const initialHeight = await filters.evaluate((element) => element.getBoundingClientRect().height)
  const actionButtons = [
    page.getByRole('button', { name: '条件重置', exact: true }),
    page.getByRole('button', { name: '查询', exact: true }),
  ]
  const initialActionPositions = await Promise.all(
    actionButtons.map((button) => button.evaluate((element) => {
      const box = element.getBoundingClientRect()
      return { x: box.x, y: box.y }
    })),
  )

  await primaryTrigger.click()
  await expect(primaryDialog).toBeVisible()
  await expect.poll(
    () => filters.evaluate((element) => element.getBoundingClientRect().height),
  ).toBe(initialHeight)
  await expect.poll(() => Promise.all(
    actionButtons.map((button) => button.evaluate((element) => {
      const box = element.getBoundingClientRect()
      return { x: box.x, y: box.y }
    })),
  )).toEqual(initialActionPositions)
  const panelMetrics = await primaryDialog.evaluate((element) => ({
    height: element.getBoundingClientRect().height,
    overflowY: getComputedStyle(element).overflowY,
  }))
  expect(panelMetrics.height).toBeLessThanOrEqual(270)
  expect(panelMetrics.overflowY).toBe('auto')
  await primaryDialog.getByRole('checkbox', { name: '产品体验', exact: true }).check()
  await expect(primaryDialog).toBeVisible()

  await secondaryTrigger.click()
  await expect(primaryDialog).toBeHidden()
  await expect(secondaryDialog).toBeVisible()
  await secondaryTrigger.click()
  await expect(secondaryDialog).toBeHidden()

  await secondaryTrigger.click()
  await page.getByRole('heading', { name: '声音广场', exact: true }).click()
  await expect(secondaryDialog).toBeHidden()

  await primaryTrigger.click()
  await page.keyboard.press('Escape')
  await expect(primaryDialog).toBeHidden()
  await expect(primaryTrigger).toBeFocused()
})

test('后台筛选目录延迟和失败保留草稿、打开的面板和几何', async ({ page }) => {
  await page.clock.install()
  let reads = 0
  let release!: () => void
  const delayed = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/content-filter-options', async (route) => {
    reads += 1
    if (reads === 1) return route.fulfill({ json: { ...voicePlazaFilterOptionsFixture, catalog_status: 'building' } })
    await delayed
    return route.fulfill({ status: 503, json: { status: 503, detail: '目录暂时不可用', request_id: 'warm-options', errors: [] } })
  })
  await page.goto('/voice-plaza')
  const filters = page.locator('section.filters')
  await expect(filters.getByLabel('情感', { exact: true })).toBeEnabled()
  await filters.getByRole('button', { name: /^一级标签/ }).click()
  const dialog = page.getByRole('dialog', { name: '选择一级标签', exact: true })
  await dialog.getByRole('checkbox', { name: '产品体验', exact: true }).check()
  const before = await filters.boundingBox()
  const tableBefore = await page.locator('.content-list').boundingBox()
  await page.clock.fastForward(15_000)
  await expect.poll(() => reads).toBe(2)
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('checkbox', { name: '产品体验', exact: true })).toBeChecked()
  await expect(filters.getByLabel('情感', { exact: true })).toBeEnabled()
  expect(await filters.boundingBox()).toEqual(before)
  expect(await page.locator('.content-list').boundingBox()).toEqual(tableBefore)
  release()
  await expect(page.getByText('部分动态筛选项暂不可用', { exact: true })).toBeVisible()
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('checkbox', { name: '产品体验', exact: true })).toBeChecked()
  await expect(filters.getByLabel('情感', { exact: true })).toBeEnabled()
  expect(await filters.boundingBox()).toEqual(before)
  expect(await page.locator('.content-list').boundingBox()).toEqual(tableBefore)
})

test('详情后台失败保持人工纠正草稿、正文几何和滚动位置', async ({ page }) => {
  await page.clock.install()
  let changed = false
  await page.route('**/api/v1/analysis/content-runs', (route) => route.fulfill({ json: { items: [{
    ...analysisRun, stats: { ...analysisRun.stats, succeeded: changed ? 5 : 4 },
  }] } }))
  let detailReads = 0
  let release!: () => void
  const delayed = new Promise<void>((resolve) => { release = resolve })
  await page.route(`**/api/v1/contents/${contentId}?*`, async (route) => {
    detailReads += 1
    if (detailReads === 1) return route.fallback()
    await delayed
    return route.fulfill({ status: 503, json: { status: 503, detail: '详情暂时不可用', request_id: 'detail-refresh', errors: [] } })
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '内容详情' })
  await expect(detail.locator('.drawer-body')).toBeVisible()
  await detail.getByRole('button', { name: '人工纠正', exact: true }).click()
  await detail.getByRole('combobox', { name: /^情感/ }).selectOption('正面')
  const scroll = detail.locator('.aima-dialog-body')
  await scroll.evaluate((element) => { element.scrollTop = 200 })
  const before = await detail.locator('.drawer-body').boundingBox()
  const scrollBefore = await scroll.evaluate((element) => element.scrollTop)
  changed = true
  await page.clock.fastForward(1_000)
  await expect.poll(() => detailReads).toBe(2)
  expect(await detail.locator('.drawer-body').boundingBox()).toEqual(before)
  release()
  await expect(detail.getByText('更新失败，保留上次详情。', { exact: false })).toBeVisible()
  expect(await detail.locator('.drawer-body').boundingBox()).toEqual(before)
  expect(await scroll.evaluate((element) => element.scrollTop)).toBe(scrollBefore)
  await expect(detail.getByRole('combobox', { name: /^情感/ })).toHaveValue('正面')
})

test('主动查询清除旧结果，延迟和失败保持列表几何', async ({ page }) => {
  let release!: () => void
  const delayed = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/contents?*', async (route) => {
    if (new URL(route.request().url()).searchParams.get('search') !== '新查询') return route.fallback()
    await delayed
    return route.fulfill({ status: 503, json: { status: 503, detail: '新查询暂时不可用', request_id: 'query-change', errors: [] } })
  })
  await page.goto('/voice-plaza')
  const table = page.locator('.content-list')
  await expect(table.getByText(item.title)).toBeVisible()
  const before = await table.boundingBox()
  await page.getByLabel('搜索内容', { exact: true }).fill('新查询')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(table.getByText(item.title)).toHaveCount(0)
  expect(await table.boundingBox()).toEqual(before)
  release()
  await expect(table.getByText('暂时无法加载声音记录', { exact: true })).toBeVisible()
  expect(await table.boundingBox()).toEqual(before)
})

test('声音广场详情浮层滚动条三状态保持几何', async ({ page }, testInfo) => {
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '查看详情' }).click()
  const body = page.getByRole('dialog', { name: '内容详情' }).locator('.aima-dialog-body')
  await expect(body.locator('.drawer-body')).toBeVisible()
  await captureScrollbarEvidence(page, body, testInfo, 'voice-detail')
})

test('完整多选深链替换旧会话，并在筛选摘要显示真实条件', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('aima.applied-filters.principal.v1', JSON.stringify(['local-administrator', 'administrator', 'development']))
    sessionStorage.setItem('aima.voice-plaza.applied-search.v1', JSON.stringify({
      filters: { search: '旧搜索', sourceIdentifier: '旧来源', platform: 'weibo', analysisStatus: 'pending', relevance: 'irrelevant' },
    }))
  })
  const request = page.waitForRequest((request) => new URL(request.url()).pathname === '/api/v1/contents')
  const query = new URLSearchParams({ published_from: '2026-09-25', published_to: '2026-10-01', brand_ids: brandId,
    vehicle_model_ids: vehicleId, primary_labels: '产品体验', secondary_labels: '续航表现', content_id: contentId })
  for (const platform of ['xiaohongshu', 'douyin']) query.append('platforms', platform)
  for (const sentiment of ['正面', '负面']) query.append('sentiments', sentiment)
  for (const voiceType of ['真实用户发声', '媒体机构发声']) query.append('voice_types', voiceType)
  await page.goto(`/voice-plaza?${query.toString()}`)
  const params = new URL((await request).url()).searchParams
  expect(params.getAll('platforms')).toEqual(['xiaohongshu', 'douyin'])
  expect(params.getAll('sentiments')).toEqual(['正面', '负面'])
  expect(params.getAll('voice_types')).toEqual(['真实用户发声', '媒体机构发声'])
  for (const key of ['search', 'source_identifier', 'analysis_status', 'relevance', 'platform']) expect(params.get(key)).toBeNull()
  await expect(page.locator('.filter-summary')).toContainText('小红书、抖音')
  await expect(page.locator('.filter-summary')).toContainText('正面、负面')
  await expect(page.getByRole('dialog', { name: '内容详情' })).toBeVisible()
})

test('一级标签多选约束二级候选，父级取消后失效二级不会进入查询', async ({ page }) => {
  await page.goto('/voice-plaza')
  const filters = page.locator('section.filters')
  const primarySummary = filters.getByLabel('一级标签', { exact: true })
  const secondarySummary = filters.getByLabel('二级标签', { exact: true })
  const primaryField = filters.locator('.filter-row--tertiary .field').nth(0)
  const secondaryField = filters.locator('.filter-row--tertiary .field').nth(1)

  await expect(secondarySummary).toHaveAttribute('aria-disabled', 'true')
  await expect(secondarySummary).toContainText('请先选择一级标签')

  await primarySummary.click()
  await primaryField.getByRole('checkbox', { name: '产品体验' }).check()
  await primaryField.getByRole('checkbox', { name: '电池、续航与充电' }).check()
  await expect(secondarySummary).toHaveAttribute('aria-disabled', 'false')

  await secondarySummary.click()
  await expect(secondaryField.getByRole('checkbox', { name: '产品体验 / 续航表现', exact: true })).toBeVisible()
  await expect(secondaryField.getByRole('checkbox', { name: '产品体验 / 通勤体验', exact: true })).toBeVisible()
  await expect(secondaryField.getByRole('checkbox', { name: '电池、续航与充电 / 实际续航表现', exact: true })).toBeVisible()
  await secondaryField.getByRole('checkbox', { name: '产品体验 / 续航表现', exact: true }).check()
  await secondaryField.getByRole('checkbox', { name: '电池、续航与充电 / 实际续航表现', exact: true }).check()
  await expect(secondarySummary).toContainText('已选 2 个二级标签')

  await primarySummary.click()
  await primaryField.getByRole('checkbox', { name: '产品体验' }).uncheck()
  await expect(
    secondaryField.getByRole('checkbox', { name: '产品体验 / 续航表现', exact: true }),
  ).toHaveCount(0)
  await expect(secondarySummary).toContainText('已选 1 个二级标签')

  const requestPromise = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return request.method() === 'GET'
      && url.pathname === '/api/v1/contents'
      && url.searchParams.getAll('primary_labels').includes('电池、续航与充电')
  })
  await page.getByRole('button', { name: '查询' }).click()
  const request = await requestPromise
  const url = new URL(request.url())
  expect(url.searchParams.getAll('primary_labels')).toEqual(['电池、续航与充电'])
  expect(url.searchParams.getAll('secondary_labels')).toEqual(['实际续航表现'])
  expect(url.searchParams.getAll('secondary_labels')).not.toContain('续航表现')
})

test('restores the applied platform filter after leaving and reloading the page', async ({ page }) => {
  await page.goto('/voice-plaza')
  const voicePlaza = page.getByRole('main', { name: '声音广场' })
  await voicePlaza.getByLabel('平台', { exact: true }).click()
  await voicePlaza.getByRole('checkbox', { name: '小红书' }).check()

  await page.getByRole('button', { name: '查询' }).click()

  const restoredRequest = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return request.method() === 'GET'
      && url.pathname === '/api/v1/contents'
      && url.searchParams.get('platforms') === 'xiaohongshu'
  })
  // 中途访问的首页已是工作台；本用例只验证声音广场筛选恢复，明确模拟工作台暂不可用。
  await page.route('**/api/v1/workbench/**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 503,
        title: '工作台暂不可用',
        detail: '测试中途页面不提供工作台数据。',
        request_id: 'voice-plaza-home-navigation',
      }),
    })
  })
  await page.goto('/')
  await page.goto('/voice-plaza')
  await restoredRequest

  await expect(voicePlaza.getByLabel('平台', { exact: true })).toContainText('小红书')
  await expect(page.getByText(item.title)).toBeVisible()
})

test('shows AI unavailable and disables analysis when runtime is not configured', async ({ page }) => {
  await page.unroute('**/api/v1/content-analysis-capabilities')
  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ configured: false }),
    })
  })

  await page.goto('/voice-plaza')

  await expect(page.getByText(/AI 分析暂不可用：管理员尚未完成 AI 模型配置/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'AI 分析', exact: true })).toBeDisabled()
})

test('慢导出初始化不阻塞活动 AI 的自动刷新', async ({ page }) => {
  let succeeded = 4
  let releaseExport!: () => void
  const exportReady = new Promise<void>((resolve) => { releaseExport = resolve })
  await page.route('**/api/v1/data-exports', async (route) => {
    await exportReady
    await route.fulfill({ json: { items: [], has_more: false } })
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    await route.fulfill({ json: { items: [{ ...analysisRun,
      stats: { ...analysisRun.stats, pending: 20 - succeeded, succeeded } }] } })
  })
  try {
    await page.goto('/voice-plaza')
    const progress = page.getByRole('progressbar', { name: 'AI 分析进度' })
    await expect(progress).toHaveAttribute('aria-valuenow', '20')
    succeeded = 10
    await expect(progress).toHaveAttribute('aria-valuenow', '50', { timeout: 2500 })
    await page.getByRole('button', { name: '任务中心', exact: true }).click()
    await expect(page.getByRole('complementary', { name: '任务中心' })).toContainText('10 / 20 条已处理')
  } finally {
    releaseExport()
  }
})

test('creates explicit analysis and durable Excel export jobs', async ({ page }) => {
  let analysisRequest: unknown
  let exportRequest: unknown
  let previewRequest: unknown
  let analysisCreated = false
  let analysisCancelled = false
  let cancelRequested = false
  const cancelledRun = {
    ...analysisRun,
    status: 'cancelled',
    stats: { pending: 0, succeeded: 0, failed: 0, cancelled: 20, stale: 0 },
    finished_at: '2026-08-21T03:01:00Z',
    shards: [],
  }
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    previewRequest = route.request().postDataJSON()
    await route.fallback()
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: analysisCancelled ? [cancelledRun] : analysisCreated ? [analysisRun] : [],
        }),
      })
      return
    }
    analysisRequest = route.request().postDataJSON()
    analysisCreated = true
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: analysisRunId,
        planner_job_id: analysisJobId,
        target_count: 1,
        shard_count: 1,
        status: 'queued',
      }),
    })
  })
  await page.route('**/api/v1/data-exports', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    exportRequest = route.request().postDataJSON()
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        export_id: exportId,
        job_id: exportJobId,
        target_count: 1,
        status: 'queued',
      }),
    })
  })
  await page.route(`**/api/v1/analysis/content-runs/${analysisRunId}/cancel`, async (route) => {
    cancelRequested = true
    analysisCancelled = true
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(cancelledRun),
    })
  })

  await page.goto('/voice-plaza')
  const analysisButton = page.getByRole('button', { name: 'AI 分析', exact: true })
  await expect(analysisButton).toBeEnabled()
  await expect(page.getByRole('region', { name: 'AI 分析活动任务' })).toHaveCount(0)
  await page.getByLabel('选择当前已加载内容').check()
  await expect(analysisButton).toBeEnabled()
  await analysisButton.click()
  await expect(page.getByText('预计分析 1 条内容')).toBeVisible()
  await expect(page.getByText('openai-compatible / fixture-model')).not.toBeVisible()
  await expect(page.getByText(/分析可能产生服务费用/)).toBeVisible()
  await expect(page.getByText(/分片/)).toHaveCount(0)
  await expect(page.getByText('高级配置', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '确认开始分析' }).click()
  await expect(page.getByText(/已创建 AI 分析任务/)).toBeVisible()
  await expect(page.getByText('AI Analysis Run 历史')).toHaveCount(0)
  await expect(page.getByText('AI 分析任务', { exact: true })).toBeVisible()
  await expect(page.getByText('AI 分析 · 处理中')).toBeVisible()
  await expect(page.getByRole('progressbar', { name: 'AI 分析进度' })).toHaveAttribute('aria-valuenow', '20')
  expect(previewRequest).toMatchObject({
    targets: { scope: 'selected', content_ids: [contentId] },
  })
  expect(analysisRequest).toMatchObject({
    targets: { scope: 'selected', content_ids: [contentId] },
    expected_target_count: 1,
    expected_configuration_hash: 'd'.repeat(64),
    run_intent: 'manual_reanalysis',
  })
  await page.getByRole('button', { name: '取消任务' }).click()
  await expect(page.getByText('AI 分析 · 处理中')).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'AI 分析活动任务' })).toHaveCount(0)
  expect(cancelRequested).toBe(true)

  await page.getByRole('button', { name: '任务中心', exact: true }).click()
  const taskCenter = page.getByRole('complementary', { name: '任务中心' })
  await expect(taskCenter).toBeVisible()
  await expect(taskCenter).toContainText('AI 分析任务 1')
  await expect(taskCenter).toContainText('已取消')
  await taskCenter.getByRole('button', { name: '关闭任务中心' }).click()

  await page.getByRole('button', { name: /导出记录/ }).click()
  await expect(page.getByText('未完成 AI 分析的内容不会被丢弃')).toBeVisible()
  await page.getByText('当前页内容').click()
  await page.getByRole('button', { name: /开始导出/ }).click()
  await expect(page.getByText(/已创建 Excel 导出任务/)).toBeVisible()
  expect(exportRequest).toMatchObject({
    format: 'xlsx',
    targets: { scope: 'selected', content_ids: [contentId] },
    columns: ['platform'],
  })
})


test('旧内容类型会话及链接不会进入列表、计数、AI 和导出筛选快照', async ({ page }) => {
  let previewRequest: Record<string, any> | undefined
  let analysisRequest: Record<string, any> | undefined
  let exportRequest: Record<string, any> | undefined
  const listRequests: URL[] = []
  const countFilters: Record<string, unknown>[] = []
  await page.addInitScript(() => {
    sessionStorage.setItem('aima.applied-filters.principal.v1', JSON.stringify(['local-administrator', 'administrator', 'development']))
    sessionStorage.setItem('aima.voice-plaza.applied-search.v1', JSON.stringify({
      filters: { contentType: 'video', platform: 'xiaohongshu' },
      sortBy: 'published_at', sortDirection: 'desc',
    }))
  })
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (request.method() === 'GET' && ['/api/v1/contents', '/api/v1/contents/count'].includes(url.pathname)) listRequests.push(url)
    if (request.method() === 'POST' && url.pathname === '/api/v1/contents/count') countFilters.push(request.postDataJSON().filters)
  })
  await page.route('**/api/v1/contents/count**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: 27, count_kind: 'exact', count_mode: 'exact', as_of: '2026-09-30T22:00:00+08:00' }) })
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() === 'POST') analysisRequest = route.request().postDataJSON()
    await route.fallback()
  })
  await page.route('**/api/v1/data-exports', async (route) => {
    if (route.request().method() === 'POST') exportRequest = route.request().postDataJSON()
    await route.fallback()
  })
  await page.unroute('**/api/v1/analysis/content-runs/preview')
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    previewRequest = route.request().postDataJSON() as Record<string, any>
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        target_count: 27,
        shard_count: 1,
        shard_size: 100,
        prompt_version: 'content-labeling.v3.0',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '运行后以实际 token/cost 审计为准。',
      }),
    })
  })

  await page.goto('/voice-plaza?content_types=video&contentType=video&content_type=video')
  const voicePlaza = page.getByRole('main', { name: '声音广场' })
  await expect(voicePlaza.getByLabel('内容类型', { exact: true })).toHaveCount(0)
  await expect.poll(() => new URL(page.url()).search).toBe('')
  await voicePlaza.getByLabel('平台', { exact: true }).click()
  await voicePlaza.getByRole('checkbox', { name: '小红书' }).check()

  await page.getByRole('button', { name: '查询' }).click()
  await page.getByRole('button', { name: 'AI 分析', exact: true }).click()

  const dialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  await expect(dialog.getByRole('radio', { name: /当前筛选结果/ })).toBeChecked()
  await expect(dialog.getByText('预计分析 27 条内容')).toBeVisible()
  expect(previewRequest?.targets).toMatchObject({
    scope: 'query',
    filters: { platforms: ['xiaohongshu'] },
  })
  expect(previewRequest?.targets).not.toHaveProperty('content_ids')
  expect(previewRequest?.targets?.filters).not.toHaveProperty('sort_by')
  expect(previewRequest?.targets?.filters).not.toHaveProperty('cursor')
  expect(previewRequest?.targets?.filters).not.toHaveProperty('content_types')
  await dialog.getByRole('button', { name: '确认开始分析' }).click()
  await expect(page.getByText(/已创建 AI 分析任务/)).toBeVisible()
  expect(analysisRequest?.targets?.filters).not.toHaveProperty('content_types')
  await page.getByRole('button', { name: /导出记录/ }).click()
  await page.getByRole('dialog', { name: '导出声音记录' }).getByRole('radio', { name: /全部查询结果/ }).check()
  await page.getByRole('button', { name: /开始导出/ }).click()
  await expect(page.getByText(/已创建 Excel 导出任务/)).toBeVisible()
  expect(exportRequest?.targets?.filters).toMatchObject({ platforms: ['xiaohongshu'] })
  expect(exportRequest?.targets?.filters).not.toHaveProperty('content_types')
  expect(listRequests.length).toBeGreaterThan(0)
  expect(listRequests.every((url) => !url.searchParams.has('content_types'))).toBe(true)
  expect(countFilters.length).toBeGreaterThan(0)
  expect(countFilters.every((filters) => !('content_types' in filters))).toBe(true)
  const saved = await page.evaluate(() => JSON.parse(sessionStorage.getItem('aima.voice-plaza.applied-search.v1')!))
  expect(saved.filters).not.toHaveProperty('contentType')
})

test('creates an all-data analysis run without browser-side content ids', async ({ page }) => {
  let previewRequest: Record<string, unknown> | undefined
  let createRequest: Record<string, unknown> | undefined
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    previewRequest = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        target_count: 4200,
        shard_count: 42,
        shard_size: 100,
        prompt_version: 'content-labeling.v3.0',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '运行后以实际 token/cost 审计为准。',
      }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    createRequest = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: analysisRunId,
        planner_job_id: analysisJobId,
        target_count: 4200,
        shard_count: 42,
        status: 'queued',
      }),
    })
  })

  await page.goto('/voice-plaza')
  const analysisButton = page.getByRole('button', { name: 'AI 分析', exact: true })
  await expect(analysisButton).toBeEnabled()
  await analysisButton.click()
  const dialog = page.getByRole('dialog', { name: '开始 AI 分析' })
  await expect(dialog.getByRole('radio', { name: /当前筛选结果/ })).toBeChecked()
  await dialog.getByRole('radio', { name: /全部系统内容/ }).check()
  await expect(dialog.getByRole('radio', { name: /全部系统内容/ })).toBeChecked()
  await expect(dialog.getByText('预计分析 4200 条内容')).toBeVisible()
  await expect(dialog.getByText(/分析可能产生服务费用/)).toBeVisible()
  expect(previewRequest).toEqual({ targets: { scope: 'all' } })
  await dialog.getByRole('button', { name: '确认开始分析' }).click()
  expect(createRequest).toMatchObject({
    targets: { scope: 'all' },
    expected_target_count: 4200,
    expected_configuration_hash: 'd'.repeat(64),
  })
})

test('keeps export history visible but disables empty query export creation', async ({ page }) => {
  await page.unroute('**/api/v1/contents**')
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null, has_more: false }),
    })
  })

  await page.goto('/voice-plaza')
  await expect(page.getByRole('button', { name: 'AI 分析', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: /导出记录/ }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(dialog).toContainText('系统将在后台生成可下载的 Excel 文件')
  await expect(dialog).not.toContainText('Artifact')
  await expect(dialog.getByText('当前筛选没有可导出内容')).toBeVisible()
  await expect(dialog.getByRole('radio', { name: /全部查询结果/ })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: /开始导出/ })).toBeDisabled()
  await expect(dialog.getByText('最近导出记录')).toBeVisible()
  await expect(dialog.getByRole('progressbar', { name: '导出 72345678 进度' })).toHaveAttribute('aria-valuenow', '64')
})

test('普通用户保留选择和详情结果，任务中心不请求管理数据', async ({ page }) => {
  const management: string[] = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (/^\/api\/v1\/(analysis\/content-runs|collection-runtime)/.test(path)) management.push(path)
  })
  await page.route('**/api/v1/principal', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      principal_id: 'browser-user-a', display_name: '普通用户甲', role: 'user', source: 'feishu', is_administrator: false,
    }) })
  })
  await page.goto('/voice-plaza')
  await expect(page.getByRole('navigation', { name: '业务导航' }).getByRole('link')).toHaveCount(2)
  await page.getByRole('checkbox', { name: '选择当前已加载内容' }).check()
  await expect(page.getByText('已选 1 条', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: /AI 分析|评论补采|标记相关|标记不相关|撤销人工判断/ })).toHaveCount(0)
  await page.getByRole('button', { name: '查看详情' }).click()
  const detail = page.getByRole('dialog', { name: '内容详情' })
  await expect(detail).toContainText('小满的通勤日记')
  await expect(detail).toContainText('负面')
  await expect(detail.getByRole('button', { name: /修改|纠正|解除人工/ })).toHaveCount(0)
  await detail.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '任务中心', exact: true }).click()
  await expect(page.getByRole('button', { name: '取消任务', exact: true })).toHaveCount(0)
  expect(management).toEqual([])
})

test('个人默认字段加载完成前不展示错误勾选，临时导出不保存默认', async ({ page }) => {
  await personalColumnCatalog(page)
  let release!: () => void
  const gate = new Promise<void>((done) => { release = done })
  let preferenceReads = 0
  let preferenceWrites = 0
  await page.route('**/api/v1/me/export-column-default', async (route) => {
    if (route.request().method() === 'PUT') preferenceWrites += 1
    preferenceReads += 1
    await gate
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      revision: 4, columns: ['title'], saved_catalog_version: 3, updated_at: '2026-10-10T08:00:00+08:00',
    }) })
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '导出记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect.poll(() => preferenceReads).toBe(1)
  await expect(dialog.locator('.column-picker input')).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: /开始导出/ })).toBeDisabled()
  release()
  await expect(dialog.getByLabel('标题', { exact: true })).toBeChecked()
  await expect(dialog.getByLabel('平台', { exact: true })).not.toBeChecked()
  await dialog.getByLabel('作者', { exact: true }).check()
  await dialog.getByText('当前页内容', { exact: true }).click()
  await dialog.getByRole('button', { name: /开始导出/ }).click()
  await expect(page.getByText(/已创建 Excel 导出任务/)).toBeVisible()
  expect(preferenceWrites).toBe(0)
})

test('默认字段并发冲突保留草稿，重新读取后显式保存新 revision', async ({ page }) => {
  await personalColumnCatalog(page)
  let reads = 0
  const writes: Record<string, unknown>[] = []
  await page.route('**/api/v1/me/export-column-default', async (route) => {
    if (route.request().method() === 'PUT') {
      writes.push(route.request().postDataJSON())
      if (writes.length === 1) {
        await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({
          status: 409, title: 'Conflict', detail: 'revision conflict', request_id: 'browser-default-conflict',
        }) })
        return
      }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        revision: 6, columns: ['title', 'author'], saved_catalog_version: 3, updated_at: '2026-10-10T08:00:00+08:00',
      }) })
      return
    }
    reads += 1
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      revision: reads === 1 ? 4 : 5, columns: reads === 1 ? ['title'] : ['text'], saved_catalog_version: 3, updated_at: null,
    }) })
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '导出记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(dialog.getByLabel('标题', { exact: true })).toBeChecked()
  await dialog.getByLabel('作者', { exact: true }).check()
  const save = dialog.getByRole('button', { name: '设为我的默认字段', exact: true })
  await save.click()
  await expect(dialog.getByRole('alert')).toContainText('当前草稿已保留')
  await expect(save).toBeDisabled()
  await expect(dialog.getByLabel('作者', { exact: true })).toBeChecked()
  await dialog.getByRole('button', { name: '重新读取', exact: true }).click()
  await expect(save).toBeEnabled()
  await expect(dialog.getByLabel('标题', { exact: true })).toBeChecked()
  await expect(dialog.getByLabel('正文', { exact: true })).not.toBeChecked()
  await save.click()
  await expect(dialog.getByText('已保存为我的默认字段。')).toBeVisible()
  expect(writes).toEqual([
    { revision: 4, catalog_version: 3, columns: ['title', 'author'] },
    { revision: 5, catalog_version: 3, columns: ['title', 'author'] },
  ])
})

test('失效个人字段安全回退，恢复系统默认显式提交 null 并保留 revision', async ({ page }) => {
  await personalColumnCatalog(page)
  const writes: Record<string, unknown>[] = []
  await page.route('**/api/v1/me/export-column-default', async (route) => {
    const saving = route.request().method() === 'PUT'
    if (saving) writes.push(route.request().postDataJSON())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      revision: saving ? 8 : 7, columns: saving ? null : [], saved_catalog_version: 2, updated_at: null,
    }) })
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '导出记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  await expect(dialog.getByText('原默认字段已失效或当前账号无权使用，已采用系统默认字段。')).toBeVisible()
  await expect(dialog.getByLabel('平台', { exact: true })).toBeChecked()
  await expect(dialog.getByLabel('正文', { exact: true })).toBeChecked()
  expect(writes).toEqual([])
  await dialog.getByRole('button', { name: '恢复系统默认字段', exact: true }).click()
  await expect(dialog.getByText('已恢复系统默认字段。')).toBeVisible()
  expect(writes).toEqual([{ revision: 7, catalog_version: 3, columns: null }])
})

test('恢复默认等待期间锁定字段，失败后原草稿仍可继续编辑', async ({ page }) => {
  await personalColumnCatalog(page)
  let release!: () => void
  const pending = new Promise<void>((done) => { release = done })
  await page.route('**/api/v1/me/export-column-default', async (route) => {
    if (route.request().method() === 'PUT') {
      await pending
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({
        status: 503, title: 'Service unavailable', detail: 'temporary', request_id: 'browser-default-save',
      }) })
      return
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      revision: 2, columns: ['title'], saved_catalog_version: 3, updated_at: null,
    }) })
  })
  await page.goto('/voice-plaza')
  await page.getByRole('button', { name: '导出记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出声音记录' })
  const title = dialog.getByLabel('标题', { exact: true })
  await expect(title).toBeChecked()
  await dialog.getByRole('button', { name: '恢复系统默认字段', exact: true }).click()
  await expect(title).toBeDisabled()
  await expect(dialog.getByLabel('作者', { exact: true })).toBeDisabled()
  release()
  await expect(dialog.getByRole('alert')).toContainText('当前草稿已保留')
  await expect(title).toBeEnabled()
  await expect(title).toBeChecked()
  await dialog.getByLabel('作者', { exact: true }).check()
})

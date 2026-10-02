import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { createSSRApp, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { renderToString } from '@vue/server-renderer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  fetchWorkbenchTaxonomy: vi.fn(),
  fetchWorkbenchStream: vi.fn(),
  fetchWorkbenchTrend: vi.fn(),
  fetchWorkbenchMind: vi.fn(),
  fetchWorkbenchLayout: vi.fn(),
  saveWorkbenchLayout: vi.fn(),
  fetchActiveBrands: vi.fn(),
  fetchActiveVehicleModels: vi.fn(),
}))
vi.mock('../src/features/workbench/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/features/workbench/api')>()
  return { ...actual, ...api, fetchActiveBrands: actual.fetchActiveBrands, fetchActiveVehicleModels: actual.fetchActiveVehicleModels }
})
vi.mock('../src/generated/api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../src/generated/api/client')>(),
  listVehicleBrands: async () => { const items = await api.fetchActiveBrands(); return { items, total: items.length } },
  listVehicleModels: async () => { const items = await api.fetchActiveVehicleModels(); return { items, total: items.length } },
}))

import WorkbenchPage from '../src/features/workbench/pages/WorkbenchPage.vue'
import { useWorkbenchStore } from '../src/features/workbench/store'
import { AimaApiError } from '../src/shared/api/http'
import { useVehicleCatalogStore } from '../src/shared/domain/vehicleCatalog'

const schemeId = '11111111-1111-4111-8111-111111111111'
const taxonomyHash = 'a'.repeat(64)
const savedFiltersKey = 'aima.workbench.applied-filters'
let savedFilters: Map<string, string>
const taxonomy = {
  prompt_version: 'content-labeling.v3.0',
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
const layout = {
  schema_version: 1 as const,
  revision: 3,
  updated_at: '2026-09-27T08:00:00+08:00',
  modules: [
    { module_id: 'sound-stream' as const, visible: true, order: 0, column_span: 6, row_units: 48 },
    { module_id: 'brand-mind' as const, visible: true, order: 1, column_span: 6, row_units: 48 },
    { module_id: 'ugc-trend' as const, visible: true, order: 2, column_span: 6, row_units: 48 },
  ],
}
const stream = {
  analysis_scheme_version_id: schemeId,
  taxonomy_sha256: taxonomyHash,
  as_of: '2026-09-27T08:10:00+08:00',
  items: [],
  next_cursor: null,
  has_more: false,
}
const mind = {
  analysis_scheme_version_id: schemeId,
  taxonomy_sha256: taxonomyHash,
  as_of: '2026-09-27T08:10:00+08:00',
  date_from: '2026-08-29',
  date_to: '2026-09-27',
  previous_date_from: '2026-07-30',
  previous_date_to: '2026-08-28',
  relevant_content_count: 100,
  unidentified_content_count: 2,
  analyzed_count: 80,
  analysis_coverage_rate: 0.8,
  dimensions: [
    {
      primary_label: '外观设计',
      content_count: 35,
      content_share: 0.35,
      positive_rate: 0.7,
      content_share_change_pp: 2.2,
      secondary_labels: [{ secondary_label: '颜色与配色', content_count: 20 }],
      change_summary: '外观设计用户占比较紧邻等长上期上升 2.20pp。',
    },
    {
      primary_label: '电池、续航与充电',
      content_count: 28,
      content_share: 0.28,
      positive_rate: 0.55,
      content_share_change_pp: -1.1,
      secondary_labels: [{ secondary_label: '续航里程', content_count: 18 }],
      change_summary: '电池、续航与充电用户占比较紧邻等长上期下降 1.10pp。',
    },
  ],
}
const trend = {
  analysis_scheme_version_id: schemeId,
  taxonomy_sha256: taxonomyHash,
  as_of: '2026-09-27T08:10:00+08:00',
  date_from: '2026-08-29',
  date_to: '2026-09-27',
  previous_date_from: '2026-07-30',
  previous_date_to: '2026-08-28',
  total_count: 120,
  daily_average: 4.49,
  peak_day: '2026-09-20',
  peak_count: 12,
  period_change_rate: 0.12,
  positive_rate: 0.6,
  positive_rate_change_pp: 3.2,
  analyzed_count: 100,
  analysis_coverage_rate: 0.833333,
  daily: [{ day: '2026-09-20', count: 12 }],
  sentiments: [
    { sentiment: '正面', count: 60, share: 0.6 },
    { sentiment: '混合', count: 10, share: 0.1 },
    { sentiment: '无法判断', count: 5, share: 0.05 },
  ],
  summary: '09/20 为当前周期声量峰值。',
}

beforeEach(() => {
  savedFilters = new Map()
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => savedFilters.get(key) ?? null,
    setItem: (key: string, value: string) => savedFilters.set(key, value),
    removeItem: (key: string) => savedFilters.delete(key),
  })
  setActivePinia(createPinia())
  vi.resetAllMocks()
  api.fetchWorkbenchTaxonomy.mockResolvedValue(taxonomy)
  api.fetchActiveBrands.mockResolvedValue([])
  api.fetchActiveVehicleModels.mockResolvedValue([])
  api.fetchWorkbenchLayout.mockResolvedValue(layout)
  api.fetchWorkbenchStream.mockResolvedValue(stream)
  api.fetchWorkbenchMind.mockResolvedValue(mind)
  api.fetchWorkbenchTrend.mockResolvedValue(trend)
  api.saveWorkbenchLayout.mockImplementation(async (request: { revision: number; modules: typeof layout.modules }) => ({
    schema_version: 1,
    revision: request.revision + 1,
    updated_at: '2026-09-27T08:11:00+08:00',
    modules: request.modules,
  }))
})
afterEach(() => vi.unstubAllGlobals())

it('preserves saved vehicle filters when only the vehicle catalog fails to load', async () => {
  api.fetchActiveBrands.mockResolvedValue([{ id: 'aima', code: 'AIMA', display_name: '爱玛', aliases: [] }])
  api.fetchActiveVehicleModels.mockRejectedValue(new Error('vehicle catalog unavailable'))
  const store = useWorkbenchStore()
  const saved = { ...store.filters, dateFrom: '2026-08-01', dateTo: '2026-08-31', brandIds: ['aima'], vehicleModelIds: ['vehicle'] }
  savedFilters.set(savedFiltersKey, JSON.stringify({ schema_version: 1, ...saved }))
  await store.initialize()
  expect(store.filters.vehicleModelIds).toEqual(['vehicle'])
  expect(JSON.parse(savedFilters.get(savedFiltersKey)!).vehicleModelIds).toEqual(['vehicle'])
  for (const call of [api.fetchWorkbenchStream, api.fetchWorkbenchMind, api.fetchWorkbenchTrend]) {
    expect(call).toHaveBeenCalledWith(expect.objectContaining({ brand_ids: ['aima'], vehicle_model_ids: ['vehicle'] }))
  }
  // 目录成功恢复后，归属不符及真实删除的车型仍按现有规则清理。
  api.fetchActiveVehicleModels.mockResolvedValue([{ id: 'vehicle', brand_id: 'other' }])
  await store.refreshReferenceData()
  store.setFilters({ ...store.filters, vehicleModelIds: ['vehicle', 'deleted'] })
  expect(store.filters.vehicleModelIds).toEqual([])
})

it('restores the complete applied snapshot before the first queries and persists reset', async () => {
  api.fetchActiveBrands.mockResolvedValue([{ id: 'aima', code: 'AIMA', display_name: '爱玛', aliases: [] }])
  api.fetchActiveVehicleModels.mockResolvedValue([{ id: 'vehicle', brand_id: 'aima' }])
  const first = useWorkbenchStore()
  await first.initialize()
  first.setFilters({ ...first.filters, dateFrom: '2026-08-31', dateTo: '2026-08-01', platforms: ['douyin'],
    brandIds: ['aima'], vehicleModelIds: ['vehicle'], voiceTypes: ['真实用户发声'], sentiments: ['负面'],
    primaryLabels: ['外观设计'], secondaryLabels: ['颜色与配色'] })
  const expected = { ...first.filters }
  expect(Object.keys(JSON.parse(savedFilters.get(savedFiltersKey)!)).sort()).toEqual([
    'schema_version', 'dateFrom', 'dateTo', 'platforms', 'brandIds', 'vehicleModelIds', 'voiceTypes', 'sentiments', 'primaryLabels', 'secondaryLabels',
  ].sort())
  api.fetchWorkbenchStream.mockClear(); api.fetchWorkbenchMind.mockClear(); api.fetchWorkbenchTrend.mockClear()
  setActivePinia(createPinia())
  const restored = useWorkbenchStore()
  await restored.initialize()
  expect(restored.filters).toEqual(expected)
  for (const request of [api.fetchWorkbenchStream, api.fetchWorkbenchMind, api.fetchWorkbenchTrend]) {
    expect(request).toHaveBeenCalledTimes(1)
    expect(request).toHaveBeenCalledWith(expect.objectContaining({ date_from: '2026-08-01', date_to: '2026-08-31',
      platforms: ['douyin'], brand_ids: ['aima'], vehicle_model_ids: ['vehicle'], voice_types: ['真实用户发声'],
      sentiments: ['负面'], primary_labels: ['外观设计'], secondary_labels: ['颜色与配色'] }))
  }
  restored.resetFilters()
  const reset = { ...restored.filters }
  setActivePinia(createPinia())
  const reopened = useWorkbenchStore()
  await reopened.initialize()
  expect(reopened.filters).toEqual(reset)
})

it('cleans stale catalog and taxonomy values when restoring applied filters', async () => {
  savedFilters.set(savedFiltersKey, JSON.stringify({ schema_version: 1, dateFrom: '2026-08-01', dateTo: '2026-08-31',
    platforms: ['douyin', 'removed'], brandIds: ['aima', 'removed'], vehicleModelIds: ['v1', 'v2', 'removed'],
    voiceTypes: ['真实用户发声', 'removed'], sentiments: ['负面', 'removed'], primaryLabels: ['外观设计', 'removed'],
    secondaryLabels: ['颜色与配色', '续航里程', 'removed'] }))
  api.fetchActiveBrands.mockResolvedValue([{ id: 'aima', code: 'AIMA', display_name: '爱玛', aliases: [] }])
  api.fetchActiveVehicleModels.mockResolvedValue([{ id: 'v1', brand_id: 'aima' }, { id: 'v2', brand_id: 'other' }])
  const store = useWorkbenchStore()
  await store.initialize()
  expect(store.filters).toMatchObject({ platforms: ['douyin'], brandIds: ['aima'], vehicleModelIds: ['v1'],
    voiceTypes: ['真实用户发声'], sentiments: ['负面'], primaryLabels: ['外观设计'], secondaryLabels: ['颜色与配色'] })
})

it.each(['{bad', '{}', JSON.stringify({ schema_version: 9 }), JSON.stringify({ schema_version: 1, dateFrom: '2026-02-30', dateTo: '2026-03-01' })])(
  'discards malformed filters %s and still queries the default range', async (value) => {
    savedFilters.set(savedFiltersKey, value)
    const store = useWorkbenchStore()
    await store.initialize()
    expect(savedFilters.has(savedFiltersKey)).toBe(false)
    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(1)
    expect(store.filters.dateFrom).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  },
)

it('storage read and write failures do not block the workbench', async () => {
  vi.stubGlobal('sessionStorage', { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') }, removeItem: () => { throw new Error('denied') } })
  const store = useWorkbenchStore()
  await store.initialize()
  store.setFilters({ ...store.filters, dateFrom: '2026-08-01', dateTo: '2026-08-31' })
  await store.refreshData()
  expect(api.fetchWorkbenchStream).toHaveBeenLastCalledWith(expect.objectContaining({ date_from: '2026-08-01', date_to: '2026-08-31' }))
})

it('shares reactive catalog updates and keeps the name when active candidates no longer contain a selected ID', async () => {
  const brand = { id: 'aima', code: 'AIMA', display_name: '爱玛', catalog_version: 1, version: 1, aliases: [] }
  api.fetchActiveBrands.mockResolvedValueOnce([brand])
  const store = useWorkbenchStore()
  await store.initialize()
  const catalog = useVehicleCatalogStore()
  api.fetchActiveBrands.mockResolvedValueOnce([{ ...brand, display_name: '爱玛新名称', catalog_version: 2, version: 2 }])
  await catalog.loadBrands('active', true)
  expect(store.brands[0]?.display_name).toBe('爱玛新名称')
  expect(store.brandLabel).toBe('爱玛新名称')
  api.fetchActiveBrands.mockResolvedValueOnce([])
  await catalog.loadBrands('active', true)
  expect(store.brands).toEqual([])
  expect(store.filters.brandIds).toEqual(['aima'])
  expect(store.brandLabel).toBe('爱玛新名称')
})

describe('工作台状态与 Figma 基线', () => {
  it('等待目录后只发一次昨日结束的爱玛七日查询，目录刷新不覆盖用户品牌', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-02T00:30:00Z'))
    api.fetchActiveBrands.mockResolvedValue([{ id: 'aima-id', code: 'AIMA', display_name: '爱玛', aliases: [] }])
    let finish!: (value: unknown[]) => void
    api.fetchActiveBrands.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const store = useWorkbenchStore()
    const initialization = store.initialize()
    await Promise.resolve()
    expect(api.fetchWorkbenchStream).not.toHaveBeenCalled()
    finish([{ id: 'aima-id', code: 'AIMA', display_name: '爱玛', aliases: [] }])
    await initialization
    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(1)
    expect(api.fetchWorkbenchStream).toHaveBeenLastCalledWith(expect.objectContaining({
      date_from: '2026-09-25', date_to: '2026-10-01', brand_ids: ['aima-id'],
    }))
    store.setFilters({ ...store.filters, brandIds: [] })
    await store.refreshReferenceData()
    expect(store.filters.brandIds).toEqual([])
    store.resetFilters()
    expect(store.filters.brandIds).toEqual(['aima-id'])
    expect(store.filters.dateFrom).toBe('2026-09-25')
    vi.useRealTimers()
  })

  it('品牌集合变化清理不属于任一当前品牌的车型，声音流不能隐藏或缩到六列以下', async () => {
    api.fetchActiveVehicleModels.mockResolvedValue([
      { id: 'v1', brand_id: 'b1' }, { id: 'v2', brand_id: 'b2' }, { id: 'v3', brand_id: 'b3' },
    ])
    const store = useWorkbenchStore()
    await store.initialize()
    store.setFilters({ ...store.filters, brandIds: ['b1', 'b2'], vehicleModelIds: ['v1', 'v2', 'v3'] })
    expect(store.filters.vehicleModelIds).toEqual(['v1', 'v2'])
    store.startEditing()
    store.setModuleVisible('sound-stream', false)
    store.resizeModule('sound-stream', 4, 48)
    expect(store.currentModules.find((item) => item.module_id === 'sound-stream')).toMatchObject({ visible: true, column_span: 6 })
  })

  it('动态消费 active Taxonomy，并保持三个模块同一 Scheme Version', async () => {
    const store = useWorkbenchStore()
    await store.initialize()

    expect(store.taxonomy?.taxonomy_sha256).toBe(taxonomyHash)
    expect(store.primaryLabelOptions.map((item) => item.primary_label)).toEqual([
      '外观设计',
      '电池、续航与充电',
    ])
    expect(store.activeSchemeVersionId).toBe(schemeId)
    expect(store.activeMind?.primary_label).toBe('外观设计')
  })

  it('一级标签变化后只保留所选父级的二级标签', async () => {
    const store = useWorkbenchStore()
    await store.initialize()

    store.setFilters({
      ...store.filters,
      primaryLabels: ['外观设计', '电池、续航与充电'],
      secondaryLabels: ['颜色与配色', '续航里程'],
    })
    expect(store.secondaryLabelOptions.map((item) => item.value)).toEqual([
      '颜色与配色',
      '整体造型与颜值',
      '续航里程',
    ])

    store.setFilters({
      ...store.filters,
      primaryLabels: ['外观设计'],
      secondaryLabels: ['颜色与配色', '续航里程'],
    })

    expect(store.filters.secondaryLabels).toEqual(['颜色与配色'])
    expect(store.secondaryLabelOptions.map((item) => item.value)).toEqual([
      '颜色与配色',
      '整体造型与颜值',
    ])

    store.setFilters({
      ...store.filters,
      primaryLabels: [],
      secondaryLabels: ['颜色与配色'],
    })
    expect(store.filters.secondaryLabels).toEqual([])
    expect(store.secondaryLabelOptions).toEqual([])
  })

  it('三个模块的显式重试分别只调用自身接口', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    const initial = {
      stream: api.fetchWorkbenchStream.mock.calls.length,
      mind: api.fetchWorkbenchMind.mock.calls.length,
      trend: api.fetchWorkbenchTrend.mock.calls.length,
    }

    await store.refreshModule('stream')
    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(initial.stream + 1)
    expect(api.fetchWorkbenchMind).toHaveBeenCalledTimes(initial.mind)
    expect(api.fetchWorkbenchTrend).toHaveBeenCalledTimes(initial.trend)

    await store.refreshModule('mind')
    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(initial.stream + 1)
    expect(api.fetchWorkbenchMind).toHaveBeenCalledTimes(initial.mind + 1)
    expect(api.fetchWorkbenchTrend).toHaveBeenCalledTimes(initial.trend)

    await store.refreshModule('trend')
    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(initial.stream + 1)
    expect(api.fetchWorkbenchMind).toHaveBeenCalledTimes(initial.mind + 1)
    expect(api.fetchWorkbenchTrend).toHaveBeenCalledTimes(initial.trend + 1)
  })

  it('声音流按游标换页且周期聚合刷新不会把它重置到第一页', async () => {
    const firstPage = {
      ...stream,
      items: [{
        content_id: '33333333-3333-4333-8333-333333333333',
        platform: 'douyin' as const,
        author_display_name: '用户甲',
        published_at: '2026-09-27T14:35:00+08:00',
        title: null,
        text: '第一页声音',
        sentiment: '正面',
        voice_type: '真实用户发声',
        labels: [],
        analysis_current: true,
        vehicle_names: [],
      }],
      next_cursor: 'signed-page-2',
      has_more: true,
    }
    const secondPage = {
      ...firstPage,
      items: [{ ...firstPage.items[0], content_id: '44444444-4444-4444-8444-444444444444', text: '第二页声音' }],
      next_cursor: null,
      has_more: false,
    }
    api.fetchWorkbenchStream.mockResolvedValueOnce(firstPage)
    const store = useWorkbenchStore()
    await store.initialize()
    const firstPageCallCount = api.fetchWorkbenchStream.mock.calls.length
    api.fetchWorkbenchStream.mockResolvedValueOnce(secondPage)

    await store.advanceStream()

    expect(api.fetchWorkbenchStream).toHaveBeenLastCalledWith(expect.objectContaining({
      cursor: 'signed-page-2',
      limit: 100,
    }))
    expect(store.stream?.items[0]?.text).toBe('第二页声音')
    await store.refreshAggregates()
    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(firstPageCallCount + 1)
    expect(store.stream?.items[0]?.text).toBe('第二页声音')
  })

  it('后台补读或自动翻页遇到瞬时失败时保留当前结果且不弹出模块错误', async () => {
    const currentStream = {
      ...stream,
      items: [{
        content_id: '33333333-3333-4333-8333-333333333333',
        platform: 'douyin' as const,
        author_display_name: '用户甲',
        published_at: '2026-09-27T14:35:00+08:00',
        title: null,
        text: '当前声音',
        sentiment: '正面',
        voice_type: '真实用户发声',
        labels: [],
        analysis_current: true,
        vehicle_names: [],
      }],
      next_cursor: 'signed-page-2',
      has_more: true,
    }
    api.fetchWorkbenchStream.mockResolvedValueOnce(currentStream)
    const store = useWorkbenchStore()
    await store.initialize()
    api.fetchWorkbenchStream.mockRejectedValueOnce(new Error('temporary stream failure'))
    api.fetchWorkbenchMind.mockRejectedValueOnce(new Error('temporary mind failure'))
    api.fetchWorkbenchTrend.mockRejectedValueOnce(new Error('temporary trend failure'))

    await Promise.all([store.advanceStream(), store.refreshAggregates()])

    expect(store.stream).toEqual(currentStream)
    expect(store.mind).toEqual(mind)
    expect(store.trend).toEqual(trend)
    expect(store.moduleErrors).toEqual({ stream: null, mind: null, trend: null })
  })

  it('自动翻页游标过期后从当前筛选第一页恢复，不会永久重试失效游标', async () => {
    const currentStream = {
      ...stream,
      items: [{
        content_id: '33333333-3333-4333-8333-333333333333',
        platform: 'douyin' as const,
        author_display_name: '用户甲',
        published_at: '2026-09-27T14:35:00+08:00',
        title: null,
        text: '当前声音',
        sentiment: '正面',
        voice_type: '真实用户发声',
        labels: [],
        analysis_current: true,
        vehicle_names: [],
      }],
      next_cursor: 'expired-page-2',
      has_more: true,
    }
    const recoveredFirstPage = {
      ...currentStream,
      items: [{ ...currentStream.items[0], text: '恢复后的第一页声音' }],
      next_cursor: 'fresh-page-2',
    }
    api.fetchWorkbenchStream.mockResolvedValueOnce(currentStream)
    const store = useWorkbenchStore()
    await store.initialize()
    api.fetchWorkbenchStream
      .mockRejectedValueOnce(new AimaApiError({
        detail: '声音流游标无效或已过期。',
        errors: [{ code: 'invalid_content_cursor', field: 'query.cursor', message: '游标无效或已过期。' }],
        request_id: 'request-cursor-expired',
        status: 400,
        title: 'Invalid content cursor',
        type: 'https://aima.example/errors/invalid_content_cursor',
      }))
      .mockResolvedValueOnce(recoveredFirstPage)

    await store.advanceStream()

    const pageCalls = api.fetchWorkbenchStream.mock.calls.slice(-2)
    expect(pageCalls[0]?.[0]).toEqual(expect.objectContaining({ cursor: 'expired-page-2', limit: 100 }))
    expect(pageCalls[1]?.[0]).toEqual(expect.objectContaining({ cursor: undefined, limit: 100 }))
    expect(store.stream).toEqual(recoveredFirstPage)
    expect(store.moduleErrors.stream).toBeNull()
  })

  it('筛选改变后清除上一筛选结果，避免把旧数据冒充当前筛选快照', async () => {
    const store = useWorkbenchStore()
    await store.initialize()

    store.setFilters({ ...store.filters, sentiments: ['负面'] })

    expect(store.stream).toBeNull()
    expect(store.mind).toBeNull()
    expect(store.trend).toBeNull()
    expect(store.selectedMind).toBeNull()
  })

  it('编辑态只改草稿，取消恢复；保存时一次提交 revision CAS', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    store.startEditing()
    store.reorderModule('ugc-trend', 'sound-stream')
    store.setModuleVisible('brand-mind', false)

    expect(store.currentModules[0]?.module_id).toBe('ugc-trend')
    expect(store.hiddenModules.map((item) => item.module_id)).toEqual(['brand-mind'])

    store.cancelEditing()
    expect(store.currentModules.map((item) => item.module_id)).toEqual([
      'sound-stream',
      'brand-mind',
      'ugc-trend',
    ])
    expect(store.hiddenModules).toEqual([])

    store.startEditing()
    store.reorderModule('ugc-trend', 'sound-stream')
    expect(await store.saveLayout()).toBe(true)
    expect(api.saveWorkbenchLayout).toHaveBeenCalledTimes(1)
    expect(api.saveWorkbenchLayout.mock.calls[0]?.[0].revision).toBe(3)
    expect(store.layout?.revision).toBe(4)
    expect(store.editing).toBe(false)
  })

  it('每个模块按独立草稿以单列和单行粒度调整尺寸', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    store.startEditing()

    store.resizeModule('sound-stream', 4.2, 55.2)
    store.resizeModule('brand-mind', 10.6, 72.5)
    store.resizeModule('ugc-trend', 8.4, 63.6)

    expect(store.currentModules.find((item) => item.module_id === 'ugc-trend')).toEqual(
      expect.objectContaining({ column_span: 8, row_units: 64 }),
    )
    expect(store.currentModules.find((item) => item.module_id === 'sound-stream')).toEqual(
      expect.objectContaining({ column_span: 6, row_units: 55 }),
    )
    expect(store.currentModules.find((item) => item.module_id === 'brand-mind')).toEqual(
      expect.objectContaining({ column_span: 11, row_units: 73 }),
    )
  })

  it('active Taxonomy 切换后自动移除失效 AI 筛选值', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    store.setFilters({
      ...store.filters,
      sentiments: ['正面', '已删除情感'],
      voiceTypes: ['真实用户发声', '已删除发声'],
      primaryLabels: ['外观设计', '已删除一级'],
      secondaryLabels: ['颜色与配色', '已删除二级'],
    })

    await store.refreshTaxonomy()

    expect(store.filters.sentiments).toEqual(['正面'])
    expect(store.filters.voiceTypes).toEqual(['真实用户发声'])
    expect(store.filters.primaryLabels).toEqual(['外观设计'])
    expect(store.filters.secondaryLabels).toEqual(['颜色与配色'])
  })

  it('反向日期在进入三个模块请求前统一规范为有序区间', async () => {
    const store = useWorkbenchStore()
    store.setFilters({ ...store.filters, dateFrom: '2026-08-29', dateTo: '2026-08-28' })
    expect(store.filters.dateFrom).toBe('2026-08-28')
    expect(store.filters.dateTo).toBe('2026-08-29')
    await store.refreshData()
    for (const call of [api.fetchWorkbenchStream, api.fetchWorkbenchMind, api.fetchWorkbenchTrend]) {
      expect(call).toHaveBeenCalledWith(expect.objectContaining({
        date_from: '2026-08-28',
        date_to: '2026-08-29',
      }))
    }
  })

  it('声音流和趋势先返回时无需等待较慢的品牌心智请求', async () => {
    let finishMind: (value: typeof mind) => void = () => {}
    api.fetchWorkbenchMind.mockImplementation(() => new Promise<typeof mind>((resolve) => {
      finishMind = resolve
    }))
    const store = useWorkbenchStore()
    const pending = store.refreshData()
    await Promise.resolve()
    await Promise.resolve()
    expect(store.stream).toEqual(stream)
    expect(store.trend).toEqual(trend)
    expect(store.moduleLoading.mind).toBe(true)
    finishMind(mind)
    await pending
    expect(store.mind).toEqual(mind)
    expect(store.moduleLoading.mind).toBe(false)
  })

  it('较晚返回的单模块重试不会覆盖更新后的全局筛选结果', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    let finishRetry: (value: typeof mind) => void = () => {}
    api.fetchWorkbenchMind.mockImplementationOnce(() => new Promise<typeof mind>((resolve) => {
      finishRetry = resolve
    }))
    const staleRetry = store.refreshModule('mind')
    await Promise.resolve()

    const newerMind = { ...mind, relevant_content_count: 200 }
    api.fetchWorkbenchMind.mockResolvedValue(newerMind)
    await store.refreshData()
    finishRetry({ ...mind, relevant_content_count: 50 })
    await staleRetry

    expect(store.mind?.relevant_content_count).toBe(200)
  })

  it('active Scheme 切换时不会展示混合口径的三个模块', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    const nextStream = {
      ...stream,
      analysis_scheme_version_id: '22222222-2222-4222-8222-222222222222',
      taxonomy_sha256: 'c'.repeat(64),
    }
    api.fetchWorkbenchStream.mockResolvedValue(nextStream)
    api.fetchWorkbenchMind.mockRejectedValue(new Error('mind unavailable'))
    api.fetchWorkbenchTrend.mockRejectedValue(new Error('trend unavailable'))

    await store.refreshData()

    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(2)
    expect(store.stream).toEqual(nextStream)
    expect(store.mind).toBeNull()
    expect(store.trend).toBeNull()
    expect(store.globalError).toContain('Taxonomy 暂未同步')
  })

  it('正式页面呈现动态心智和情感结构，不再展示首页占位图', async () => {
    const pinia: Pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkbenchStore(pinia)
    store.taxonomy = taxonomy
    store.layout = layout
    store.stream = stream
    store.mind = mind
    store.trend = trend
    store.selectedMind = '外观设计'

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { render: () => h('div') } },
        { path: '/voice-plaza', component: { render: () => h('div') } },
        { path: '/collection-runtime', component: { render: () => h('div') } },
        { path: '/collection-strategy', component: { render: () => h('div') } },
        { path: '/admin/configuration', component: { render: () => h('div') } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const app = createSSRApp({ render: () => h(WorkbenchPage) })
    app.use(pinia)
    app.use(router)
    const html = await renderToString(app)

    expect(html).toContain('工作台')
    expect(html).toContain('基于当前 active Taxonomy')
    expect(html).toContain('用户心智图')
    expect(html).toContain('外观设计')
    expect(html).toContain('电池、续航与充电')
    expect(html).toContain('混合')
    expect(html).toContain('无法判断')
    expect(html).toContain('编辑工作台')
    expect(html).not.toContain('工作台开发中')
    expect(html).not.toContain('品牌印象')
    expect(html).not.toContain('设计审美')
    expect(html).not.toContain('日均声量</span><strong>4.49')
  })

  it('冷聚合显示后台准备状态，声音流显示北京时间时分', async () => {
    const pinia: Pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkbenchStore(pinia)
    store.taxonomy = taxonomy
    store.layout = layout
    store.stream = {
      ...stream,
      items: [{
        content_id: '33333333-3333-4333-8333-333333333333',
        platform: 'douyin',
        author_display_name: '用户甲',
        published_at: '2026-09-27T14:35:00+08:00',
        title: null,
        text: '带真实时间的声音',
        sentiment: '正面',
        voice_type: '真实用户发声',
        labels: [],
        analysis_current: true,
        vehicle_names: [],
      }],
    }
    store.mind = { ...mind, snapshot_status: 'preparing', dimensions: [] }
    store.trend = { ...trend, snapshot_status: 'preparing', daily: [] }

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { render: () => h('div') } },
        { path: '/voice-plaza', component: { render: () => h('div') } },
        { path: '/collection-runtime', component: { render: () => h('div') } },
        { path: '/collection-strategy', component: { render: () => h('div') } },
        { path: '/admin/configuration', component: { render: () => h('div') } },
      ],
    })
    await router.push('/')
    await router.isReady()
    const app = createSSRApp({ render: () => h(WorkbenchPage) })
    app.use(pinia)
    app.use(router)

    const html = await renderToString(app)

    expect(html).toContain('首次聚合正在后台准备')
    expect(html).toContain('首次趋势聚合正在后台准备')
    expect(html).toContain('09/27 14:35')
  })
})
